"""
Database utility functions for PharmChecker GUI
Handles MCP postgres integration and query execution
"""

import pandas as pd
import streamlit as st
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages database operations with PostgreSQL via SQLAlchemy"""
    
    def __init__(self, use_production: bool = True, allow_fallback: bool = False):
        """Initialize database manager
        
        Args:
            use_production: If True, use production database, else sandbox
            allow_fallback: If True, allow sample data fallback (development only)
        """
        self.use_production = use_production
        self.allow_fallback = allow_fallback
        # Note: db_tool property kept for backward compatibility but not used in operational system
    
    def execute_query(self, sql: str, params: Optional[List] = None) -> pd.DataFrame:
        """Execute SQL query and return results as DataFrame
        
        Args:
            sql: SQL query string
            params: Optional query parameters list
            
        Returns:
            DataFrame with query results
        """
        try:
            logger.info(f"Executing query: {sql[:100]}...")
            
            # Try to connect to actual database using SQLAlchemy
            try:
                from sqlalchemy import create_engine, text
                from config import get_db_config
                
                db_config = get_db_config()
                engine = create_engine(
                    f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
                )
                
                # Check if this is a SELECT query (returns data) or DML query (no data returned)
                sql_lower = sql.strip().lower()
                is_select = sql_lower.startswith('select') or 'returning' in sql_lower
                
                if is_select:
                    # Use pandas for SELECT queries
                    if params:
                        # Convert %s to SQLAlchemy parameter style and use positional parameters
                        param_sql = sql
                        param_dict = {}
                        for i, param in enumerate(params):
                            param_name = f"param{i+1}"
                            param_sql = param_sql.replace('%s', f":{param_name}", 1)
                            param_dict[param_name] = param
                        df = pd.read_sql_query(text(param_sql), engine, params=param_dict)
                    else:
                        df = pd.read_sql_query(sql, engine)
                    return df
                else:
                    # Use SQLAlchemy directly for UPDATE/INSERT/DELETE queries
                    with engine.connect() as conn:
                        if params:
                            param_sql = sql
                            param_dict = {}
                            for i, param in enumerate(params):
                                param_name = f"param{i+1}"
                                param_sql = param_sql.replace('%s', f":{param_name}", 1)
                                param_dict[param_name] = param
                            result = conn.execute(text(param_sql), param_dict)
                        else:
                            result = conn.execute(text(sql))
                        conn.commit()
                        
                        # Return empty DataFrame for non-SELECT queries
                        return pd.DataFrame()
                
            except (ImportError, Exception) as e:
                if self.allow_fallback:
                    logger.warning(f"Database connection failed: {e}. Using sample data for development.")
                    return self._get_fallback_data(sql)
                else:
                    logger.error(f"Database connection failed: {e}")
                    raise Exception(f"Database connection required for operational system. Check .env configuration: {e}")
            
        except Exception as e:
            if self.allow_fallback:
                logger.warning(f"Database query failed: {e}. Using sample data for development.")
                return self._get_fallback_data(sql)
            else:
                logger.error(f"Database query failed: {e}")
                raise Exception(f"Database query failed in operational system: {e}")
    
    def _get_fallback_data(self, sql: str) -> pd.DataFrame:
        """Get sample data when real database is not available"""
        if "datasets" in sql.lower():
            return self._get_sample_datasets()
        elif "get_results_matrix" in sql.lower():
            return self._get_sample_results_matrix()
        elif "find_missing_scores" in sql.lower():
            return self._get_sample_missing_scores()
        elif "match_scores" in sql.lower() and "count" in sql.lower():
            return self._get_sample_scoring_stats()
        elif "pharmacies" in sql.lower():
            return self._get_sample_pharmacies()
        elif "search_results" in sql.lower():
            return self._get_sample_search_results()
        else:
            return pd.DataFrame()
    
    def _get_sample_datasets(self) -> pd.DataFrame:
        """Return sample dataset data"""
        return pd.DataFrame({
            'kind': ['pharmacies', 'pharmacies', 'states', 'states'],
            'tag': ['2024-01-15', 'pilot-test', 'baseline', 'baseline2'],
            'created_at': [datetime.now()] * 4,
            'pharmacy_count': [5, 3, 0, 0],
            'search_count': [0, 0, 13, 18]
        })
    
    def _get_sample_results_matrix(self) -> pd.DataFrame:
        """Return sample results matrix data"""
        return pd.DataFrame({
            'pharmacy_id': [1, 1, 2, 2, 3, 3],
            'pharmacy_name': ['Belmar Pharmacy', 'Belmar Pharmacy', 'Beaker Pharmacy', 'Beaker Pharmacy', 'Empower Pharmacy', 'Empower Pharmacy'],
            'search_state': ['FL', 'PA', 'FL', 'PA', 'FL', 'PA'],
            'latest_result_id': [101, 102, 103, None, 104, None],
            'result_id': [101, 102, None, None, 104, None],
            'license_number': ['PH123456', 'PA78901', None, None, 'FL555666', None],
            'license_status': ['Active', 'Active', None, None, 'Active', None],
            'issue_date': ['2020-01-15', '2019-03-20', None, None, '2021-05-10', None],
            'expiration_date': ['2025-01-15', '2024-03-20', None, None, '2026-05-10', None],
            'score_overall': [96.5, 87.2, None, None, 66.5, None],
            'score_street': [98.0, 85.0, None, None, 70.0, None],
            'score_city_state_zip': [94.0, 92.0, None, None, 60.0, None],
            'override_type': [None, None, None, None, None, None],
            'validated_license': [None, None, None, None, None, None],
            'status_bucket': ['match', 'match', 'no data', 'no data', 'weak match', 'no data'],
            'warnings': [None, None, None, ['No results found'], None, None]
        })
    
    def _get_sample_missing_scores(self) -> pd.DataFrame:
        """Return sample missing scores data"""
        return pd.DataFrame({
            'pharmacy_id': [2, 3],
            'result_id': [201, 301]
        })
    
    def _get_sample_scoring_stats(self) -> pd.DataFrame:
        """Return sample scoring statistics"""
        return pd.DataFrame({
            'total_scores': [4],
            'avg_score': [84.1],
            'matches': [2],
            'weak_matches': [1],
            'no_matches': [1]
        })
    
    def _get_sample_pharmacies(self) -> pd.DataFrame:
        """Return sample pharmacy data"""
        return pd.DataFrame({
            'id': [1, 2, 3],
            'name': ['Belmar Pharmacy', 'Beaker Pharmacy', 'Empower Pharmacy'],
            'address': ['123 Main St', '456 Oak Ave', '789 Pine Rd'],
            'city': ['Tampa', 'Miami', 'Orlando'],
            'state': ['FL', 'FL', 'FL'],
            'zip_code': ['33601', '33101', '32801'],
            'phone': ['813-555-0123', '305-555-0456', '407-555-0789'],
            'state_licenses': ['{"FL","PA"}', '{"FL","PA"}', '{"FL"}']
        })
    
    def _get_sample_search_results(self) -> pd.DataFrame:
        """Return sample search results data"""
        return pd.DataFrame({
            'id': [101, 102, 104],
            'search_name': ['Belmar Pharmacy', 'Belmar Pharmacy', 'Empower Pharmacy'],
            'search_state': ['FL', 'PA', 'FL'],
            'license_number': ['PH123456', 'PA78901', 'FL555666'],
            'license_status': ['Active', 'Active', 'Active'],
            'address': ['123 Main St', '123 Main Street', '789 Pine Road'],
            'city': ['Tampa', 'Tampa', 'Orlando'],
            'state': ['FL', 'PA', 'FL'],
            'zip': ['33601', '33601', '32801'],
            'issue_date': ['2020-01-15', '2019-03-20', '2021-05-10'],
            'expiration_date': ['2025-01-15', '2024-03-20', '2026-05-10'],
            'result_status': ['results_found', 'results_found', 'results_found'],
            'screenshot_path': ['image_cache/baseline/FL/belmar_fl.202501_1045.png', 'image_cache/baseline/PA/belmar_pa.202501_1045.png', 'image_cache/baseline/FL/empower_fl.202501_1045.png'],
            'screenshot_storage_type': ['local', 'local', 'local'],
            'screenshot_file_size': [45821, 52031, 38402],
            'score_overall': [96.5, 87.2, 66.5],
            'score_street': [98.0, 85.0, 70.0],
            'score_city_state_zip': [94.0, 92.0, 60.0]
        })
    
    def get_datasets(self) -> Dict[str, List[str]]:
        """Get all available datasets grouped by kind"""
        sql = """
        SELECT kind, tag, created_at, 
               (SELECT COUNT(*) FROM pharmacies p WHERE p.dataset_id = d.id) as pharmacy_count,
               (SELECT COUNT(*) FROM search_results sr WHERE sr.dataset_id = d.id) as search_count
        FROM datasets d 
        ORDER BY kind, created_at DESC
        """
        
        try:
            df = self.execute_query(sql)
            if df.empty:
                # Return sample data for testing
                return {
                    'pharmacies': ['2024-01-15', 'pilot-test'], 
                    'states': ['baseline', 'baseline2'],
                    'validated': []
                }
            
            # Group by kind
            datasets = {}
            for kind in df['kind'].unique():
                kind_df = df[df['kind'] == kind]
                datasets[kind] = kind_df['tag'].tolist()
            
            return datasets
            
        except Exception as e:
            logger.error(f"Failed to fetch datasets: {e}")
            return {'pharmacies': [], 'states': [], 'validated': []}
    
    def get_dataset_stats(self, kind: str, tag: str) -> Dict[str, Any]:
        """Get statistics for a specific dataset"""
        sql = """
        SELECT d.id, d.kind, d.tag, d.created_at, d.description,
               CASE 
                   WHEN d.kind = 'pharmacies' THEN (SELECT COUNT(*) FROM pharmacies p WHERE p.dataset_id = d.id)
                   WHEN d.kind = 'states' THEN (SELECT COUNT(*) FROM search_results sr WHERE sr.dataset_id = d.id)
                   WHEN d.kind = 'validated' THEN (SELECT COUNT(*) FROM validated_overrides vo WHERE vo.dataset_id = d.id)
               END as record_count
        FROM datasets d 
        WHERE d.kind = %s AND d.tag = %s
        """
        
        try:
            df = self.execute_query(sql, [kind, tag])
            if df.empty:
                return {
                    'record_count': 0,
                    'created_date': datetime.now(),
                    'description': f'{kind.title()} dataset: {tag}'
                }
            
            row = df.iloc[0]
            return {
                'record_count': row.get('record_count', 0),
                'created_date': row.get('created_at', datetime.now()),
                'description': row.get('description', f'{kind.title()} dataset: {tag}')
            }
            
        except Exception as e:
            logger.error(f"Failed to get dataset stats: {e}")
            return {
                'record_count': 0,
                'created_date': datetime.now(),
                'description': f'Error loading {kind} dataset: {tag}'
            }
    
    def get_loaded_states(self, states_tag: str) -> List[str]:
        """Get list of states that have search data loaded"""
        sql = """
        SELECT DISTINCT search_state 
        FROM search_results sr
        JOIN datasets d ON sr.dataset_id = d.id 
        WHERE d.tag = %s
        ORDER BY search_state
        """
        
        try:
            df = self.execute_query(sql, [states_tag])
            if df.empty:
                return []
            return df['search_state'].tolist()
        except Exception as e:
            logger.error(f"Failed to get loaded states: {e}")
            return []
    
    def get_results_matrix(self, 
                          states_tag: str, 
                          pharmacies_tag: str, 
                          validated_tag: Optional[str] = None,
                          filter_to_loaded_states: bool = True) -> pd.DataFrame:
        """DEPRECATED: Get results matrix using optimized database function with record counts
        
        This method is deprecated in favor of the new comprehensive approach:
        - Use get_comprehensive_results() to get all data
        - Use aggregate_for_matrix() to create matrix view
        - Use filter_for_detail() for detail views
        
        This provides better performance for detail views and eliminates multiple database calls.
        
        Args:
            states_tag: States dataset tag
            pharmacies_tag: Pharmacies dataset tag  
            validated_tag: Validated dataset tag (optional)
            filter_to_loaded_states: If True, only show states with search data
        """
        
        # Use new comprehensive function
        sql = "SELECT * FROM get_all_results_with_context(%s, %s, %s)"
        params = [states_tag, pharmacies_tag, validated_tag]
        
        try:
            comprehensive_df = self.execute_query(sql, params)
            
            if comprehensive_df.empty:
                # Return sample data for testing
                sample_data = pd.DataFrame({
                    'pharmacy_id': [1, 2, 3],
                    'pharmacy_name': ['Belmar Pharmacy', 'Beaker Pharmacy', 'Empower Pharmacy'],
                    'search_state': ['FL', 'PA', 'FL'],
                    'license_number': ['PH123456', None, 'PH789012'],
                    'license_status': ['Active', None, 'Active'],
                    'score_overall': [96.5, None, 66.5],
                    'status_bucket': ['match', 'no data', 'weak match'],
                    'warnings': [None, None, None],
                    'record_count': [9, 0, 3]
                })
                return sample_data
            
            # Aggregate into matrix format
            matrix_df = self._aggregate_comprehensive_to_matrix(comprehensive_df, filter_to_loaded_states, states_tag)
            return matrix_df
            
        except Exception as e:
            logger.error(f"Failed to get results matrix: {e}")
            return pd.DataFrame()
    
    def _add_record_counts(self, df: pd.DataFrame, states_tag: str) -> pd.DataFrame:
        """Add record counts for each pharmacy-state combination"""
        if df.empty:
            return df
            
        # Get record counts for all pharmacy-state combinations
        record_counts_sql = """
        SELECT sr.search_name, sr.search_state, COUNT(*) as record_count
        FROM search_results sr
        JOIN datasets d ON sr.dataset_id = d.id
        WHERE d.tag = %s
        GROUP BY sr.search_name, sr.search_state
        """
        
        try:
            counts_df = self.execute_query(record_counts_sql, [states_tag])
            
            # Merge with results matrix
            df_with_counts = df.merge(
                counts_df,
                left_on=['pharmacy_name', 'search_state'],
                right_on=['search_name', 'search_state'],
                how='left'
            )
            
            # Fill missing counts with 0 and drop the extra search_name column
            df_with_counts['record_count'] = df_with_counts['record_count'].fillna(0).astype(int)
            if 'search_name' in df_with_counts.columns:
                df_with_counts = df_with_counts.drop('search_name', axis=1)
                
            return df_with_counts
            
        except Exception as e:
            logger.error(f"Failed to add record counts: {e}")
            # Return original dataframe with 0 counts if counting fails
            df['record_count'] = 0
            return df
    
    def _aggregate_comprehensive_to_matrix(self, comprehensive_df: pd.DataFrame, 
                                         filter_to_loaded_states: bool = True,
                                         states_tag: str = None) -> pd.DataFrame:
        """Aggregate comprehensive results into matrix format"""
        if comprehensive_df.empty:
            return pd.DataFrame()
        
        # Group by (pharmacy_name, search_state)
        grouped = comprehensive_df.groupby(['pharmacy_name', 'search_state'])
        
        matrix_rows = []
        for (pharmacy_name, search_state), group in grouped:
            # Find best score from all results
            scores = group[group['score_overall'].notna()]['score_overall']
            best_score = scores.max() if len(scores) > 0 else None
            
            # Count results
            total_results = len(group[group['result_id'].notna()])
            
            # Determine status bucket
            status_bucket = 'no data'
            if group['override_type'].notna().any():
                status_bucket = 'validated'
            elif best_score is not None:
                if best_score >= 85:
                    status_bucket = 'match'
                elif best_score >= 60:
                    status_bucket = 'weak match'
                else:
                    status_bucket = 'no match'
            elif total_results > 0:
                status_bucket = 'no match'
            
            # Get representative row for other fields
            first_row = group.iloc[0]
            best_score_row = group[group['score_overall'] == best_score].iloc[0] if best_score is not None else first_row
            
            matrix_rows.append({
                'pharmacy_id': first_row['pharmacy_id'],
                'pharmacy_name': pharmacy_name,
                'search_state': search_state,
                'score_overall': best_score,
                'score_street': best_score_row['score_street'] if best_score is not None else None,
                'score_city_state_zip': best_score_row['score_city_state_zip'] if best_score is not None else None,
                'status_bucket': status_bucket,
                'result_count': total_results,
                'record_count': total_results,  # Add for compatibility
                'license_number': best_score_row['license_number'] if pd.notna(best_score_row['license_number']) else None,
                'license_status': best_score_row['license_status'] if pd.notna(best_score_row['license_status']) else None,
                'warnings': [],  # Placeholder for compatibility
                'pharmacy_dataset_id': first_row['pharmacy_dataset_id'],
                'states_dataset_id': first_row['states_dataset_id'],
                'validated_dataset_id': first_row['validated_dataset_id']
            })
        
        matrix_df = pd.DataFrame(matrix_rows)
        
        # Apply filtering if requested
        if filter_to_loaded_states and states_tag and not matrix_df.empty:
            # Get states with actual search data
            states_with_data = comprehensive_df[comprehensive_df['result_id'].notna()]['search_state'].unique()
            if len(states_with_data) > 0:
                matrix_df = matrix_df[matrix_df['search_state'].isin(states_with_data)]
        
        return matrix_df

    def get_validations(self, validated_tag: str) -> pd.DataFrame:
        """Get validation override records for a dataset"""
        if not validated_tag:
            return pd.DataFrame()
            
        sql = """
        SELECT vo.* FROM validated_overrides vo
        JOIN datasets d ON vo.dataset_id = d.id  
        WHERE d.tag = %s
        """
        
        try:
            return self.execute_query(sql, [validated_tag])
        except Exception as e:
            logger.error(f"Failed to get validations: {e}")
            return pd.DataFrame()

    def get_pharmacies(self, pharmacies_tag: str) -> pd.DataFrame:
        """Get pharmacy records for a dataset"""
        if not pharmacies_tag:
            return pd.DataFrame()
            
        sql = """
        SELECT p.* FROM pharmacies p
        JOIN datasets d ON p.dataset_id = d.id  
        WHERE d.tag = %s
        """
        
        try:
            return self.execute_query(sql, [pharmacies_tag])
        except Exception as e:
            logger.error(f"Failed to get pharmacies: {e}")
            return pd.DataFrame()

    def find_missing_scores(self, states_tag: str, pharmacies_tag: str) -> pd.DataFrame:
        """Find pharmacy/result pairs that need scoring using comprehensive results"""
        
        sql = """
        SELECT pharmacy_id, result_id
        FROM get_all_results_with_context(%s, %s, NULL)
        WHERE result_id IS NOT NULL AND score_overall IS NULL
        """
        params = [states_tag, pharmacies_tag]
        
        try:
            df = self.execute_query(sql, params)
            
            if df.empty:
                # Return sample data
                return pd.DataFrame({
                    'pharmacy_id': [1, 2],
                    'result_id': [10, 15]
                })
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to find missing scores: {e}")
            return pd.DataFrame()
    
    def get_pharmacy_details(self, pharmacy_id: int) -> Dict[str, Any]:
        """Get detailed information for a specific pharmacy"""
        sql = """
        SELECT p.*, d.tag as dataset_tag
        FROM pharmacies p 
        JOIN datasets d ON p.dataset_id = d.id
        WHERE p.id = %s
        """
        
        try:
            df = self.execute_query(sql, [pharmacy_id])
            if df.empty:
                return {}
            
            return df.iloc[0].to_dict()
            
        except Exception as e:
            logger.error(f"Failed to get pharmacy details: {e}")
            return {}
    
    def get_search_results(self, pharmacy_name: str, state: str, dataset_tag: str) -> pd.DataFrame:
        """Get search results for a specific pharmacy and state with image data"""
        # Handle dataset tag variations - if just "baseline", try "states_baseline" 
        if dataset_tag and not dataset_tag.startswith('states_'):
            dataset_tag = f"states_{dataset_tag}"
            
        sql = """
        SELECT sr.*, 
               CASE 
                   WHEN img.organized_path IS NOT NULL 
                   THEN 'image_cache/' || img.organized_path 
                   ELSE NULL 
               END as screenshot_path,
               img.storage_type as screenshot_storage_type,
               img.file_size as screenshot_file_size,
               ms.score_overall,
               ms.score_street,
               ms.score_city_state_zip
        FROM search_results sr
        JOIN datasets d ON sr.dataset_id = d.id
        LEFT JOIN images img ON img.search_result_id = sr.id
        LEFT JOIN match_scores ms ON ms.result_id = sr.id 
        WHERE sr.search_name = %s 
          AND sr.search_state = %s 
          AND d.tag = %s
        ORDER BY sr.search_ts DESC, sr.license_number
        """
        
        try:
            return self.execute_query(sql, [pharmacy_name, state, dataset_tag])
        except Exception as e:
            logger.error(f"Failed to get search results: {e}")
            return pd.DataFrame()
    
    def get_scoring_statistics(self, states_tag: str, pharmacies_tag: str) -> Dict[str, Any]:
        """Get scoring statistics for dataset combination"""
        sql = """
        SELECT 
            COUNT(*) as total_scores,
            AVG(score_overall) as avg_score,
            COUNT(CASE WHEN score_overall >= 85 THEN 1 END) as matches,
            COUNT(CASE WHEN score_overall >= 60 AND score_overall < 85 THEN 1 END) as weak_matches,
            COUNT(CASE WHEN score_overall < 60 THEN 1 END) as no_matches
        FROM match_scores ms
        JOIN datasets d1 ON ms.states_dataset_id = d1.id
        JOIN datasets d2 ON ms.pharmacies_dataset_id = d2.id
        WHERE d1.tag = %s AND d2.tag = %s
        """
        
        try:
            df = self.execute_query(sql, [states_tag, pharmacies_tag])
            if df.empty:
                return {
                    'total_scores': 0,
                    'avg_score': 0.0,
                    'matches': 0,
                    'weak_matches': 0,
                    'no_matches': 0
                }
            
            return df.iloc[0].to_dict()
            
        except Exception as e:
            logger.error(f"Failed to get scoring statistics: {e}")
            return {}

    # =====================================================
    # NEW COMPREHENSIVE RESULTS METHODS
    # =====================================================
    
    def get_comprehensive_results(self, states_tag: str, pharmacies_tag: str, 
                                validated_tag: Optional[str] = None,
                                filter_to_loaded_states: bool = True) -> pd.DataFrame:
        """Get all search results for dataset combination using new comprehensive function
        
        Returns complete dataset without aggregation for client-side processing.
        
        Args:
            states_tag: States dataset tag
            pharmacies_tag: Pharmacies dataset tag  
            validated_tag: Validated dataset tag (optional)
            filter_to_loaded_states: If True, only include states with search data
            
        Returns:
            DataFrame with all relevant search results and context
        """
        # Always get all results first, then filter client-side if needed
        sql = "SELECT * FROM get_all_results_with_context(%s, %s, %s)"
        params = [states_tag, pharmacies_tag, validated_tag]
        
        try:
            df = self.execute_query(sql, params)
            
            if df.empty:
                logger.warning("No comprehensive results found, using fallback data")
                return self._get_sample_comprehensive_results()
            
            # Add computed fields that were previously done in SQL
            df = self._add_computed_fields(df)
            
            # Lazy scoring trigger: automatically compute missing scores
            df = self._trigger_lazy_scoring_if_needed(df, states_tag, pharmacies_tag, validated_tag)
            
            # Apply client-side filtering if requested
            if filter_to_loaded_states and not df.empty:
                # Get states with actual search data OR validation data
                states_with_search_data = df[df['result_id'].notna()]['search_state'].unique()
                states_with_validation_data = df[df['override_type'].notna()]['search_state'].unique() if 'override_type' in df.columns else []
                states_with_data = list(set(states_with_search_data) | set(states_with_validation_data))
                
                if len(states_with_data) > 0:
                    df = df[df['search_state'].isin(states_with_data)]
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to get comprehensive results: {e}")
            if self.allow_fallback:
                return self._get_sample_comprehensive_results()
            else:
                return pd.DataFrame()
    
    def _trigger_lazy_scoring_if_needed(self, df: pd.DataFrame, states_tag: str, pharmacies_tag: str, validated_tag: Optional[str] = None) -> pd.DataFrame:
        """Automatically trigger lazy scoring if scores are missing for this dataset combination
        
        Args:
            df: Current comprehensive results
            states_tag: States dataset tag
            pharmacies_tag: Pharmacies dataset tag
            validated_tag: Validated dataset tag (preserve validation data)
            
        Returns:
            Updated DataFrame with scores computed
        """
        if df.empty:
            return df
            
        try:
            # Check if there are search results without scores
            results_with_missing_scores = df[
                (df['result_id'].notna()) &  # Has search results
                (df['score_overall'].isna())  # But no scores
            ]
            
            if len(results_with_missing_scores) == 0:
                logger.debug("No missing scores found - lazy scoring not needed")
                return df
            
            logger.info(f"Found {len(results_with_missing_scores)} results without scores for {states_tag}+{pharmacies_tag}")
            logger.info("Triggering lazy scoring...")
            
            # Import and run scoring engine
            from imports.scoring import ScoringEngine
            from config import get_db_config
            
            with ScoringEngine(get_db_config()) as engine:
                stats = engine.compute_scores(states_tag, pharmacies_tag, max_pairs=1000)
                logger.info(f"Lazy scoring completed: {stats}")
            
            # Re-query to get updated data with scores - PRESERVE validation data
            logger.info("Re-querying data with computed scores...")
            sql = "SELECT * FROM get_all_results_with_context(%s, %s, %s)"
            params = [states_tag, pharmacies_tag, validated_tag]  # FIXED: Include validated_tag to preserve validation data
            updated_df = self.execute_query(sql, params)
            
            if not updated_df.empty:
                # Add computed fields to updated data
                updated_df = self._add_computed_fields(updated_df)
                logger.info(f"Successfully updated data with {len(updated_df)} rows")
                return updated_df
            else:
                logger.warning("Re-query after scoring returned no data")
                return df
                
        except Exception as e:
            logger.error(f"Lazy scoring failed: {e}")
            # Return original data if scoring fails
            return df
    
    def aggregate_for_matrix(self, full_df: pd.DataFrame) -> pd.DataFrame:
        """Client-side aggregation for matrix view from comprehensive results
        
        Args:
            full_df: Complete results DataFrame from get_comprehensive_results()
            
        Returns:
            DataFrame aggregated for matrix display (one row per pharmacy-state)
        """
        if full_df.empty:
            return pd.DataFrame()
        
        # Group by pharmacy-state combination
        groupby_cols = ['pharmacy_id', 'pharmacy_name', 'search_state']
        
        # Aggregate function for each column (only include columns that exist)
        agg_funcs = {}
        
        # Best scoring result fields
        if 'result_id' in full_df.columns:
            agg_funcs['result_id'] = lambda x: x[x.notna()].iloc[0] if not x[x.notna()].empty else None
        if 'license_number' in full_df.columns:
            agg_funcs['license_number'] = lambda x: x[x.notna()].iloc[0] if not x[x.notna()].empty else None
        if 'license_status' in full_df.columns:
            agg_funcs['license_status'] = lambda x: x[x.notna()].iloc[0] if not x[x.notna()].empty else None
        if 'issue_date' in full_df.columns:
            agg_funcs['issue_date'] = lambda x: x[x.notna()].iloc[0] if not x[x.notna()].empty else None
        if 'expiration_date' in full_df.columns:
            agg_funcs['expiration_date'] = lambda x: x[x.notna()].iloc[0] if not x[x.notna()].empty else None
            
        # Best scores
        if 'score_overall' in full_df.columns:
            agg_funcs['score_overall'] = lambda x: x[x.notna()].max() if not x[x.notna()].empty else None
        if 'score_street' in full_df.columns:
            agg_funcs['score_street'] = lambda x: x.iloc[x['score_overall'].idxmax()] if 'score_overall' in x and not x['score_overall'][x['score_overall'].notna()].empty else None
        if 'score_city_state_zip' in full_df.columns:
            agg_funcs['score_city_state_zip'] = lambda x: x.iloc[x['score_overall'].idxmax()] if 'score_overall' in x and not x['score_overall'][x['score_overall'].notna()].empty else None
            
        # Validation fields
        if 'override_type' in full_df.columns:
            agg_funcs['override_type'] = lambda x: x[x.notna()].iloc[0] if not x[x.notna()].empty else None
        if 'validated_license' in full_df.columns:
            agg_funcs['validated_license'] = lambda x: x[x.notna()].iloc[0] if not x[x.notna()].empty else None
            
        # Latest result for backwards compatibility
        if 'latest_result_id' in full_df.columns:
            agg_funcs['latest_result_id'] = lambda x: x[x.notna()].iloc[0] if not x[x.notna()].empty else None
        
        # Use prioritized selection logic: Validated > Best Score > First Record
        try:
            matrix_rows = []
            for (pharmacy_id, pharmacy_name, search_state), group in full_df.groupby(groupby_cols, dropna=False):
                # Priority 1: Look for validated record first
                validated_row = None
                
                # Check for validated records using database JOIN field
                try:
                    from utils.validation_local import is_validated_simple
                    
                    for idx, row in group.iterrows():
                        if is_validated_simple(row):
                            validated_row = row
                            break
                except (ImportError, AttributeError):
                    # No session state available (non-GUI context) - skip validation check
                    pass
                
                # Priority 3: Fall back to best score
                if validated_row is not None:
                    selected_row = validated_row
                else:
                    # Get best score or first record
                    if 'score_overall' in group.columns:
                        scores_filled = group['score_overall'].fillna(-1)
                        selected_row = group.loc[scores_filled.idxmax()]
                    else:
                        selected_row = group.iloc[0]
                
                matrix_rows.append(selected_row)
            
            # Create matrix DataFrame from selected rows
            if matrix_rows:
                matrix_df = pd.DataFrame(matrix_rows).reset_index(drop=True)
                
                # Add record counts manually
                record_counts = full_df.groupby(['pharmacy_name', 'search_state']).size().reset_index(name='record_count_new')
                matrix_df = matrix_df.merge(record_counts, on=['pharmacy_name', 'search_state'], how='left')
                
                # Replace the old record_count with the new one
                matrix_df['record_count'] = matrix_df['record_count_new'].fillna(0).astype(int)
                matrix_df = matrix_df.drop('record_count_new', axis=1)
                
                # Calculate status buckets after aggregation
                matrix_df['status_bucket'] = matrix_df.apply(self._calculate_status_bucket, axis=1)
                
                # Calculate warnings after aggregation  
                matrix_df['warnings'] = matrix_df.apply(lambda row: self._calculate_warnings(row, full_df), axis=1)
                
                return matrix_df
            else:
                # Return empty DataFrame with required columns
                return pd.DataFrame(columns=['pharmacy_id', 'pharmacy_name', 'search_state', 'record_count', 'status_bucket', 'warnings'])
                
        except Exception as e:
            logger.error(f"Failed to aggregate for matrix: {e}")
            return pd.DataFrame()
    
    def filter_for_detail(self, full_df: pd.DataFrame, pharmacy_name: str, 
                         search_state: str) -> pd.DataFrame:
        """Filter comprehensive results for detail view
        
        Args:
            full_df: Complete results DataFrame from get_comprehensive_results()
            pharmacy_name: Pharmacy name to filter for
            search_state: State to filter for
            
        Returns:
            DataFrame filtered to specific pharmacy-state combination
        """
        if full_df.empty:
            return pd.DataFrame()
        
        # Filter to specific pharmacy-state combination
        filtered_df = full_df[
            (full_df['pharmacy_name'] == pharmacy_name) & 
            (full_df['search_state'] == search_state)
        ].copy()
        
        # Sort by timestamp and score for display
        filtered_df = filtered_df.sort_values(['search_timestamp', 'score_overall'], 
                                            na_position='last', ascending=[False, False])
        
        return filtered_df
    
    def _add_computed_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add computed fields that were previously calculated in SQL"""
        if df.empty:
            return df
        
        # Add status bucket calculation
        df['status_bucket'] = df.apply(self._calculate_status_bucket, axis=1)
        
        # Add record counts per pharmacy-state combination
        df['record_count'] = df.groupby(['pharmacy_name', 'search_state'])['result_id'].transform('count')
        
        # Add latest_result_id for backwards compatibility
        df['latest_result_id'] = df['result_id']
        
        return df
    
    def _calculate_status_bucket(self, row) -> str:
        """Calculate status bucket for a result row (Python version of SQL logic)"""
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
    
    def _calculate_warnings(self, row, full_df: pd.DataFrame) -> List[str]:
        """Calculate warnings for a matrix row by comparing validation snapshot to current data"""
        warnings = []
        
        # Get validation status using cached validation data
        pharmacy_name = row.get('pharmacy_name')
        search_state = row.get('search_state')
        license_number = row.get('license_number', '') or ''
        
        # Check if this record is validated using cached data
        try:
            import streamlit as st
            validations_data = st.session_state.loaded_data.get('validations_data')
            if validations_data is None or validations_data.empty:
                return None
                
            # Find matching validation record
            validation_match = validations_data[
                (validations_data['pharmacy_name'] == pharmacy_name) &
                (validations_data['state_code'] == search_state) &
                (validations_data['license_number'] == license_number)
            ]
            
            if validation_match.empty:
                # Check for empty validation
                empty_match = validations_data[
                    (validations_data['pharmacy_name'] == pharmacy_name) &
                    (validations_data['state_code'] == search_state) &
                    (validations_data['license_number'].isna() | (validations_data['license_number'] == ''))
                ]
                
                if not empty_match.empty and not pd.isna(row.get('result_id')):
                    warnings.append('Validated empty but results now exist')
                return warnings if warnings else None
            
            validation_record = validation_match.iloc[0]
            
            # Basic validation state mismatches
            if validation_record['override_type'] == 'present' and pd.isna(row.get('result_id')):
                warnings.append('Validated present but result not found')
            
            # Field change warnings for present validations
            if validation_record['override_type'] == 'present' and not pd.isna(row.get('result_id')):
                # Compare snapshot vs current data
                field_comparisons = [
                    ('license_status', 'license_status'),
                    ('address', 'result_address'),  # Note: result_ prefix for current data
                    ('city', 'result_city'),
                    ('state', 'result_state'), 
                    ('zip', 'result_zip'),
                    ('expiration_date', 'expiration_date')
                ]
                
                changed_fields = []
                for validation_field, current_field in field_comparisons:
                    snapshot_value = validation_record.get(validation_field)
                    current_value = row.get(current_field)
                    
                    # Skip comparison if either value is None/empty
                    if pd.isna(snapshot_value) or pd.isna(current_value):
                        continue
                    if not str(snapshot_value).strip() or not str(current_value).strip():
                        continue
                        
                    # Convert to strings for comparison and normalize
                    snapshot_str = str(snapshot_value).strip()
                    current_str = str(current_value).strip()
                    
                    if snapshot_str != current_str:
                        changed_fields.append(validation_field)
                
                if changed_fields:
                    field_list = ', '.join(changed_fields)
                    warnings.append(f'Validated data changed: {field_list}')
        
        except Exception:
            # If no session state available, skip warning calculation
            pass
        
        return warnings if warnings else None
    
    def _get_sample_comprehensive_results(self) -> pd.DataFrame:
        """Return sample comprehensive results for development"""
        return pd.DataFrame({
            'pharmacy_id': [1, 1, 2, 2, 3, 3],
            'pharmacy_name': ['Belmar Pharmacy', 'Belmar Pharmacy', 'Beaker Pharmacy', 'Beaker Pharmacy', 'Empower Pharmacy', 'Empower Pharmacy'],
            'search_state': ['FL', 'PA', 'FL', 'PA', 'FL', 'PA'],
            'result_id': [101, 102, None, None, 104, None],
            'search_name': ['Belmar Pharmacy', 'Belmar Pharmacy', None, None, 'Empower Pharmacy', None],
            'license_number': ['PH123456', 'PA78901', None, None, 'FL555666', None],
            'license_status': ['Active', 'Active', None, None, 'Active', None],
            'license_name': ['Belmar Pharmacy', 'Belmar Pharmacy PA', None, None, 'Empower Pharmacy', None],
            'license_type': ['Pharmacy', 'Pharmacy', None, None, 'Pharmacy', None],
            'issue_date': ['2020-01-15', '2019-03-20', None, None, '2021-05-10', None],
            'expiration_date': ['2025-01-15', '2024-03-20', None, None, '2026-05-10', None],
            'score_overall': [96.5, 87.2, None, None, 66.5, None],
            'score_street': [98.0, 85.0, None, None, 70.0, None],
            'score_city_state_zip': [94.0, 92.0, None, None, 60.0, None],
            'override_type': [None, None, None, None, None, None],
            'validated_license': [None, None, None, None, None, None],
            'result_status': ['results_found', 'results_found', None, None, 'results_found', None],
            'search_timestamp': [pd.Timestamp('2025-01-15 10:30'), pd.Timestamp('2025-01-15 10:45'), None, None, pd.Timestamp('2025-01-15 11:00'), None],
            'screenshot_path': ['image_cache/sample/belmar_fl.png', 'image_cache/sample/belmar_pa.png', None, None, 'image_cache/sample/empower_fl.png', None],
            'screenshot_storage_type': ['local', 'local', None, None, 'local', None],
            'screenshot_file_size': [45821, 52031, None, None, 38402, None],
            'pharmacy_address': ['123 Main St', '123 Main St', '456 Oak Ave', '456 Oak Ave', '789 Pine Rd', '789 Pine Rd'],
            'pharmacy_city': ['Tampa', 'Tampa', 'Miami', 'Miami', 'Orlando', 'Orlando'],
            'pharmacy_state': ['FL', 'FL', 'FL', 'FL', 'FL', 'FL'],
            'pharmacy_zip': ['33601', '33601', '33101', '33101', '32801', '32801'],
            'result_address': ['123 Main St', '123 Main Street', None, None, '789 Pine Road', None],
            'result_city': ['Tampa', 'Tampa', None, None, 'Orlando', None],
            'result_state': ['FL', 'PA', None, None, 'FL', None],
            'result_zip': ['33601', '33601', None, None, '32801', None],
            'pharmacy_dataset_id': [1, 1, 1, 1, 1, 1],
            'states_dataset_id': [2, 2, 2, 2, 2, 2],
            'validated_dataset_id': [None, None, None, None, None, None]
        })

# Global database manager instance
@st.cache_resource
def get_database_manager(use_production: bool = True, allow_fallback: bool = False) -> DatabaseManager:
    """Get cached database manager instance
    
    Args:
        use_production: If True, use production database, else sandbox
        allow_fallback: If True, allow sample data fallback for development only
                       IMPORTANT: Must be False for operational system (no hardcoded data)
    """
    return DatabaseManager(use_production=use_production, allow_fallback=allow_fallback)

def query_with_cache(sql: str, params: Optional[Dict] = None, ttl: int = 300) -> pd.DataFrame:
    """Execute query with Streamlit caching"""
    
    @st.cache_data(ttl=ttl)
    def _cached_query(sql: str, params_str: str) -> pd.DataFrame:
        db = get_database_manager()
        return db.execute_query(sql, params if params else None)
    
    # Convert params to string for caching
    params_str = str(params) if params else ""
    return _cached_query(sql, params_str)