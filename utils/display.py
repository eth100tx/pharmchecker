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
    status_icons = {
        'match': '✅',
        'weak match': '⚠️', 
        'no match': '❌',
        'no data': '⚫'
    }
    
    icon = status_icons.get(status.lower(), '❓')
    return f"{icon} {status.title()}"

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

def display_dense_results_table(df: pd.DataFrame, debug_mode: bool) -> Optional[Dict]:
    """Display dense results table with row selection"""
    if df.empty:
        st.warning("No results to display")
        return None
    
    # Group by pharmacy and state to show best result per combination
    grouped_results = []
    
    for (pharmacy_name, state), group in df.groupby(['pharmacy_name', 'search_state']):
        # Get the best result (highest score or first if no scores)
        if 'score_overall' in group.columns:
            scores_filled = group['score_overall'].fillna(-1).infer_objects(copy=False)
            best_row = group.loc[scores_filled.idxmax()]
        else:
            best_row = group.iloc[0]
        
        # Count multiple license numbers
        license_numbers = group['license_number'].dropna().unique()
        license_count = len(license_numbers)
        
        # Format license display
        if license_count == 0:
            license_display = "No License"
        elif license_count == 1:
            license_display = str(license_numbers[0])
        else:
            additional_count = license_count - 1
            license_display = f"{license_numbers[0]} (+{additional_count} more)"
        
        # Create row for display
        row_data = best_row.copy()
        row_data['license_display'] = license_display
        row_data['result_count'] = len(group)
        grouped_results.append(row_data)
    
    # Create display dataframe for the table
    display_data = []
    for row in grouped_results:
        display_row = {
            'Pharmacy': row['pharmacy_name'],
            'State': row['search_state'],
            'License #': row['license_display'],
            'Status': format_status_badge(row.get('status_bucket', 'unknown')),
            'Score': f"{row['score_overall']:.1f}%" if pd.notna(row.get('score_overall')) else "No Score"
        }
        
        if debug_mode:
            display_row['Street Score'] = f"{row['score_street']:.1f}%" if pd.notna(row.get('score_street')) else "N/A"
            display_row['City/State/ZIP'] = f"{row['score_city_state_zip']:.1f}%" if pd.notna(row.get('score_city_state_zip')) else "N/A"
            display_row['IDs'] = f"P:{row.get('pharmacy_id', 'N/A')} R:{row.get('result_id', 'N/A')}"
        
        display_data.append(display_row)
    
    display_df = pd.DataFrame(display_data)
    
    # Use streamlit dataframe with selection
    selected_indices = st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )
    
    # Return selected row data if any
    if selected_indices and len(selected_indices.selection.rows) > 0:
        selected_idx = selected_indices.selection.rows[0]
        return grouped_results[selected_idx]
    
    return None

