"""
PharmChecker MVP GUI - Streamlit Application
Main application with navigation and core functionality
"""

import streamlit as st
import pandas as pd
from typing import Dict, List, Optional, Tuple
import json
from datetime import datetime
import os
import sys
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# Add API POC client to path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'api_poc', 'gui'))

# Configure logger
logger = logging.getLogger(__name__)

# Import API client (NEW - replaces direct database access)
from client import create_client

# Import existing utility modules (keeping display utilities)
from utils.display import (
    display_dataset_summary, display_results_table,
    create_export_button, format_status_badge,
    display_dense_results_table, display_row_detail_section
)
from utils.auth import get_auth_manager, get_user_context, require_auth
from utils.session import auto_restore_dataset_selection, save_dataset_selection

# Import comprehensive results validation from API POC
from components.comprehensive_results import validate_comprehensive_results

# Page configuration
st.set_page_config(
    page_title="PharmChecker",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize API client
@st.cache_resource
def get_api_client():
    """Get cached API client instance"""
    # Use environment variable to determine cloud vs local
    from config import use_cloud_database
    return create_client(prefer_supabase=use_cloud_database())

def get_client():
    """Get API client with fallback initialization"""
    if 'api_client' not in st.session_state:
        st.session_state.api_client = get_api_client()
    
    # Ensure client has new scoring methods (for development)
    if not hasattr(st.session_state.api_client, 'has_scores'):
        st.session_state.api_client = get_api_client()
    
    return st.session_state.api_client

def get_detailed_validation_warning(pharmacy_name: str, search_state: str, license_number: str, 
                                   comprehensive_results: pd.DataFrame) -> Dict:
    """Get detailed field-by-field differences for a validation warning"""
    
    # Find the validation record in comprehensive results
    validation_match = comprehensive_results[
        (comprehensive_results['pharmacy_name'] == pharmacy_name) &
        (comprehensive_results['search_state'] == search_state) &
        (comprehensive_results['license_number'] == license_number) &
        (comprehensive_results['override_type'].notna())
    ]
    
    if validation_match.empty:
        return {'pharmacy': pharmacy_name, 'state': search_state, 'license': license_number, 'changes': []}
    
    validation_record = validation_match.iloc[0]
    
    # Find the current search result
    current_match = comprehensive_results[
        (comprehensive_results['pharmacy_name'] == pharmacy_name) &
        (comprehensive_results['search_state'] == search_state) &
        (comprehensive_results['license_number'] == license_number)
    ]
    
    if current_match.empty:
        return {'pharmacy': pharmacy_name, 'state': search_state, 'license': license_number, 'changes': []}
    
    current_record = current_match.iloc[0]
    
    # Compare fields and collect differences
    field_comparisons = [
        ('license_status', 'license_status'),
        ('address', 'result_address'),
        ('city', 'result_city'),
        ('state', 'result_state'),
        ('zip', 'result_zip'),
        ('expiration_date', 'expiration_date')
    ]
    
    changes = []
    for validation_field, current_field in field_comparisons:
        validated_value = validation_record.get(validation_field)
        current_value = current_record.get(current_field)
        
        # Skip if either is None/empty
        if pd.isna(validated_value) or pd.isna(current_value):
            continue
        if not str(validated_value).strip() or not str(current_value).strip():
            continue
            
        validated_str = str(validated_value).strip()
        current_str = str(current_value).strip()
        
        if validated_str != current_str:
            changes.append({
                'field': validation_field,
                'validated': validated_str,
                'current': current_str
            })
    
    return {
        'pharmacy': pharmacy_name,
        'state': search_state, 
        'license': license_number,
        'changes': changes
    }

# Initialize session state
def initialize_session_state():
    """Initialize session state variables with persistence"""
    # Check authentication first
    if not require_auth():
        return
    
    # Try to restore dataset selection from previous session
    restored_datasets = auto_restore_dataset_selection()
    
    if 'selected_datasets' not in st.session_state:
        if restored_datasets:
            st.session_state.selected_datasets = restored_datasets
            logger.info(f"Restored dataset selection: {restored_datasets}")
        else:
            st.session_state.selected_datasets = {
                'pharmacies': None,
                'states': None,
                'validated': None
            }
    
    if 'current_page' not in st.session_state:
        # If we restored datasets, go to Results Matrix, otherwise Dataset Manager
        if restored_datasets and all(restored_datasets.get(k) for k in ['pharmacies', 'states']):
            st.session_state.current_page = 'Results Matrix'
            # Auto-load the restored data
            # load_dataset_combination now defined locally
            validated_tag = restored_datasets.get('validated')
            load_dataset_combination(
                restored_datasets['pharmacies'], 
                restored_datasets['states'], 
                validated_tag
            )
        else:
            st.session_state.current_page = 'Dataset Manager'
    
    if 'last_query_time' not in st.session_state:
        st.session_state.last_query_time = None
    
    # Enhanced session state for loaded data management
    if 'loaded_data' not in st.session_state:
        st.session_state.loaded_data = {
            'comprehensive_results': None,
            'pharmacies_data': None,
            'loaded_tags': None,
            'last_load_time': None
        }
    
    # Initialize user context
    if 'user_context' not in st.session_state:
        st.session_state.user_context = get_user_context()

# Database operations using utility functions
def get_available_datasets() -> Dict[str, List[str]]:
    """Get all available dataset tags by kind"""
    client = get_client()
    datasets = client.get_datasets()
    
    # Group by kind
    result = {'pharmacies': [], 'states': [], 'validated': []}
    for dataset in datasets:
        kind = dataset.get('kind')
        tag = dataset.get('tag')
        if kind in result and tag:
            result[kind].append(tag)
    
    return result

def get_dataset_stats(kind: str, tag: str) -> Dict:
    """Get statistics for a specific dataset"""
    client = get_client()
    datasets = client.get_datasets()
    
    # Find the specific dataset
    dataset_info = None
    for dataset in datasets:
        if dataset.get('kind') == kind and dataset.get('tag') == tag:
            dataset_info = dataset
            break
    
    if not dataset_info:
        return {'record_count': 0}
    
    # Get record count by querying the appropriate table
    try:
        dataset_id = dataset_info.get('id')
        if kind == 'pharmacies':
            records = client.get_pharmacies(dataset_id=dataset_id, limit=9999)
            record_count = len(records) if isinstance(records, list) else 0
        elif kind == 'states':
            records = client.get_search_results(dataset_id=dataset_id, limit=9999)  
            record_count = len(records) if isinstance(records, list) else 0
        elif kind == 'validated':
            # Get validated overrides count
            validated_data = client.get_table_data('validated_overrides', filters={'dataset_id': f'eq.{dataset_id}'}, limit=9999)
            record_count = len(validated_data) if isinstance(validated_data, list) else 0
        else:
            record_count = 0
    except Exception as e:
        record_count = 0
    
    return {
        'id': dataset_info.get('id'),
        'tag': tag,
        'kind': kind,
        'description': dataset_info.get('description', ''),
        'created_at': dataset_info.get('created_at'),
        'created_by': dataset_info.get('created_by', 'Unknown'),
        'record_count': record_count
    }

# NEW: API-based data loading functions (replacing validation_local)
def load_dataset_combination(pharmacy_tag: str, states_tag: str, validated_tag: str = None) -> bool:
    """Load dataset combination using API client with transparent scoring"""
    try:
        client = get_client()
        
        # Check if scores exist for this combination
        has_scores = client.has_scores(states_tag, pharmacy_tag)
        
        if not has_scores:
            # Trigger scoring automatically
            with st.spinner("Computing address match scores..."):
                result = client.trigger_scoring(states_tag, pharmacy_tag)
                if 'error' in result:
                    st.error(f"Scoring failed: {result['error']}")
                    return False
                else:
                    st.success(f"✅ Computed {result.get('scores_computed', 0)} scores")
        
        # Get comprehensive results
        results = client.get_comprehensive_results(states_tag, pharmacy_tag, validated_tag or "")
        
        if isinstance(results, dict) and 'error' in results:
            st.error(f"Failed to load data: {results['error']}")
            return False
        
        # Store in session state (compatible with existing code)
        st.session_state.comprehensive_results = pd.DataFrame(results)
        st.session_state.loaded_tags = {
            'pharmacies': pharmacy_tag,
            'states': states_tag, 
            'validated': validated_tag
        }
        
        # Update loaded_data with load time
        from datetime import datetime
        if 'loaded_data' not in st.session_state:
            st.session_state.loaded_data = {}
        st.session_state.loaded_data['last_load_time'] = datetime.now()
        
        # Run validation checks
        validation_warnings = validate_comprehensive_results(results, states_tag, pharmacy_tag)
        if validation_warnings:
            st.warning("⚠️ **Data Quality Issues Detected:**")
            for warning in validation_warnings:
                st.warning(f"• {warning}")
        
        return True
        
    except Exception as e:
        st.error(f"Error loading dataset combination: {e}")
        return False

def get_comprehensive_results() -> pd.DataFrame:
    """Get comprehensive results from session state"""
    return st.session_state.get('comprehensive_results', pd.DataFrame())

def is_data_loaded() -> bool:
    """Check if data is loaded in session state"""
    return 'comprehensive_results' in st.session_state and not st.session_state.comprehensive_results.empty

def get_loaded_tags() -> Dict[str, str]:
    """Get currently loaded dataset tags"""
    return st.session_state.get('loaded_tags', {})

def clear_loaded_data():
    """Clear loaded data from session state"""
    if 'comprehensive_results' in st.session_state:
        del st.session_state.comprehensive_results
    if 'loaded_tags' in st.session_state:
        del st.session_state.loaded_tags

# Legacy compatibility wrapper (temporary)
def get_database_manager():
    """Temporary wrapper for legacy code - returns a mock object"""
    class MockDB:
        def get_backend_info(self):
            client = get_client()
            backend_name = client.get_active_backend()
            api_url = client.get_active_api_url()
            return {
                'type': 'api',  # Always API mode in this app
                'active_backend': backend_name,
                'api_url': api_url,
                'fallback_available': False  # No fallback in new system
            }
        
        def get_dataset_stats(self, kind: str, tag: str) -> Dict:
            # Delegate to the updated function
            return get_dataset_stats(kind, tag)
        
        def get_loaded_states(self, states_tag: str) -> List[str]:
            # Get unique states that actually have search results data
            if 'comprehensive_results' in st.session_state and not st.session_state.comprehensive_results.empty:
                df = st.session_state.comprehensive_results
                if 'search_state' in df.columns and 'result_id' in df.columns:
                    # Only return states that have actual search result data
                    states_with_data = df[df['result_id'].notna()]['search_state'].dropna().unique()
                    return sorted(states_with_data.tolist())
            return []
        
        def filter_for_detail(self, df, pharmacy_name: str, search_state: str):
            # Filter comprehensive results for a specific pharmacy-state combination
            return df[
                (df['pharmacy_name'] == pharmacy_name) & 
                (df['search_state'] == search_state)
            ].copy()
        
        def aggregate_for_matrix(self, df):
            # Client-side aggregation with proper record counting and best record selection
            if df.empty:
                return df
            
            # Group by pharmacy-state combination and select best record for each
            grouped_results = []
            
            for (pharmacy_name, state), group in df.groupby(['pharmacy_name', 'search_state']):
                # PRIORITY ORDER: Validated > Best Score > First Record
                validated_row = None
                
                # Import here to avoid circular imports
                try:
                    from utils.validation_local import is_validated_simple
                    
                    # 1. Look for validated record first (HIGHEST PRIORITY)
                    for idx, row in group.iterrows():
                        if is_validated_simple(row):
                            validated_row = row
                            break  # Found validated record - use this one
                except ImportError:
                    # If validation module not available, skip validation check
                    pass
                
                # 2. Fall back to best score or first record
                if validated_row is not None:
                    best_row = validated_row
                else:
                    # Get best score or first record
                    if 'score_overall' in group.columns:
                        # Filter to records that actually have scores (not NaN)
                        records_with_scores = group[group['score_overall'].notna()]
                        if not records_with_scores.empty:
                            # Pick the record with the highest score
                            best_row = records_with_scores.loc[records_with_scores['score_overall'].idxmax()]
                        else:
                            # No scores available, fall back to first record
                            best_row = group.iloc[0]
                    else:
                        best_row = group.iloc[0]
                
                # Add record count - count non-null result_ids in the group
                record_count = group['result_id'].notna().sum()
                # For combinations with no search results, set count to 1 (the pharmacy record itself)
                record_count = max(1, record_count)
                
                # Create result row with record count
                result_row = best_row.copy()
                result_row['record_count'] = record_count
                grouped_results.append(result_row)
            
            # Convert back to DataFrame
            if grouped_results:
                import pandas as pd
                result = pd.DataFrame(grouped_results)
                return result
            else:
                return df
    
    return MockDB()

# UI Components
def render_sidebar():
    """Render the navigation sidebar"""
    st.sidebar.title("PharmChecker")
    st.sidebar.caption("v1.2 - Session Management")
    
    # Navigation at top
    pages = [
        "Dataset Manager",
        "Results Matrix"
    ]
    
    selected_page = st.sidebar.selectbox(
        "Navigate to:",
        pages,
        index=pages.index(st.session_state.current_page)
    )
    
    if selected_page != st.session_state.current_page:
        st.session_state.current_page = selected_page
        st.rerun()
    
    st.sidebar.markdown("---")
    
    # Current Context with pretty boxes
    st.sidebar.subheader("Current Context")
    datasets = st.session_state.selected_datasets
    db = get_database_manager()
    
    # Pharmacies box
    if datasets.get('pharmacies'):
        stats = db.get_dataset_stats('pharmacies', datasets['pharmacies'])
        record_count = stats.get('record_count', 0)
        st.sidebar.success(f"**Pharmacies:**\n{datasets['pharmacies']} ({record_count} records)")
    else:
        st.sidebar.info("**Pharmacies:**\nNot selected")
    
    # States box
    if datasets.get('states'):
        stats = db.get_dataset_stats('states', datasets['states'])
        record_count = stats.get('record_count', 0)
        st.sidebar.success(f"**States:**\n{datasets['states']} ({record_count} records)")
    else:
        st.sidebar.info("**States:**\nNot selected")
    
    # Validated box with padlock and status
    if datasets.get('validated'):
        stats = db.get_dataset_stats('validated', datasets['validated'])
        record_count = stats.get('record_count', 0)
        
        # Get validation lock state and all valid status
        validation_locked = st.session_state.get('validation_system_locked', True)
        lock_icon = "🔒" if validation_locked else "🔓"
        
        # Check if all validations are valid (you could add logic here to check warnings)
        all_valid_icon = "✅"  # This could be dynamic based on validation warnings
        
        st.sidebar.success(f"**Validated:** {lock_icon} {all_valid_icon}\n{datasets['validated']} ({record_count} records)")
    else:
        st.sidebar.info("**Validated:**\nNot selected")
    
    
    # Validation controls (inline with validated box above)
    if datasets.get('validated') or st.session_state.current_page == 'Results Matrix':
        # Initialize validation lock state
        if 'validation_system_locked' not in st.session_state:
            st.session_state.validation_system_locked = True
        
        # Toggle lock state with toggle switch
        lock_state = st.sidebar.toggle(
            "🔓 Validation Unlocked" if not st.session_state.validation_system_locked else "🔒 Validation Locked",
            value=not st.session_state.validation_system_locked,
            key="validation_system_toggle",
            help="Toggle validation system lock/unlock"
        )
        st.session_state.validation_system_locked = not lock_state
    
    st.sidebar.markdown("---")
    
    # Quick actions
    st.sidebar.subheader("Quick Actions")
    if st.sidebar.button("🔄 Reload Data", help="Reload data from database and clear cache"):
        clear_loaded_data()
        st.cache_data.clear()
        st.rerun()
    
    if st.sidebar.button("Clear Session", help="Clears datasets from GUI and session history"):
        from utils.session import clear_all_session_data
        clear_all_session_data()
        st.cache_data.clear()
        st.session_state.current_page = 'Dataset Manager'
        # Reset selected datasets in GUI to match cleared session
        st.session_state.selected_datasets = {
            'pharmacies': None,
            'states': None,
            'validated': None
        }
        st.sidebar.success("Session cleared!")
        st.rerun()
    
    # Debug mode controls
    debug_mode = st.sidebar.checkbox("Debug Mode", False, help="Show technical fields and validation debugging")
    st.session_state.debug_mode = debug_mode
    
    if debug_mode:
        user_context = st.session_state.get('user_context', {})
        st.sidebar.text("Session Storage:")
        if user_context.get('authenticated'):
            st.sidebar.success("✅ Database storage enabled")
        else:
            st.sidebar.warning("⚠️ No persistence (not authenticated)")
    
    # Database Connection Info
    st.sidebar.markdown("---")
    st.sidebar.subheader("Database Connection")
    
    try:
        # Get backend information from database manager
        if hasattr(db, 'get_backend_info'):
            backend_info = db.get_backend_info()
            backend_type = backend_info.get('type', 'unknown')
            
            if backend_type == 'api':
                # API mode
                active_backend = backend_info.get('active_backend', 'Unknown')
                api_url = backend_info.get('api_url', 'Unknown')
                
                if 'supabase' in active_backend.lower():
                    st.sidebar.success(f"🌐 **{active_backend}**")
                    st.sidebar.caption(f"Cloud API: {api_url.split('//')[1].split('.')[0] if '//' in api_url else api_url}")
                else:
                    st.sidebar.success(f"🔗 **{active_backend}**")
                    st.sidebar.caption(f"Local API: {api_url}")
                
                # No fallback in new system
                st.sidebar.caption("⚠️ No fallback - fails hard if connection lost")
                    
            else:
                # Direct database mode
                from config import get_db_config
                db_config = get_db_config()
                st.sidebar.success("🔗 **Direct Database**")
                st.sidebar.caption(f"PostgreSQL: {db_config['host']}:{db_config['port']}")
                st.sidebar.caption(f"Database: {db_config['database']}")
        else:
            # Legacy database manager without backend info
            from config import get_db_config
            db_config = get_db_config()
            st.sidebar.info("🔗 **Direct Database** (Legacy)")
            st.sidebar.caption(f"PostgreSQL: {db_config['host']}:{db_config['port']}")
            
    except Exception as e:
        st.sidebar.error("❌ **Connection Error**")
        st.sidebar.caption(f"Error: {str(e)[:50]}")
        
    # No dark mode toggle needed - keeping default Streamlit theme
    
    # User context display at bottom
    user_context = st.session_state.get('user_context', {})
    if user_context.get('authenticated'):
        st.sidebar.success(f"👤 **{user_context['email']}** ({user_context['role']})")
        st.sidebar.caption(f"Auth: {user_context['auth_mode']}")
    else:
        st.sidebar.error("❌ Not authenticated")

def render_dataset_manager():
    """Enhanced dataset management interface with full CRUD operations"""
    st.header("📊 Dataset Manager")
    
    # 1. Dataset Selection and Load (Top Section)
    st.subheader("🎯 Dataset Selection")
    available_datasets = get_available_datasets()
    current_selection = st.session_state.selected_datasets
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Pharmacies**")
        pharmacy_options = available_datasets.get('pharmacies', [])
        pharmacy_default = current_selection.get('pharmacies', 'None')
        if pharmacy_default not in ['None'] + pharmacy_options:
            pharmacy_default = 'None'
        selected_pharmacy_tag = st.selectbox(
            "Select pharmacy dataset:",
            ['None'] + pharmacy_options,
            index=(['None'] + pharmacy_options).index(pharmacy_default),
            key="top_pharmacy_select"
        )
        if selected_pharmacy_tag != 'None':
            stats = get_dataset_stats('pharmacies', selected_pharmacy_tag)
            st.info(f"📊 {stats['record_count']} records")
    
    with col2:
        st.markdown("**States**")
        states_options = available_datasets.get('states', [])
        states_default = current_selection.get('states', 'None')
        if states_default not in ['None'] + states_options:
            states_default = 'None'
        selected_states_tag = st.selectbox(
            "Select states dataset:",
            ['None'] + states_options,
            index=(['None'] + states_options).index(states_default),
            key="top_states_select"
        )
        if selected_states_tag != 'None':
            stats = get_dataset_stats('states', selected_states_tag)
            st.info(f"📊 {stats['record_count']} records")
    
    with col3:
        st.markdown("**Validated**")
        validated_options = available_datasets.get('validated', [])
        validated_default = current_selection.get('validated') or 'None'
        if validated_default not in ['None'] + validated_options:
            validated_default = 'None'
        selected_validated_tag = st.selectbox(
            "Select validated dataset:",
            ['None'] + validated_options,
            index=(['None'] + validated_options).index(validated_default),
            key="top_validated_select"
        )
        if selected_validated_tag != 'None':
            stats = get_dataset_stats('validated', selected_validated_tag)
            st.info(f"📊 {stats['record_count']} records")
    
    # Update session state with top selector values
    new_selection = {
        'pharmacies': selected_pharmacy_tag if selected_pharmacy_tag != 'None' else None,
        'states': selected_states_tag if selected_states_tag != 'None' else None,
        'validated': selected_validated_tag if selected_validated_tag != 'None' else None
    }
    
    # Only update if changed to avoid infinite reruns
    if new_selection != st.session_state.selected_datasets:
        st.session_state.selected_datasets = new_selection
        save_dataset_selection(new_selection)
    
    # Load Data functionality (in the top section)
    load_enabled = (selected_pharmacy_tag != 'None' and selected_states_tag != 'None')
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔄 Load Data", type="primary", disabled=not load_enabled, 
                    help="Load selected datasets into memory for analysis"):
            if load_enabled:
                validated_tag = selected_validated_tag if selected_validated_tag != 'None' else None
                success = load_dataset_combination(selected_pharmacy_tag, selected_states_tag, validated_tag)
                
                if success:
                    st.session_state.validation_load_attempted = False
                    st.session_state.current_page = 'Results Matrix'
                    st.rerun()
            else:
                st.error("Please select both Pharmacies and States datasets")
    
    # Show current loaded data status
    if is_data_loaded():
        loaded_tags = get_loaded_tags()
        last_load_time = st.session_state.loaded_data.get('last_load_time')
        
        st.success("✅ **Data Loaded**")
        st.info(f"""
        **Loaded Dataset Combination:**
        - **Pharmacies:** {loaded_tags['pharmacies']}
        - **States:** {loaded_tags['states']}  
        - **Validated:** {loaded_tags['validated'] or 'None'}
        - **Loaded:** {last_load_time.strftime('%Y-%m-%d %H:%M:%S') if last_load_time else 'Unknown'}
        """)
            
    else:
        st.warning("⚠️ **No Data Loaded**")
        st.markdown("Select dataset combination and load data to begin analysis.")
    
    st.markdown("---")
    
    # 2. Dataset Management Section
    st.subheader("🛠️ Dataset Management")
    
    # Simplified tabs for Export/Import/Manage
    tab1, tab2, tab3 = st.tabs(["📤 Export CSV", "📥 Import CSV", "🔍 Manage"])
    
    with tab1:
        render_simple_export_csv()
    
    with tab2:
        render_simple_import_csv()
    
    with tab3:
        render_api_poc_dataset_explorer()


