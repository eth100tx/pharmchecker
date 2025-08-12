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

# Configure logger
logger = logging.getLogger(__name__)

# Import utility modules
from utils.database import get_database_manager, query_with_cache
from utils.display import (
    display_dataset_summary, display_results_table, display_metrics_row,
    create_status_distribution_chart, create_score_histogram,
    create_export_button, format_status_badge, display_pharmacy_card,
    display_search_result_card, display_dense_results_table,
    display_row_detail_section
)
from utils.validation_local import (
    load_dataset_combination, is_data_loaded, get_loaded_tags,
    get_comprehensive_results, clear_loaded_data
)
from utils.auth import get_auth_manager, get_user_context, require_auth
from utils.session import auto_restore_dataset_selection, save_dataset_selection
from imports.validated import ValidatedImporter

# Page configuration
st.set_page_config(
    page_title="PharmChecker",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
            from utils.validation_local import load_dataset_combination
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
    db = get_database_manager()
    return db.get_datasets()

def get_dataset_stats(kind: str, tag: str) -> Dict:
    """Get statistics for a specific dataset"""
    db = get_database_manager()
    return db.get_dataset_stats(kind, tag)

# UI Components
def render_sidebar():
    """Render the navigation sidebar"""
    st.sidebar.title("PharmChecker")
    st.sidebar.caption("v1.2 - Session Management")
    
    # Navigation at top
    pages = [
        "Dataset Manager",
        "Results Matrix", 
        "Scoring Manager",
        "Pharmacy Details",
        "Search Details",
        "Validation Manager"
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
        
        # Toggle lock state button
        lock_icon = "🔒" if st.session_state.validation_system_locked else "🔓"
        if st.sidebar.button(f"{lock_icon} {'Locked' if st.session_state.validation_system_locked else 'Unlocked'}", key="validation_system_lock", help="Lock/unlock validation system"):
            st.session_state.validation_system_locked = not st.session_state.validation_system_locked
    
    st.sidebar.markdown("---")
    
    # Quick actions
    st.sidebar.subheader("Quick Actions")
    if st.sidebar.button("🔄 Reload Data", help="Reload data from database and clear cache"):
        clear_loaded_data()
        st.cache_data.clear()
        st.rerun()
    
    if st.sidebar.button("Clear Session"):
        from utils.session import clear_all_session_data
        clear_all_session_data()
        st.cache_data.clear()
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
    
    if st.sidebar.button("Export Current View"):
        st.sidebar.info("Export functionality coming soon")
        
    # No dark mode toggle needed - keeping default Streamlit theme
    
    # User context display at bottom
    user_context = st.session_state.get('user_context', {})
    if user_context.get('authenticated'):
        st.sidebar.success(f"👤 **{user_context['email']}** ({user_context['role']})")
        st.sidebar.caption(f"Auth: {user_context['auth_mode']}")
    else:
        st.sidebar.error("❌ Not authenticated")

def render_dataset_manager():
    """Load-based dataset management interface"""
    st.header("Dataset Manager")
    
    # Show current loaded data status
    if is_data_loaded():
        loaded_tags = get_loaded_tags()
        last_load_time = st.session_state.loaded_data['last_load_time']
        
        st.success("✅ **Data Loaded**")
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.info(f"""
            **Loaded Dataset Combination:**
            - **Pharmacies:** {loaded_tags['pharmacies']}
            - **States:** {loaded_tags['states']}  
            - **Validated:** {loaded_tags['validated'] or 'None'}
            - **Loaded:** {last_load_time.strftime('%Y-%m-%d %H:%M:%S')}
            """)
            
        with col2:
            if st.button("🗑️ Clear Data", help="Clear loaded data from memory"):
                clear_loaded_data()
                st.rerun()
    else:
        st.warning("⚠️ **No Data Loaded**")
        st.markdown("Select dataset combination and load data to begin analysis.")
    
    st.markdown("---")
    
    # Dataset selection for loading
    st.subheader("Load Dataset Combination")
    
    # Show session restoration info if available
    current_selection = st.session_state.selected_datasets
    has_saved_selection = any(v for v in current_selection.values())
    
    if has_saved_selection:
        st.info(f"💾 **Restored from session:** Pharmacies: {current_selection['pharmacies'] or 'None'}, States: {current_selection['states'] or 'None'}, Validated: {current_selection['validated'] or 'None'}")
    
    # Get available datasets
    available_datasets = get_available_datasets()
    
    # Dataset selection
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Pharmacies** (Required)")
        pharmacy_options = available_datasets.get('pharmacies', [])
        # Set default to restored value if available
        pharmacy_default = current_selection.get('pharmacies', 'None')
        if pharmacy_default not in ['None'] + pharmacy_options:
            pharmacy_default = 'None'
        selected_pharmacy = st.selectbox(
            "Select pharmacy dataset:",
            ['None'] + pharmacy_options,
            index=(['None'] + pharmacy_options).index(pharmacy_default),
            key="load_pharmacy_select"
        )
        if selected_pharmacy != 'None':
            stats = get_dataset_stats('pharmacies', selected_pharmacy)
            st.info(f"📊 Records: {stats['record_count']}")
    
    with col2:
        st.markdown("**State Searches** (Required)")
        states_options = available_datasets.get('states', [])
        # Set default to restored value if available
        states_default = current_selection.get('states', 'None')
        if states_default not in ['None'] + states_options:
            states_default = 'None'
        selected_states = st.selectbox(
            "Select states dataset:",
            ['None'] + states_options,
            index=(['None'] + states_options).index(states_default),
            key="load_states_select"
        )
        if selected_states != 'None':
            stats = get_dataset_stats('states', selected_states)
            st.info(f"📊 Records: {stats['record_count']}")
    
    with col3:
        st.markdown("**Validated Overrides** (Optional)")
        validated_options = available_datasets.get('validated', [])
        # Set default to restored value if available
        validated_default = current_selection.get('validated') or 'None'
        if validated_default not in ['None'] + validated_options:
            validated_default = 'None'
        selected_validated = st.selectbox(
            "Select validated dataset:",
            ['None'] + validated_options,
            index=(['None'] + validated_options).index(validated_default),
            key="load_validated_select"
        )
        if selected_validated != 'None':
            stats = get_dataset_stats('validated', selected_validated)
            st.info(f"📊 Records: {stats['record_count']}")
    
    # Auto-load feature for restored sessions
    auto_load_possible = (
        has_saved_selection and 
        not is_data_loaded() and 
        selected_pharmacy != 'None' and 
        selected_states != 'None'
    )
    
    if auto_load_possible:
        st.info("🔄 **Auto-loading restored session data...**")
        validated_tag = selected_validated if selected_validated != 'None' else None
        success = load_dataset_combination(selected_pharmacy, selected_states, validated_tag)
        
        if success:
            new_datasets = {
                'pharmacies': selected_pharmacy,
                'states': selected_states,
                'validated': validated_tag
            }
            st.session_state.selected_datasets = new_datasets
            save_dataset_selection(new_datasets)
            st.session_state.validation_load_attempted = False
            st.session_state.current_page = 'Results Matrix'
            st.rerun()
    
    # Load button
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        load_enabled = (selected_pharmacy != 'None' and selected_states != 'None')
        
        if st.button("🔄 Load Data", type="primary", disabled=not load_enabled, 
                    help="Load selected datasets into memory for analysis"):
            if load_enabled:
                validated_tag = selected_validated if selected_validated != 'None' else None
                success = load_dataset_combination(selected_pharmacy, selected_states, validated_tag)
                
                if success:
                    # Update legacy session state for compatibility
                    new_datasets = {
                        'pharmacies': selected_pharmacy,
                        'states': selected_states,
                        'validated': validated_tag
                    }
                    st.session_state.selected_datasets = new_datasets
                    
                    # Save dataset selection for persistence
                    save_dataset_selection(new_datasets)
                    
                    # Reset validation load attempt flag for new data
                    st.session_state.validation_load_attempted = False
                    # Navigate to Results Matrix after successful loading
                    st.session_state.current_page = 'Results Matrix'
                    st.rerun()
            else:
                st.error("Please select both Pharmacies and States datasets")
    
    # Quick navigation if data is loaded
    if is_data_loaded():
        st.markdown("---")
        st.subheader("Quick Navigation")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📊 Results Matrix", type="secondary"):
                st.session_state.current_page = 'Results Matrix'
                st.rerun()
        
        with col2:
            if st.button("⚡ Scoring Manager", type="secondary"):
                st.session_state.current_page = 'Scoring Manager'
                st.rerun()
                
        with col3:
            if st.button("✅ Validation Manager", type="secondary"):
                st.session_state.current_page = 'Validation Manager'
                st.rerun()

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
        
        from utils.validation_local import load_dataset_combination
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
        
        # Find records with warnings
        warning_records = warning_check_df[
            warning_check_df['warnings'].notna() & 
            (warning_check_df['warnings'].astype(str) != '') & 
            (warning_check_df['warnings'].astype(str) != '[]')
        ]
        
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
    states_with_data = full_results_df[full_results_df['latest_result_id'].notna()]['search_state'].unique()
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
    from utils.validation_local import calculate_status_simple
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
    not_found = len(filtered_data[(filtered_data['status_bucket'] == 'no data') & filtered_data['latest_result_id'].notna()])
    no_data = len(filtered_data[(filtered_data['status_bucket'] == 'no data') & filtered_data['latest_result_id'].isna()])
    
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

def render_scoring_manager():
    """Scoring management and status"""
    st.header("Scoring Manager")
    
    datasets = st.session_state.selected_datasets
    if not (datasets['pharmacies'] and datasets['states']):
        st.warning("Please select Pharmacies and States datasets first")
        return
    
    st.info(f"Scoring context: Pharmacies({datasets['pharmacies']}) + States({datasets['states']})")
    
    # Get scoring status
    db = get_database_manager()
    
    with st.spinner("Loading scoring status..."):
        missing_scores_df = db.find_missing_scores(datasets['states'], datasets['pharmacies'])
        scoring_stats = db.get_scoring_statistics(datasets['states'], datasets['pharmacies'])
    
    # Scoring status
    st.subheader("Scoring Status")
    
    total_scores = scoring_stats.get('total_scores', 0)
    missing_count = len(missing_scores_df)
    total_pairs = total_scores + missing_count
    
    metrics = {
        "Total Pairs": total_pairs,
        "Scored Pairs": total_scores,
        "Missing Scores": missing_count
    }
    
    display_metrics_row(metrics)
    
    # Scoring actions
    st.subheader("Scoring Actions")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Refresh Missing Scores", type="primary"):
            st.cache_data.clear()
            st.rerun()
    
    with col2:
        if st.button("Compute All Missing"):
            if missing_count > 0:
                st.info(f"Would compute scores for {missing_count} pairs using scoring engine")
                # This would integrate with imports/scoring.py
            else:
                st.success("All scores are up to date!")
    
    # Display missing scores if any
    if not missing_scores_df.empty:
        st.subheader(f"Missing Scores ({len(missing_scores_df)} pairs)")
        st.dataframe(missing_scores_df, hide_index=True)
    else:
        st.success("✅ All scores computed!")
    
    # Scoring statistics
    st.subheader("Scoring Statistics")
    
    if scoring_stats and scoring_stats.get('total_scores', 0) > 0:
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Average Score", f"{scoring_stats.get('avg_score', 0):.1f}%")
            
        with col2:
            accuracy = (scoring_stats.get('matches', 0) / scoring_stats.get('total_scores', 1)) * 100
            st.metric("Match Rate", f"{accuracy:.1f}%")
        
        # Score distribution
        distribution_data = {
            'Classification': ['Perfect Match (≥85)', 'Weak Match (60-84)', 'No Match (<60)'],
            'Count': [
                scoring_stats.get('matches', 0),
                scoring_stats.get('weak_matches', 0), 
                scoring_stats.get('no_matches', 0)
            ]
        }
        
        distribution_df = pd.DataFrame(distribution_data)
        distribution_df['Percentage'] = (distribution_df['Count'] / distribution_df['Count'].sum() * 100).round(1)
        
        st.dataframe(distribution_df, hide_index=True)
    else:
        st.info("No scoring statistics available. Compute some scores first.")

def render_pharmacy_details():
    """Pharmacy details and search results view"""
    st.header("Pharmacy Details")
    
    datasets = st.session_state.selected_datasets
    if not datasets['pharmacies']:
        st.warning("Please select a Pharmacies dataset first")
        return
    
    # Get available pharmacies
    db = get_database_manager()
    
    try:
        # Get pharmacy list
        pharmacy_sql = """
        SELECT id, name, address, city, state, zip_code, phone, state_licenses
        FROM pharmacies p
        JOIN datasets d ON p.dataset_id = d.id
        WHERE d.tag = %s
        ORDER BY name
        """
        
        pharmacy_df = db.execute_query(pharmacy_sql, [datasets['pharmacies']])
        
        if pharmacy_df.empty:
            st.warning("No pharmacies found in selected dataset")
            return
        
        # Pharmacy selection
        pharmacy_names = pharmacy_df['name'].tolist()
        selected_pharmacy = st.selectbox("Select Pharmacy:", pharmacy_names)
        
        if selected_pharmacy:
            # Get selected pharmacy data
            pharmacy_data = pharmacy_df[pharmacy_df['name'] == selected_pharmacy].iloc[0].to_dict()
            
            # Display pharmacy card
            display_pharmacy_card(pharmacy_data)
            
            # Get search results for this pharmacy
            if datasets['states']:
                st.subheader("Search Results by State")
                
                # Get states this pharmacy claims licenses in
                try:
                    import json
                    licenses = pharmacy_data['state_licenses']
                    if isinstance(licenses, str):
                        licenses = json.loads(licenses)
                    
                    for state in licenses:
                        with st.expander(f"Results for {state}", expanded=False):
                            search_results_df = db.get_search_results(
                                selected_pharmacy, state, datasets['states']
                            )
                            
                            if not search_results_df.empty:
                                for _, result in search_results_df.iterrows():
                                    display_search_result_card(result.to_dict())
                                    st.markdown("---")
                            else:
                                st.info(f"No search results found for {state}")
                                
                except Exception as e:
                    st.error(f"Error loading search results: {e}")
            
    except Exception as e:
        st.error(f"Error loading pharmacy details: {e}")

def render_search_details():
    """Search result details and comparison view"""
    st.header("Search Details")
    
    datasets = st.session_state.selected_datasets
    if not datasets['states']:
        st.warning("Please select a States dataset first")
        return
    
    # Search filters
    col1, col2 = st.columns(2)
    
    with col1:
        pharmacy_name = st.text_input("Pharmacy Name:", placeholder="Enter pharmacy name")
    
    with col2:
        search_state = st.selectbox("State:", ["FL", "PA", "CA", "NY", "TX", "AL", "AZ"])
    
    if pharmacy_name and search_state:
        db = get_database_manager()
        
        try:
            # Get search results
            search_results_df = db.get_search_results(pharmacy_name, search_state, datasets['states'])
            
            if search_results_df.empty:
                st.warning(f"No search results found for {pharmacy_name} in {search_state}")
            else:
                # Debug info
                st.subheader(f"Search Results ({len(search_results_df)} found)")
                if st.session_state.get('debug_mode', False):
                    st.write("**DataFrame Info:**")
                    st.write(f"Shape: {search_results_df.shape}")
                    st.write(f"Columns: {list(search_results_df.columns)}")
                    st.write("**License Numbers:**")
                    st.write(search_results_df['license_number'].tolist())
                    st.write("**Unique License Numbers:**")
                    st.write(search_results_df['license_number'].unique().tolist())
                
                # Remove potential duplicates based on license_number and id
                search_results_df = search_results_df.drop_duplicates(subset=['id'])
                st.caption(f"After deduplication: {len(search_results_df)} results")
                
                for i, (_, result) in enumerate(search_results_df.iterrows()):
                    # More descriptive expander label
                    license_num = result.get('license_number', 'No License')
                    license_name = result.get('license_name', 'Unknown')
                    result_label = f"Result {i+1}: {license_num} - {license_name}"
                    
                    with st.expander(result_label, expanded=False): 
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            display_search_result_card(result.to_dict())
                        
                        with col2:
                            # Show scoring info if available
                            if datasets['pharmacies']:
                                scoring_sql = """
                                SELECT ms.score_overall, ms.score_street, ms.score_city_state_zip
                                FROM match_scores ms
                                JOIN pharmacies p ON ms.pharmacy_id = p.id  
                                JOIN datasets pd ON p.dataset_id = pd.id
                                JOIN datasets sd ON ms.states_dataset_id = sd.id
                                WHERE p.name = %s AND ms.result_id = %s 
                                  AND pd.tag = %s AND sd.tag = %s
                                """
                                
                                score_df = db.execute_query(scoring_sql, [
                                    pharmacy_name, result['id'], 
                                    datasets['pharmacies'], datasets['states']
                                ])
                                
                                if not score_df.empty:
                                    score_data = score_df.iloc[0]
                                    st.write("**Address Matching Scores:**")
                                    st.write(f"Overall: {score_data['score_overall']:.1f}%")
                                    st.write(f"Street: {score_data['score_street']:.1f}%")
                                    st.write(f"City/State/ZIP: {score_data['score_city_state_zip']:.1f}%")
                                else:
                                    st.info("No scoring data available")
                        
                        st.markdown("---")
                        
        except Exception as e:
            st.error(f"Error loading search details: {e}")

def render_validation_manager():
    """Validation override management"""
    st.header("Validation Manager")
    
    st.info("Manual validation override functionality")
    
    # Quick validation form
    with st.form("validation_form"):
        st.subheader("Create Validation Override")
        
        col1, col2 = st.columns(2)
        
        with col1:
            pharmacy_name = st.text_input("Pharmacy Name")
            state_code = st.selectbox("State", ["FL", "PA", "CA", "NY", "TX"])
            override_type = st.selectbox("Override Type", ["present", "empty"])
        
        with col2:
            license_number = st.text_input("License Number (if present)")
            reason = st.text_area("Validation Reason")
        
        submitted = st.form_submit_button("Create Override")
        
        if submitted:
            if pharmacy_name and state_code and override_type and reason:
                try:
                    # Get current datasets
                    datasets = st.session_state.selected_datasets
                    
                    with ValidatedImporter() as importer:
                        # Determine dataset to use
                        validated_tag = datasets.get('validated')
                        if not validated_tag:
                            # Create new validation dataset
                            validated_tag = f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                            dataset_id = importer.create_dataset(
                                'validated',
                                validated_tag,
                                f"GUI-created validation dataset",
                                'gui_user'
                            )
                            st.info(f"✨ Created new validation dataset: {validated_tag}")
                            # Update session state
                            st.session_state.selected_datasets['validated'] = validated_tag
                            # Clear cache to refresh dataset lists
                            if hasattr(st, 'cache_data'):
                                st.cache_data.clear()
                        else:
                            # Get existing dataset ID
                            with importer.conn.cursor() as cur:
                                cur.execute("SELECT id FROM datasets WHERE kind = 'validated' AND tag = %s", [validated_tag])
                                result = cur.fetchone()
                                if result:
                                    dataset_id = result[0]
                                else:
                                    st.error(f"Validation dataset '{validated_tag}' not found")
                                    return
                        
                        # Create validation record
                        success = importer.create_validation_record(
                            dataset_id=dataset_id,
                            pharmacy_name=pharmacy_name,
                            state_code=state_code,
                            license_number=license_number if override_type == 'present' else '',
                            override_type=override_type,
                            reason=reason,
                            validated_by='gui_user'
                        )
                        
                        if success:
                            st.success(f"✅ Created {override_type} validation for {pharmacy_name} in {state_code}")
                        else:
                            st.error("Failed to create validation record")
                            
                except Exception as e:
                    st.error(f"Error creating validation: {e}")
            else:
                st.error("Please fill in all required fields")
    
    # Show existing validation overrides
    datasets = st.session_state.selected_datasets
    if datasets['validated']:
        st.subheader("Existing Validation Overrides")
        
        db = get_database_manager()
        try:
            # Get validation overrides with key fields for comparison
            overrides_sql = """
            SELECT vo.id, vo.pharmacy_name, vo.state_code, vo.override_type, vo.license_number,
                   vo.license_status, vo.address, vo.city, vo.state, vo.zip, vo.expiration_date,
                   vo.reason, vo.validated_by, vo.validated_at
            FROM validated_overrides vo
            JOIN datasets d ON vo.dataset_id = d.id
            WHERE d.tag = %s
            ORDER BY validated_at DESC
            """
            
            overrides_df = db.execute_query(overrides_sql, [datasets['validated']])
            
            if not overrides_df.empty:
                st.write(f"**{len(overrides_df)} validation overrides found:**")
                
                # Show compact table with essential fields including record ID
                display_columns = ['id', 'pharmacy_name', 'state_code', 'override_type', 'license_number', 'validated_at']
                available_columns = [col for col in display_columns if col in overrides_df.columns]
                compact_df = overrides_df[available_columns].copy()
                st.dataframe(compact_df, hide_index=True)
                
                # Show comprehensive validation data from database JOIN
                st.subheader("Comprehensive Results with Validation Data")
                
                if datasets.get('pharmacies') and datasets.get('states'):
                    comprehensive_sql = """
                    SELECT pharmacy_id, pharmacy_name, search_state, result_id, license_number,
                           override_type, validated_license, score_overall, result_status
                    FROM get_all_results_with_context(%s, %s, %s)
                    WHERE override_type IS NOT NULL
                    ORDER BY pharmacy_name, search_state
                    """
                    
                    try:
                        comprehensive_df = db.execute_query(comprehensive_sql, [datasets['states'], datasets['pharmacies'], datasets['validated']])
                        
                        if not comprehensive_df.empty:
                            st.write(f"**{len(comprehensive_df)} records with validation data from JOIN:**")
                            st.dataframe(comprehensive_df, hide_index=True)
                        else:
                            st.info("No records found with validation data in comprehensive results")
                            
                    except Exception as e:
                        st.error(f"Error loading comprehensive validation data: {e}")
                        
            else:
                st.info("No validation overrides found in database")
                
        except Exception as e:
            st.error(f"Error loading validation overrides from database: {e}")
            
        # Show validation consistency check
        if datasets.get('pharmacies') and datasets.get('states'):
            st.subheader("Validation Consistency Check")
            
            try:
                consistency_sql = "SELECT * FROM check_validation_consistency(%s, %s, %s)"
                consistency_df = db.execute_query(consistency_sql, [datasets['states'], datasets['pharmacies'], datasets['validated']])
                
                if not consistency_df.empty:
                    st.warning(f"**{len(consistency_df)} validation consistency issues found:**")
                    st.dataframe(consistency_df, hide_index=True)
                else:
                    st.success("✅ No validation consistency issues found")
                    
            except Exception as e:
                st.error(f"Error running validation consistency check: {e}")
    else:
        st.info("Select a Validated dataset to view existing overrides")

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
    elif current_page == "Scoring Manager":
        render_scoring_manager()
    elif current_page == "Pharmacy Details":
        render_pharmacy_details()
    elif current_page == "Search Details":
        render_search_details()
    elif current_page == "Validation Manager":
        render_validation_manager()
    
    # Footer
    st.markdown("---")
    st.markdown("*PharmChecker MVP GUI - Built with Streamlit*")

if __name__ == "__main__":
    main()