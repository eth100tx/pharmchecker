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
    
    def delete_dataset(self, dataset_id: int) -> Dict:
        """Delete a dataset and all its associated data via PostgREST"""
        try:
            # Note: This would normally use a stored procedure for safe cascading delete
            # For now, return error indicating manual deletion needed
            return {"error": "Dataset deletion via PostgREST not yet implemented. Use direct database access."}
        except Exception as e:
            return {"error": str(e)}
    
    def rename_dataset(self, dataset_id: int, new_tag: str) -> Dict:
        """Rename a dataset tag via PostgREST"""
        try:
            # Update the datasets table
            response = self._request('PATCH', f'datasets?id=eq.{dataset_id}', data={'tag': new_tag})
            if response.status_code == 204:  # No content = success
                return {"success": True, "message": f"Dataset renamed to '{new_tag}'"}
            else:
                return {"error": f"Failed to rename dataset: {response.text}"}
        except Exception as e:
            return {"error": str(e)}
    
    def get_table_counts(self, tables: List[str]) -> Dict[str, str]:
        """Get record counts for multiple tables via PostgREST"""
        counts = {}
        for table in tables:
            try:
                # Use HEAD request with Prefer header
                url = f"{self.base_url}/{table}"
                headers = {'Prefer': 'count=exact'}
                response = requests.head(url, headers=headers, timeout=10)
                
                count_range = response.headers.get('Content-Range', '')
                if '/' in count_range:
                    count = count_range.split('/')[-1]
                    counts[table] = count
                else:
                    counts[table] = "Unable to get count"
            except Exception as e:
                counts[table] = f"Error: {str(e)[:30]}"
        return counts


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
            # Use REST API for Supabase
            filters = {}
            if dataset_id:
                filters['dataset_id'] = f'eq.{dataset_id}'
            result = self.supabase_client.get_table_data_via_rest('pharmacies', limit=limit, filters=filters)
            return result if isinstance(result, list) else []
        else:
            return self.postgrest_client.get_pharmacies(dataset_id, limit)
    
    def get_search_results(self, dataset_id: int = None, limit: int = 100) -> List[Dict]:
        """Get search results from active backend"""
        if self.use_supabase:
            # Use REST API for Supabase
            filters = {}
            if dataset_id:
                filters['dataset_id'] = f'eq.{dataset_id}'
            result = self.supabase_client.get_table_data_via_rest('search_results', limit=limit, filters=filters)
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
            # Use REST API for Supabase
            result = self.supabase_client.get_table_data_via_rest(table, limit=limit, filters=filters)
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
    
    def get_table_schema(self) -> Dict:
        """Get table schema from active backend"""
        if self.use_supabase:
            # For Supabase, we can't get OpenAPI schema easily, so return a simplified version
            return {
                "paths": {
                    "/datasets": {},
                    "/pharmacies": {},
                    "/search_results": {},
                    "/validated_overrides": {},
                    "/rpc/get_all_results_with_context": {}
                }
            }
        else:
            return self.postgrest_client.get_table_schema()
    
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
    
    def delete_dataset(self, dataset_id: int) -> Dict:
        """Delete a dataset and all its associated data"""
        if self.use_supabase:
            return self.supabase_client.delete_dataset_supabase(dataset_id)
        else:
            return self.postgrest_client.delete_dataset(dataset_id)
    
    def rename_dataset(self, dataset_id: int, new_tag: str) -> Dict:
        """Rename a dataset tag"""
        if self.use_supabase:
            return self.supabase_client.rename_dataset_supabase(dataset_id, new_tag)
        else:
            return self.postgrest_client.rename_dataset(dataset_id, new_tag)
    
    def get_table_counts(self, tables: List[str]) -> Dict[str, str]:
        """Get record counts for multiple tables"""
        if self.use_supabase:
            return self.supabase_client.get_table_counts_supabase(tables)
        else:
            return self.postgrest_client.get_table_counts(tables)
    
    def _get_dataset_id(self, tag: str, kind: str) -> Optional[int]:
        """Get dataset ID for a tag and kind"""
        datasets = self.get_datasets()
        for dataset in datasets:
            if dataset.get('tag') == tag and dataset.get('kind') == kind:
                return dataset.get('id')
        return None
    
    def has_scores(self, states_tag: str, pharmacies_tag: str) -> bool:
        """Check if scores exist for dataset pair"""
        # Get dataset IDs
        states_id = self._get_dataset_id(states_tag, 'states')
        pharmacies_id = self._get_dataset_id(pharmacies_tag, 'pharmacies')
        
        if not states_id or not pharmacies_id:
            return False
        
        # Count existing scores via active backend
        if self.use_supabase:
            # Use Supabase REST API - just check if any records exist
            filters = {
                'states_dataset_id': f'eq.{states_id}',
                'pharmacies_dataset_id': f'eq.{pharmacies_id}'
            }
            result = self.supabase_client.get_table_data_via_rest(
                'match_scores', limit=1, filters=filters
            )
            # If we get any results, scores exist
            return len(result) > 0 if isinstance(result, list) else False
        else:
            # Use PostgREST count
            try:
                response = self.postgrest_client._request(
                    'GET', 'match_scores',
                    params={
                        'select': 'count',
                        'states_dataset_id': f'eq.{states_id}',
                        'pharmacies_dataset_id': f'eq.{pharmacies_id}'
                    },
                    headers={'Prefer': 'count=exact'}
                )
                count = response.json()[0]['count']
                return count > 0
            except Exception:
                return False
    
    def trigger_scoring(self, states_tag: str, pharmacies_tag: str, batch_size: int = 200) -> Dict[str, Any]:
        """Trigger client-side scoring computation for dataset pair"""
        try:
            # Step 1: Get all results (including those without scores)
            results = self.get_comprehensive_results(states_tag, pharmacies_tag, "")
            if isinstance(results, dict) and 'error' in results:
                return results
            
            # Step 2: Find pharmacy/result pairs that need scoring
            missing_pairs = []
            for result in results:
                if result.get('result_id') and result.get('score_overall') is None:
                    missing_pairs.append({
                        'pharmacy_id': result['pharmacy_id'],
                        'result_id': result['result_id'],
                        'pharmacy_address': result.get('pharmacy_address', ''),
                        'pharmacy_city': result.get('pharmacy_city', ''),
                        'pharmacy_state': result.get('pharmacy_state', ''),
                        'pharmacy_zip': result.get('pharmacy_zip', ''),
                        'result_address': result.get('result_address', ''),
                        'result_city': result.get('result_city', ''),
                        'result_state': result.get('result_state', ''),
                        'result_zip': result.get('result_zip', '')
                    })
            
            if not missing_pairs:
                return {'success': True, 'message': 'No scoring needed - all pairs already scored', 'scores_computed': 0}
            
            # Step 3: Compute scores client-side using scoring_plugin.py
            computed_scores = self._compute_scores_client_side(missing_pairs, states_tag, pharmacies_tag)
            
            # Step 4: Insert scores via API
            if computed_scores:
                insert_result = self._insert_scores(computed_scores)
                if 'error' in insert_result:
                    return insert_result
            
            return {
                'success': True, 
                'message': f'Computed {len(computed_scores)} scores client-side',
                'scores_computed': len(computed_scores)
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _compute_scores_client_side(self, missing_pairs: List[Dict], states_tag: str, pharmacies_tag: str) -> List[Dict]:
        """Compute scores client-side using scoring_plugin.py"""
        # Import scoring plugin
        import sys
        from pathlib import Path
        
        # Add project root to path to import scoring_plugin
        project_root = Path(__file__).parent.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        try:
            from scoring_plugin import Address, match_addresses
        except ImportError as e:
            return []  # Return empty if can't import plugin
        
        # Get dataset IDs for the scores
        states_id = self._get_dataset_id(states_tag, 'states')
        pharmacies_id = self._get_dataset_id(pharmacies_tag, 'pharmacies')
        
        computed_scores = []
        
        for pair in missing_pairs:
            try:
                # Create address objects
                pharmacy_addr = Address(
                    address=pair['pharmacy_address'],
                    suite=None,  # Suite not typically in pharmacy data
                    city=pair['pharmacy_city'],
                    state=pair['pharmacy_state'],
                    zip=pair['pharmacy_zip']
                )
                
                result_addr = Address(
                    address=pair['result_address'],
                    suite=None,  # Suite not typically in search results
                    city=pair['result_city'],
                    state=pair['result_state'],
                    zip=pair['result_zip']
                )
                
                # Compute scores using plugin
                street_score, csz_score, overall_score = match_addresses(result_addr, pharmacy_addr)
                
                # Prepare score record
                computed_scores.append({
                    'states_dataset_id': states_id,
                    'pharmacies_dataset_id': pharmacies_id,
                    'pharmacy_id': pair['pharmacy_id'],
                    'result_id': pair['result_id'],
                    'score_overall': round(overall_score, 2),
                    'score_street': round(street_score, 2),
                    'score_city_state_zip': round(csz_score, 2),
                    'scoring_meta': {
                        'algorithm': 'v1.0',
                        'computed_client_side': True,
                        'states_tag': states_tag,
                        'pharmacies_tag': pharmacies_tag
                    }
                })
                
            except Exception as e:
                # Skip this pair if scoring fails
                continue
        
        return computed_scores
    
    def _insert_scores(self, scores: List[Dict]) -> Dict[str, Any]:
        """Insert computed scores via API"""
        if not scores:
            return {'success': True, 'inserted': 0}
        
        try:
            if self.use_supabase:
                # Use Supabase REST API to insert
                import requests
                url = f"{self.supabase_client.url}/rest/v1/match_scores"
                
                # Convert scoring_meta to JSON string for database
                for score in scores:
                    if isinstance(score.get('scoring_meta'), dict):
                        import json
                        score['scoring_meta'] = json.dumps(score['scoring_meta'])
                
                response = requests.post(url, 
                                       headers=self.supabase_client.headers,
                                       json=scores,
                                       timeout=30)
                
                if response.status_code in [200, 201]:
                    return {'success': True, 'inserted': len(scores)}
                else:
                    return {'error': f'Insert failed: {response.status_code} {response.text}'}
            else:
                # Use PostgREST to insert
                import json
                
                # Convert scoring_meta to JSON string for database
                for score in scores:
                    if isinstance(score.get('scoring_meta'), dict):
                        score['scoring_meta'] = json.dumps(score['scoring_meta'])
                
                response = self.postgrest_client._request(
                    'POST', 'match_scores',
                    data=scores
                )
                return {'success': True, 'inserted': len(scores)}
                
        except Exception as e:
            return {'error': str(e)}
    
    def clear_scores(self, states_tag: str, pharmacies_tag: str) -> Dict[str, Any]:
        """Clear scores for dataset pair (for testing)"""
        # Get dataset IDs
        states_id = self._get_dataset_id(states_tag, 'states')
        pharmacies_id = self._get_dataset_id(pharmacies_tag, 'pharmacies')
        
        if not states_id or not pharmacies_id:
            return {'error': 'Dataset IDs not found'}
        
        if self.use_supabase:
            # Use Supabase REST API delete
            try:
                import requests
                url = f"{self.supabase_client.url}/rest/v1/match_scores"
                params = {
                    'states_dataset_id': f'eq.{states_id}',
                    'pharmacies_dataset_id': f'eq.{pharmacies_id}'
                }
                response = requests.delete(url, 
                                         headers=self.supabase_client.headers, 
                                         params=params, 
                                         timeout=30)
                if response.status_code in [200, 204]:
                    return {'success': True, 'message': 'Scores cleared'}
                else:
                    return {'error': f'Delete failed: {response.status_code} {response.text}'}
            except Exception as e:
                return {'error': str(e)}
        else:
            # Use PostgREST delete
            try:
                response = self.postgrest_client._request(
                    'DELETE', 'match_scores',
                    params={
                        'states_dataset_id': f'eq.{states_id}',
                        'pharmacies_dataset_id': f'eq.{pharmacies_id}'
                    }
                )
                return {'success': True, 'message': 'Scores cleared'}
            except Exception as e:
                return {'error': str(e)}


def create_client(prefer_supabase: bool = False) -> UnifiedClient:
    """Factory function to create unified client"""
    return UnifiedClient(prefer_supabase=prefer_supabase)


def datasets_to_dataframe(datasets: List[Dict]) -> pd.DataFrame:
    """Convert datasets list to pandas DataFrame"""
    return pd.DataFrame(datasets)


def results_to_dataframe(results: List[Dict]) -> pd.DataFrame:
    """Convert comprehensive results to pandas DataFrame"""
    return pd.DataFrame(results)