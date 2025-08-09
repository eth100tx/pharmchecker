"""
Display utilities for PharmChecker GUI
Handles UI components, formatting, and styling
"""

import streamlit as st
import pandas as pd
from typing import Dict, List, Optional, Any
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

def format_score(score: Optional[float]) -> str:
    """Format score value for display"""
    if score is None:
        return "No Score"
    return f"{score:.1f}%"

def format_status_badge(status: str) -> str:
    """Format status as colored badge"""
    status_colors = {
        'match': '🟢',
        'weak match': '🟡', 
        'no match': '🔴',
        'no data': '⚪'
    }
    
    color = status_colors.get(status.lower(), '⚫')
    return f"{color} {status.title()}"

def format_warnings(warnings: Optional[List[str]]) -> str:
    """Format warnings list for display"""
    if not warnings:
        return ""
    
    warning_icons = {
        'Pharmacy not in current dataset': '❌',
        'Validated present but result not found': '⚠️',
        'Validated empty but results now exist': '🔄',
        'Search result fields changed since validation': '📝'
    }
    
    formatted = []
    for warning in warnings:
        icon = warning_icons.get(warning, '⚠️')
        formatted.append(f"{icon} {warning}")
    
    return " | ".join(formatted)

def create_status_distribution_chart(df: pd.DataFrame, status_col: str = 'status_bucket') -> go.Figure:
    """Create pie chart showing status distribution"""
    if df.empty or status_col not in df.columns:
        return go.Figure()
    
    status_counts = df[status_col].value_counts()
    
    colors = {
        'match': '#28a745',      # Green
        'weak match': '#ffc107', # Yellow  
        'no match': '#dc3545',   # Red
        'no data': '#6c757d'     # Gray
    }
    
    fig = px.pie(
        values=status_counts.values,
        names=status_counts.index,
        title="Status Distribution",
        color_discrete_map=colors
    )
    
    fig.update_traces(textinfo='percent+label')
    fig.update_layout(height=400)
    
    return fig

def create_score_histogram(df: pd.DataFrame, score_col: str = 'score_overall') -> go.Figure:
    """Create histogram of score distribution"""
    if df.empty or score_col not in df.columns:
        return go.Figure()
    
    # Filter out null scores
    scores = df[df[score_col].notna()][score_col]
    
    if scores.empty:
        return go.Figure()
    
    fig = px.histogram(
        x=scores,
        nbins=20,
        title="Score Distribution",
        labels={'x': 'Score', 'y': 'Count'}
    )
    
    # Add vertical lines for thresholds
    fig.add_vline(x=85, line_dash="dash", line_color="green", 
                  annotation_text="Match Threshold (85)")
    fig.add_vline(x=60, line_dash="dash", line_color="orange",
                  annotation_text="Weak Match Threshold (60)")
    
    fig.update_layout(height=400)
    return fig

def display_dataset_summary(datasets: Dict[str, Optional[str]]) -> None:
    """Display current dataset selection summary"""
    st.subheader("Current Dataset Context")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if datasets.get('pharmacies'):
            st.success(f"**Pharmacies:** {datasets['pharmacies']}")
        else:
            st.info("**Pharmacies:** Not selected")
    
    with col2:
        if datasets.get('states'):
            st.success(f"**States:** {datasets['states']}")
        else:
            st.info("**States:** Not selected")
    
    with col3:
        if datasets.get('validated'):
            st.success(f"**Validated:** {datasets['validated']}")
        else:
            st.info("**Validated:** Not selected")

def display_results_table(df: pd.DataFrame, 
                         selectable: bool = False,
                         height: int = 400) -> Optional[Dict]:
    """Display results in a formatted table"""
    if df.empty:
        st.warning("No results to display")
        return None
    
    # Format display columns
    display_df = df.copy()
    
    # Format score columns
    score_columns = [col for col in display_df.columns if 'score' in col.lower()]
    for col in score_columns:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(format_score)
    
    # Format status column
    if 'status_bucket' in display_df.columns:
        display_df['Status'] = display_df['status_bucket'].apply(format_status_badge)
        display_df = display_df.drop('status_bucket', axis=1)
    
    # Format warnings column
    if 'warnings' in display_df.columns:
        display_df['Warnings'] = display_df['warnings'].apply(format_warnings)
        display_df = display_df.drop('warnings', axis=1)
    
    # Clean up column names for display
    display_columns = {
        'pharmacy_name': 'Pharmacy',
        'search_state': 'State',
        'license_number': 'License #',
        'license_status': 'License Status',
        'score_overall': 'Overall Score',
        'score_street': 'Street Score',
        'score_city_state_zip': 'City/State/ZIP Score'
    }
    
    display_df = display_df.rename(columns=display_columns)
    
    if selectable:
        # Allow row selection
        selected_indices = st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            height=height,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        if selected_indices and len(selected_indices.selection.rows) > 0:
            selected_idx = selected_indices.selection.rows[0]
            return df.iloc[selected_idx].to_dict()
    else:
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            height=height
        )
    
    return None

