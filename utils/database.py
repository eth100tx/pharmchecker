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
    """Legacy database manager - now redirects to API-based manager
    
    This class is kept for backward compatibility but now automatically
    uses the API-based system. All operations are delegated to ApiDatabaseManager.
    """
    
    def __init__(self, use_production: bool = True, allow_fallback: bool = False):
        """Initialize database manager
        
        Args:
            use_production: If True, use production database, else sandbox
            allow_fallback: If True, allow sample data fallback (development only)
        """
        # Import here to avoid circular imports
        from utils.api_database import get_api_database_manager
        
        # Always use API manager with Supabase
        self._api_manager = get_api_database_manager(
            use_api=True,
            use_cloud_db=True,
            allow_fallback=allow_fallback
        )
        
        self.use_production = use_production
        self.allow_fallback = allow_fallback
    
    def execute_query(self, sql: str, params: Optional[List] = None) -> pd.DataFrame:
        """Execute SQL query and return results as DataFrame
        
        Args:
            sql: SQL query string
            params: Optional query parameters list
            
        Returns:
            DataFrame with query results
        """
        # Delegate to API manager
        return self._api_manager.execute_query(sql, params)
    
    # Legacy fallback methods removed - all handled by API manager
    
    # Legacy sample data methods removed - handled by API manager
    
    def get_datasets(self) -> Dict[str, List[str]]:
        """Get all available datasets grouped by kind"""
        # Delegate to API manager
        return self._api_manager.get_datasets()
    
    def get_dataset_stats(self, kind: str, tag: str) -> Dict[str, Any]:
        """Get statistics for a specific dataset"""
        # Delegate to API manager
        return self._api_manager.get_dataset_stats(kind, tag)
    
    def get_loaded_states(self, states_tag: str) -> List[str]:
        """Get list of states that have search data loaded"""
        # Delegate to API manager
        return self._api_manager.get_loaded_states(states_tag)
    
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
        # Delegate to API manager
        return self._api_manager.get_results_matrix(
            states_tag, pharmacies_tag, validated_tag, filter_to_loaded_states
        )
    
    # Legacy record count methods removed - handled by API manager
    
    # Legacy aggregation methods removed - handled by API manager

    def get_validations(self, validated_tag: str) -> pd.DataFrame:
        """Get validation override records for a dataset"""
        # Delegate to API manager
        return self._api_manager.get_validations(validated_tag)

    def get_pharmacies(self, pharmacies_tag: str) -> pd.DataFrame:
        """Get pharmacy records for a dataset"""
        # Delegate to API manager
        return self._api_manager.get_pharmacies(pharmacies_tag)

    def find_missing_scores(self, states_tag: str, pharmacies_tag: str) -> pd.DataFrame:
        """Find pharmacy/result pairs that need scoring using comprehensive results"""
        # Delegate to API manager
        return self._api_manager.find_missing_scores(states_tag, pharmacies_tag)
    
    def get_pharmacy_details(self, pharmacy_id: int) -> Dict[str, Any]:
        """Get detailed information for a specific pharmacy"""
        # Delegate to API manager
        return self._api_manager.get_pharmacy_details(pharmacy_id)
    
    def get_search_results(self, pharmacy_name: str, state: str, dataset_tag: str) -> pd.DataFrame:
        """Get search results for a specific pharmacy and state with image data"""
        # Delegate to API manager
        return self._api_manager.get_search_results(pharmacy_name, state, dataset_tag)
    
    def get_scoring_statistics(self, states_tag: str, pharmacies_tag: str) -> Dict[str, Any]:
        """Get scoring statistics for dataset combination"""
        # Delegate to API manager
        return self._api_manager.get_scoring_statistics(states_tag, pharmacies_tag)

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
        # Delegate to API manager
        return self._api_manager.get_comprehensive_results(
            states_tag, pharmacies_tag, validated_tag, filter_to_loaded_states
        )
    
    # Legacy scoring trigger methods removed - handled by API manager
    
    def aggregate_for_matrix(self, full_df: pd.DataFrame) -> pd.DataFrame:
        """Client-side aggregation for matrix view from comprehensive results
        
        Args:
            full_df: Complete results DataFrame from get_comprehensive_results()
            
        Returns:
            DataFrame aggregated for matrix display (one row per pharmacy-state)
        """
        # Delegate to API manager
        return self._api_manager.aggregate_for_matrix(full_df)
    
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
        # Delegate to API manager
        return self._api_manager.filter_for_detail(full_df, pharmacy_name, search_state)
    
    # Legacy helper methods removed - handled by API manager

# Global database manager instance
@st.cache_resource
def get_database_manager(use_production: bool = True, allow_fallback: bool = False, _api_first: bool = True):
    """Get cached database manager instance - always returns API-based manager
    
    Args:
        use_production: If True, use production database, else sandbox
        allow_fallback: If True, allow sample data fallback for development only
    
    Returns:
        API-based DatabaseManager (legacy wrapper) or ApiDatabaseManager
    """
    # Always return the legacy DatabaseManager wrapper which delegates to API manager
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