def render_simple_export_csv():
    """Simple CSV export for all dataset types"""
    st.markdown("**📤 Export Datasets to CSV**")
    st.caption("Direct database dumps to CSV format")
    
    available_datasets = get_available_datasets()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Export Pharmacies**")
        pharmacy_options = available_datasets.get('pharmacies', [])
        if pharmacy_options:
            export_pharmacy = st.selectbox(
                "Select dataset:",
                ['Select...'] + pharmacy_options,
                key="simple_export_pharmacy"
            )
            
            if export_pharmacy != 'Select...':
                stats = get_dataset_stats('pharmacies', export_pharmacy)
                st.info(f"📊 {stats['record_count']} records")
                
                if st.button("💾 Export CSV", key="simple_export_pharmacy_btn"):
                    try:
                        client = get_client()
                        datasets = client.get_datasets()
                        dataset_id = None
                        for d in datasets:
                            if d.get('kind') == 'pharmacies' and d.get('tag') == export_pharmacy:
                                dataset_id = d.get('id')
                                break
                        
                        if dataset_id:
                            data = client.get_pharmacies(dataset_id=dataset_id, limit=9999)
                            if data:
                                df = pd.DataFrame(data)
                                
                                # Export only the essential fields (exclude database internals)
                                essential_cols = ['name', 'alias', 'address', 'suite', 'city', 'state', 'zip', 'state_licenses']
                                export_cols = [col for col in essential_cols if col in df.columns]
                                
                                export_df = df[export_cols].copy()
                                
                                # Clean up complex fields that may cause import issues
                                if 'state_licenses' in export_df.columns:
                                    # Convert state_licenses to string format (avoid pandas array comparison issues)
                                    cleaned_licenses = []
                                    for idx, val in export_df['state_licenses'].items():
                                        try:
                                            # Check for None/NaN first (without using pd.isna on potentially array-like objects)
                                            if val is None:
                                                cleaned_licenses.append('[]')
                                            elif isinstance(val, (list, tuple)):
                                                cleaned_licenses.append(str(val))
                                            elif val == '' or str(val).lower() == 'nan':
                                                cleaned_licenses.append('[]')
                                            else:
                                                cleaned_licenses.append(str(val))
                                        except Exception as e:
                                            st.write(f"Debug: Error cleaning value {val}: {e}")
                                            cleaned_licenses.append('[]')
                                    export_df['state_licenses'] = cleaned_licenses
                                    
                                # Skip additional_info for now to avoid complex JSON issues
                                # TODO: Properly serialize additional_info as valid JSON
                                csv_data = export_df.to_csv(index=False)
                                
                                st.download_button(
                                    "⬇️ Download CSV",
                                    csv_data,
                                    f"pharmacies_{export_pharmacy}.csv",
                                    "text/csv"
                                )
                                st.success(f"✅ Ready to export {len(export_df)} records with {len(export_cols)} fields")
                            else:
                                st.error("No data found")
                    except Exception as e:
                        st.error(f"Export failed: {e}")
        else:
            st.warning("No pharmacy datasets")
    
    with col2:
        st.markdown("**Export States**")
        states_options = available_datasets.get('states', [])
        if states_options:
            export_states = st.selectbox(
                "Select dataset:",
                ['Select...'] + states_options,
                key="simple_export_states"
            )
            
            if export_states != 'Select...':
                stats = get_dataset_stats('states', export_states)
                st.info(f"📊 {stats['record_count']} records")
                
                if st.button("💾 Export CSV", key="simple_export_states_btn"):
                    try:
                        client = get_client()
                        datasets = client.get_datasets()
                        dataset_id = None
                        for d in datasets:
                            if d.get('kind') == 'states' and d.get('tag') == export_states:
                                dataset_id = d.get('id')
                                break
                        
                        if dataset_id:
                            data = client.get_search_results(dataset_id=dataset_id, limit=9999)
                            if data:
                                df = pd.DataFrame(data)
                                
                                # Export only essential fields (exclude database internals)
                                exclude_cols = ['id', 'dataset_id', 'created_at']
                                export_cols = [col for col in df.columns if col not in exclude_cols]
                                
                                export_df = df[export_cols].copy()
                                csv_data = export_df.to_csv(index=False)
                                
                                st.download_button(
                                    "⬇️ Download CSV",
                                    csv_data,
                                    f"states_{export_states}.csv",
                                    "text/csv"
                                )
                                st.success(f"✅ Ready to export {len(export_df)} records with {len(export_cols)} fields")
                            else:
                                st.error("No data found")
                    except Exception as e:
                        st.error(f"Export failed: {e}")
        else:
            st.warning("No states datasets")
    
    with col3:
        st.markdown("**Export Validated**")
        validated_options = available_datasets.get('validated', [])
        if validated_options:
            export_validated = st.selectbox(
                "Select dataset:",
                ['Select...'] + validated_options,
                key="simple_export_validated"
            )
            
            if export_validated != 'Select...':
                stats = get_dataset_stats('validated', export_validated)
                st.info(f"📊 {stats['record_count']} records")
                
                if st.button("💾 Export CSV", key="simple_export_validated_btn"):
                    try:
                        client = get_client()
                        datasets = client.get_datasets()
                        dataset_id = None
                        for d in datasets:
                            if d.get('kind') == 'validated' and d.get('tag') == export_validated:
                                dataset_id = d.get('id')
                                break
                        
                        if dataset_id:
                            data = client.get_table_data('validated_overrides', 
                                                       filters={'dataset_id': f'eq.{dataset_id}'}, 
                                                       limit=9999)
                            if data:
                                df = pd.DataFrame(data)
                                
                                # Export only essential fields (exclude database internals)
                                exclude_cols = ['id', 'dataset_id', 'created_at']
                                export_cols = [col for col in df.columns if col not in exclude_cols]
                                
                                export_df = df[export_cols].copy()
                                csv_data = export_df.to_csv(index=False)
                                
                                st.download_button(
                                    "⬇️ Download CSV",
                                    csv_data,
                                    f"validated_{export_validated}.csv",
                                    "text/csv"
                                )
                                st.success(f"✅ Ready to export {len(export_df)} records with {len(export_cols)} fields")
                            else:
                                st.error("No data found")
                    except Exception as e:
                        st.error(f"Export failed: {e}")
        else:
            st.warning("No validated datasets")


