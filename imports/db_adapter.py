"""
Database adapter interface for PharmChecker imports
Provides unified interface for both PostgreSQL and Supabase backends
"""
import os
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple, Optional
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class DatabaseAdapter(ABC):
    """Abstract base class for database adapters"""
    
    @abstractmethod
    def connect(self) -> bool:
        """Establish database connection"""
        pass
    
    @abstractmethod
    def close(self):
        """Close database connection"""
        pass
    
    @abstractmethod
    def execute_query(self, query: str, params: Tuple = None) -> List[Tuple]:
        """Execute a SELECT query and return results"""
        pass
    
    @abstractmethod
    def execute_one(self, query: str, params: Tuple = None) -> Optional[Tuple]:
        """Execute a SELECT query and return first result"""
        pass
    
    @abstractmethod
    def execute_statement(self, statement: str, params: Tuple = None) -> int:
        """Execute an INSERT/UPDATE/DELETE statement"""
        pass
    
    @abstractmethod
    def batch_insert(self, table: str, columns: List[str], data: List[Tuple], 
                    batch_size: int = 1000, on_conflict: str = None) -> int:
        """Batch insert data with error handling"""
        pass
    
    @abstractmethod
    def commit(self):
        """Commit current transaction"""
        pass
    
    @abstractmethod
    def rollback(self):
        """Rollback current transaction"""
        pass


class PostgreSQLAdapter(DatabaseAdapter):
    """PostgreSQL database adapter using psycopg2"""
    
    def __init__(self, conn_params: Optional[Dict[str, Any]] = None):
        """
        Initialize PostgreSQL adapter
        
        Args:
            conn_params: Database connection parameters. If None, uses config.
        """
        if conn_params is None:
            from config import get_db_config
            conn_params = get_db_config()
            
        self.conn_params = conn_params
        self.conn = None
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def connect(self) -> bool:
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(**self.conn_params)
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to PostgreSQL: {e}")
            return False
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def execute_query(self, query: str, params: Tuple = None) -> List[Tuple]:
        """Execute a SELECT query and return results"""
        with self.conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()
    
    def execute_one(self, query: str, params: Tuple = None) -> Optional[Tuple]:
        """Execute a SELECT query and return first result"""
        with self.conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()
    
    def execute_statement(self, statement: str, params: Tuple = None) -> int:
        """Execute an INSERT/UPDATE/DELETE statement"""
        with self.conn.cursor() as cur:
            cur.execute(statement, params)
            return cur.rowcount
    
    def batch_insert(self, table: str, columns: List[str], data: List[Tuple], 
                    batch_size: int = 1000, on_conflict: str = None) -> int:
        """
        Batch insert data with error handling
        
        Args:
            table: Target table name
            columns: List of column names
            data: List of tuples containing row data
            batch_size: Number of rows to insert per batch
            on_conflict: Optional ON CONFLICT clause (e.g., "DO NOTHING")
        
        Returns:
            Number of rows affected
        """
        if not data:
            return 0
            
        total_inserted = 0
        
        # Build the INSERT query
        cols_str = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))
        query = f"INSERT INTO {table} ({cols_str}) VALUES ({placeholders})"
        
        if on_conflict:
            query += f" {on_conflict}"
        
        # Process in batches
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            
            try:
                with self.conn.cursor() as cur:
                    if len(batch) == 1:
                        # Single row insert
                        cur.execute(query, batch[0])
                        total_inserted += cur.rowcount
                    else:
                        # Batch insert using execute_values
                        template = f"({placeholders})"
                        execute_values(
                            cur, 
                            f"INSERT INTO {table} ({cols_str}) VALUES %s {on_conflict if on_conflict else ''}",
                            batch,
                            template=template
                        )
                        total_inserted += cur.rowcount
                        
            except Exception as e:
                self.logger.error(f"Error in batch insert: {e}")
                # Try individual inserts for this batch
                for row in batch:
                    try:
                        with self.conn.cursor() as cur:
                            cur.execute(query, row)
                            total_inserted += cur.rowcount
                    except Exception as row_err:
                        self.logger.debug(f"Failed to insert row: {row_err}")
                        continue
        
        return total_inserted
    
    def commit(self):
        """Commit current transaction"""
        if self.conn:
            self.conn.commit()
    
    def rollback(self):
        """Rollback current transaction"""
        if self.conn:
            self.conn.rollback()


