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

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import utility modules
from utils.database import get_database_manager, query_with_cache
from utils.display import (
    display_dataset_summary, display_results_table, display_metrics_row,
    create_status_distribution_chart, create_score_histogram,
    create_export_button, format_status_badge, display_pharmacy_card,
    display_search_result_card
)

# Page configuration
st.set_page_config(
    page_title="PharmChecker",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
def initialize_session_state():
    """Initialize session state variables"""
    if 'selected_datasets' not in st.session_state:
        st.session_state.selected_datasets = {
            'pharmacies': None,
            'states': None,
            'validated': None
        }
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'Dataset Manager'
    if 'last_query_time' not in st.session_state:
        st.session_state.last_query_time = None

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
    st.sidebar.markdown("---")
    
    # Navigation
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
    
    # Dataset context display
    st.sidebar.subheader("Current Context")
    datasets = st.session_state.selected_datasets
    
    for kind, tag in datasets.items():
        if tag:
            st.sidebar.success(f"**{kind.title()}:** {tag}")
        else:
            st.sidebar.info(f"**{kind.title()}:** Not selected")
    
    st.sidebar.markdown("---")
    
    # Quick actions
    st.sidebar.subheader("Quick Actions")
    if st.sidebar.button("Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    
    if st.sidebar.button("Export Current View"):
        st.sidebar.info("Export functionality coming soon")

def render_dataset_manager():
    """Dataset selection and management interface"""
    st.header("Dataset Manager")
    st.markdown("Select dataset combinations for analysis")
    
    # Get available datasets
    available_datasets = get_available_datasets()
    
    # Dataset selection
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Pharmacies")
        pharmacy_options = available_datasets.get('pharmacies', [])
        selected_pharmacy = st.selectbox(
            "Select pharmacy dataset:",
            ['None'] + pharmacy_options,
            index=0 if not st.session_state.selected_datasets['pharmacies'] else 
                  pharmacy_options.index(st.session_state.selected_datasets['pharmacies']) + 1
        )
        if selected_pharmacy != 'None':
            st.session_state.selected_datasets['pharmacies'] = selected_pharmacy
            stats = get_dataset_stats('pharmacies', selected_pharmacy)
            st.info(f"Records: {stats['record_count']}")
        else:
            st.session_state.selected_datasets['pharmacies'] = None
    
    with col2:
        st.subheader("State Searches")
        states_options = available_datasets.get('states', [])
        selected_states = st.selectbox(
            "Select states dataset:",
            ['None'] + states_options,
            index=0 if not st.session_state.selected_datasets['states'] else 
                  states_options.index(st.session_state.selected_datasets['states']) + 1
        )
        if selected_states != 'None':
            st.session_state.selected_datasets['states'] = selected_states
            stats = get_dataset_stats('states', selected_states)
            st.info(f"Records: {stats['record_count']}")
        else:
            st.session_state.selected_datasets['states'] = None
    
    with col3:
        st.subheader("Validated Overrides")
        validated_options = available_datasets.get('validated', [])
        selected_validated = st.selectbox(
            "Select validated dataset:",
            ['None'] + validated_options,
            index=0 if not st.session_state.selected_datasets['validated'] else 
                  validated_options.index(st.session_state.selected_datasets['validated']) + 1
        )
        if selected_validated != 'None':
            st.session_state.selected_datasets['validated'] = selected_validated
            stats = get_dataset_stats('validated', selected_validated)
            st.info(f"Records: {stats['record_count']}")
        else:
            st.session_state.selected_datasets['validated'] = None
    
    # Action buttons
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Load Results Matrix", type="primary"):
            if st.session_state.selected_datasets['pharmacies'] and st.session_state.selected_datasets['states']:
                st.session_state.current_page = 'Results Matrix'
                st.rerun()
            else:
                st.error("Please select at least Pharmacies and States datasets")
    
    with col2:
        if st.button("Check Scoring Status"):
            st.session_state.current_page = 'Scoring Manager'
            st.rerun()
    
    with col3:
        if st.button("View All Datasets"):
            st.info("Dataset listing functionality coming soon")

def render_results_matrix():
    """Main results matrix view"""
    st.header("Results Matrix")
    
    datasets = st.session_state.selected_datasets
    if not (datasets['pharmacies'] and datasets['states']):
        st.warning("Please select Pharmacies and States datasets first")
        if st.button("Go to Dataset Manager"):
            st.session_state.current_page = 'Dataset Manager'
            st.rerun()
        return
    
    # Display current context
    display_dataset_summary(datasets)
    
    # Filters
    st.subheader("Filters")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        state_filter = st.multiselect("Filter by State:", ["FL", "PA", "CA", "NY", "TX"])
    
    with col2:
        status_filter = st.multiselect("Filter by Status:", ["match", "weak match", "no match", "no data"])
    
    with col3:
        score_range = st.slider("Score Range:", 0.0, 100.0, (0.0, 100.0))
    
    with col4:
        show_warnings = st.checkbox("Show only items with warnings", False)
    
    # Load results using database function
    st.subheader("Results")
    
    db = get_database_manager()
    
    with st.spinner("Loading results matrix..."):
        results_df = db.get_results_matrix(
            datasets['states'],
            datasets['pharmacies'], 
            datasets['validated']
        )
    
    if results_df.empty:
        st.warning("No results found for the selected datasets")
        return
    
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
    
    if show_warnings:
        filtered_data = filtered_data[filtered_data['warnings'].notna() & (filtered_data['warnings'] != '')]
    
    # Display results table
    selected_row = display_results_table(filtered_data, selectable=True)
    
    if selected_row:
        st.subheader("Selected Row Details")
        col1, col2 = st.columns(2)
        with col1:
            st.json({k: str(v) for k, v in selected_row.items() if k not in ['warnings']}, expanded=False)
        with col2:
            if selected_row.get('warnings'):
                st.write("**Warnings:**")
                for warning in selected_row['warnings']:
                    st.warning(warning)
    
    # Summary statistics
    st.subheader("Summary Statistics")
    
    total_results = len(filtered_data)
    matches = len(filtered_data[filtered_data['status_bucket'] == 'match'])
    weak_matches = len(filtered_data[filtered_data['status_bucket'] == 'weak match']) 
    no_matches = len(filtered_data[filtered_data['status_bucket'] == 'no match'])
    no_data = len(filtered_data[filtered_data['status_bucket'] == 'no data'])
    
    metrics = {
        "Total Results": total_results,
        "Matches": matches,
        "Weak Matches": weak_matches,
        "No Matches": no_matches,
        "No Data": no_data
    }
    
    display_metrics_row(metrics)
    
    # Charts
    col1, col2 = st.columns(2)
    with col1:
        chart = create_status_distribution_chart(filtered_data)
        if chart:
            st.plotly_chart(chart, use_container_width=True)
    
    with col2:
        score_chart = create_score_histogram(filtered_data)
        if score_chart:
            st.plotly_chart(score_chart, use_container_width=True)
    
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
                st.subheader(f"Search Results ({len(search_results_df)} found)")
                
                for i, (_, result) in enumerate(search_results_df.iterrows()):
                    with st.expander(f"Result {i+1} - {result.get('license_number', 'No License')}"): 
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
                st.success(f"Would create {override_type} override for {pharmacy_name} in {state_code}")
                st.info("This would integrate with imports/validated.py when implemented")
            else:
                st.error("Please fill in all required fields")
    
    # Show existing validation overrides
    datasets = st.session_state.selected_datasets
    if datasets['validated']:
        st.subheader("Existing Validation Overrides")
        
        db = get_database_manager()
        try:
            overrides_sql = """
            SELECT pharmacy_name, state_code, override_type, license_number, 
                   reason, created_at, created_by
            FROM validated_overrides vo
            JOIN datasets d ON vo.dataset_id = d.id
            WHERE d.tag = %s
            ORDER BY created_at DESC
            """
            
            overrides_df = db.execute_query(overrides_sql, [datasets['validated']])
            
            if not overrides_df.empty:
                st.dataframe(overrides_df, hide_index=True)
            else:
                st.info("No validation overrides found")
                
        except Exception as e:
            st.error(f"Error loading validation overrides: {e}")
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