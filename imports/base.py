"""
Base importer class for PharmChecker
Provides shared database functionality for all importers
"""
import logging
from typing import Dict, Any, List, Tuple, Optional
import psycopg2
from psycopg2.extras import execute_values
from config import get_db_config

class BaseImporter:
    """Base class for all PharmChecker data importers"""
    
    def __init__(self, conn_params: Optional[Dict[str, Any]] = None):
        """
        Initialize base importer
        
        Args:
            conn_params: Database connection parameters. If None, uses config.
        """
        if conn_params is None:
            conn_params = get_db_config()
            
        self.conn_params = conn_params
        self.conn = psycopg2.connect(**conn_params)
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def __enter__(self):
        """Context manager entry"""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
    
    def create_dataset(self, kind: str, tag: str, description: str = None, 
                      created_by: str = None) -> int:
        """
        Create or get dataset ID
        
        Args:
            kind: Dataset type ('states', 'pharmacies', 'validated')
            tag: Dataset tag/version
            description: Optional description
            created_by: Who created this dataset
            
        Returns:
            Dataset ID
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO datasets (kind, tag, description, created_by)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (kind, tag) DO UPDATE 
                SET description = EXCLUDED.description,
                    created_by = COALESCE(EXCLUDED.created_by, datasets.created_by)
                RETURNING id
            """, (kind, tag, description, created_by))
            dataset_id = cur.fetchone()[0]
            self.conn.commit()
            
        self.logger.info(f"Dataset {kind}:{tag} -> ID {dataset_id}")
        return dataset_id
    
    def batch_insert(self, table: str, columns: List[str], data: List[Tuple], 
                    batch_size: int = 1000, on_conflict: str = None) -> int:
        """
        Batch insert data with error handling
        
        Args:
            table: Table name
            columns: Column names
            data: List of tuples to insert
            batch_size: Number of rows per batch
            on_conflict: Optional ON CONFLICT clause
            
        Returns:
            Number of rows successfully inserted
        """
        if not data:
            self.logger.info("No data to insert")
            return 0
            
        template = f"({','.join(['%s'] * len(columns))})"
        base_query = f"INSERT INTO {table} ({','.join(columns)}) VALUES %s"
        
        if on_conflict:
            query = f"{base_query} {on_conflict}"
        else:
            query = base_query
        
        total_inserted = 0
        failed_batches = 0
        
        with self.conn.cursor() as cur:
            for i in range(0, len(data), batch_size):
                batch = data[i:i + batch_size]
                batch_num = i // batch_size + 1
                
                try:
                    execute_values(
                        cur,
                        query,
                        batch,
                        template=template
                    )
                    self.conn.commit()
                    total_inserted += len(batch)
                    self.logger.info(f"Batch {batch_num}: inserted {len(batch)} rows")
                    
                except Exception as e:
                    self.logger.error(f"Batch {batch_num} failed: {e}")
                    self.conn.rollback()
                    failed_batches += 1
                    
                    # Try individual inserts to isolate the problem
                    if len(batch) > 1:
                        self.logger.info(f"Trying individual inserts for batch {batch_num}")
                        individual_success = 0
                        for row in batch:
                            try:
                                cur.execute(
                                    query.replace('%s', template),
                                    (row,)
                                )
                                self.conn.commit()
                                individual_success += 1
                            except Exception as row_error:
                                self.logger.error(f"Row failed: {row_error}")
                                self.conn.rollback()
                        
                        if individual_success > 0:
                            total_inserted += individual_success
                            self.logger.info(f"Batch {batch_num}: {individual_success} individual inserts succeeded")
        
        self.logger.info(f"Total inserted: {total_inserted} rows, {failed_batches} batches failed")
        return total_inserted
    
    def execute_query(self, query: str, params: Tuple = None) -> List[Tuple]:
        """
        Execute a SELECT query and return results
        
        Args:
            query: SQL query
            params: Query parameters
            
        Returns:
            List of result tuples
        """
        with self.conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()
    
    def execute_one(self, query: str, params: Tuple = None) -> Optional[Tuple]:
        """
        Execute a SELECT query and return first result
        
        Args:
            query: SQL query
            params: Query parameters
            
        Returns:
            First result tuple or None
        """
        with self.conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()
    
    def execute_statement(self, statement: str, params: Tuple = None) -> int:
        """
        Execute an INSERT/UPDATE/DELETE statement
        
        Args:
            statement: SQL statement
            params: Statement parameters
            
        Returns:
            Number of affected rows
        """
        with self.conn.cursor() as cur:
            cur.execute(statement, params)
            affected_rows = cur.rowcount
            self.conn.commit()
            return affected_rows
    
    def get_dataset_id(self, kind: str, tag: str) -> Optional[int]:
        """
        Get dataset ID if it exists
        
        Args:
            kind: Dataset type
            tag: Dataset tag
            
        Returns:
            Dataset ID or None if not found
        """
        result = self.execute_one(
            "SELECT id FROM datasets WHERE kind = %s AND tag = %s",
            (kind, tag)
        )
        return result[0] if result else None
    
    def list_datasets(self, kind: str = None) -> List[Dict[str, Any]]:
        """
        List available datasets
        
        Args:
            kind: Optional filter by dataset type
            
        Returns:
            List of dataset info dictionaries
        """
        if kind:
            query = """
                SELECT id, kind, tag, description, created_by, created_at 
                FROM datasets WHERE kind = %s 
                ORDER BY created_at DESC
            """
            params = (kind,)
        else:
            query = """
                SELECT id, kind, tag, description, created_by, created_at 
                FROM datasets 
                ORDER BY kind, created_at DESC
            """
            params = None
        
        results = self.execute_query(query, params)
        
        datasets = []
        for row in results:
            datasets.append({
                'id': row[0],
                'kind': row[1],
                'tag': row[2],
                'description': row[3],
                'created_by': row[4],
                'created_at': row[5]
            })
        
        return datasets
    
    def cleanup_failed_dataset(self, dataset_id: int):
        """
        Clean up a partially created dataset
        
        Args:
            dataset_id: Dataset ID to clean up
        """
        try:
            self.execute_statement("DELETE FROM datasets WHERE id = %s", (dataset_id,))
            self.logger.info(f"Cleaned up failed dataset {dataset_id}")
        except Exception as e:
            self.logger.error(f"Failed to cleanup dataset {dataset_id}: {e}")
    
    def get_dataset_stats(self, dataset_id: int) -> Dict[str, int]:
        """
        Get statistics for a dataset
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            Dictionary with counts for different data types
        """
        stats = {}
        
        # Get dataset info
        dataset_info = self.execute_one(
            "SELECT kind, tag FROM datasets WHERE id = %s",
            (dataset_id,)
        )
        
        if not dataset_info:
            return {}
        
        kind, tag = dataset_info
        stats['kind'] = kind
        stats['tag'] = tag
        
        # Count records based on dataset type
        if kind == 'pharmacies':
            count = self.execute_one(
                "SELECT COUNT(*) FROM pharmacies WHERE dataset_id = %s",
                (dataset_id,)
            )[0]
            stats['pharmacies'] = count
            
        elif kind == 'states':
            search_count = self.execute_one(
                "SELECT COUNT(*) FROM searches WHERE dataset_id = %s",
                (dataset_id,)
            )[0]
            result_count = self.execute_one("""
                SELECT COUNT(*) FROM search_results sr 
                JOIN searches s ON sr.search_id = s.id 
                WHERE s.dataset_id = %s
            """, (dataset_id,))[0]
            
            stats['searches'] = search_count
            stats['results'] = result_count
            
        elif kind == 'validated':
            count = self.execute_one(
                "SELECT COUNT(*) FROM validated_overrides WHERE dataset_id = %s",
                (dataset_id,)
            )[0]
            stats['overrides'] = count
        
        return stats