def display_row_detail_section(selected_row: Dict, datasets: Dict[str, str], debug_mode: bool) -> None:
    """Display detailed view section below the table for selected row"""
    
    # Pharmacy information section (highlighted in blue)
    st.markdown("##### :blue[Pharmacy Information]")
    
    # Get pharmacy details from database
    pharmacy_details = get_pharmacy_info(selected_row['pharmacy_name'], datasets.get('pharmacies', ''))
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Name:** :blue[{selected_row['pharmacy_name']}]")
        if pharmacy_details.get('address'):
            addr_parts = []
            if pharmacy_details.get('address'): addr_parts.append(pharmacy_details['address'])
            if pharmacy_details.get('city'): addr_parts.append(pharmacy_details['city'])
            if pharmacy_details.get('state'): addr_parts.append(pharmacy_details['state'])
            if pharmacy_details.get('zip_code'): addr_parts.append(pharmacy_details['zip_code'])
            
            st.markdown(f"**Address:** :blue[{', '.join(addr_parts)}]")
        
    with col2:
        if pharmacy_details.get('phone'):
            st.markdown(f"**Phone:** :blue[{pharmacy_details['phone']}]")
    
    # Search Results section
    st.markdown("##### Search Results")
    
    # Get all search results for this pharmacy/state combination
    search_results = get_search_results_for_detail(
        selected_row['pharmacy_name'], 
        selected_row['search_state'], 
        datasets.get('states', '')
    )
    
    if search_results.empty:
        st.info("No search results available")
    else:
        # Create pulldown for each search result
        for i, (_, result) in enumerate(search_results.iterrows()):
            match_pct = ""
            if pd.notna(result.get('score_overall')):
                match_pct = f" ({result['score_overall']:.1f}% match)"
            
            # Build comprehensive license info for title
            license_parts = []
            license_number = result.get('license_number')
            if license_number and license_number != 'No License' and str(license_number).strip():
                license_parts.append(str(license_number))
            
            license_name = result.get('license_name')
            if license_name and str(license_name).strip():
                license_parts.append(str(license_name))
                
            license_status = result.get('license_status')
            if license_status and str(license_status).strip():
                license_parts.append(str(license_status))
                
            license_type = result.get('license_type')
            if license_type and str(license_type).strip():
                license_parts.append(f"({str(license_type)})")
            
            license_info = ' - '.join(license_parts) if license_parts else 'No License'
            
            expander_title = f"Result {i+1}: {license_info}{match_pct}"
            
            with st.expander(expander_title, expanded=(i == 0)):
                display_enhanced_search_result_detail(result, pharmacy_details, datasets, debug_mode, i)


def get_pharmacy_info(pharmacy_name: str, pharmacies_dataset: str) -> Dict:
    """Get pharmacy information from database"""
    # This would query the database for pharmacy details
    # For now, return sample data
    sample_pharmacies = {
        'Belmar Pharmacy': {
            'name': 'Belmar Pharmacy',
            'address': '123 Main St',
            'city': 'Tampa', 
            'state': 'FL',
            'zip_code': '33601',
            'phone': '813-555-0123'
        },
        'Beaker Pharmacy': {
            'name': 'Beaker Pharmacy',
            'address': '456 Oak Ave',
            'city': 'Miami',
            'state': 'FL', 
            'zip_code': '33101',
            'phone': '305-555-0456'
        },
        'Empower Pharmacy': {
            'name': 'Empower Pharmacy',
            'address': '789 Pine Rd',
            'city': 'Orlando',
            'state': 'FL',
            'zip_code': '32801',
            'phone': '407-555-0789'
        }
    }
    
    return sample_pharmacies.get(pharmacy_name, {})

def get_search_results_for_detail(pharmacy_name: str, state: str, states_dataset: str) -> pd.DataFrame:
    """Get all search results for detailed view"""
    from .database import DatabaseManager
    
    try:
        db = DatabaseManager(use_production=True)
        return db.get_search_results(pharmacy_name, state, states_dataset)
    except Exception as e:
        st.error(f"Failed to load search results: {e}")
        return pd.DataFrame()

