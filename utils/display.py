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
import os
import sys

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from imports.validated import ValidatedImporter
from config import get_db_config

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
        'no data': '⚫',
        'validated': '🔵',
        'validated empty': '🔵'
    }
    
    icon = status_icons.get(status.lower(), '❓')
    return f"{icon} {status.title()}"

def format_smart_status_badge(row: dict) -> str:
    """Format status with distinction between No Data Loaded and No Results Found, and validation overrides"""
    
    # Check for validation override first
    override_type = row.get('override_type')
    if override_type:
        if override_type == 'present':
            return "🔵 Validated"  # Blue circle for validated present
        elif override_type == 'empty':
            return "🔵 Validated Empty"  # Blue circle for validated empty
    
    status_bucket = row.get('status_bucket', 'unknown')
    
    # Handle non-"no data" cases normally
    if status_bucket != 'no data':
        return format_status_badge(status_bucket)
    
    # For "no data" cases, distinguish between the two types
    latest_result_id = row.get('latest_result_id')
    result_id = row.get('result_id')
    
    if pd.isna(latest_result_id) or latest_result_id is None:
        # No search record exists at all
        return "⚪ No Data Loaded"
    else:
        # Search record exists but no results found
        return "⚫ No Results Found"

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
            if pharmacy_data.get('zip'):
                address_parts.append(pharmacy_data['zip'])
            
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
                    # Display thumbnail
                    st.image(result_data['screenshot_path'], caption="Search Screenshot", width=200)
                    
                    # Add expandable full-size view
                    with st.expander("🔍 View Full Size"):
                        st.image(result_data['screenshot_path'], caption="Full Size Search Screenshot", use_container_width=True)
                except Exception as e:
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
            license_display = ""  # Leave blank if no license
        elif license_count == 1:
            license_display = str(license_numbers[0])
        else:
            additional_count = license_count - 1
            license_display = f"{license_numbers[0]} (+{additional_count} more)"
        
        # Create row for display
        row_data = best_row.copy()
        row_data['license_display'] = license_display
        # Use the record_count from database if available, otherwise use group length
        row_data['result_count'] = best_row.get('record_count', len(group))
        grouped_results.append(row_data)
    
    # Create display dataframe for the table
    display_data = []
    for row in grouped_results:
        display_row = {
            'Pharmacy': row['pharmacy_name'],
            'State': row['search_state'],
            'License #': row['license_display'],
            'Records': row['result_count'],
            'Status': format_smart_status_badge(row),
            'Score': f"{row['score_overall']:.1f}%" if pd.notna(row.get('score_overall')) else ""
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
    
    # Pharmacy information section with search context
    search_state = selected_row.get('search_state', 'Unknown')
    st.markdown(f"##### :blue[Pharmacy Information] - Viewing {search_state} Search Results")
    
    # Get pharmacy details from database
    pharmacy_details = get_pharmacy_info(selected_row['pharmacy_name'], datasets.get('pharmacies', ''))
    
    # Debug info if pharmacy_details is empty
    if not pharmacy_details:
        st.warning(f"⚠️ No pharmacy details found for '{selected_row['pharmacy_name']}' in dataset '{datasets.get('pharmacies', 'None')}'")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Name:** :blue[{selected_row['pharmacy_name']}]")
        
        # Show alias if available
        alias = pharmacy_details.get('alias') if pharmacy_details else None
        if alias:
            st.markdown(f"**Alias:** :blue[{alias}]")
        
        # Build and show full address
        addr_parts = []
        if pharmacy_details:
            if pharmacy_details.get('address'): addr_parts.append(pharmacy_details['address'])
            if pharmacy_details.get('suite'): addr_parts.append(f"Suite {pharmacy_details['suite']}")
            if pharmacy_details.get('city'): addr_parts.append(pharmacy_details['city'])
            if pharmacy_details.get('state'): addr_parts.append(pharmacy_details['state'])
            if pharmacy_details.get('zip'): addr_parts.append(str(pharmacy_details['zip']))
        
        if addr_parts:
            st.markdown(f"**Address:** :blue[{', '.join(addr_parts)}]")
        elif pharmacy_details:  # We have pharmacy_details but no address components
            st.markdown("**Address:** :blue[Address not available]")
        
    with col2:
        # Show phone if available
        phone = pharmacy_details.get('phone') if pharmacy_details else None
        if phone:
            st.markdown(f"**Phone:** :blue[{phone}]")
        
        # Show licensed states if available
        state_licenses = pharmacy_details.get('state_licenses') if pharmacy_details else None
        if state_licenses:
            try:
                import json
                licenses = state_licenses
                if isinstance(licenses, str):
                    licenses = json.loads(licenses)
                if isinstance(licenses, list):
                    st.markdown(f"**Licensed States:** :blue[{', '.join(licenses)}]")
                else:
                    st.markdown(f"**Licensed States:** :blue[{licenses}]")
            except Exception as e:
                st.markdown(f"**Licensed States:** :blue[{state_licenses}]")
    
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
        
        # Add validation button for empty records - this is the special case
        # mentioned by user: for empty records, validate button goes in Pharmacy info section
        st.markdown("**Validation:**")
        
        # Check if validation system is locked
        system_locked = st.session_state.get('validation_system_locked', True)
        
        if system_locked:
            st.info("🔒 Unlock validation in sidebar to validate empty records")
        else:
            # Create a mock result for empty validation  
            empty_result = pd.Series({
                'search_name': selected_row['pharmacy_name'],
                'search_state': selected_row['search_state'],
                'state': selected_row['search_state'],
                'license_number': '',  # Empty for empty validations
                'override_type': None  # Will be set if already validated
            })
            
            # Check if this pharmacy-state combination is already validated as empty
            try:
                validated_tag = datasets.get('validated')
                if validated_tag:
                    from .database import DatabaseManager
                    db = DatabaseManager(use_production=True, allow_fallback=False)
                    
                    # Query for existing empty validation
                    existing_validation_sql = """
                    SELECT override_type FROM validated_overrides vo
                    JOIN datasets d ON vo.dataset_id = d.id
                    WHERE d.tag = %s 
                      AND vo.pharmacy_name = %s 
                      AND vo.state_code = %s
                      AND (vo.license_number = '' OR vo.license_number IS NULL)
                    """
                    
                    result_df = db.execute_query(existing_validation_sql, [
                        validated_tag, 
                        selected_row['pharmacy_name'], 
                        selected_row['search_state']
                    ])
                    
                    if not result_df.empty:
                        empty_result['override_type'] = result_df.iloc[0]['override_type']
                    
            except Exception:
                pass  # Ignore errors in validation check
            
            # Show validation toggle for empty record
            current_validated = empty_result.get('override_type')
            is_validated_empty = current_validated == 'empty'
            
            validation_changed = st.toggle("Validate as Empty", 
                        value=is_validated_empty, 
                        key=f"toggle_empty_pharmacy_{selected_row['pharmacy_name']}_{selected_row['search_state']}",
                        help="Validate that no license exists for this pharmacy in this state")
                        
            if validation_changed != is_validated_empty:  # Only act if state actually changed
                if validation_changed:  # Toggled to validated
                    handle_validation_toggle(empty_result, datasets, 'empty')
                else:  # Toggled to not validated
                    handle_validation_toggle(empty_result, datasets, 'remove')
            
            # Show current validation status
            if current_validated:
                status_icon = "✅" if current_validated == 'present' else "❌"
                st.markdown(f"{status_icon} **{current_validated.title()}**")
            else:
                st.markdown("⚪ **Not Validated**")
    else:
        # Create pulldown for each search result
        for i, (_, result) in enumerate(search_results.iterrows()):
            # Get score information for highlighting
            score = result.get('score_overall')
            score_text = ""
            is_strong_match = False
            
            if pd.notna(score):
                is_strong_match = score >= 90  # Bold for >90% matches
                score_text = f" (**{score:.1f}% match**)" if is_strong_match else f" ({score:.1f}% match)"
            
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
            
            # Build search result address for comparison
            search_addr_parts = []
            if result.get('address'): search_addr_parts.append(str(result['address']))
            if result.get('city'): search_addr_parts.append(str(result['city']))
            if result.get('state'): search_addr_parts.append(str(result['state']))
            if result.get('zip'): search_addr_parts.append(str(result['zip']))
            
            search_address = ', '.join(search_addr_parts) if search_addr_parts else 'No Address'
            
            # Highlight matching address parts by comparing to pharmacy address
            highlighted_address = _highlight_address_matches(search_address, pharmacy_details)
            
            expander_title = f"Result {i+1}: {license_info}{score_text} | {highlighted_address}"
            
            with st.expander(expander_title, expanded=(i == 0)):
                display_enhanced_search_result_detail(result, pharmacy_details, datasets, debug_mode, i)


def _highlight_address_matches(search_address: str, pharmacy_details: Dict) -> str:
    """Highlight parts of search address that match pharmacy address"""
    if not pharmacy_details or not search_address:
        return search_address
    
    # Build individual pharmacy address components for matching
    pharmacy_components = {
        'address': pharmacy_details.get('address', '').lower().strip(),
        'city': pharmacy_details.get('city', '').lower().strip(), 
        'state': pharmacy_details.get('state', '').lower().strip(),
        'zip': str(pharmacy_details.get('zip', '')).lower().strip()
    }
    
    # Remove empty components
    pharmacy_components = {k: v for k, v in pharmacy_components.items() if v}
    
    if not pharmacy_components:
        return search_address
    
    # Split search address into parts
    search_parts = [part.strip() for part in search_address.split(',')]
    highlighted_parts = []
    
    for part in search_parts:
        part_lower = part.lower().strip()
        is_match = False
        
        # Check if this part matches any pharmacy component
        for comp_type, comp_value in pharmacy_components.items():
            if comp_value and (part_lower == comp_value or comp_value in part_lower or part_lower in comp_value):
                is_match = True
                break
        
        if is_match:
            highlighted_parts.append(f"**{part}**")
        else:
            highlighted_parts.append(part)
    
    return ', '.join(highlighted_parts)

def get_pharmacy_info(pharmacy_name: str, pharmacies_dataset: str) -> Dict:
    """Get pharmacy information from database"""
    from .database import DatabaseManager
    
    try:
        db = DatabaseManager(use_production=True, allow_fallback=False)
        sql = """
        SELECT p.name, p.alias, p.address, p.suite, p.city, p.state, p.zip, p.state_licenses
        FROM pharmacies p
        JOIN datasets d ON p.dataset_id = d.id
        WHERE p.name = %s AND d.tag = %s
        """
        
        df = db.execute_query(sql, [pharmacy_name, pharmacies_dataset])
        
        if not df.empty:
            return df.iloc[0].to_dict()
            
    except Exception as e:
        logger.warning(f"Failed to get pharmacy info from database: {e}")
    
    # Fallback to sample data
    sample_pharmacies = {
        'Belmar Pharmacy': {
            'name': 'Belmar Pharmacy',
            'alias': 'Belmar',
            'address': '123 Main St',
            'city': 'Tampa', 
            'state': 'FL',
            'zip': '33601',
            'phone': '813-555-0123'
        },
        'Beaker Pharmacy': {
            'name': 'Beaker Pharmacy',
            'alias': 'Beaker',
            'address': '456 Oak Ave',
            'city': 'Miami',
            'state': 'FL', 
            'zip': '33101',
            'phone': '305-555-0456'
        },
        'Empower Pharmacy': {
            'name': 'Empower Pharmacy',
            'alias': 'Empower',
            'address': '789 Pine Rd',
            'city': 'Orlando',
            'state': 'FL',
            'zip': '32801',
            'phone': '407-555-0789'
        }
    }
    
    return sample_pharmacies.get(pharmacy_name, {})

def get_search_results_for_detail(pharmacy_name: str, state: str, states_dataset: str) -> pd.DataFrame:
    """Get all search results for detailed view"""
    from .database import DatabaseManager
    
    try:
        db = DatabaseManager(use_production=True, allow_fallback=False)
        return db.get_search_results(pharmacy_name, state, states_dataset)
    except Exception as e:
        st.error(f"Failed to load search results: {e}")
        return pd.DataFrame()

def display_enhanced_search_result_detail(result: pd.Series, pharmacy_info: Dict, datasets: Dict, debug_mode: bool, result_idx: int) -> None:
    """Display enhanced search result with address comparison and validation controls"""
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        st.markdown("**Search Result:**")
        
        # Search results pharmacy name and state
        st.write(f"**Search Name:** {result.get('search_name', 'N/A')}")
        st.write(f"**Search State:** {result.get('search_state', 'N/A')}")
        
        # License information including license_name and license_type
        st.write(f"**License #:** {result.get('license_number', 'N/A')}")
        if result.get('license_name'):
            st.write(f"**License Name:** {result.get('license_name', 'N/A')}")
        st.write(f"**Status:** {result.get('license_status', 'N/A')}")
        if result.get('license_type'):
            st.write(f"**Type:** {result.get('license_type', 'N/A')}")
        
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
        if pharmacy_info.get('zip'): pharmacy_addr_parts.append(pharmacy_info['zip'])
        
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
        
        # Match scores - show all three if available
        if pd.notna(result.get('score_overall')):
            st.write(f"**Overall Score:** {result['score_overall']:.1f}%")
            
        if pd.notna(result.get('score_street')):
            st.write(f"**Address Score:** {result['score_street']:.1f}%")
            
        if pd.notna(result.get('score_city_state_zip')):
            st.write(f"**City/State/ZIP Score:** {result['score_city_state_zip']:.1f}%")
        
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
        
        # Show small thumbnail if available
        if result.get('screenshot_path'):
            try:
                st.image(result['screenshot_path'], caption="Screenshot", width=150)
            except Exception as e:
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
    
    # Full-size screenshot at bottom for side-by-side comparison
    if result.get('screenshot_path'):
        with st.expander("📷 View Full Size Screenshot (for comparison with data above)", expanded=False):
            st.markdown("**Use this to verify the search result data matches the screenshot:**")
            try:
                st.image(result['screenshot_path'], caption="Full Size Search Screenshot", use_container_width=True)
            except Exception as e:
                st.error(f"Could not load screenshot: {e}")

def format_address_with_matching_parts(search_address: str, pharmacy_address: str) -> str:
    """Format address with bold parts that match the pharmacy address"""
    if search_address == 'N/A' or pharmacy_address == 'N/A':
        return search_address
    
    # Split addresses into components for better matching
    search_parts = [part.strip() for part in search_address.split(',')]
    pharmacy_parts = [part.strip().lower() for part in pharmacy_address.split(',')]
    
    if not pharmacy_parts:
        return search_address
    
    highlighted_parts = []
    total_matches = 0
    
    for search_part in search_parts:
        part_lower = search_part.lower().strip()
        is_match = False
        
        # Check if this search part matches any pharmacy part (partial or exact)
        for pharm_part in pharmacy_parts:
            if pharm_part and (part_lower == pharm_part or pharm_part in part_lower or part_lower in pharm_part):
                is_match = True
                total_matches += 1
                break
        
        if is_match:
            highlighted_parts.append(f"**{search_part}**")
        else:
            highlighted_parts.append(search_part)
    
    result_address = ', '.join(highlighted_parts)
    
    # Add visual indicators based on match quality
    if total_matches >= 3:  # Very strong match (address, city, state/zip)
        return f":green[{result_address}] ✅"
    elif total_matches >= 2:  # Good match (likely address + city or state)
        return f":yellow[{result_address}] ⚠️"
    elif total_matches >= 1:  # Some match
        return result_address
    else:
        return f":red[{result_address}]"

def display_detailed_validation_controls(result: pd.Series, datasets: Dict, result_idx: int) -> None:
    """Display simple toggle validation controls"""
    
    # Check if validation system is locked (from sidebar)
    system_locked = st.session_state.get('validation_system_locked', True)
    
    # Get current validation state by looking up in validation dataset
    current_validated = None
    debug_info = ""
    
    validated_tag = datasets.get('validated')
    if validated_tag:
        try:
            from .database import DatabaseManager
            db = DatabaseManager(use_production=True, allow_fallback=False)
            
            # Look up validation for this specific search result
            pharmacy_name = result.get('search_name', '')
            search_state = result.get('search_state', '')
            license_number = result.get('license_number', '') or ''
            
            validation_sql = """
            SELECT vo.override_type, vo.dataset_id, d.tag
            FROM validated_overrides vo
            JOIN datasets d ON vo.dataset_id = d.id
            WHERE d.tag = %s 
              AND vo.pharmacy_name = %s 
              AND vo.state_code = %s
              AND (%s = '' AND vo.license_number IS NULL OR vo.license_number = %s)
            """
            
            result_df = db.execute_query(validation_sql, [
                validated_tag, pharmacy_name, search_state, license_number, license_number
            ])
            
            if not result_df.empty:
                current_validated = result_df.iloc[0]['override_type']
                # Debug info for troubleshooting
                debug_info = f" (Dataset: {result_df.iloc[0]['tag']}, ID: {result_df.iloc[0]['dataset_id']})"
            
        except Exception as e:
            # Continue without validation status on error
            pass
    
    if system_locked:
        st.info("🔒 Unlock validation in sidebar to make changes")
        if current_validated:
            status_icon = "✅" if current_validated == 'present' else "❌"
            st.markdown(f"{status_icon} **{current_validated.title()}**{debug_info if st.session_state.get('debug_mode', False) else ''}")
        else:
            st.markdown("⚪ **Not Validated**")
        return
    
    # Determine if this is a no_data record (for Empty validation)
    has_data = pd.notna(result.get('license_number')) and result.get('license_number') != 'No License'
    
    # Simple toggle for validation
    if has_data:
        # For records with data: toggle between None/present
        is_validated = current_validated == 'present'
        
        validation_changed = st.toggle("Validate", 
                    value=is_validated, 
                    key=f"toggle_present_{result_idx}",
                    help="Toggle validation for this search result")
                    
        if validation_changed != is_validated:  # Only act if state actually changed
            if validation_changed:  # Toggled to validated
                handle_validation_toggle(result, datasets, 'present')
            else:  # Toggled to not validated
                handle_validation_toggle(result, datasets, 'remove')
    else:
        # For no_data records: toggle between None/empty
        is_validated_empty = current_validated == 'empty'
        
        validation_changed = st.toggle("Validated as Empty", 
                    value=is_validated_empty, 
                    key=f"toggle_empty_{result_idx}",
                    help="Toggle empty validation for this search")
                    
        if validation_changed != is_validated_empty:  # Only act if state actually changed
            if validation_changed:  # Toggled to validated
                handle_validation_toggle(result, datasets, 'empty')
            else:  # Toggled to not validated
                handle_validation_toggle(result, datasets, 'remove')
    
    # Show current status
    if current_validated:
        status_icon = "✅" if current_validated == 'present' else "❌"
        debug_text = debug_info if st.session_state.get('debug_mode', False) else ''
        st.markdown(f"{status_icon} **{current_validated.title()}**{debug_text}")
    else:
        st.markdown("⚪ **Not Validated**")

def handle_validation_toggle(result: pd.Series, datasets: Dict, action: str) -> bool:
    """
    Handle validation toggle actions - actually create/remove validation records
    
    Returns:
        True if action was successful, False otherwise
    """
    
    pharmacy_name = result.get('search_name', 'Unknown')
    state = result.get('search_state', 'Unknown')  # Use search_state, not result state
    license_num = result.get('license_number', '') or ''
    
    try:
        with ValidatedImporter() as importer:
            if action == 'present':
                # Determine dataset to use
                validated_tag = datasets.get('validated')
                if not validated_tag:
                    # Create new validation dataset
                    validated_tag = f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    dataset_id = importer.create_dataset(
                        'validated', 
                        validated_tag, 
                        f"Auto-created validation dataset for {pharmacy_name} - {state}",
                        'gui_user'
                    )
                    st.info(f"✨ Created validation dataset: {validated_tag}")
                    # Update session state to use new dataset
                    st.session_state.selected_datasets['validated'] = validated_tag
                    # Clear cache to refresh dataset lists
                    if hasattr(st, 'cache_data'):
                        st.cache_data.clear()
                else:
                    # Get existing dataset ID
                    with importer.conn.cursor() as cur:
                        cur.execute("SELECT id FROM datasets WHERE kind = 'validated' AND tag = %s", [validated_tag])
                        result_row = cur.fetchone()
                        if result_row:
                            dataset_id = result_row[0]
                        else:
                            st.error(f"Validation dataset '{validated_tag}' not found")
                            return False
                
                # Create validation record
                success = importer.create_validation_record(
                    dataset_id=dataset_id,
                    pharmacy_name=pharmacy_name,
                    state_code=state,
                    license_number=license_num,
                    override_type='present',
                    reason=f"Manual validation via GUI - marked as present",
                    validated_by='gui_user'
                )
                
                if success:
                    st.success(f"✅ Validated {pharmacy_name} - {state} - {license_num} as PRESENT")
                    return True
                else:
                    st.error("Failed to create validation record")
                    return False
            
            elif action == 'empty':
                # Determine dataset to use
                validated_tag = datasets.get('validated')
                if not validated_tag:
                    # Create new validation dataset
                    validated_tag = f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    dataset_id = importer.create_dataset(
                        'validated',
                        validated_tag,
                        f"Auto-created validation dataset for {pharmacy_name} - {state}",
                        'gui_user'
                    )
                    st.info(f"✨ Created validation dataset: {validated_tag}")
                    # Update session state to use new dataset
                    st.session_state.selected_datasets['validated'] = validated_tag
                    # Clear cache to refresh dataset lists
                    if hasattr(st, 'cache_data'):
                        st.cache_data.clear()
                else:
                    # Get existing dataset ID
                    with importer.conn.cursor() as cur:
                        cur.execute("SELECT id FROM datasets WHERE kind = 'validated' AND tag = %s", [validated_tag])
                        result_row = cur.fetchone()
                        if result_row:
                            dataset_id = result_row[0]
                        else:
                            st.error(f"Validation dataset '{validated_tag}' not found")
                            return False
                
                # Create validation record
                success = importer.create_validation_record(
                    dataset_id=dataset_id,
                    pharmacy_name=pharmacy_name,
                    state_code=state,
                    license_number='',  # Empty for 'empty' validations
                    override_type='empty',
                    reason=f"Manual validation via GUI - marked as empty",
                    validated_by='gui_user'
                )
                
                if success:
                    st.success(f"✅ Validated {pharmacy_name} - {state} as EMPTY")
                    return True
                else:
                    st.error("Failed to create validation record")
                    return False
            
            elif action == 'remove':
                validated_tag = datasets.get('validated')
                if not validated_tag:
                    st.error("No validation dataset selected")
                    return False
                
                # Get dataset ID
                with importer.conn.cursor() as cur:
                    cur.execute("SELECT id FROM datasets WHERE kind = 'validated' AND tag = %s", [validated_tag])
                    result_row = cur.fetchone()
                    if result_row:
                        dataset_id = result_row[0]
                    else:
                        st.error(f"Validation dataset '{validated_tag}' not found")
                        return False
                
                # Remove validation record
                success = importer.remove_validation_record(
                    dataset_id=dataset_id,
                    pharmacy_name=pharmacy_name,
                    state_code=state,
                    license_number=license_num
                )
                
                if success:
                    st.success(f"🗑️ Removed validation for {pharmacy_name} - {state} - {license_num}")
                    return True
                else:
                    st.warning("No validation record found to remove")
                    return False
            
            else:
                st.error(f"Unknown validation action: {action}")
                return False
                
    except Exception as e:
        st.error(f"Error performing validation action: {e}")
        return False

def handle_validation_action(result: pd.Series, datasets: Dict, action: str) -> None:
    """Legacy function - kept for compatibility"""
    handle_validation_toggle(result, datasets, action)

def display_search_result_detail(result: pd.Series, pharmacy_info: Dict, debug_mode: bool) -> None:
    """Legacy function - kept for compatibility"""
    pass