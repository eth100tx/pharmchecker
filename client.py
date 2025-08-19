"""
API client for PharmChecker - Supabase only
"""
import requests
import pandas as pd
import os
from typing import Dict, List, Any, Optional
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from supabase_client import SupabaseClient


class UnifiedClient:
    """Client that works exclusively with Supabase"""
    
    def __init__(self):
        """Initialize Supabase-only client"""
        self.supabase_client = SupabaseClient()
        
        # Test connection
        if not self.supabase_client.test_connection():
            raise Exception("Supabase connection failed - check SUPABASE_URL and SUPABASE_ANON_KEY")
        
        self.backend_info = {
            "backend": "supabase",
            "url": self.supabase_client.get_project_url()
        }
    
    def get_backend_info(self) -> Dict:
        """Get information about the backend"""
        return self.backend_info.copy()
    
    def test_connection(self) -> bool:
        """Test connection to Supabase"""
        return self.supabase_client.test_connection()
    
    def get_datasets(self) -> List[Dict]:
        """Get datasets from Supabase"""
        return self.supabase_client.get_datasets_supabase()
    
    def get_pharmacies(self, dataset_id: int = None, limit: int = 100) -> List[Dict]:
        """Get pharmacies from Supabase"""
        filters = {}
        if dataset_id:
            filters['dataset_id'] = f'eq.{dataset_id}'
        result = self.supabase_client.get_table_data_via_rest('pharmacies', limit=limit, filters=filters)
        return result if isinstance(result, list) else []
    
    def get_search_results(self, dataset_id: int = None, limit: int = 100) -> List[Dict]:
        """Get search results from Supabase"""
        filters = {}
        if dataset_id:
            filters['dataset_id'] = f'eq.{dataset_id}'
        result = self.supabase_client.get_table_data_via_rest('search_results', limit=limit, filters=filters)
        return result if isinstance(result, list) else []
    
    def get_comprehensive_results(self, states_tag: str, pharmacies_tag: str, validated_tag: str = "") -> List[Dict]:
        """Get comprehensive results from Supabase"""
        return self.supabase_client.get_comprehensive_results_supabase(states_tag, pharmacies_tag, validated_tag)
    
    def get_table_data(self, table: str, limit: int = 1000, filters: Dict = None, select: str = None) -> List[Dict]:
        """Get data from any table"""
        result = self.supabase_client.get_table_data_via_rest(table, limit=limit, filters=filters)
        return result if isinstance(result, list) else []
    
    def get_record_count(self, table: str, filters: Dict = None) -> int:
        """Get count of records in table (efficient - no data transfer)"""
        return self.supabase_client.get_record_count_via_rest(table, filters)
    
    def get_active_backend(self) -> str:
        """Get the name of the active backend"""
        return "Supabase"
    
    def get_active_api_url(self) -> str:
        """Get the API URL for the active backend"""
        return f"{self.supabase_client.get_project_url()}/rest/v1"
    
    def get_table_schema(self) -> Dict:
        """Get table schema from Supabase"""
        return {
            "paths": {
                "/datasets": {},
                "/pharmacies": {},
                "/search_results": {},
                "/validated_overrides": {},
                "/match_scores": {},
                "/app_users": {},
                "/rpc/get_all_results_with_context": {}
            }
        }
    
    # Supabase-specific methods
    def get_supabase_info(self) -> Dict:
        """Get Supabase project information"""
        return {
            "project_url": self.supabase_client.get_project_url(),
            "anon_key": self.supabase_client.get_anon_key()[:20] + "...",
            "tables": self.supabase_client.list_tables(),
            "migrations": self.supabase_client.list_migrations()
        }
    
    def setup_supabase_database(self) -> Dict:
        """Set up the database schema and functions in Supabase"""
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
        return self.supabase_client.delete_dataset_supabase(dataset_id)
    
    def rename_dataset(self, dataset_id: int, new_tag: str) -> Dict:
        """Rename a dataset tag"""
        return self.supabase_client.rename_dataset_supabase(dataset_id, new_tag)
    
    def update_table_record(self, table: str, record_id: int, data: Dict) -> Dict:
        """Update a record in any table"""
        try:
            import requests
            url = f"{self.supabase_client.url}/rest/v1/{table}"
            
            headers = self.supabase_client.headers.copy()
            headers['Prefer'] = 'return=minimal'
            
            params = {'id': f'eq.{record_id}'}
            
            response = requests.patch(url, 
                                     headers=headers,
                                     params=params,
                                     json=data,
                                     timeout=10)
            
            if response.status_code in [200, 204]:
                return {"success": True}
            else:
                return {"error": f"Update failed: {response.status_code} {response.text}"}
        except Exception as e:
            return {"error": str(e)}
    
    def delete_table_record(self, table: str, record_id: int) -> Dict:
        """Delete a record from any table"""
        try:
            import requests
            url = f"{self.supabase_client.url}/rest/v1/{table}"
            
            params = {'id': f'eq.{record_id}'}
            
            response = requests.delete(url, 
                                      headers=self.supabase_client.headers,
                                      params=params,
                                      timeout=10)
            
            if response.status_code in [200, 204]:
                return {"success": True}
            else:
                return {"error": f"Delete failed: {response.status_code} {response.text}"}
        except Exception as e:
            return {"error": str(e)}
    
    def get_table_counts(self, tables: List[str]) -> Dict[str, str]:
        """Get record counts for multiple tables"""
        return self.supabase_client.get_table_counts_supabase(tables)
    
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
        
        # Check if any scores exist
        filters = {
            'states_dataset_id': f'eq.{states_id}',
            'pharmacies_dataset_id': f'eq.{pharmacies_id}'
        }
        result = self.supabase_client.get_table_data_via_rest(
            'match_scores', limit=1, filters=filters
        )
        return len(result) > 0 if isinstance(result, list) else False
    
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
                    suite=None,
                    city=pair['pharmacy_city'],
                    state=pair['pharmacy_state'],
                    zip=pair['pharmacy_zip']
                )
                
                result_addr = Address(
                    address=pair['result_address'],
                    suite=None,
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
            import requests
            url = f"{self.supabase_client.url}/rest/v1/match_scores"
            
            # Convert scoring_meta to JSON string for database
            for score in scores:
                if isinstance(score.get('scoring_meta'), dict):
                    score['scoring_meta'] = json.dumps(score['scoring_meta'])
            
            response = requests.post(url, 
                                   headers=self.supabase_client.headers,
                                   json=scores,
                                   timeout=30)
            
            if response.status_code in [200, 201]:
                return {'success': True, 'inserted': len(scores)}
            else:
                return {'error': f'Insert failed: {response.status_code} {response.text}'}
                
        except Exception as e:
            return {'error': str(e)}
    
    def clear_scores(self, states_tag: str, pharmacies_tag: str) -> Dict[str, Any]:
        """Clear scores for dataset pair (for testing)"""
        # Get dataset IDs
        states_id = self._get_dataset_id(states_tag, 'states')
        pharmacies_id = self._get_dataset_id(pharmacies_tag, 'pharmacies')
        
        if not states_id or not pharmacies_id:
            return {'error': 'Dataset IDs not found'}
        
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
    
    def create_validation_record(self, dataset_id: int, pharmacy_name: str, state_code: str, 
                               license_number: str, override_type: str, reason: str, 
                               validated_by: str = "gui_user", search_result_snapshot: dict = None) -> Dict:
        """Create a validation record via API with full search result snapshot"""
        from datetime import datetime
        
        record = {
            'dataset_id': dataset_id,
            'pharmacy_name': pharmacy_name,
            'state_code': state_code,
            'license_number': license_number or '',
            'override_type': override_type,
            'reason': reason,
            'validated_by': validated_by,
            'validated_at': datetime.now().isoformat()
        }
        
        # Add search result snapshot fields if provided
        if search_result_snapshot:
            # Map comprehensive results field names to validation schema field names
            field_mapping = {
                'license_status': 'license_status',
                'license_name': 'license_name', 
                # 'license_type': 'license_type',  # TODO: Add column to DB first
                'result_address': 'address',       # result_address -> address
                'result_city': 'city',             # result_city -> city
                'result_state': 'state',           # result_state -> state
                'result_zip': 'zip',               # result_zip -> zip
                'issue_date': 'issue_date',
                'expiration_date': 'expiration_date',
                'result_status': 'result_status'
            }
            
            for source_field, target_field in field_mapping.items():
                if source_field in search_result_snapshot:
                    # Handle date fields properly
                    value = search_result_snapshot[source_field]
                    if value is not None and target_field in ['issue_date', 'expiration_date']:
                        # Convert pandas timestamps to string format if needed
                        if hasattr(value, 'strftime'):
                            value = value.strftime('%Y-%m-%d')
                        elif isinstance(value, str) and value.strip():
                            # Keep as string if it's already formatted
                            pass
                        else:
                            value = None
                    record[target_field] = value
        
        try:
            import requests
            url = f"{self.supabase_client.url}/rest/v1/validated_overrides"
            
            response = requests.post(url, 
                                   headers=self.supabase_client.headers,
                                   json=[record],
                                   timeout=30)
            
            if response.status_code in [200, 201]:
                return {"success": True, "message": "Validation record created"}
            else:
                return {"error": f"Failed to create validation: {response.status_code} {response.text}"}
        except Exception as e:
            return {"error": str(e)}
    
    def delete_validation_record(self, dataset_id: int, pharmacy_name: str, state_code: str, 
                               license_number: str = None) -> Dict:
        """Delete a validation record via API"""
        try:
            import requests
            url = f"{self.supabase_client.url}/rest/v1/validated_overrides"
            
            params = {
                'dataset_id': f'eq.{dataset_id}',
                'pharmacy_name': f'eq.{pharmacy_name}',
                'state_code': f'eq.{state_code}'
            }
            
            if license_number:
                params['license_number'] = f'eq.{license_number}'
            else:
                params['license_number'] = 'is.null'
            
            response = requests.delete(url, 
                                     headers=self.supabase_client.headers,
                                     params=params,
                                     timeout=30)
            
            if response.status_code in [200, 204]:
                return {"success": True, "message": "Validation record deleted"}
            else:
                return {"error": f"Failed to delete validation: {response.status_code} {response.text}"}
        except Exception as e:
            return {"error": str(e)}
    
    def create_dataset(self, kind: str, tag: str, description: str = None, created_by: str = "gui_user") -> Dict:
        """Create a new dataset via API"""
        try:
            import requests
            
            # Find unique tag if conflicts exist
            unique_tag = self._find_unique_tag(kind, tag)
            
            record = {
                'kind': kind,
                'tag': unique_tag,
                'description': description,
                'created_by': created_by
            }
            
            url = f"{self.supabase_client.url}/rest/v1/datasets"
            response = requests.post(url, 
                                   headers=self.supabase_client.headers,
                                   json=[record],
                                   timeout=30)
            
            if response.status_code in [200, 201]:
                # Get the created dataset to return ID
                get_url = f"{self.supabase_client.url}/rest/v1/datasets"
                params = {'kind': f'eq.{kind}', 'tag': f'eq.{unique_tag}'}
                get_response = requests.get(get_url, 
                                          headers=self.supabase_client.headers,
                                          params=params,
                                          timeout=30)
                
                if get_response.status_code == 200:
                    datasets = get_response.json()
                    if datasets:
                        dataset_id = datasets[0]['id']
                        return {"success": True, "dataset_id": dataset_id, "tag": unique_tag}
                
                return {"error": "Dataset created but could not retrieve ID"}
            else:
                return {"error": f"Failed to create dataset: {response.status_code} {response.text}"}
        except Exception as e:
            return {"error": str(e)}
    
    def _find_unique_tag(self, kind: str, base_tag: str) -> str:
        """Find a unique tag by adding (2), (3), etc. if conflicts exist"""
        try:
            # Check if base tag exists
            datasets = self.get_datasets()
            existing = [d for d in datasets if d.get('kind') == kind and d.get('tag') == base_tag]
            
            if not existing:
                return base_tag
            
            # Find next available number
            counter = 2
            while True:
                test_tag = f"{base_tag} ({counter})"
                existing = [d for d in datasets if d.get('kind') == kind and d.get('tag') == test_tag]
                
                if not existing:
                    return test_tag
                counter += 1
                
                # Safety limit
                if counter > 100:
                    return f"{base_tag} ({counter})"
                    
        except Exception:
            # If we can't check for uniqueness, just return base tag
            return base_tag


def create_client() -> UnifiedClient:
    """Factory function to create Supabase-only client"""
    return UnifiedClient()


def datasets_to_dataframe(datasets: List[Dict]) -> pd.DataFrame:
    """Convert datasets list to pandas DataFrame"""
    return pd.DataFrame(datasets)


def results_to_dataframe(results: List[Dict]) -> pd.DataFrame:
    """Convert comprehensive results to pandas DataFrame"""
    return pd.DataFrame(results)