"""
Supabase client wrapper for PharmChecker API POC
"""
import os
import sys
import requests
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    from supabase import create_client, Client
    SUPABASE_LIB_AVAILABLE = True
except ImportError:
    SUPABASE_LIB_AVAILABLE = False
    Client = None


class SupabaseClient:
    """Client for interacting with Supabase via REST API and Python client"""
    
    def __init__(self):
        self.url = os.getenv('SUPABASE_URL')
        self.anon_key = os.getenv('SUPABASE_ANON_KEY')
        self.service_key = os.getenv('SUPABASE_SERVICE_KEY')
        
        # Create Supabase client if library is available
        self.client = None
        if SUPABASE_LIB_AVAILABLE and self.url and self.anon_key:
            try:
                self.client = create_client(self.url, self.anon_key)
            except Exception as e:
                print(f"Failed to create Supabase client: {e}")
        
        # REST API headers
        self.headers = {
            'apikey': self.anon_key,
            'Authorization': f'Bearer {self.anon_key}',
            'Content-Type': 'application/json'
        }
    
    def test_connection(self) -> bool:
        """Test if Supabase connection is available"""
        if not self.url or not self.anon_key:
            return False
        
        try:
            # Test via REST API
            response = requests.get(f"{self.url}/rest/v1/", headers=self.headers, timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def get_project_url(self) -> str:
        """Get the Supabase project URL"""
        return self.url or "Not configured"
    
    def get_anon_key(self) -> str:
        """Get the anonymous API key (truncated for security)"""
        if self.anon_key:
            return self.anon_key[:20] + "..."
        return "Not configured"
    
    def list_tables(self, schemas: List[str] = None) -> List[Dict]:
        """List all tables in Supabase"""
        try:
            # Query information_schema via REST API
            url = f"{self.url}/rest/v1/rpc/list_tables"
            response = requests.post(url, headers=self.headers, json={}, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                # Fallback: try to get tables via direct SQL
                return self._get_tables_fallback()
        except Exception as e:
            return [{"error": str(e)}]
    
    def _get_tables_fallback(self) -> List[Dict]:
        """Fallback method to get tables"""
        try:
            # Query information_schema directly
            url = f"{self.url}/rest/v1/rpc/execute_sql"
            query = """
            SELECT table_name, table_schema 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
            """
            response = requests.post(url, headers=self.headers, json={"query": query}, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                return [{"table_name": "datasets"}, {"table_name": "pharmacies"}, {"table_name": "search_results"}]
        except Exception:
            return [{"error": "Could not fetch tables"}]
    
    def execute_sql(self, query: str) -> Any:
        """Execute raw SQL query via Supabase client"""
        try:
            if self.client:
                # Use Python client if available
                result = self.client.rpc('execute_sql', {'query': query}).execute()
                return result.data
            else:
                # Fallback to REST API
                url = f"{self.url}/rest/v1/rpc/execute_sql"
                response = requests.post(url, headers=self.headers, json={"query": query}, timeout=30)
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return {"error": f"SQL execution failed: {response.status_code} {response.text}"}
        except Exception as e:
            return {"error": str(e)}
    
    def get_datasets_via_rest(self) -> List[Dict]:
        """Get datasets using direct REST API call"""
        try:
            url = f"{self.url}/rest/v1/datasets"
            params = {"select": "*", "order": "created_at.desc", "limit": "100"}
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                return [{"error": f"Failed to fetch datasets: {response.status_code}"}]
        except Exception as e:
            return [{"error": str(e)}]
    
    def get_table_data_via_rest(self, table: str, limit: int = 100, filters: Dict = None) -> List[Dict]:
        """Get data from any table via REST API"""
        try:
            url = f"{self.url}/rest/v1/{table}"
            params = {"limit": str(limit)}
            
            if filters:
                params.update(filters)
            
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                return [{"error": f"Failed to fetch {table}: {response.status_code}"}]
        except Exception as e:
            return [{"error": str(e)}]
    
    def call_rpc_function(self, function_name: str, params: Dict = None) -> Any:
        """Call an RPC function via REST API"""
        try:
            url = f"{self.url}/rest/v1/rpc/{function_name}"
            data = params or {}
            response = requests.post(url, headers=self.headers, json=data, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"RPC call failed: {response.status_code} {response.text}"}
        except Exception as e:
            return {"error": str(e)}
    
    def get_comprehensive_results_via_rest(self, states_tag: str, pharmacies_tag: str, validated_tag: str = "") -> List[Dict]:
        """Call comprehensive results function via REST API"""
        return self.call_rpc_function("get_all_results_with_context", {
            "p_states_tag": states_tag,
            "p_pharmacies_tag": pharmacies_tag, 
            "p_validated_tag": validated_tag
        })
    
    def get_project_info(self) -> Dict:
        """Get basic project information"""
        return {
            "url": self.get_project_url(),
            "anon_key": self.get_anon_key(),
            "connection_status": "Connected" if self.test_connection() else "Disconnected",
            "client_library": "Available" if SUPABASE_LIB_AVAILABLE else "Not installed"
        }
    
    def get_datasets_supabase(self) -> List[Dict]:
        """Get datasets from Supabase"""
        return self.get_datasets_via_rest()
    
    def get_comprehensive_results_supabase(self, states_tag: str, pharmacies_tag: str, validated_tag: str = "") -> List[Dict]:
        """Call the comprehensive results function via Supabase REST API"""
        return self.get_comprehensive_results_via_rest(states_tag, pharmacies_tag, validated_tag)


def create_supabase_client() -> SupabaseClient:
    """Factory function to create Supabase client"""
    return SupabaseClient()


# Test if Supabase is available
def test_supabase_available() -> bool:
    """Test if Supabase client can be created and is available"""
    try:
        client = SupabaseClient()
        return client.test_connection()
    except Exception:
        return False