def display_enhanced_search_result_detail(result: pd.Series, pharmacy_info: Dict, datasets: Dict, debug_mode: bool, result_idx: int) -> None:
    """Display enhanced search result with address comparison and validation controls"""
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        st.markdown("**Search Result:**")
        
        # Search results pharmacy name
        st.write(f"**Search Name:** {result.get('search_name', 'N/A')}")
        
        # License information including license_name and license_type
        st.write(f"**License #:** {result.get('license_number', 'N/A')}")
        if result.get('license_name'):
            st.write(f"**License Name:** {result.get('license_name', 'N/A')}")
        st.write(f"**Status:** {result.get('license_status', 'N/A')}")
        if result.get('license_type'):
            st.write(f"**Type:** {result.get('license_type', 'N/A')}")
        st.write(f"**State:** {result.get('state', 'N/A')}")
        
        # Search result address with bold matching parts
        search_addr_parts = []
        if result.get('address'): search_addr_parts.append(result['address'])
        if result.get('city'): search_addr_parts.append(result['city'])
        if result.get('state'): search_addr_parts.append(result['state'])
        if result.get('zip'): search_addr_parts.append(result['zip'])
        
        search_address = ', '.join(search_addr_parts) if search_addr_parts else 'N/A'
        
        # License address (if different from search address)
        license_addr_parts = []
        if result.get('license_address'): license_addr_parts.append(result['license_address'])
        if result.get('license_city'): license_addr_parts.append(result['license_city'])
        if result.get('license_state'): license_addr_parts.append(result['license_state'])
        if result.get('license_zip'): license_addr_parts.append(result['license_zip'])
        
        license_address = ', '.join(license_addr_parts) if license_addr_parts else None
        
        # Get pharmacy address for comparison
        pharmacy_addr_parts = []
        if pharmacy_info.get('address'): pharmacy_addr_parts.append(pharmacy_info['address'])
        if pharmacy_info.get('city'): pharmacy_addr_parts.append(pharmacy_info['city'])
        if pharmacy_info.get('state'): pharmacy_addr_parts.append(pharmacy_info['state'])
        if pharmacy_info.get('zip_code'): pharmacy_addr_parts.append(pharmacy_info['zip_code'])
        
        pharmacy_address = ', '.join(pharmacy_addr_parts) if pharmacy_addr_parts else 'N/A'
        
        # Display search address with matching
        display_search_address = format_address_with_matching_parts(search_address, pharmacy_address)
        st.markdown(f"**Search Address:** {display_search_address}")
        
        # Display license address if available and different
        if license_address and license_address != search_address:
            display_license_address = format_address_with_matching_parts(license_address, pharmacy_address)
            st.markdown(f"**License Address:** {display_license_address}")
        elif license_address:
            st.markdown(f"**License Address:** Same as search address")
        
        # Match percentage
        if pd.notna(result.get('score_overall')):
            st.write(f"**Match:** {result['score_overall']:.1f}%")
        
        # Dates
        if result.get('issue_date'):
            st.write(f"**Issue Date:** {result['issue_date']}")
        if result.get('expiration_date'):
            st.write(f"**Expiration:** {result['expiration_date']}")
    
    with col2:
        st.markdown("**:blue[Pharmacy Reference:]**")
        st.markdown(f"**Name:** :blue[{pharmacy_info.get('name', 'N/A')}]")
        
        # Pharmacy address with blue highlighting for easy comparison
        if pharmacy_address != 'N/A':
            st.markdown(f"**Address:** :blue[**{pharmacy_address}**]")
        else:
            st.write("**Address:** N/A")
        
        if pharmacy_info.get('phone'):
            st.markdown(f"**Phone:** :blue[{pharmacy_info['phone']}]")
        
        # Show screenshot if available
        if result.get('screenshot_path'):
            try:
                st.image(result['screenshot_path'], caption="Search Screenshot", width=250)
            except:
                st.info("Screenshot not available")
    
    with col3:
        # Validation controls in the detailed view
        st.markdown("**Validation:**")
        display_detailed_validation_controls(result, datasets, result_idx)
    
    if debug_mode and pd.notna(result.get('score_overall')):
        st.markdown("**Debug Info:**")
        col1, col2, col3 = st.columns(3)
        with col1:
            if pd.notna(result.get('score_street')):
                st.write(f"Street Score: {result['score_street']:.1f}%")
        with col2:
            if pd.notna(result.get('score_city_state_zip')):
                st.write(f"City/State/ZIP: {result['score_city_state_zip']:.1f}%")
        with col3:
            if result.get('result_id'):
                st.write(f"Result ID: {result['result_id']}")

def format_address_with_matching_parts(search_address: str, pharmacy_address: str) -> str:
    """Format address with bold parts that match the pharmacy address"""
    if search_address == 'N/A' or pharmacy_address == 'N/A':
        return search_address
    
    # Simple word-level matching for demonstration
    search_words = search_address.lower().replace(',', '').split()
    pharmacy_words = pharmacy_address.lower().replace(',', '').split()
    
    # Check if addresses match closely
    matching_words = set(search_words) & set(pharmacy_words)
    
    if len(matching_words) >= 2:  # If at least 2 words match
        return f":green[**{search_address}**] ✓"
    elif len(matching_words) >= 1:  # If some words match
        return f"**{search_address}**"
    else:
        return search_address

