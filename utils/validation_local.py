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
            'comprehensive_results': None,  # Search results + pharmacies (cached)
            'pharmacies_data': None,        # Pharmacy records (cached)
            'validations_data': None,       # Validation overrides (cached)
            'loaded_tags': None,
            'last_load_time': None
        }

def is_validated(pharmacy_name: str, state_code: str, license_number: str = '') -> bool:
    """Simple validation check using cached validation data"""
    validations_data = st.session_state.loaded_data.get('validations_data')
    if validations_data is None or validations_data.empty:
        return False
    
    # Check cached validation data
    if license_number:  # Present validation
        matches = validations_data[
            (validations_data['pharmacy_name'] == pharmacy_name) &
            (validations_data['state_code'] == state_code) &
            (validations_data['license_number'] == license_number)
        ]
    else:  # Empty validation  
        matches = validations_data[
            (validations_data['pharmacy_name'] == pharmacy_name) &
            (validations_data['state_code'] == state_code) &
            (validations_data['license_number'].isna())
        ]
    
    return not matches.empty

def calculate_status_simple(row: pd.Series) -> str:
    """Single status calculation function using cached validation data"""
    pharmacy_name = row.get('pharmacy_name')
    search_state = row.get('search_state')
    license_number = row.get('license_number', '') or ''
    
    # Check if validated using cached data
    if is_validated(pharmacy_name, search_state, license_number) or \
       is_validated(pharmacy_name, search_state, ''):  # Check empty validation too
        return 'validated'
    
    # Fall back to score-based status
    score = row.get('score_overall')
    if pd.isna(score): return 'no data'
    elif score >= 85: return 'match'
    elif score >= 60: return 'weak match'  
    else: return 'no match'


def load_dataset_combination(pharmacies_tag: str, states_tag: str, validated_tag: Optional[str] = None) -> bool:
    """Load dataset combination - cache three separate datasets"""
    
    with st.spinner("Loading dataset combination..."):
        try:
            from utils.database import get_database_manager
            db = get_database_manager()
            
            # Load three separate datasets and cache
            comprehensive_results = db.get_comprehensive_results(states_tag, pharmacies_tag, None)
            pharmacies_data = db.get_pharmacies(pharmacies_tag)
            validations_data = db.get_validations(validated_tag) if validated_tag else pd.DataFrame()
            
            # Store all three DataFrames - cached until reload
            st.session_state.loaded_data = {
                'comprehensive_results': comprehensive_results,
                'pharmacies_data': pharmacies_data,
                'validations_data': validations_data,
                'loaded_tags': {
                    'pharmacies': pharmacies_tag,
                    'states': states_tag, 
                    'validated': validated_tag
                },
                'last_load_time': datetime.now()
            }
            
            # Generate warnings once on load (required)
            try:
                generate_validation_warnings_simple()
            except Exception as e:
                st.warning(f"Warning generation failed: {e}")
            
            record_count = len(comprehensive_results)
            validation_count = len(validations_data)
            
            st.success(f"✅ Loaded {record_count} records with {validation_count} validations")
            return True
            
        except Exception as e:
            st.error(f"Failed to load dataset combination: {e}")
            return False

def generate_validation_warnings_simple():
    """Generate validation warnings once on load using cached data"""
    # Simple implementation - can be expanded later if needed
    # For now, just mark that warnings have been checked
    if hasattr(st.session_state, 'loaded_data'):
        st.session_state.loaded_data['warnings_generated'] = True

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
        'validations_data': None,
        'loaded_tags': None,
        'last_load_time': None
    }
    st.info("🗑️ Cleared loaded data")