def render_simple_import_csv():
    """Simple CSV import for all dataset types"""
    st.markdown("**📥 Import Datasets from CSV**")
    st.caption("Upload CSV files to create new datasets")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Import Pharmacies**")
        pharmacy_file = st.file_uploader("CSV file:", type=['csv'], key="simple_import_pharmacy_file")
        pharmacy_tag = st.text_input("Dataset tag:", placeholder="e.g., jan_2024", key="simple_import_pharmacy_tag")
        
        if pharmacy_file and pharmacy_tag:
            if st.button("📥 Import", key="simple_import_pharmacy_btn"):
                try:
                    # Debug: File info
                    st.write("**DEBUG: File Info**")
                    st.write(f"- File name: {pharmacy_file.name}")
                    st.write(f"- File size: {pharmacy_file.size} bytes")
                    st.write(f"- Target tag: {pharmacy_tag}")
                    
                    # Read and validate CSV
                    df = pd.read_csv(pharmacy_file)
                    st.write(f"**DEBUG: CSV Data**")
                    st.write(f"- Rows: {len(df)}")
                    st.write(f"- Columns: {list(df.columns)}")
                    st.write(f"- Sample data:")
                    st.dataframe(df.head(3))
                    
                    # Check required columns
                    required_cols = ['name', 'address', 'city', 'state', 'zip']
                    missing_cols = [col for col in required_cols if col not in df.columns]
                    if missing_cols:
                        st.error(f"❌ Missing required columns: {missing_cols}")
                        return
                    
                    # Use API importer via subprocess
                    import tempfile, subprocess, os
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp:
                        df.to_csv(tmp.name, index=False)
                        tmp_path = tmp.name
                    
                    st.write(f"**DEBUG: Import Process**")
                    st.write(f"- Temp file: {tmp_path}")
                    
                    client = get_client()
                    backend = client.get_active_backend().lower()
                    st.write(f"- Backend: {backend}")
                    
                    # Build command
                    cmd = [
                        'python', '-m', 'imports.api_importer', 
                        'pharmacies', tmp_path, pharmacy_tag, '--backend', backend
                    ]
                    st.write(f"- Command: {' '.join(cmd)}")
                    
                    # Run import
                    with st.spinner("Running import..."):
                        result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
                    
                    # Debug: Command results
                    st.write(f"**DEBUG: Import Results**")
                    st.write(f"- Return code: {result.returncode}")
                    st.write(f"- STDOUT: {result.stdout}")
                    st.write(f"- STDERR: {result.stderr}")
                    
                    # Clean up temp file
                    os.unlink(tmp_path)
                    
                    if result.returncode == 0:
                        st.success(f"✅ Imported {len(df)} records as '{pharmacy_tag}'")
                        st.rerun()
                    else:
                        st.error(f"❌ Import failed with code {result.returncode}")
                        st.error(f"Error details: {result.stderr}")
                        if result.stdout:
                            st.info(f"Output: {result.stdout}")
                            
                except Exception as e:
                    st.error(f"❌ Import failed with exception: {e}")
                    import traceback
                    st.code(traceback.format_exc())
    
    with col2:
        st.markdown("**Import States**")
        states_file = st.file_uploader("CSV file:", type=['csv'], key="simple_import_states_file")
        states_tag = st.text_input("Dataset tag:", placeholder="e.g., jan_2024_fl", key="simple_import_states_tag")
        
        if states_file and states_tag:
            if st.button("📥 Import", key="simple_import_states_btn"):
                try:
                    # Debug: File info
                    st.write("**DEBUG: File Info**")
                    st.write(f"- File name: {states_file.name}")
                    st.write(f"- File size: {states_file.size} bytes")
                    st.write(f"- Target tag: {states_tag}")
                    
                    # Read and validate CSV
                    df = pd.read_csv(states_file)
                    st.write(f"**DEBUG: CSV Data**")
                    st.write(f"- Rows: {len(df)}")
                    st.write(f"- Columns: {list(df.columns)}")
                    st.write(f"- Sample data:")
                    st.dataframe(df.head(3))
                    
                    # Check required columns for states
                    required_cols = ['search_name', 'search_state']
                    missing_cols = [col for col in required_cols if col not in df.columns]
                    if missing_cols:
                        st.error(f"❌ Missing required columns: {missing_cols}")
                        return
                    
                    # Use API importer via subprocess
                    import tempfile, subprocess, os
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp:
                        df.to_csv(tmp.name, index=False)
                        tmp_path = tmp.name
                    
                    st.write(f"**DEBUG: Import Process**")
                    st.write(f"- Temp file: {tmp_path}")
                    
                    client = get_client()
                    backend = client.get_active_backend().lower()
                    st.write(f"- Backend: {backend}")
                    
                    # Build command
                    cmd = [
                        'python', '-m', 'imports.api_importer', 
                        'states', tmp_path, states_tag, '--backend', backend
                    ]
                    st.write(f"- Command: {' '.join(cmd)}")
                    
                    # Run import
                    with st.spinner("Running import..."):
                        result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
                    
                    # Debug: Command results
                    st.write(f"**DEBUG: Import Results**")
                    st.write(f"- Return code: {result.returncode}")
                    st.write(f"- STDOUT: {result.stdout}")
                    st.write(f"- STDERR: {result.stderr}")
                    
                    # Clean up temp file
                    os.unlink(tmp_path)
                    
                    if result.returncode == 0:
                        st.success(f"✅ Imported {len(df)} records as '{states_tag}'")
                        st.rerun()
                    else:
                        st.error(f"❌ Import failed with code {result.returncode}")
                        st.error(f"Error details: {result.stderr}")
                        if result.stdout:
                            st.info(f"Output: {result.stdout}")
                            
                except Exception as e:
                    st.error(f"❌ Import failed with exception: {e}")
                    import traceback
                    st.code(traceback.format_exc())
    
    with col3:
        st.markdown("**Import Validated**")
        validated_file = st.file_uploader("CSV file:", type=['csv'], key="simple_import_validated_file")
        validated_tag = st.text_input("Dataset tag:", placeholder="e.g., jan_2024_val", key="simple_import_validated_tag")
        
        if validated_file and validated_tag:
            if st.button("📥 Import", key="simple_import_validated_btn"):
                try:
                    df = pd.read_csv(validated_file)
                    st.info(f"Found {len(df)} records")
                    
                    import tempfile, subprocess, os
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp:
                        df.to_csv(tmp.name, index=False)
                        tmp_path = tmp.name
                    
                    client = get_client()
                    backend = client.get_active_backend().lower()
                    
                    result = subprocess.run([
                        'python', '-m', 'imports.api_importer', 
                        'validated', tmp_path, validated_tag, '--backend', backend
                    ], capture_output=True, text=True)
                    
                    os.unlink(tmp_path)
                    
                    if result.returncode == 0:
                        st.success(f"✅ Imported {len(df)} records as '{validated_tag}'")
                        st.rerun()
                    else:
                        st.error(f"Import failed: {result.stderr}")
                except Exception as e:
                    st.error(f"Import failed: {e}")


