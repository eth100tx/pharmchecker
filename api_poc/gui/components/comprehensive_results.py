"""
Comprehensive Results component for the API POC GUI
"""
import streamlit as st
import pandas as pd
from typing import List, Dict, Any


def render_comprehensive_results(client):
    """Render the comprehensive results interface"""
    st.header("🏥 Comprehensive Results")
    
    st.write("This interface calls the main `get_all_results_with_context()` function that powers the existing GUI.")
    
    try:
        # Get available datasets for tag selection
        datasets = client.get_datasets()
        if not datasets:
            st.warning("No datasets found. Please import some data first.")
            return
        
        df = pd.DataFrame(datasets)
        
        # Separate datasets by kind
        pharmacy_datasets = df[df['kind'] == 'pharmacies']['tag'].tolist()
        states_datasets = df[df['kind'] == 'states']['tag'].tolist()
        validated_datasets = df[df['kind'] == 'validated']['tag'].tolist()
        
        # Parameter selection
        st.subheader("Select Dataset Tags")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if pharmacy_datasets:
                pharmacies_tag = st.selectbox("Pharmacies Dataset", pharmacy_datasets, 
                                            index=len(pharmacy_datasets)-1 if pharmacy_datasets else 0)
            else:
                st.warning("No pharmacy datasets found")
                pharmacies_tag = ""
        
        with col2:
            if states_datasets:
                states_tag = st.selectbox("States Dataset", states_datasets,
                                        index=len(states_datasets)-1 if states_datasets else 0)
            else:
                st.warning("No states datasets found")
                states_tag = ""
        
        with col3:
            validated_options = [""] + validated_datasets  # Allow empty for optional param
            validated_tag = st.selectbox("Validated Dataset (Optional)", validated_options)
        
        # Query options
        st.subheader("Query Options")
        col1, col2 = st.columns(2)
        
        with col1:
            limit_results = st.checkbox("Limit Results", value=True)
            if limit_results:
                max_results = st.number_input("Maximum Results", min_value=10, max_value=10000, value=500)
        
        with col2:
            cache_results = st.checkbox("Cache Results", value=True, help="Cache results in session state")
        
        # Execute query
        if st.button("Get Comprehensive Results", type="primary", disabled=not (pharmacies_tag and states_tag)):
            # Use cache if enabled
            cache_key = f"results_{states_tag}_{pharmacies_tag}_{validated_tag}"
            
            if cache_results and cache_key in st.session_state:
                st.info("Using cached results")
                results = st.session_state[cache_key]
            else:
                with st.spinner("Fetching comprehensive results..."):
                    try:
                        results = client.get_comprehensive_results(states_tag, pharmacies_tag, validated_tag)
                        
                        if cache_results:
                            st.session_state[cache_key] = results
                        
                        st.success(f"Retrieved {len(results)} records")
                    except Exception as e:
                        st.error(f"Error fetching results: {e}")
                        return
            
            # Apply limit if requested
            if limit_results and len(results) > max_results:
                results = results[:max_results]
                st.warning(f"Results limited to {max_results} records")
            
            # Display results
            display_comprehensive_results(results)
    
    except Exception as e:
        st.error(f"Error: {e}")


