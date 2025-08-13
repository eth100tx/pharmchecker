"""
Unified API client wrapper for PharmChecker - supports both PostgREST and Supabase
"""
import requests
import pandas as pd
import os
from typing import Dict, List, Any, Optional
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    from supabase_client import SupabaseClient, test_supabase_available
    SUPABASE_AVAILABLE = test_supabase_available()
except ImportError:
    SUPABASE_AVAILABLE = False
    SupabaseClient = None


class PostgRESTClient:
    """Client for interacting with PostgREST API"""
    
    def __init__(self, base_url: str = "http://localhost:3000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def _request(self, method: str, endpoint: str, params: Dict = None, data: Dict = None) -> requests.Response:
        """Make HTTP request to PostgREST API"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=data if data else None
            )
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {e}")
    
    def get_table_data(self, table: str, limit: int = 1000, filters: Dict = None, select: str = None) -> List[Dict]:
        """Get data from any table"""
        params = {}
        
        if limit:
            params['limit'] = limit
        if select:
            params['select'] = select
        if filters:
            params.update(filters)
        
        response = self._request('GET', table, params=params)
        return response.json()
    
    def get_datasets(self) -> List[Dict]:
        """Get all datasets"""
        return self.get_table_data('datasets', select='*')
    
    def get_pharmacies(self, dataset_id: int = None, limit: int = 100) -> List[Dict]:
        """Get pharmacies, optionally filtered by dataset"""
        filters = {}
        if dataset_id:
            filters['dataset_id'] = f'eq.{dataset_id}'
        
        return self.get_table_data('pharmacies', limit=limit, filters=filters)
    
    def get_search_results(self, dataset_id: int = None, limit: int = 100) -> List[Dict]:
        """Get search results, optionally filtered by dataset"""
        filters = {}
        if dataset_id:
            filters['dataset_id'] = f'eq.{dataset_id}'
        
        return self.get_table_data('search_results', limit=limit, filters=filters)
    
    def get_comprehensive_results(self, states_tag: str, pharmacies_tag: str, validated_tag: str = "") -> List[Dict]:
        """Call the main comprehensive results RPC function"""
        params = {
            'p_states_tag': states_tag,
            'p_pharmacies_tag': pharmacies_tag,
            'p_validated_tag': validated_tag
        }
        
        response = self._request('GET', 'rpc/get_all_results_with_context', params=params)
        return response.json()
    
    def export_table_to_csv(self, table: str, filename: str, filters: Dict = None) -> str:
        """Export table data to CSV"""
        # Get data in CSV format
        params = filters or {}
        headers = {'Accept': 'text/csv'}
        
        url = f"{self.base_url}/{table}"
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        
        with open(filename, 'w') as f:
            f.write(response.text)
        
        return filename
    
    def get_table_schema(self) -> Dict:
        """Get OpenAPI schema for all tables"""
        response = self._request('GET', '')
        return response.json()
    
    def test_connection(self) -> bool:
        """Test if API is accessible"""
        try:
            response = self._request('GET', '')
            return response.status_code == 200
        except:
            return False


class UnifiedClient:
    """Unified client that can work with both PostgREST and Supabase"""
    
    def __init__(self, prefer_supabase: bool = False):
        self.postgrest_client = PostgRESTClient()
        self.supabase_client = SupabaseClient() if SUPABASE_AVAILABLE else None
        self.prefer_supabase = prefer_supabase and self.supabase_client is not None
        
        # Determine which backend to use
        self.use_supabase = self.prefer_supabase and self.supabase_available()
        
        self.backend_info = {
            "supabase_available": SUPABASE_AVAILABLE,
            "supabase_client_available": self.supabase_client is not None,
            "using_supabase": self.use_supabase,
            "postgrest_available": self.postgrest_client.test_connection()
        }
    
    def supabase_available(self) -> bool:
        """Check if Supabase is available and working"""
        if not self.supabase_client:
            return False
        return self.supabase_client.test_connection()
    
    def get_backend_info(self) -> Dict:
        """Get information about available backends"""
        return self.backend_info.copy()
    
    def test_connection(self) -> bool:
        """Test connection to active backend"""
        if self.use_supabase:
            return self.supabase_client.test_connection()
        else:
            return self.postgrest_client.test_connection()
    
    def get_datasets(self) -> List[Dict]:
        """Get datasets from active backend"""
        if self.use_supabase:
            return self.supabase_client.get_datasets_supabase()
        else:
            return self.postgrest_client.get_datasets()
    
    def get_pharmacies(self, dataset_id: int = None, limit: int = 100) -> List[Dict]:
        """Get pharmacies from active backend"""
        if self.use_supabase:
            # Build query for Supabase
            if dataset_id:
                query = f"SELECT * FROM pharmacies WHERE dataset_id = {dataset_id} LIMIT {limit}"
            else:
                query = f"SELECT * FROM pharmacies LIMIT {limit}"
            result = self.supabase_client.execute_sql(query)
            return result if isinstance(result, list) else []
        else:
            return self.postgrest_client.get_pharmacies(dataset_id, limit)
    
    def get_search_results(self, dataset_id: int = None, limit: int = 100) -> List[Dict]:
        """Get search results from active backend"""
        if self.use_supabase:
            # Build query for Supabase
            if dataset_id:
                query = f"SELECT * FROM search_results WHERE dataset_id = {dataset_id} LIMIT {limit}"
            else:
                query = f"SELECT * FROM search_results LIMIT {limit}"
            result = self.supabase_client.execute_sql(query)
            return result if isinstance(result, list) else []
        else:
            return self.postgrest_client.get_search_results(dataset_id, limit)
    
    def get_comprehensive_results(self, states_tag: str, pharmacies_tag: str, validated_tag: str = "") -> List[Dict]:
        """Get comprehensive results from active backend"""
        if self.use_supabase:
            return self.supabase_client.get_comprehensive_results_supabase(states_tag, pharmacies_tag, validated_tag)
        else:
            return self.postgrest_client.get_comprehensive_results(states_tag, pharmacies_tag, validated_tag)
    
    def get_table_data(self, table: str, limit: int = 1000, filters: Dict = None, select: str = None) -> List[Dict]:
        """Get data from any table"""
        if self.use_supabase:
            # Build SQL query for Supabase
            query = f"SELECT "
            if select:
                query += select
            else:
                query += "*"
            query += f" FROM {table}"
            
            if filters:
                # Simple filter conversion (expand as needed)
                conditions = []
                for key, value in filters.items():
                    if value.startswith('eq.'):
                        conditions.append(f"{key} = '{value[3:]}'")
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
            
            query += f" LIMIT {limit}"
            
            result = self.supabase_client.execute_sql(query)
            return result if isinstance(result, list) else []
        else:
            return self.postgrest_client.get_table_data(table, limit, filters, select)
    
    def switch_backend(self, use_supabase: bool = None) -> bool:
        """Switch between backends"""
        if use_supabase is None:
            # Toggle
            use_supabase = not self.use_supabase
        
        if use_supabase and not self.supabase_available():
            return False
        
        self.use_supabase = use_supabase
        self.backend_info["using_supabase"] = self.use_supabase
        return True
    
    def get_active_backend(self) -> str:
        """Get the name of the active backend"""
        return "Supabase" if self.use_supabase else "PostgREST (Local)"
    
    def get_active_api_url(self) -> str:
        """Get the API URL for the active backend"""
        if self.use_supabase:
            return f"{self.supabase_client.get_project_url()}/rest/v1" if self.supabase_client else "Not configured"
        else:
            return self.postgrest_client.base_url
    
    # Supabase-specific methods
    def get_supabase_info(self) -> Dict:
        """Get Supabase project information"""
        if not self.supabase_client:
            return {"error": "Supabase not available"}
        
        return {
            "project_url": self.supabase_client.get_project_url(),
            "anon_key": self.supabase_client.get_anon_key()[:20] + "...",  # Truncated for security
            "tables": self.supabase_client.list_tables(),
            "migrations": self.supabase_client.list_migrations()
        }
    
    def setup_supabase_database(self) -> Dict:
        """Set up the database schema and functions in Supabase"""
        if not self.supabase_client:
            return {"error": "Supabase not available"}
        
        results = {}
        
        # Set up schema
        schema_result = self.supabase_client.setup_database_schema()
        results["schema"] = schema_result
        
        # Set up functions
        functions_result = self.supabase_client.setup_database_functions()
        results["functions"] = functions_result
        
        return results


def create_client(prefer_supabase: bool = False) -> UnifiedClient:
    """Factory function to create unified client"""
    return UnifiedClient(prefer_supabase=prefer_supabase)


def datasets_to_dataframe(datasets: List[Dict]) -> pd.DataFrame:
    """Convert datasets list to pandas DataFrame"""
    return pd.DataFrame(datasets)


def results_to_dataframe(results: List[Dict]) -> pd.DataFrame:
    """Convert comprehensive results to pandas DataFrame"""
    return pd.DataFrame(results)