def render_api_poc_dataset_explorer():
    """Dataset Explorer from API POC - Browse and preview datasets"""
    st.subheader("🔍 Dataset Explorer & Management")
    st.caption("Browse datasets and preview data")
    
    try:
        client = get_client()
        
        # Get all datasets
        datasets = client.get_datasets()
        
        if not datasets:
            st.warning("No datasets found in the database.")
            return
        
        df = pd.DataFrame(datasets)
        
        # Display datasets table
        st.markdown("**Available Datasets**")
        st.dataframe(df, use_container_width=True)
        
        # Dataset selector
        st.markdown("---")
        st.markdown("**Explore Dataset**")
        col1, col2 = st.columns(2)
        
        with col1:
            dataset_options = [f"{row['tag']} ({row['kind']})" for _, row in df.iterrows()]
            selected_dataset = st.selectbox("Select Dataset", dataset_options, key="explore_dataset_select")
        
        with col2:
            preview_limit = st.number_input("Preview Limit", min_value=10, max_value=1000, value=50, key="explore_preview_limit")
        
        if selected_dataset:
            # Parse selection
            selected_row = df[df.apply(lambda x: f"{x['tag']} ({x['kind']})" == selected_dataset, axis=1)].iloc[0]
            dataset_id = selected_row['id']
            dataset_kind = selected_row['kind']
            
            st.subheader(f"Dataset Details: {selected_row['tag']}")
            
            # Get record count for this dataset
            dataset_stats = get_dataset_stats(dataset_kind, selected_row['tag'])
            record_count = dataset_stats.get('record_count', 0)
            
            # Show dataset metadata
            metadata_cols = st.columns(4)
            with metadata_cols[0]:
                st.metric("Kind", dataset_kind)
            with metadata_cols[1]:
                st.metric("Records", record_count)
            with metadata_cols[2]:
                st.metric("Created By", selected_row.get('created_by', 'Unknown'))
            with metadata_cols[3]:
                st.metric("Created", pd.to_datetime(selected_row['created_at']).strftime('%Y-%m-%d'))
            
            if selected_row.get('description'):
                st.info(f"**Description:** {selected_row['description']}")
            
            # Show data preview based on kind
            if dataset_kind == 'pharmacies':
                st.subheader("Pharmacy Data Preview")
                pharmacies = client.get_pharmacies(dataset_id=dataset_id, limit=preview_limit)
                if pharmacies:
                    pharmacy_df = pd.DataFrame(pharmacies)
                    st.dataframe(pharmacy_df, use_container_width=True)
                    st.caption(f"Showing {len(pharmacies)} records")
                    
                    # Export options
                    csv_data = pharmacy_df.to_csv(index=False)
                    st.download_button(
                        label="⬇️ Export Pharmacies CSV",
                        data=csv_data,
                        file_name=f"pharmacies_{selected_row['tag']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        key="export_explore_pharmacies"
                    )
                else:
                    st.warning("No pharmacy data found for this dataset.")
            
            elif dataset_kind == 'states':
                st.subheader("Search Results Preview")
                results = client.get_search_results(dataset_id=dataset_id, limit=preview_limit)
                if results:
                    results_df = pd.DataFrame(results)
                    st.dataframe(results_df, use_container_width=True)
                    st.caption(f"Showing {len(results)} records")
                    
                    # Export options
                    csv_data = results_df.to_csv(index=False)
                    st.download_button(
                        label="⬇️ Export States CSV",
                        data=csv_data,
                        file_name=f"states_{selected_row['tag']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        key="export_explore_states"
                    )
                else:
                    st.warning("No search results found for this dataset.")
            
            elif dataset_kind == 'validated':
                st.subheader("Validated Overrides Preview")
                data = client.get_table_data('validated_overrides', 
                                           filters={'dataset_id': f'eq.{dataset_id}'}, 
                                           limit=preview_limit)
                if data:
                    data_df = pd.DataFrame(data)
                    st.dataframe(data_df, use_container_width=True)
                    st.caption(f"Showing {len(data)} records")
                    
                    # Export options
                    csv_data = data_df.to_csv(index=False)
                    st.download_button(
                        label="⬇️ Export Validated CSV",
                        data=csv_data,
                        file_name=f"validated_{selected_row['tag']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        key="export_explore_validated"
                    )
                else:
                    st.warning("No validated overrides found for this dataset.")
            
            # Dataset Management (Rename and Delete)
            st.markdown("---")
            st.subheader("Dataset Management")
            st.warning("⚠️ **Use with caution!** These operations cannot be undone.")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Rename Dataset**")
                new_tag = st.text_input(
                    "New Tag Name", 
                    value=selected_row['tag'],
                    help="Enter a new tag name for this dataset",
                    key="explore_rename_input"
                )
                
                if st.button(f"🏷️ Rename to '{new_tag}'", disabled=(new_tag == selected_row['tag'] or not new_tag), key="explore_rename_btn"):
                    if st.session_state.get('explore_confirm_rename') != dataset_id:
                        st.session_state.explore_confirm_rename = dataset_id
                        st.warning("Click again to confirm rename operation")
                    else:
                        with st.spinner("Renaming dataset..."):
                            try:
                                # Use the update method from manage datasets
                                update_data = {'tag': new_tag}
                                result = client.update_table_record('datasets', dataset_id, update_data)
                                
                                if 'error' not in result:
                                    st.success(f"✅ Renamed '{selected_row['tag']}' to '{new_tag}'")
                                    st.session_state.explore_confirm_rename = None
                                    st.rerun()
                                else:
                                    st.error(f"Rename failed: {result['error']}")
                            except Exception as e:
                                st.error(f"Rename failed: {e}")
            
            with col2:
                st.write("**Delete Dataset**")
                st.error("This will permanently delete ALL data associated with this dataset!")
                
                if st.button(f"🗑️ Delete '{selected_row['tag']}'", key="explore_delete_btn"):
                    if st.session_state.get('explore_confirm_delete') != dataset_id:
                        st.session_state.explore_confirm_delete = dataset_id
                        st.error("⚠️ Click again to PERMANENTLY delete this dataset and ALL its data!")
                    else:
                        with st.spinner("Deleting dataset..."):
                            try:
                                # Use the delete method from manage datasets
                                result = client.delete_table_record('datasets', dataset_id)
                                
                                if 'error' not in result:
                                    st.success(f"✅ Deleted dataset '{selected_row['tag']}'")
                                    st.info("📝 **Note:** Related data records may still exist. Use database cleanup if needed.")
                                    st.session_state.explore_confirm_delete = None
                                    st.rerun()
                                else:
                                    st.error(f"Delete failed: {result['error']}")
                            except Exception as e:
                                st.error(f"Delete failed: {e}")
    
    except Exception as e:
        st.error(f"Error loading datasets: {e}")


