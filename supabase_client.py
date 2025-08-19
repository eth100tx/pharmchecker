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
    
    def get_record_count_via_rest(self, table: str, filters: Dict = None) -> int:
        """Get count of records in table via REST API"""
        try:
            url = f"{self.url}/rest/v1/{table}"
            headers = self.headers.copy()
            headers['Prefer'] = 'count=exact'
            
            params = {"select": "id"}
            if filters:
                params.update(filters)
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code in [200, 206]:  # 206 = Partial Content (paginated)
                content_range = response.headers.get('content-range', '')
                if '/' in content_range:
                    total_count = content_range.split('/')[-1]
                    if total_count.isdigit():
                        return int(total_count)
            
            # If count header failed, fallback to high-limit actual count
            fallback_params = params.copy()
            fallback_params['limit'] = '100000'  # Very high limit
            
            fallback_response = requests.get(url, headers=self.headers, params=fallback_params, timeout=60)
            if fallback_response.status_code == 200:
                return len(fallback_response.json())
            
            return 0
        except Exception as e:
            return 0
    
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
    
    def delete_dataset_supabase(self, dataset_id: int) -> Dict:
        """Delete a dataset and all its associated data from Supabase"""
        try:
            # First get dataset info for confirmation
            dataset_response = requests.get(
                f"{self.url}/rest/v1/datasets?id=eq.{dataset_id}",
                headers=self.headers,
                timeout=10
            )
            
            if dataset_response.status_code != 200:
                return {"error": f"Dataset {dataset_id} not found"}
            
            datasets = dataset_response.json()
            if not datasets:
                return {"error": f"Dataset {dataset_id} not found"}
            
            dataset = datasets[0]
            kind = dataset.get('kind', 'unknown')
            
            # Delete associated data based on kind
            tables_to_clean = []
            if kind == 'pharmacies':
                tables_to_clean = ['pharmacies', 'match_scores']
            elif kind == 'states':
                tables_to_clean = ['search_results', 'match_scores', 'images']
            elif kind == 'validated':
                tables_to_clean = ['validated_overrides']
            
            # Delete from associated tables first
            deleted_counts = {}
            for table in tables_to_clean:
                try:
                    delete_response = requests.delete(
                        f"{self.url}/rest/v1/{table}?dataset_id=eq.{dataset_id}",
                        headers=self.headers,
                        timeout=30
                    )
                    
                    # Get count from Content-Range header
                    content_range = delete_response.headers.get('Content-Range', '')
                    if '/' in content_range:
                        count = content_range.split('/')[-1]
                        deleted_counts[table] = count
                    else:
                        deleted_counts[table] = "unknown"
                        
                except Exception as e:
                    deleted_counts[table] = f"error: {e}"
            
            # Finally delete the dataset itself
            dataset_delete_response = requests.delete(
                f"{self.url}/rest/v1/datasets?id=eq.{dataset_id}",
                headers=self.headers,
                timeout=10
            )
            
            if dataset_delete_response.status_code in [204, 200]:
                return {
                    "success": True,
                    "message": f"Dataset '{dataset['tag']}' ({kind}) deleted successfully",
                    "deleted_counts": deleted_counts
                }
            else:
                return {"error": f"Failed to delete dataset: {dataset_delete_response.text}"}
                
        except Exception as e:
            return {"error": str(e)}
    
    def rename_dataset_supabase(self, dataset_id: int, new_tag: str) -> Dict:
        """Rename a dataset tag in Supabase"""
        try:
            # Check if new tag already exists
            check_response = requests.get(
                f"{self.url}/rest/v1/datasets?tag=eq.{new_tag}",
                headers=self.headers,
                timeout=10
            )
            
            if check_response.status_code == 200:
                existing = check_response.json()
                if existing:
                    return {"error": f"Dataset with tag '{new_tag}' already exists"}
            
            # Update the tag
            update_response = requests.patch(
                f"{self.url}/rest/v1/datasets?id=eq.{dataset_id}",
                headers=self.headers,
                json={"tag": new_tag},
                timeout=10
            )
            
            if update_response.status_code in [204, 200]:
                return {"success": True, "message": f"Dataset renamed to '{new_tag}'"}
            else:
                return {"error": f"Failed to rename dataset: {update_response.text}"}
                
        except Exception as e:
            return {"error": str(e)}
    
    def get_table_counts_supabase(self, tables: List[str]) -> Dict[str, str]:
        """Get record counts for multiple tables from Supabase"""
        counts = {}
        for table in tables:
            try:
                # Use HEAD request with proper authentication
                url = f"{self.url}/rest/v1/{table}"
                headers = self.headers.copy()
                headers['Prefer'] = 'count=exact'
                
                response = requests.head(url, headers=headers, timeout=10)
                
                count_range = response.headers.get('Content-Range', '')
                if '/' in count_range:
                    count = count_range.split('/')[-1]
                    counts[table] = count
                elif response.status_code == 200:
                    # Try GET with limit 1 to get count
                    get_response = requests.get(
                        url, 
                        headers=headers, 
                        params={'limit': '1'}, 
                        timeout=10
                    )
                    count_range = get_response.headers.get('Content-Range', '')
                    if '/' in count_range:
                        count = count_range.split('/')[-1]
                        counts[table] = count
                    else:
                        # Fallback: sample and estimate
                        try:
                            data = self.get_table_data_via_rest(table, limit=100)
                            counts[table] = f"{len(data)}+ (sampled)"
                        except:
                            counts[table] = "Unable to count"
                else:
                    counts[table] = f"Error (status {response.status_code})"
                    
            except Exception as e:
                counts[table] = f"Error: {str(e)[:30]}"
        return counts


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