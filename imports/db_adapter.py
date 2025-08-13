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
            affected_rows = cur.rowcount
            self.conn.commit()
            return affected_rows
    
    def batch_insert(self, table: str, columns: List[str], data: List[Tuple], 
                    batch_size: int = 1000, on_conflict: str = None) -> int:
        """Batch insert data with error handling"""
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
    
    def commit(self):
        """Commit current transaction"""
        if self.conn:
            self.conn.commit()
    
    def rollback(self):
        """Rollback current transaction"""
        if self.conn:
            self.conn.rollback()


class SupabaseAdapter(DatabaseAdapter):
    """Supabase database adapter using direct API calls"""
    
    def __init__(self):
        """Initialize Supabase adapter"""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.connected = False
        
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
        # For Supabase, we'll test connectivity by trying a simple REST API call
        try:
            import requests
            
            # Test connection with a simple query to the REST API
            headers = {
                'apikey': self.api_key,
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            # Try to access datasets table
            response = requests.get(
                f"{self.supabase_url}/rest/v1/datasets?limit=1",
                headers=headers,
                timeout=10
            )
            
            if response.status_code in [200, 404]:  # 200 = success, 404 = table might not exist but connection works
                self.connected = True
                self.logger.info("Connected to Supabase")
                return True
            else:
                self.logger.error(f"Supabase connection failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to connect to Supabase: {e}")
            self.connected = False
            return False
    
    def close(self):
        """Close database connection (no-op for Supabase)"""
        self.connected = False
    
    def execute_query(self, query: str, params: Tuple = None) -> List[Tuple]:
        """Execute a SELECT query and return results"""
        # For now, Supabase queries should go through the unified client
        # Direct SQL execution via REST API is complex and not recommended
        self.logger.error("Direct SQL queries not supported for Supabase adapter. Use unified client instead.")
        raise NotImplementedError("Use unified client for Supabase queries")
    
    def execute_one(self, query: str, params: Tuple = None) -> Optional[Tuple]:
        """Execute a SELECT query and return first result"""
        self.logger.error("Direct SQL queries not supported for Supabase adapter. Use unified client instead.")
        raise NotImplementedError("Use unified client for Supabase queries")
    
    def execute_statement(self, statement: str, params: Tuple = None) -> int:
        """Execute an INSERT/UPDATE/DELETE statement"""
        self.logger.error("Direct SQL statements not supported for Supabase adapter. Use unified client instead.")
        raise NotImplementedError("Use unified client for Supabase operations")
    
    def batch_insert(self, table: str, columns: List[str], data: List[Tuple], 
                    batch_size: int = 1000, on_conflict: str = None) -> int:
        """Batch insert data with error handling"""
        self.logger.error("Direct batch insert not supported for Supabase adapter. Use unified client instead.")
        raise NotImplementedError("Use unified client for Supabase operations")
    
    def commit(self):
        """Commit current transaction (no-op for Supabase)"""
        pass
    
    def rollback(self):
        """Rollback current transaction (no-op for Supabase)"""
        pass


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
    prefer_supabase = os.getenv('PREFER_SUPABASE', '').lower() in ('true', '1', 'yes')
    
    if supabase_url and prefer_supabase:
        return create_adapter("supabase")
    else:
        return create_adapter("postgresql")