def display_metrics_row(metrics: Dict[str, Any]) -> None:
    """Display a row of metrics"""
    cols = st.columns(len(metrics))
    
    for i, (label, value) in enumerate(metrics.items()):
        with cols[i]:
            if isinstance(value, tuple) and len(value) == 2:
                st.metric(label, value[0], value[1])
            else:
                st.metric(label, value)

def display_pharmacy_card(pharmacy_data: Dict[str, Any]) -> None:
    """Display pharmacy information as a card"""
    with st.container():
        st.subheader(pharmacy_data.get('name', 'Unknown Pharmacy'))
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Address:**")
            address_parts = []
            if pharmacy_data.get('address'):
                address_parts.append(pharmacy_data['address'])
            if pharmacy_data.get('city'):
                address_parts.append(pharmacy_data['city'])
            if pharmacy_data.get('state'):
                address_parts.append(pharmacy_data['state'])
            if pharmacy_data.get('zip_code'):
                address_parts.append(pharmacy_data['zip_code'])
            
            if address_parts:
                st.write(", ".join(address_parts))
            else:
                st.write("Address not available")
        
        with col2:
            st.write("**Phone:**")
            st.write(pharmacy_data.get('phone', 'Not available'))
            
            if pharmacy_data.get('state_licenses'):
                st.write("**Licensed States:**")
                try:
                    # Handle JSON string or list
                    import json
                    licenses = pharmacy_data['state_licenses']
                    if isinstance(licenses, str):
                        licenses = json.loads(licenses)
                    st.write(", ".join(licenses))
                except:
                    st.write(str(pharmacy_data['state_licenses']))

def display_search_result_card(result_data: Dict[str, Any]) -> None:
    """Display search result information as a card"""
    with st.container():
        col1, col2 = st.columns([2, 1])
        
        with col1:
            if result_data.get('license_number'):
                st.write(f"**License #:** {result_data['license_number']}")
            
            if result_data.get('license_status'):
                st.write(f"**Status:** {result_data['license_status']}")
            
            if result_data.get('address'):
                st.write(f"**Address:** {result_data['address']}")
                if result_data.get('city'):
                    st.write(f"**City:** {result_data['city']}, {result_data.get('state', '')} {result_data.get('zip', '')}")
            
            # Display dates if available
            if result_data.get('issue_date'):
                st.write(f"**Issue Date:** {result_data['issue_date']}")
            if result_data.get('expiration_date'):
                st.write(f"**Expiration:** {result_data['expiration_date']}")
        
        with col2:
            # Display screenshot if available
            if result_data.get('screenshot_path'):
                try:
                    st.image(result_data['screenshot_path'], caption="Search Screenshot", width=200)
                except:
                    st.info("Screenshot not available")

def create_export_button(df: pd.DataFrame, filename_prefix: str = "pharmchecker_export") -> None:
    """Create CSV export button for DataFrame"""
    if df.empty:
        return
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{filename_prefix}_{timestamp}.csv"
    
    csv_data = df.to_csv(index=False)
    
    st.download_button(
        label="📥 Export to CSV",
        data=csv_data,
        file_name=filename,
        mime="text/csv",
        help="Download current results as CSV file"
    )

def display_progress_bar(current: int, total: int, text: str = "Progress") -> None:
    """Display progress bar with current status"""
    if total == 0:
        return
    
    progress = current / total
    st.progress(progress, text=f"{text}: {current}/{total} ({progress:.1%})")

def display_alert(message: str, alert_type: str = "info") -> None:
    """Display styled alert message"""
    if alert_type == "success":
        st.success(message)
    elif alert_type == "warning":
        st.warning(message)
    elif alert_type == "error":
        st.error(message)
    else:
        st.info(message)