def display_comprehensive_results(results: List[Dict]):
    """Display the comprehensive results data"""
    if not results:
        st.warning("No results found")
        return
    
    df = pd.DataFrame(results)
    
    # Summary metrics
    st.subheader("Results Summary")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Records", len(df))
    
    with col2:
        unique_pharmacies = df['pharmacy_name'].nunique()
        st.metric("Unique Pharmacies", unique_pharmacies)
    
    with col3:
        unique_states = df['search_state'].nunique()
        st.metric("Search States", unique_states)
    
    with col4:
        has_results = df['result_id'].notna().sum()
        st.metric("With Search Results", has_results)
    
    # Data filters and views
    st.subheader("Data Explorer")
    
    # Filter options
    with st.expander("Filters"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            pharmacy_filter = st.multiselect("Filter by Pharmacy", df['pharmacy_name'].unique())
        
        with col2:
            state_filter = st.multiselect("Filter by State", df['search_state'].unique())
        
        with col3:
            result_status_filter = st.multiselect("Filter by Result Status", 
                                                 df['result_status'].dropna().unique())
    
    # Apply filters
    filtered_df = df.copy()
    if pharmacy_filter:
        filtered_df = filtered_df[filtered_df['pharmacy_name'].isin(pharmacy_filter)]
    if state_filter:
        filtered_df = filtered_df[filtered_df['search_state'].isin(state_filter)]
    if result_status_filter:
        filtered_df = filtered_df[filtered_df['result_status'].isin(result_status_filter)]
    
    if len(filtered_df) < len(df):
        st.info(f"Filtered to {len(filtered_df)} records")
    
    # Display options
    display_mode = st.radio("Display Mode", 
                           ["Summary View", "Detailed Table", "Match Analysis"], 
                           horizontal=True)
    
    if display_mode == "Summary View":
        render_summary_view(filtered_df)
    elif display_mode == "Detailed Table":
        render_detailed_table(filtered_df)
    elif display_mode == "Match Analysis":
        render_match_analysis(filtered_df)
    
    # Export options
    st.subheader("Export")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Export Filtered Data"):
            csv = filtered_df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"comprehensive_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    
    with col2:
        if st.button("Export Full Results"):
            csv = df.to_csv(index=False)
            st.download_button(
                label="Download Full CSV",
                data=csv,
                file_name=f"comprehensive_results_full_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )


def render_summary_view(df: pd.DataFrame):
    """Render summary view of results"""
    st.write("**Key Columns:**")
    
    summary_cols = ['pharmacy_name', 'search_state', 'license_number', 'license_status', 
                   'score_overall', 'result_status', 'override_type']
    
    available_cols = [col for col in summary_cols if col in df.columns]
    
    if available_cols:
        summary_df = df[available_cols].copy()
        
        # Format score for display
        if 'score_overall' in summary_df.columns:
            summary_df['score_overall'] = summary_df['score_overall'].round(2)
        
        st.dataframe(summary_df, use_container_width=True)
    else:
        st.dataframe(df, use_container_width=True)


def render_detailed_table(df: pd.DataFrame):
    """Render full detailed table"""
    st.write("**All Columns:**")
    
    # Column selector
    all_columns = df.columns.tolist()
    default_columns = [col for col in ['pharmacy_name', 'search_state', 'license_number', 
                                      'license_status', 'score_overall', 'pharmacy_address',
                                      'result_address', 'result_status'] if col in all_columns]
    
    selected_columns = st.multiselect("Select Columns to Display", 
                                     all_columns, 
                                     default=default_columns or all_columns[:10])
    
    if selected_columns:
        display_df = df[selected_columns]
        st.dataframe(display_df, use_container_width=True)
    else:
        st.warning("Please select at least one column to display")


def render_match_analysis(df: pd.DataFrame):
    """Render match score analysis"""
    st.write("**Address Matching Analysis:**")
    
    if 'score_overall' not in df.columns:
        st.warning("No scoring data available for analysis")
        return
    
    # Score distribution
    scores = df['score_overall'].dropna()
    
    if len(scores) == 0:
        st.warning("No match scores found")
        return
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        high_matches = (scores >= 85).sum()
        st.metric("High Matches (≥85)", high_matches)
    
    with col2:
        weak_matches = ((scores >= 60) & (scores < 85)).sum()
        st.metric("Weak Matches (60-84)", weak_matches)
    
    with col3:
        no_matches = (scores < 60).sum()
        st.metric("No Matches (<60)", no_matches)
    
    # Score histogram
    import plotly.express as px
    
    fig = px.histogram(scores, nbins=20, title="Match Score Distribution")
    fig.add_vline(x=85, line_dash="dash", line_color="green", annotation_text="High Match Threshold")
    fig.add_vline(x=60, line_dash="dash", line_color="orange", annotation_text="Weak Match Threshold")
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Top scoring matches
    st.subheader("Top Scoring Matches")
    top_matches = df[df['score_overall'].notna()].nlargest(10, 'score_overall')
    
    if not top_matches.empty:
        match_cols = ['pharmacy_name', 'search_state', 'license_number', 'score_overall',
                     'pharmacy_address', 'result_address']
        available_match_cols = [col for col in match_cols if col in top_matches.columns]
        
        if available_match_cols:
            st.dataframe(top_matches[available_match_cols], use_container_width=True)
        else:
            st.dataframe(top_matches, use_container_width=True)