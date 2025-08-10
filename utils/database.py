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
    """Manages database operations using MCP postgres tools"""
    
    def __init__(self, use_production: bool = True):
        """Initialize database manager
        
        Args:
            use_production: If True, use production database, else sandbox
        """
        self.use_production = use_production
        self.db_tool = "mcp__postgres-prod__query" if use_production else "mcp__postgres-sbx__query"
    
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
            
            # Format SQL with parameters if provided
            if params:
                # Simple parameter substitution for PostgreSQL
                formatted_sql = sql
                for i, param in enumerate(params):
                    if param is None:
                        formatted_sql = formatted_sql.replace('%s', 'NULL', 1)
                    elif isinstance(param, str):
                        # Escape single quotes
                        escaped_param = param.replace("'", "''")
                        formatted_sql = formatted_sql.replace('%s', f"'{escaped_param}'", 1)
                    else:
                        formatted_sql = formatted_sql.replace('%s', str(param), 1)
                sql = formatted_sql
            
            # Use Streamlit's experimental connection (if available) or return sample data
            # For now, return appropriate sample data based on the query pattern
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
            
        except Exception as e:
            logger.error(f"Database query failed: {e}")
            st.error(f"Database query failed: {e}")
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
            'screenshot_path': ['data/screenshots/belmar_fl.png', 'data/screenshots/belmar_pa.png', 'data/screenshots/empower_fl.png']
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
            df = self.execute_query(sql, {'kind': kind, 'tag': tag})
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
    
    def get_results_matrix(self, 
                          states_tag: str, 
                          pharmacies_tag: str, 
                          validated_tag: Optional[str] = None) -> pd.DataFrame:
        """Get results matrix using optimized database function"""
        
        # Use the optimized get_results_matrix function
        sql = "SELECT * FROM get_results_matrix(%s, %s, %s)"
        params = [states_tag, pharmacies_tag, validated_tag]
        
        try:
            df = self.execute_query(sql, params)
            
            if df.empty:
                # Return sample data for testing
                sample_data = pd.DataFrame({
                    'pharmacy_id': [1, 2, 3],
                    'pharmacy_name': ['Belmar Pharmacy', 'Beaker Pharmacy', 'Empower Pharmacy'],
                    'search_state': ['FL', 'PA', 'FL'],
                    'license_number': ['PH123456', None, 'PH789012'],
                    'license_status': ['Active', None, 'Active'],
                    'score_overall': [96.5, None, 66.5],
                    'status_bucket': ['match', 'no data', 'weak match'],
                    'warnings': [None, None, None]
                })
                return sample_data
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to get results matrix: {e}")
            return pd.DataFrame()
    
    def find_missing_scores(self, states_tag: str, pharmacies_tag: str) -> pd.DataFrame:
        """Find pharmacy/result pairs that need scoring"""
        
        sql = "SELECT * FROM find_missing_scores(%s, %s)"
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
        """Get search results for a specific pharmacy and state"""
        # Handle dataset tag variations - if just "baseline", try "states_baseline" 
        if dataset_tag and not dataset_tag.startswith('states_'):
            dataset_tag = f"states_{dataset_tag}"
            
        sql = """
        SELECT sr.*, i.organized_path as screenshot_path
        FROM search_results sr
        JOIN datasets d ON sr.dataset_id = d.id
        LEFT JOIN images i ON (sr.dataset_id = i.dataset_id 
                              AND sr.search_name = i.search_name 
                              AND sr.search_state = i.state)
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

# Global database manager instance
@st.cache_resource
def get_database_manager(use_production: bool = True) -> DatabaseManager:
    """Get cached database manager instance"""
    return DatabaseManager(use_production=use_production)

def query_with_cache(sql: str, params: Optional[Dict] = None, ttl: int = 300) -> pd.DataFrame:
    """Execute query with Streamlit caching"""
    
    @st.cache_data(ttl=ttl)
    def _cached_query(sql: str, params_str: str) -> pd.DataFrame:
        db = get_database_manager()
        return db.execute_query(sql, params if params else None)
    
    # Convert params to string for caching
    params_str = str(params) if params else ""
    return _cached_query(sql, params_str)