class SupabaseAdapter(DatabaseAdapter):
    """Supabase database adapter using Supabase Python client"""
    
    def __init__(self):
        """Initialize Supabase adapter"""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.connected = False
        self.client = None
        
        # Check if Supabase credentials are available
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_anon_key = os.getenv('SUPABASE_ANON_KEY')
        self.supabase_service_key = os.getenv('SUPABASE_SERVICE_KEY')
        
        if not (self.supabase_url and (self.supabase_anon_key or self.supabase_service_key)):
            self.logger.error("Supabase credentials not found in environment")
            
        # Use service key for admin operations, fallback to anon key
        self.api_key = self.supabase_service_key or self.supabase_anon_key
    
    def connect(self) -> bool:
        """Establish database connection"""
        try:
            from supabase import create_client
            
            # Create Supabase client
            self.client = create_client(self.supabase_url, self.api_key)
            
            # Test connection by querying datasets table
            response = self.client.table('datasets').select('*').limit(1).execute()
            
            self.connected = True
            self.logger.info("Connected to Supabase")
            return True
                
        except Exception as e:
            self.logger.error(f"Failed to connect to Supabase: {e}")
            self.connected = False
            return False
    
    def close(self):
        """Close database connection (no-op for Supabase)"""
        self.connected = False
        self.client = None
    
    def execute_query(self, query: str, params: Tuple = None) -> List[Tuple]:
        """Execute a SELECT query and return results"""
        # Parse simple SELECT queries and convert to Supabase API calls
        # This is a simplified implementation for common queries
        
        if not self.client:
            raise RuntimeError("Not connected to Supabase")
        
        # For complex queries, we need to use RPC functions
        # For now, return empty result and log warning
        self.logger.warning(f"Complex SQL query not fully supported via REST API: {query}")
        return []
    
    def execute_one(self, query: str, params: Tuple = None) -> Optional[Tuple]:
        """Execute a SELECT query and return first result"""
        results = self.execute_query(query, params)
        return results[0] if results else None
    
    def execute_statement(self, statement: str, params: Tuple = None) -> int:
        """Execute an INSERT/UPDATE/DELETE statement"""
        if not self.client:
            raise RuntimeError("Not connected to Supabase")
            
        # This would need to parse SQL and convert to Supabase API calls
        # For now, return 0 and log warning
        self.logger.warning(f"Direct SQL statement not supported via REST API: {statement}")
        return 0
    
    def batch_insert(self, table: str, columns: List[str], data: List[Tuple], 
                    batch_size: int = 1000, on_conflict: str = None) -> int:
        """Batch insert data using Supabase client"""
        if not self.client:
            raise RuntimeError("Not connected to Supabase")
            
        if not data:
            return 0
        
        total_inserted = 0
        
        # Convert tuples to dictionaries for Supabase
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            
            # Convert each tuple to a dictionary
            batch_dicts = []
            for row in batch:
                row_dict = {col: val for col, val in zip(columns, row)}
                batch_dicts.append(row_dict)
            
            try:
                # Use upsert for conflict handling, insert otherwise
                if on_conflict and 'DO NOTHING' in on_conflict:
                    # For DO NOTHING, we need to check existence first
                    # This is not efficient but works
                    for row_dict in batch_dicts:
                        try:
                            response = self.client.table(table).insert(row_dict).execute()
                            total_inserted += len(response.data)
                        except Exception as e:
                            # Row likely exists, skip
                            self.logger.debug(f"Skipping existing row: {e}")
                            continue
                elif on_conflict and 'DO UPDATE' in on_conflict:
                    # Use upsert for UPDATE conflicts
                    response = self.client.table(table).upsert(batch_dicts).execute()
                    total_inserted += len(response.data)
                else:
                    # Regular insert
                    response = self.client.table(table).insert(batch_dicts).execute()
                    total_inserted += len(response.data)
                    
            except Exception as e:
                self.logger.error(f"Error in batch insert: {e}")
                # Try individual inserts for this batch
                for row_dict in batch_dicts:
                    try:
                        response = self.client.table(table).insert(row_dict).execute()
                        total_inserted += len(response.data)
                    except Exception as row_err:
                        self.logger.debug(f"Failed to insert row: {row_err}")
                        continue
        
        return total_inserted
    
    def commit(self):
        """Commit current transaction (no-op for Supabase REST API)"""
        # Supabase REST API doesn't have explicit transactions
        pass
    
    def rollback(self):
        """Rollback current transaction (no-op for Supabase REST API)"""
        # Supabase REST API doesn't have explicit transactions
        pass
    
    # Additional helper methods for Supabase-specific operations
    def get_dataset_id(self, kind: str, tag: str) -> Optional[int]:
        """Get dataset ID by kind and tag"""
        if not self.client:
            raise RuntimeError("Not connected to Supabase")
            
        try:
            response = self.client.table('datasets').select('id').eq('kind', kind).eq('tag', tag).execute()
            if response.data:
                return response.data[0]['id']
            return None
        except Exception as e:
            self.logger.error(f"Error getting dataset ID: {e}")
            return None
    
    def create_dataset(self, kind: str, tag: str, description: str = None) -> Optional[int]:
        """Create a new dataset and return its ID"""
        if not self.client:
            raise RuntimeError("Not connected to Supabase")
            
        try:
            data = {
                'kind': kind,
                'tag': tag,
                'description': description,
                'created_by': 'system'
            }
            response = self.client.table('datasets').insert(data).execute()
            if response.data:
                return response.data[0]['id']
            return None
        except Exception as e:
            self.logger.error(f"Error creating dataset: {e}")
            return None


def create_adapter(backend: str = "postgresql", **kwargs) -> DatabaseAdapter:
    """
    Factory function to create database adapter
    
    Args:
        backend: 'postgresql' or 'supabase'
        **kwargs: Additional configuration options
    
    Returns:
        DatabaseAdapter instance
    """
    if backend.lower() == "supabase":
        return SupabaseAdapter()
    elif backend.lower() == "postgresql":
        return PostgreSQLAdapter(kwargs.get('conn_params'))
    else:
        raise ValueError(f"Unsupported backend: {backend}")


def get_default_adapter() -> DatabaseAdapter:
    """Get default database adapter based on environment configuration"""
    # Check if Supabase is configured and preferred
    supabase_url = os.getenv('SUPABASE_URL')
    use_cloud_db = os.getenv('USE_CLOUD_DB', '').lower() in ('true', '1', 'yes')
    
    if supabase_url and use_cloud_db:
        return create_adapter("supabase")
    else:
        return create_adapter("postgresql")