def render_results_matrix():
    """Main results matrix view using loaded data"""
    st.markdown("### Results Matrix")
    
    # Check if data is loaded
    if not is_data_loaded():
        st.warning("⚠️ No data loaded. Please go to Dataset Manager to load data first.")
        if st.button("Go to Dataset Manager"):
            st.session_state.current_page = 'Dataset Manager'
            st.rerun()
        return
    
    # Get loaded data
    comprehensive_results = get_comprehensive_results()
    loaded_tags = get_loaded_tags()
    
    # Ensure validation data is loaded if validation dataset is selected
    if (loaded_tags and loaded_tags.get('validated') and 
        comprehensive_results is not None and 
        len(comprehensive_results[comprehensive_results['override_type'].notna()]) == 0):
        
        # load_dataset_combination now defined locally above
        success = load_dataset_combination(
            loaded_tags['pharmacies'],
            loaded_tags['states'], 
            loaded_tags['validated']
        )
        if success:
            comprehensive_results = get_comprehensive_results()
    
    # Display current context with validation count from comprehensive results
    validation_count = len(comprehensive_results[comprehensive_results['override_type'].notna()]) if comprehensive_results is not None else 0
    
    # Log validation data status
    if comprehensive_results is not None and 'override_type' in comprehensive_results.columns:
        validation_count = len(comprehensive_results[comprehensive_results['override_type'].notna()])
        if validation_count > 0:
            logger.info(f"Loaded {validation_count} validation records in Results Matrix")
    
    # Check for validation warnings and incorporate into the info box
    warning_status = ""
    validation_warnings = []
    
    if validation_count > 0:
        # Get comprehensive results for warning analysis
        comprehensive_results = get_comprehensive_results()
        db = get_database_manager()
        warning_check_df = db.aggregate_for_matrix(comprehensive_results)
        
        # Find records with warnings (only if warnings column exists)
        if 'warnings' in warning_check_df.columns:
            warning_records = warning_check_df[
                warning_check_df['warnings'].notna() & 
                (warning_check_df['warnings'].astype(str) != '') & 
                (warning_check_df['warnings'].astype(str) != '[]')
            ]
        else:
            warning_records = pd.DataFrame()  # Empty if no warnings column
        
        if len(warning_records) > 0:
            warning_status = f" | ⚠️ **{len(warning_records)} Warnings**"
            
            # Collect detailed warning information
            for _, record in warning_records.iterrows():
                pharmacy_name = record['pharmacy_name']
                search_state = record['search_state']
                license_number = record.get('license_number', 'N/A')
                warnings_list = record['warnings']
                
                # Get detailed field differences for this record
                detailed_warning = get_detailed_validation_warning(
                    pharmacy_name, search_state, license_number, 
                    comprehensive_results
                )
                validation_warnings.append(detailed_warning)
        else:
            warning_status = " | ✅ **All Valid**"
    
    # Get record counts for each dataset
    db = get_database_manager()
    pharmacy_stats = db.get_dataset_stats('pharmacies', loaded_tags['pharmacies'])
    states_stats = db.get_dataset_stats('states', loaded_tags['states'])
    validated_stats = None
    if loaded_tags['validated']:
        validated_stats = db.get_dataset_stats('validated', loaded_tags['validated'])
    
    # Simple header - just Results Matrix
    # Show loaded states
    loaded_states = db.get_loaded_states(loaded_tags['states'])
    if loaded_states:
        states_str = ", ".join(sorted(loaded_states))
        st.caption(f"🗺️ **Loaded States:** {states_str}")
    
    # Show validation warnings as expandable yellow warnings inside the info context
    if validation_warnings:
        for warning_detail in validation_warnings:
            st.warning(f"⚠️ **{warning_detail['pharmacy']} ({warning_detail['state']})** - Validation data changed")
            
            with st.expander(f"📋 Show details for {warning_detail['pharmacy']} {warning_detail['state']} {warning_detail['license']}", expanded=False):
                st.write("**Field Changes Detected:**")
                
                for field_change in warning_detail['changes']:
                    st.write(f"**{field_change['field'].title()}:**")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"🕒 **Validated:** `{field_change['validated']}`")
                    with col2:
                        st.write(f"🔍 **Current:** `{field_change['current']}`")
                
                st.write("**Action Required:** Review current search results and update validation if changes are correct, or investigate if data changed unexpectedly.")
    
    # Skip the word 'Filters' - go straight to filter controls
    
    # Get debug mode from sidebar (will be set there)
    debug_mode = st.session_state.get('debug_mode', False)
    
    # No additional filter options needed - keeping it simple
    
    # Apply filtering - always filter to loaded states (states with actual search data)
    full_results_df = comprehensive_results.copy()
    
    # Always filter to states that have actual search data
    states_with_data = full_results_df[full_results_df['result_id'].notna()]['search_state'].unique()
    full_results_df = full_results_df[full_results_df['search_state'].isin(states_with_data)]
    
    if full_results_df.empty:
        st.warning("No results found matching the current filters")
        return
    
    # Check validation data before aggregation
    validation_before = full_results_df[full_results_df['override_type'].notna()] if 'override_type' in full_results_df.columns else pd.DataFrame()
    if len(validation_before) > 0:
        logger.debug(f"Found {len(validation_before)} validation records before aggregation")
    
    # Aggregate for matrix display using local database manager
    db = get_database_manager()
    with st.spinner("Aggregating results for matrix view..."):
        results_df = db.aggregate_for_matrix(full_results_df)
        
    # Check validation data after aggregation
    validation_after = results_df[results_df['override_type'].notna()] if 'override_type' in results_df.columns else pd.DataFrame()
    if len(validation_after) > 0:
        logger.debug(f"Found {len(validation_after)} validation records after aggregation")
    
    if results_df.empty:
        st.warning("No aggregated results found")
        return
    
    # Update status buckets using simple validation check
    # Simple status calculation (replacing calculate_status_simple)
    def calculate_status_simple(row):
        if pd.isna(row.get('result_id')):
            return 'no data'
        elif pd.notna(row.get('override_type')):
            return 'validated'  
        elif pd.notna(row.get('score_overall')):
            score = float(row['score_overall'])
            if score >= 85:
                return 'match'
            elif score >= 60:
                return 'weak match'  # Fixed: use space not underscore
            else:
                return 'no match'
        else:
            return 'no data'  # Fixed: use consistent naming
    
    results_df['status_bucket'] = results_df.apply(calculate_status_simple, axis=1)
    
    # Log status results for validation records
    if 'override_type' in results_df.columns:
        validated_status = results_df[results_df['override_type'].notna()]
        if len(validated_status) > 0:
            logger.debug(f"Applied status calculation to {len(validated_status)} validated records")
    
    # Keep all records including validated ones
    
    # Get available states and statuses for filters
    available_states = sorted(results_df['search_state'].dropna().unique().tolist())
    available_statuses = sorted(results_df['status_bucket'].dropna().unique().tolist())
    
    # Single line filters with inline labels
    col1, col2, col3 = st.columns([2, 2, 3])
    
    with col1:
        state_options = ['All'] + available_states
        selected_states = st.multiselect("State:", state_options, default=['All'])
        if 'All' in selected_states:
            state_filter = available_states
        else:
            state_filter = [s for s in selected_states if s != 'All']
    
    with col2:
        status_options = ['All'] + available_statuses
        selected_statuses = st.multiselect("Status:", status_options, default=['All'])
        if 'All' in selected_statuses:
            status_filter = available_statuses
        else:
            status_filter = [s for s in selected_statuses if s != 'All']
            
    with col3:
        score_range = st.slider("Score Range:", 0.0, 100.0, (0.0, 100.0))
        st.caption(f"{score_range[0]:.0f} - {score_range[1]:.0f}")
    
    # No additional filters needed
    
    # Apply filters
    filtered_data = results_df.copy()
    
    if state_filter:
        filtered_data = filtered_data[filtered_data['search_state'].isin(state_filter)]
    
    if status_filter:
        filtered_data = filtered_data[filtered_data['status_bucket'].isin(status_filter)]
    
    if score_range != (0.0, 100.0):
        score_mask = (
            (filtered_data['score_overall'].isna()) |
            (filtered_data['score_overall'].between(score_range[0], score_range[1]))
        )
        filtered_data = filtered_data[score_mask]
    
    # No warning filtering applied
    
    # Collapsible summary statistics with validated count
    total_checked = len(results_df)
    matches_validated = len(filtered_data[filtered_data['status_bucket'] == 'match'])
    weak_matches = len(filtered_data[filtered_data['status_bucket'] == 'weak match'])
    no_matches_validated = len(filtered_data[filtered_data['status_bucket'] == 'no match'])
    validated_present = len(filtered_data[filtered_data['status_bucket'] == 'validated present'])
    validated_empty = len(filtered_data[filtered_data['status_bucket'] == 'validated empty'])
    total_validated = validated_present + validated_empty
    not_found = len(filtered_data[(filtered_data['status_bucket'] == 'no data') & filtered_data['result_id'].notna()])
    no_data = len(filtered_data[(filtered_data['status_bucket'] == 'no data') & filtered_data['result_id'].isna()])
    
    with st.expander(f"📊 Summary: {total_checked} total | {matches_validated} matches | {weak_matches} weak | {no_matches_validated} no match | {total_validated} validated | {not_found} not found | {no_data} no data", expanded=False):
        col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
        with col1:
            st.metric("Total", total_checked)
        with col2:
            st.metric("Matches", matches_validated)
        with col3:
            st.metric("Weak", weak_matches)
        with col4:
            st.metric("No Match", no_matches_validated)
        with col5:
            st.metric("Validated", total_validated)
        with col6:
            st.metric("Not Found", not_found)
        with col7:
            st.metric("No Data", no_data)
    
    # Display results table with maximum space
    st.markdown("**Results**")
    selected_row = display_dense_results_table(filtered_data, debug_mode)
    
    # Display detailed view below table if a row is selected
    if selected_row is not None:
        st.subheader("Detailed View")
        # Get detail data from comprehensive results
        detail_results = db.filter_for_detail(full_results_df, selected_row['pharmacy_name'], selected_row['search_state'])
        display_row_detail_section(selected_row, st.session_state.selected_datasets, debug_mode, detail_results)
    
    # Export functionality
    st.subheader("Export")
    create_export_button(filtered_data, "results_matrix")


# Main application
def main():
    """Main application entry point"""
    initialize_session_state()
    
    # Render sidebar
    render_sidebar()
    
    # Render main content based on current page
    current_page = st.session_state.current_page
    
    if current_page == "Dataset Manager":
        render_dataset_manager()
    elif current_page == "Results Matrix":
        render_results_matrix()
    
    # Footer
    st.markdown("---")
    st.markdown("*PharmChecker MVP GUI - Built with Streamlit*")


if __name__ == "__main__":
    main()
