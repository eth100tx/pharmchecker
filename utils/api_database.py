"""
API Database Manager for PharmChecker GUI
Provides API-compatible interface that matches existing DatabaseManager
"""

import pandas as pd
import streamlit as st
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import logging
import sys
import os

# Add api_poc to path to import client
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'api_poc', 'gui'))

try:
    from client import create_client
    API_CLIENT_AVAILABLE = True
except ImportError as e:
    API_CLIENT_AVAILABLE = False
    logging.warning(f"API client not available: {e}")

from config import get_config_summary, use_cloud_database, API_CACHE_TTL, API_RETRY_COUNT

logger = logging.getLogger(__name__)


class ApiDatabaseManager:
    """API-compatible database manager that wraps the unified client"""
    
    def __init__(self, use_api: bool = True, use_cloud_db: bool = False, allow_fallback: bool = False):
        """Initialize API database manager
        
        Args:
            use_api: If True, use API mode, otherwise fail
            use_cloud_db: If True, use Supabase cloud database, else local PostgreSQL
            allow_fallback: DEPRECATED - no fallback behavior allowed
        """
        if not API_CLIENT_AVAILABLE:
            raise Exception("API client not available - cannot initialize ApiDatabaseManager")
        
        self.use_api = use_api
        self.use_cloud_db = use_cloud_db
        
        # Initialize API client - fail if it doesn't work
        try:
            self.client = create_client(prefer_supabase=use_cloud_db)
            logger.info(f"API client initialized: {self.client.get_active_backend()}")
        except Exception as e:
            logger.error(f"Failed to initialize API client: {e}")
            raise Exception(f"Database connection failed: {e}")
        
        # No fallback manager - API client must work
    
    def _api_request_with_retry(self, func, *args, **kwargs):
        """Execute API request with retry logic"""
        last_exception = None
        
        for attempt in range(API_RETRY_COUNT):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                logger.warning(f"API request failed (attempt {attempt + 1}/{API_RETRY_COUNT}): {e}")
                if attempt < API_RETRY_COUNT - 1:
                    continue
        
        # All retries failed - no fallback
        raise Exception(f"API failed after {API_RETRY_COUNT} attempts: {last_exception}")
    
    # Removed _use_fallback method - no fallback behavior allowed
    
    def execute_query(self, sql: str, params: Optional[List] = None) -> pd.DataFrame:
        """Execute SQL query - NOT SUPPORTED in API mode
        
        API mode uses structured endpoints, not raw SQL
        """
        raise Exception("Direct SQL queries not supported in API mode - use structured methods instead")
    
    def get_datasets(self) -> Dict[str, List[str]]:
        """Get all available datasets grouped by kind"""
        if self.use_api and self.client:
            try:
                datasets_list = self._api_request_with_retry(self.client.get_datasets)
                
                # Convert API response to expected format
                datasets = {}
                for dataset in datasets_list:
                    kind = dataset.get('kind', 'unknown')
                    tag = dataset.get('tag', '')
                    if kind not in datasets:
                        datasets[kind] = []
                    if tag and tag not in datasets[kind]:
                        datasets[kind].append(tag)
                
                return datasets
                
            except Exception as e:
                logger.error(f"API get_datasets failed: {e}")
                if self.allow_fallback:
                    return self._use_fallback('get_datasets')
                raise
        else:
            return self._use_fallback('get_datasets')
    
    def get_dataset_stats(self, kind: str, tag: str) -> Dict[str, Any]:
        """Get statistics for a specific dataset"""
        if self.use_api and self.client:
            try:
                datasets_list = self._api_request_with_retry(self.client.get_datasets)
                
                # Find matching dataset
                for dataset in datasets_list:
                    if dataset.get('kind') == kind and dataset.get('tag') == tag:
                        # Extract stats from dataset record
                        created_at = dataset.get('created_at')
                        if created_at:
                            try:
                                created_date = pd.to_datetime(created_at)
                            except:
                                created_date = datetime.now()
                        else:
                            created_date = datetime.now()
                        
                        # Get record count based on kind
                        record_count = 0
                        if kind == 'pharmacies':
                            # Get pharmacy count for this dataset
                            pharmacies = self.client.get_pharmacies(dataset_id=dataset.get('id'), limit=9999)
                            record_count = len(pharmacies) if isinstance(pharmacies, list) else 0
                        elif kind == 'states':
                            # Get search results count for this dataset
                            search_results = self.client.get_search_results(dataset_id=dataset.get('id'), limit=9999)
                            record_count = len(search_results) if isinstance(search_results, list) else 0
                        
                        return {
                            'record_count': record_count,
                            'created_date': created_date,
                            'description': dataset.get('description', f'{kind.title()} dataset: {tag}')
                        }
                
                # Dataset not found
                return {
                    'record_count': 0,
                    'created_date': datetime.now(),
                    'description': f'{kind.title()} dataset: {tag} (not found)'
                }
                
            except Exception as e:
                logger.error(f"API get_dataset_stats failed: {e}")
                if self.allow_fallback:
                    return self._use_fallback('get_dataset_stats', kind, tag)
                raise
        else:
            return self._use_fallback('get_dataset_stats', kind, tag)
    
    def get_loaded_states(self, states_tag: str) -> List[str]:
        """Get list of states that have search data loaded"""
        if self.use_api and self.client:
            try:
                # Get datasets to find the states dataset
                datasets_list = self._api_request_with_retry(self.client.get_datasets)
                
                states_dataset_id = None
                for dataset in datasets_list:
                    if dataset.get('kind') == 'states' and dataset.get('tag') == states_tag:
                        states_dataset_id = dataset.get('id')
                        break
                
                if not states_dataset_id:
                    return []
                
                # Get search results for this dataset and extract unique states
                search_results = self._api_request_with_retry(
                    self.client.get_search_results, 
                    dataset_id=states_dataset_id, 
                    limit=9999
                )
                
                if isinstance(search_results, list):
                    states = list(set(result.get('search_state') for result in search_results 
                                    if result.get('search_state')))
                    return sorted([state for state in states if state])
                else:
                    return []
                
            except Exception as e:
                logger.error(f"API get_loaded_states failed: {e}")
                if self.allow_fallback:
                    return self._use_fallback('get_loaded_states', states_tag)
                raise
        else:
            return self._use_fallback('get_loaded_states', states_tag)
    
    def get_comprehensive_results(self, states_tag: str, pharmacies_tag: str, 
                                validated_tag: Optional[str] = None,
                                filter_to_loaded_states: bool = True) -> pd.DataFrame:
        """Get all search results for dataset combination using comprehensive function"""
        if self.use_api and self.client:
            try:
                # Call the comprehensive results API
                results_list = self._api_request_with_retry(
                    self.client.get_comprehensive_results,
                    states_tag=states_tag,
                    pharmacies_tag=pharmacies_tag, 
                    validated_tag=validated_tag or ""
                )
                
                if isinstance(results_list, list) and len(results_list) > 0:
                    df = pd.DataFrame(results_list)
                    
                    # Add computed fields that were previously done in SQL
                    df = self._add_computed_fields(df)
                    
                    # Apply client-side filtering if requested
                    if filter_to_loaded_states and not df.empty:
                        # Get states with actual search data OR validation data
                        states_with_search_data = df[df['result_id'].notna()]['search_state'].unique()
                        states_with_validation_data = df[df['override_type'].notna()]['search_state'].unique() if 'override_type' in df.columns else []
                        states_with_data = list(set(states_with_search_data) | set(states_with_validation_data))
                        
                        if len(states_with_data) > 0:
                            df = df[df['search_state'].isin(states_with_data)]
                    
                    logger.info(f"API comprehensive results: {len(df)} rows")
                    return df
                else:
                    logger.warning("API comprehensive results returned empty list")
                    return pd.DataFrame()
                
            except Exception as e:
                logger.error(f"API get_comprehensive_results failed: {e}")
                if self.allow_fallback:
                    return self._use_fallback('get_comprehensive_results', states_tag, pharmacies_tag, validated_tag, filter_to_loaded_states)
                raise
        else:
            return self._use_fallback('get_comprehensive_results', states_tag, pharmacies_tag, validated_tag, filter_to_loaded_states)
    
    def aggregate_for_matrix(self, full_df: pd.DataFrame) -> pd.DataFrame:
        """Client-side aggregation for matrix view from comprehensive results"""
        # Always use our robust basic implementation to avoid fallback issues
        # The fallback manager may have its own KeyError issues
        try:
            return self._basic_aggregate_for_matrix(full_df)
        except Exception as e:
            logger.error(f"aggregate_for_matrix failed: {e}")
            # Return empty result with proper columns on any error
            return pd.DataFrame(columns=['pharmacy_id', 'pharmacy_name', 'search_state', 'record_count', 'status_bucket', 'warnings'])
    
    def filter_for_detail(self, full_df: pd.DataFrame, pharmacy_name: str, 
                         search_state: str) -> pd.DataFrame:
        """Filter comprehensive results for detail view"""
        # This method works the same regardless of API or direct database
        if self.fallback_manager:
            return self.fallback_manager.filter_for_detail(full_df, pharmacy_name, search_state)
        else:
            # Basic filtering logic
            if full_df.empty:
                return pd.DataFrame()
            
            filtered_df = full_df[
                (full_df['pharmacy_name'] == pharmacy_name) & 
                (full_df['search_state'] == search_state)
            ].copy()
            
            # Sort by timestamp and score for display
            filtered_df = filtered_df.sort_values(['search_timestamp', 'score_overall'], 
                                                na_position='last', ascending=[False, False])
            
            return filtered_df
    
    def get_validations(self, validated_tag: str) -> pd.DataFrame:
        """Get validation override records for a dataset"""
        if not validated_tag:
            return pd.DataFrame()
            
        if self.use_api and self.client:
            try:
                # Get datasets to find validation dataset
                datasets_list = self._api_request_with_retry(self.client.get_datasets)
                
                validated_dataset_id = None
                for dataset in datasets_list:
                    if dataset.get('kind') == 'validated' and dataset.get('tag') == validated_tag:
                        validated_dataset_id = dataset.get('id')
                        break
                
                if not validated_dataset_id:
                    return pd.DataFrame()
                
                # Get validation data via API
                validations = self._api_request_with_retry(
                    self.client.get_table_data,
                    table='validated_overrides',
                    limit=9999,
                    filters={'dataset_id': f'eq.{validated_dataset_id}'}
                )
                
                if isinstance(validations, list):
                    return pd.DataFrame(validations)
                else:
                    return pd.DataFrame()
                
            except Exception as e:
                logger.error(f"API get_validations failed: {e}")
                if self.allow_fallback:
                    return self._use_fallback('get_validations', validated_tag)
                raise
        else:
            return self._use_fallback('get_validations', validated_tag)
    
    def get_pharmacies(self, pharmacies_tag: str) -> pd.DataFrame:
        """Get pharmacy records for a dataset"""
        if not pharmacies_tag:
            return pd.DataFrame()
            
        if self.use_api and self.client:
            try:
                # Get datasets to find pharmacy dataset
                datasets_list = self._api_request_with_retry(self.client.get_datasets)
                
                pharmacy_dataset_id = None
                for dataset in datasets_list:
                    if dataset.get('kind') == 'pharmacies' and dataset.get('tag') == pharmacies_tag:
                        pharmacy_dataset_id = dataset.get('id')
                        break
                
                if not pharmacy_dataset_id:
                    return pd.DataFrame()
                
                # Get pharmacy data via API
                pharmacies = self._api_request_with_retry(
                    self.client.get_pharmacies,
                    dataset_id=pharmacy_dataset_id,
                    limit=9999
                )
                
                if isinstance(pharmacies, list):
                    return pd.DataFrame(pharmacies)
                else:
                    return pd.DataFrame()
                
            except Exception as e:
                logger.error(f"API get_pharmacies failed: {e}")
                if self.allow_fallback:
                    return self._use_fallback('get_pharmacies', pharmacies_tag)
                raise
        else:
            return self._use_fallback('get_pharmacies', pharmacies_tag)
    
    def find_missing_scores(self, states_tag: str, pharmacies_tag: str) -> pd.DataFrame:
        """Find pharmacy/result pairs that need scoring"""
        # This uses comprehensive results, so implement via API if possible
        try:
            comprehensive_df = self.get_comprehensive_results(states_tag, pharmacies_tag, None, False)
            
            if comprehensive_df.empty:
                return pd.DataFrame()
            
            # Find results without scores
            missing_scores = comprehensive_df[
                (comprehensive_df['result_id'].notna()) &  # Has search results
                (comprehensive_df['score_overall'].isna())  # But no scores
            ][['pharmacy_id', 'result_id']].drop_duplicates()
            
            return missing_scores
            
        except Exception as e:
            logger.error(f"find_missing_scores failed: {e}")
            if self.allow_fallback:
                return self._use_fallback('find_missing_scores', states_tag, pharmacies_tag)
            return pd.DataFrame()
    
    def compute_missing_scores(self, states_tag: str, pharmacies_tag: str, batch_size: int = 50) -> Dict[str, Any]:
        """Compute missing scores via API and scoring plugin"""
        if self.use_api and self.client:
            try:
                # Import scoring plugin
                import sys
                from pathlib import Path
                parent_dir = Path(__file__).parent.parent
                if str(parent_dir) not in sys.path:
                    sys.path.insert(0, str(parent_dir))
                
                from scoring_plugin import Address, match_addresses
                
                # Find missing scores
                missing_df = self.find_missing_scores(states_tag, pharmacies_tag)
                
                if missing_df.empty:
                    logger.info("No missing scores found")
                    return {'scores_computed': 0, 'message': 'No scores needed'}
                
                logger.info(f"Found {len(missing_df)} pharmacy-result pairs needing scores")
                
                # Process in batches
                scores_computed = 0
                batch_count = 0
                
                for start_idx in range(0, len(missing_df), batch_size):
                    batch = missing_df.iloc[start_idx:start_idx + batch_size]
                    batch_scores = []
                    
                    for _, row in batch.iterrows():
                        pharmacy_id = int(row['pharmacy_id'])
                        result_id = int(row['result_id'])
                        
                        try:
                            # Get pharmacy address via API
                            pharmacy_data = self.get_table_data('pharmacies', limit=1, filters={'id': f'eq.{pharmacy_id}'})
                            if not pharmacy_data:
                                continue
                            
                            pharmacy = pharmacy_data[0]
                            pharmacy_address = Address(
                                street=pharmacy.get('address', ''),
                                city=pharmacy.get('city', ''),
                                state=pharmacy.get('state', ''),
                                zip_code=pharmacy.get('zip', '')
                            )
                            
                            # Get result address via API
                            result_data = self.get_table_data('search_results', limit=1, filters={'id': f'eq.{result_id}'})
                            if not result_data:
                                continue
                                
                            result = result_data[0]
                            result_address = Address(
                                street=result.get('address', ''),
                                city=result.get('city', ''),
                                state=result.get('state', ''),
                                zip_code=result.get('zip', '')
                            )
                            
                            # Compute score using scoring plugin
                            score = match_addresses(pharmacy_address, result_address)
                            
                            # Prepare score for database update
                            batch_scores.append({
                                'pharmacy_id': pharmacy_id,
                                'result_id': result_id,
                                'score_overall': score.overall,
                                'score_street': score.street,
                                'score_city_state_zip': score.city_state_zip,
                                'computed_at': 'now()'  # PostgreSQL function
                            })
                            
                        except Exception as e:
                            logger.warning(f"Failed to compute score for pharmacy {pharmacy_id}, result {result_id}: {e}")
                            continue
                    
                    # Insert/update scores via API if we have any
                    if batch_scores:
                        try:
                            # Use upsert via PostgREST
                            for score_data in batch_scores:
                                # Use UPSERT to handle conflicts
                                self.client.get_table_data('match_scores', limit=1, filters={
                                    'pharmacy_id': f'eq.{score_data["pharmacy_id"]}',
                                    'result_id': f'eq.{score_data["result_id"]}'
                                })
                                
                                # For now, use direct table insertion (PostgREST supports UPSERT)
                                response = self.client.session.post(
                                    f"{self.client.base_url}/match_scores",
                                    json=score_data,
                                    headers={'Prefer': 'resolution=merge-duplicates'}
                                )
                                
                                if response.status_code in [200, 201]:
                                    scores_computed += 1
                                    
                        except Exception as e:
                            logger.error(f"Failed to save batch scores: {e}")
                    
                    batch_count += 1
                    logger.info(f"Processed batch {batch_count}, computed {scores_computed} scores so far")
                
                return {
                    'scores_computed': scores_computed,
                    'batches_processed': batch_count,
                    'message': f'Successfully computed {scores_computed} scores'
                }
                
            except Exception as e:
                logger.error(f"API compute_missing_scores failed: {e}")
                if self.allow_fallback:
                    # Fall back to using the scoring engine directly
                    from imports.scoring import ScoringEngine
                    scoring_engine = ScoringEngine()
                    return scoring_engine.compute_scores(states_tag, pharmacies_tag, batch_size)
                raise
        else:
            # Direct database mode: use scoring engine
            if self.allow_fallback and self.fallback_manager:
                from imports.scoring import ScoringEngine
                scoring_engine = ScoringEngine()
                return scoring_engine.compute_scores(states_tag, pharmacies_tag, batch_size)
            else:
                return {'error': 'Scoring not available without database access'}
    
    def get_pharmacy_details(self, pharmacy_id: int) -> Dict[str, Any]:
        """Get detailed information for a specific pharmacy"""
        if self.use_api and self.client:
            try:
                # Get pharmacy data via API
                pharmacies = self._api_request_with_retry(
                    self.client.get_table_data,
                    table='pharmacies',
                    limit=1,
                    filters={'id': f'eq.{pharmacy_id}'}
                )
                
                if isinstance(pharmacies, list) and len(pharmacies) > 0:
                    return pharmacies[0]
                else:
                    return {}
                
            except Exception as e:
                logger.error(f"API get_pharmacy_details failed: {e}")
                if self.allow_fallback:
                    return self._use_fallback('get_pharmacy_details', pharmacy_id)
                raise
        else:
            return self._use_fallback('get_pharmacy_details', pharmacy_id)
    
    def get_search_results(self, pharmacy_name: str, state: str, dataset_tag: str) -> pd.DataFrame:
        """Get search results for a specific pharmacy and state with image data"""
        if self.use_api and self.client:
            try:
                # Handle dataset tag variations
                if dataset_tag and not dataset_tag.startswith('states_'):
                    dataset_tag = f"states_{dataset_tag}"
                
                # Get datasets to find the states dataset
                datasets_list = self._api_request_with_retry(self.client.get_datasets)
                
                states_dataset_id = None
                for dataset in datasets_list:
                    if dataset.get('kind') == 'states' and dataset.get('tag') == dataset_tag:
                        states_dataset_id = dataset.get('id')
                        break
                
                if not states_dataset_id:
                    return pd.DataFrame()
                
                # Get search results with filters
                search_results = self._api_request_with_retry(
                    self.client.get_table_data,
                    table='search_results',
                    limit=9999,
                    filters={
                        'dataset_id': f'eq.{states_dataset_id}',
                        'search_name': f'eq.{pharmacy_name}',
                        'search_state': f'eq.{state}'
                    }
                )
                
                if isinstance(search_results, list):
                    df = pd.DataFrame(search_results)
                    # Sort by timestamp and license number
                    if not df.empty and 'search_ts' in df.columns:
                        df = df.sort_values(['search_ts', 'license_number'], ascending=[False, True])
                    return df
                else:
                    return pd.DataFrame()
                
            except Exception as e:
                logger.error(f"API get_search_results failed: {e}")
                if self.allow_fallback:
                    return self._use_fallback('get_search_results', pharmacy_name, state, dataset_tag)
                raise
        else:
            return self._use_fallback('get_search_results', pharmacy_name, state, dataset_tag)
    
    def get_scoring_statistics(self, states_tag: str, pharmacies_tag: str) -> Dict[str, Any]:
        """Get scoring statistics for dataset combination"""
        # This could be implemented via comprehensive results analysis
        try:
            comprehensive_df = self.get_comprehensive_results(states_tag, pharmacies_tag, None, False)
            
            if comprehensive_df.empty:
                return {
                    'total_scores': 0,
                    'avg_score': 0.0,
                    'matches': 0,
                    'weak_matches': 0,
                    'no_matches': 0
                }
            
            # Calculate statistics from comprehensive results
            scored_results = comprehensive_df[comprehensive_df['score_overall'].notna()]
            
            if len(scored_results) == 0:
                return {
                    'total_scores': 0,
                    'avg_score': 0.0,
                    'matches': 0,
                    'weak_matches': 0,
                    'no_matches': 0
                }
            
            scores = scored_results['score_overall']
            
            return {
                'total_scores': len(scores),
                'avg_score': float(scores.mean()),
                'matches': int((scores >= 85).sum()),
                'weak_matches': int(((scores >= 60) & (scores < 85)).sum()),
                'no_matches': int((scores < 60).sum())
            }
            
        except Exception as e:
            logger.error(f"get_scoring_statistics failed: {e}")
            if self.allow_fallback:
                return self._use_fallback('get_scoring_statistics', states_tag, pharmacies_tag)
            return {}
    
    def _add_computed_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add computed fields that were previously calculated in SQL"""
        if df.empty:
            return df
        
        # Use fallback manager's implementation if available
        if self.fallback_manager:
            return self.fallback_manager._add_computed_fields(df)
        
        # Basic implementation without fallback
        df['status_bucket'] = df.apply(self._calculate_status_bucket, axis=1)
        df['record_count'] = df.groupby(['pharmacy_name', 'search_state'])['result_id'].transform('count')
        df['latest_result_id'] = df['result_id']
        
        return df
    
    def _calculate_status_bucket(self, row) -> str:
        """Calculate status bucket for a result row"""
        if self.fallback_manager:
            return self.fallback_manager._calculate_status_bucket(row)
        
        # Basic implementation
        if row.get('override_type') == 'empty':
            return 'no data'
        elif row.get('override_type') == 'present':
            score = row.get('score_overall')
            if pd.isna(score):
                return 'no data'
            elif score >= 85:
                return 'match'
            elif score >= 60:
                return 'weak match'
            else:
                return 'no match'
        elif pd.isna(row.get('latest_result_id', row.get('result_id'))):
            return 'no data'
        elif pd.isna(row.get('score_overall')):
            return 'no data'
        elif row.get('score_overall', 0) >= 85:
            return 'match'
        elif row.get('score_overall', 0) >= 60:
            return 'weak match'
        else:
            return 'no match'
    
    def _basic_aggregate_for_matrix(self, full_df: pd.DataFrame) -> pd.DataFrame:
        """Basic aggregation logic for matrix view when no fallback available"""
        logger.debug(f"_basic_aggregate_for_matrix called with {len(full_df)} rows")
        
        # Return empty result with proper columns if input is empty
        if full_df.empty:
            logger.debug("Input DataFrame is empty, returning empty result")
            return pd.DataFrame(columns=['pharmacy_id', 'pharmacy_name', 'search_state', 'record_count'])
        
        # Check if required columns exist
        required_cols = ['pharmacy_id', 'pharmacy_name', 'search_state']
        missing_cols = [col for col in required_cols if col not in full_df.columns]
        
        if missing_cols:
            logger.warning(f"Missing required columns for aggregation: {missing_cols}")
            return pd.DataFrame(columns=['pharmacy_id', 'pharmacy_name', 'search_state', 'record_count'])
        
        # Simple aggregation: just take the first row for each pharmacy-state combination
        try:
            # Group and select first row from each group
            matrix_df = full_df.groupby(['pharmacy_id', 'pharmacy_name', 'search_state'], dropna=False).first().reset_index()
            
            # Add record count by counting group sizes
            record_counts = full_df.groupby(['pharmacy_name', 'search_state']).size().to_dict()
            matrix_df['record_count'] = matrix_df.apply(
                lambda row: record_counts.get((row['pharmacy_name'], row['search_state']), 1), 
                axis=1
            )
            
            # Add status_bucket and warnings columns that the GUI expects
            if self.fallback_manager:
                # Use fallback manager's methods for status calculation if available
                try:
                    matrix_df['status_bucket'] = matrix_df.apply(self.fallback_manager._calculate_status_bucket, axis=1)
                    matrix_df['warnings'] = matrix_df.apply(lambda row: self.fallback_manager._calculate_warnings(row, full_df), axis=1)
                except Exception:
                    # If fallback fails, use basic calculation
                    matrix_df['status_bucket'] = matrix_df.apply(self._calculate_status_bucket, axis=1)
                    matrix_df['warnings'] = None
            else:
                # Use basic status calculation
                matrix_df['status_bucket'] = matrix_df.apply(self._calculate_status_bucket, axis=1)
                matrix_df['warnings'] = None
            
            logger.debug(f"Successfully aggregated to {len(matrix_df)} rows")
            return matrix_df
            
        except Exception as e:
            logger.error(f"Error in _basic_aggregate_for_matrix: {e}")
            # Return minimal result on any error
            return pd.DataFrame(columns=['pharmacy_id', 'pharmacy_name', 'search_state', 'record_count'])
    
    def get_backend_info(self) -> Dict[str, Any]:
        """Get information about the current backend"""
        info = {
            'type': 'api' if self.use_api else 'direct_database',
            'api_available': API_CLIENT_AVAILABLE,
            'using_api': self.use_api,
            'fallback_available': self.fallback_manager is not None
        }
        
        if self.use_api and self.client:
            info.update({
                'active_backend': self.client.get_active_backend(),
                'api_url': self.client.get_active_api_url(),
                'backend_info': self.client.get_backend_info()
            })
        
        return info


# Global API database manager instance
@st.cache_resource
def get_api_database_manager(use_api: bool = True, use_cloud_db: bool = False, allow_fallback: bool = False) -> ApiDatabaseManager:
    """Get cached API database manager instance - allow_fallback parameter deprecated and ignored"""
    return ApiDatabaseManager(use_api=use_api, use_cloud_db=use_cloud_db, allow_fallback=False)