def display_detailed_validation_controls(result: pd.Series, datasets: Dict, result_idx: int) -> None:
    """Display simple toggle validation controls"""
    
    # Check if validation system is locked (from sidebar)
    system_locked = st.session_state.get('validation_system_locked', True)
    
    if system_locked:
        st.info("🔒 Unlock validation in sidebar to make changes")
        current_validated = result.get('override_type', None)
        if current_validated:
            status_icon = "✅" if current_validated == 'present' else "❌"
            st.markdown(f"{status_icon} **{current_validated.title()}**")
        else:
            st.markdown("⚪ **Not Validated**")
        return
    
    # Get current validation state
    current_validated = result.get('override_type', None)
    
    # Determine if this is a no_data record (for Empty validation)
    has_data = pd.notna(result.get('license_number')) and result.get('license_number') != 'No License'
    
    # Simple toggle for validation
    if has_data:
        # For records with data: toggle between None/present
        is_validated = current_validated == 'present'
        
        if st.toggle("Validated as Present", 
                    value=is_validated, 
                    key=f"toggle_present_{result_idx}",
                    help="Toggle validation for this search result"):
            if not is_validated:  # Was not validated, now validating
                handle_validation_toggle(result, datasets, 'present')
            else:  # Was validated, now removing
                handle_validation_toggle(result, datasets, 'remove')
    else:
        # For no_data records: toggle between None/empty
        is_validated_empty = current_validated == 'empty'
        
        if st.toggle("Validated as Empty", 
                    value=is_validated_empty, 
                    key=f"toggle_empty_{result_idx}",
                    help="Toggle empty validation for this search"):
            if not is_validated_empty:  # Was not validated, now validating as empty
                handle_validation_toggle(result, datasets, 'empty')
            else:  # Was validated empty, now removing
                handle_validation_toggle(result, datasets, 'remove')
    
    # Show current status
    if current_validated:
        status_icon = "✅" if current_validated == 'present' else "❌"
        st.markdown(f"{status_icon} **{current_validated.title()}**")
    else:
        st.markdown("⚪ **Not Validated**")

def handle_validation_toggle(result: pd.Series, datasets: Dict, action: str) -> None:
    """Handle validation toggle actions"""
    
    pharmacy_name = result.get('search_name', 'Unknown')
    state = result.get('state', 'Unknown')
    license_num = result.get('license_number', 'N/A')
    
    if action == 'present':
        if not datasets.get('validated'):
            # Create a tag for validation if none selected
            suggested_tag = f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            st.success(f"Would create validation dataset '{suggested_tag}' and mark {pharmacy_name} - {state} - {license_num} as PRESENT")
            st.info("💡 This would integrate with imports/validated.py to create the validation record")
        else:
            st.success(f"Would validate {pharmacy_name} - {state} - {license_num} as PRESENT in dataset '{datasets['validated']}'")
    
    elif action == 'empty':
        if not datasets.get('validated'):
            # Create a tag for validation if none selected
            suggested_tag = f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            st.success(f"Would create validation dataset '{suggested_tag}' and mark {pharmacy_name} - {state} as EMPTY")
            st.info("💡 This would integrate with imports/validated.py to create the validation record")
        else:
            st.success(f"Would validate {pharmacy_name} - {state} as EMPTY in dataset '{datasets['validated']}'")
    
    elif action == 'remove':
        st.success(f"Would remove validation for {pharmacy_name} - {state} - {license_num}")
        st.info("💡 This would remove the validation record from the validated dataset")

def handle_validation_action(result: pd.Series, datasets: Dict, action: str) -> None:
    """Legacy function - kept for compatibility"""
    handle_validation_toggle(result, datasets, action)

def display_search_result_detail(result: pd.Series, pharmacy_info: Dict, debug_mode: bool) -> None:
    """Legacy function - kept for compatibility"""
    pass