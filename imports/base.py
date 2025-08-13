"""
Base importer class for PharmChecker
Provides shared database functionality for all importers
"""
import logging
from typing import Dict, Any, List, Tuple, Optional
from .db_adapter import DatabaseAdapter, get_default_adapter, create_adapter

class BaseImporter:
    """Base class for all PharmChecker data importers"""
    
    def __init__(self, db_adapter: Optional[DatabaseAdapter] = None, backend: str = None, conn_params: Optional[Dict[str, Any]] = None):
        """
        Initialize base importer
        
        Args:
            db_adapter: Database adapter instance. If None, creates default adapter.
            backend: Backend type ('postgresql' or 'supabase'). Used if db_adapter is None.
            conn_params: Database connection parameters. Used for PostgreSQL backend.
        """
        if db_adapter is not None:
            self.db = db_adapter
        elif backend is not None:
            if backend.lower() == 'postgresql':
                self.db = create_adapter("postgresql", conn_params=conn_params)
            else:
                self.db = create_adapter(backend)
        else:
            self.db = get_default_adapter()
            
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Establish connection
        try:
            if not self.db.connect():
                raise Exception("Failed to connect to database")
        except NotImplementedError as e:
            # For Supabase, we expect this - it should use the unified client instead
            if backend and backend.lower() == 'supabase':
                self.logger.warning("Supabase operations should use unified client, not direct importer")
                raise Exception("Use unified client for Supabase operations") from e
            else:
                raise
        
    def __enter__(self):
        """Context manager entry"""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
    
    def close(self):
        """Close database connection"""
        self.db.close()
    
    def create_dataset(self, kind: str, tag: str, description: str = None, 
                      created_by: str = None) -> int:
        """
        Create a new dataset with unique tag
        
        Args:
            kind: Dataset type ('states', 'pharmacies', 'validated')
            tag: Dataset tag/version (will be made unique if conflicts exist)
            description: Optional description
            created_by: Who created this dataset
            
        Returns:
            Dataset ID
        """
        # Find unique tag if conflicts exist
        unique_tag = self._find_unique_tag(kind, tag)
        
        result = self.db.execute_one("""
            INSERT INTO datasets (kind, tag, description, created_by)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (kind, unique_tag, description, created_by))
        dataset_id = result[0]
        self.db.commit()
            
        if unique_tag != tag:
            self.logger.info(f"Dataset {kind}:{tag} -> {unique_tag} (made unique) -> ID {dataset_id}")
        else:
            self.logger.info(f"Dataset {kind}:{tag} -> ID {dataset_id}")
        return dataset_id
    
    def _find_unique_tag(self, kind: str, base_tag: str) -> str:
        """
        Find a unique tag by adding (2), (3), etc. if conflicts exist
        
        Args:
            kind: Dataset type
            base_tag: Original tag name
            
        Returns:
            Unique tag name
        """
        # Check if base tag exists
        existing = self.db.execute_one(
            "SELECT id FROM datasets WHERE kind = %s AND tag = %s",
            (kind, base_tag)
        )
        
        if not existing:
            return base_tag
        
        # Find next available number
        counter = 2
        while True:
            candidate_tag = f"{base_tag} ({counter})"
            existing = self.db.execute_one(
                "SELECT id FROM datasets WHERE kind = %s AND tag = %s",
                (kind, candidate_tag)
            )
            
            if not existing:
                return candidate_tag
            
            counter += 1
            
            # Safety check to avoid infinite loop
            if counter > 100:
                raise Exception(f"Unable to find unique tag for {kind}:{base_tag}")
                
        return candidate_tag
    
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
        return self.db.batch_insert(table, columns, data, batch_size, on_conflict)
    
    def execute_query(self, query: str, params: Tuple = None) -> List[Tuple]:
        """
        Execute a SELECT query and return results
        
        Args:
            query: SQL query
            params: Query parameters
            
        Returns:
            List of result tuples
        """
        return self.db.execute_query(query, params)
    
    def execute_one(self, query: str, params: Tuple = None) -> Optional[Tuple]:
        """
        Execute a SELECT query and return first result
        
        Args:
            query: SQL query
            params: Query parameters
            
        Returns:
            First result tuple or None
        """
        return self.db.execute_one(query, params)
    
    def execute_statement(self, statement: str, params: Tuple = None) -> int:
        """
        Execute an INSERT/UPDATE/DELETE statement
        
        Args:
            statement: SQL statement
            params: Statement parameters
            
        Returns:
            Number of affected rows
        """
        return self.db.execute_statement(statement, params)
    
    def get_dataset_id(self, kind: str, tag: str) -> Optional[int]:
        """
        Get dataset ID if it exists
        
        Args:
            kind: Dataset type
            tag: Dataset tag
            
        Returns:
            Dataset ID or None if not found
        """
        result = self.db.execute_one(
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
        
        results = self.db.execute_query(query, params)
        
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
            self.db.execute_statement("DELETE FROM datasets WHERE id = %s", (dataset_id,))
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
        dataset_info = self.db.execute_one(
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
            count = self.db.execute_one(
                "SELECT COUNT(*) FROM pharmacies WHERE dataset_id = %s",
                (dataset_id,)
            )[0]
            stats['pharmacies'] = count
            
        elif kind == 'states':
            # Count total results in merged table
            result_count = self.db.execute_one(
                "SELECT COUNT(*) FROM search_results WHERE dataset_id = %s",
                (dataset_id,)
            )[0]
            
            # Count unique searches (by search_name, search_state combination)
            search_count = self.db.execute_one("""
                SELECT COUNT(DISTINCT (search_name, search_state)) 
                FROM search_results 
                WHERE dataset_id = %s
            """, (dataset_id,))[0]
            
            stats['searches'] = search_count
            stats['results'] = result_count
            
        elif kind == 'validated':
            count = self.db.execute_one(
                "SELECT COUNT(*) FROM validated_overrides WHERE dataset_id = %s",
                (dataset_id,)
            )[0]
            stats['overrides'] = count
        
        return stats