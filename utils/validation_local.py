"""
Local validation state management for PharmChecker GUI
Handles session-based validation state with immediate UI updates
"""

import streamlit as st
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def initialize_loaded_data_state():
    """Initialize loaded data session state if not present"""
    if 'loaded_data' not in st.session_state:
        st.session_state.loaded_data = {
            'comprehensive_results': None,  # Search results + pharmacies + validation data from JOIN
            'pharmacies_data': None,        # Pharmacy records (cached)
            'loaded_tags': None,
            'last_load_time': None
        }

def is_validated_simple(row: pd.Series) -> bool:
    """Simple validation check using database JOIN field"""
    return row.get('override_type') is not None

def get_validation_type(row: pd.Series) -> Optional[str]:
    """Get validation type: 'present', 'empty', or None"""
    return row.get('override_type')

def get_validated_license(row: pd.Series) -> Optional[str]:
    """Get validated license number"""
    return row.get('validated_license')

def calculate_status_simple(row: pd.Series) -> str:
    """Single status calculation function using database JOIN fields"""
    
    # Check validation status first (HIGHEST PRIORITY)
    override_type = row.get('override_type')
    if override_type == 'empty':
        return 'validated empty'
    elif override_type == 'present':
        return 'validated present'
    
    # Fall back to score-based status
    score = row.get('score_overall')
    if pd.isna(score): 
        return 'no data'
    elif score >= 85: 
        return 'match'
    elif score >= 60: 
        return 'weak match'  
    else: 
        return 'no match'


def load_dataset_combination(pharmacies_tag: str, states_tag: str, validated_tag: Optional[str] = None) -> bool:
    """Load dataset combination - single source approach"""
    
    with st.spinner("Loading dataset combination..."):
        try:
            from utils.database import get_database_manager
            db = get_database_manager()
            
            # Load ONLY comprehensive results (includes validation data via JOIN)
            comprehensive_results = db.get_comprehensive_results(states_tag, pharmacies_tag, validated_tag)
            pharmacies_data = db.get_pharmacies(pharmacies_tag)
            
            # Store simplified session state
            st.session_state.loaded_data = {
                'comprehensive_results': comprehensive_results,  # Contains override_type from JOIN
                'pharmacies_data': pharmacies_data,
                'loaded_tags': {
                    'pharmacies': pharmacies_tag,
                    'states': states_tag, 
                    'validated': validated_tag
                },
                'last_load_time': datetime.now()
            }
            
            # Run validation consistency check
            validation_warnings = run_validation_consistency_check(comprehensive_results, validated_tag)
            if validation_warnings:
                st.warning(f"⚠️ {len(validation_warnings)} validation consistency issues found")
            
            # Data loaded successfully - context shown in sidebar
            return True
            
        except Exception as e:
            st.error(f"Failed to load dataset combination: {e}")
            return False

def run_validation_consistency_check(comprehensive_df: pd.DataFrame, validated_tag: Optional[str]) -> List[Dict]:
    """Run validation consistency checks using SQL function"""
    if not validated_tag:
        return []
    
    try:
        from utils.database import get_database_manager
        db = get_database_manager()
        
        # Get loaded tags from session state
        loaded_tags = st.session_state.loaded_data['loaded_tags']
        
        # Call SQL validation function
        sql = "SELECT * FROM check_validation_consistency(%s, %s, %s)"
        params = [loaded_tags['states'], loaded_tags['pharmacies'], validated_tag]
        
        validation_issues = db.execute_query(sql, params)
        
        if not validation_issues.empty:
            # Convert to list of dicts for easy handling
            issues = validation_issues.to_dict('records')
            
            # Log issues
            for issue in issues:
                logger.warning(f"Validation consistency issue: {issue['issue_type']} - {issue['description']}")
            
            return issues
        
        return []
        
    except Exception as e:
        logger.error(f"Failed to run validation consistency check: {e}")
        return []

def is_data_loaded() -> bool:
    """Check if data is currently loaded in session state"""
    initialize_loaded_data_state()
    return st.session_state.loaded_data['comprehensive_results'] is not None

def get_loaded_tags() -> Optional[Dict[str, str]]:
    """Get currently loaded dataset tags"""
    initialize_loaded_data_state()
    return st.session_state.loaded_data.get('loaded_tags')

def get_comprehensive_results() -> Optional[pd.DataFrame]:
    """Get currently loaded comprehensive results"""
    initialize_loaded_data_state()
    return st.session_state.loaded_data.get('comprehensive_results')

def clear_loaded_data():
    """Clear loaded data from session state"""
    initialize_loaded_data_state()
    st.session_state.loaded_data = {
        'comprehensive_results': None,
        'pharmacies_data': None,
        'loaded_tags': None,
        'last_load_time': None
    }
    st.info("🗑️ Cleared loaded data")

