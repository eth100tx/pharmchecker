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
import logging
from dotenv import load_dotenv

# Initialize logger
logger = logging.getLogger(__name__)

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_image_display_url(storage_path: str, storage_type: str) -> Optional[str]:
    """
    Convert SHA256 storage path to displayable URL
    
    Args:
        storage_path: Path from image_assets table (e.g., 'sha256/ab/cd/hash.png')
        storage_type: 'local' or 'supabase'
        
    Returns:
        URL that Streamlit can display, or None if not available
    """
    if not storage_path:
        return None
        
    if storage_type == 'local':
        # For local files, prepend the image cache directory
        full_path = os.path.join('imagecache', storage_path)
        if os.path.exists(full_path):
            return full_path
        else:
            logger.warning(f"Local image not found: {full_path}")
            return None
            
    elif storage_type == 'supabase':
        # For Supabase, create signed URL
        try:
            # Try Streamlit secrets first, then fall back to environment variables
            try:
                supabase_url = st.secrets.get('SUPABASE_URL') or os.getenv('SUPABASE_URL')
                service_key = st.secrets.get('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_SERVICE_KEY')
            except Exception:
                # Fallback to environment variables if secrets not available
                load_dotenv()
                supabase_url = os.getenv('SUPABASE_URL')
                service_key = os.getenv('SUPABASE_SERVICE_KEY')
            
            if not supabase_url or not service_key:
                logger.error("Supabase credentials not available for image display")
                logger.error(f"SUPABASE_URL: {'✓' if supabase_url else '✗'}")
                logger.error(f"SUPABASE_SERVICE_KEY: {'✓' if service_key else '✗'}")
                return None
                
            # Try to create signed URL using Supabase client
            try:
                from supabase import create_client
                supabase = create_client(supabase_url, service_key)
                
                # Generate signed URL (valid for 1 hour)
                signed_url_response = supabase.storage.from_('imagecache').create_signed_url(
                    storage_path, expires_in=3600
                )
                
                if 'signedURL' in signed_url_response:
                    return signed_url_response['signedURL']
                else:
                    logger.error(f"Failed to create signed URL for {storage_path}")
                    return None
                    
            except ImportError as e:
                logger.error(f"Supabase client not available for image display: {e}")
                logger.error("Make sure 'supabase>=2.0.0' is in requirements.txt")
                return None
            except Exception as e:
                logger.error(f"Error creating signed URL for {storage_path}: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error handling Supabase image URL: {e}")
            return None
    
    else:
        logger.warning(f"Unknown storage type: {storage_type}")
        return None
from imports.validated import ValidatedImporter
from config import get_db_config

def format_score(score: Optional[float]) -> str:
    """Format score value for display"""
    if score is None:
        return "No Score"
    return f"{score:.1f}%"

def format_status_badge(status: str) -> str:
    """Format status as colored badge - no warning complexity"""
    status_icons = {
        'match': '✅',
        'weak match': '⚠️', 
        'no match': '❌',
        'no data': '⚫',
        'validated': '🔵',
        'validated present': '🔵',
        'validated empty': '🔵'
    }
    
    icon = status_icons.get(status, '⚪')
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
    
    # Recalculate status column with validation awareness
    if 'status_bucket' in display_df.columns:
        from utils.validation_local import calculate_status_simple
        # Recalculate status buckets using validation-aware function
        display_df['status_bucket'] = display_df.apply(calculate_status_simple, axis=1)
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
            screenshot_url = get_image_display_url(
                result_data.get('screenshot_path'), 
                result_data.get('screenshot_storage_type')
            )
            if screenshot_url:
                try:
                    # Display thumbnail
                    st.image(screenshot_url, caption="Search Screenshot", width=200)
                    
                    # Add expandable full-size view
                    with st.expander("🔍 View Full Size"):
                        st.image(screenshot_url, caption="Full Size Search Screenshot", use_container_width=True)
                except Exception as e:
                    st.info("Screenshot not available")
            else:
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
        # Removed complex debug code - using simplified validation system
        
        # PRIORITY ORDER: Validated > Best Score > First Record
        validated_row = None
        from utils.validation_local import is_validated_simple
        
        # 1. Look for validated record first (HIGHEST PRIORITY)
        for idx, row in group.iterrows():
            if is_validated_simple(row):
                validated_row = row
                break  # Found validated record - use this one
        
        # 3. Fall back to best score or first record
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
        
        # Simple license display - show license from best row or blank
        license_number = best_row.get('license_number', '') or ''
        license_display = str(license_number) if license_number else ""
        
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
            'License Status': row.get('license_status', 'N/A'),
            'License Type': row.get('license_type', 'N/A'),
            'Records': row['result_count'],
            'Status': format_status_badge(row.get('status_bucket', 'no data')),
            'Score': f"{row['score_overall']:.1f}%" if pd.notna(row.get('score_overall')) else ""
        }
        
        if debug_mode:
            display_row['Result Status'] = row.get('result_status', 'N/A')
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

def display_row_detail_section(selected_row: Dict, datasets: Dict[str, str], debug_mode: bool, detail_results: pd.DataFrame = None) -> None:
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
    
    # Use provided detail results or fall back to database query
    if detail_results is not None:
        search_results = detail_results
    else:
        # Fall back to legacy database query
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
        
        # Create a mock result for empty validation (always create to avoid None errors)
        empty_result = pd.Series({
            'search_name': selected_row['pharmacy_name'],
            'search_state': selected_row['search_state'],
            'state': selected_row['search_state'],
            'license_number': '',  # Empty for empty validations
            'override_type': None  # Will be set if already validated
        })
        
        # Check if validation system is locked
        system_locked = st.session_state.get('validation_system_locked', True)
        
        if system_locked:
            st.info("🔒 Unlock validation in sidebar to validate empty records")
        else:
            
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
            # Handle both old and new column names for compatibility
            address = result.get('result_address') or result.get('address')
            city = result.get('result_city') or result.get('city')
            state = result.get('result_state') or result.get('state')
            zip_code = result.get('result_zip') or result.get('zip')
            
            if address: search_addr_parts.append(str(address))
            if city: search_addr_parts.append(str(city))
            if state: search_addr_parts.append(str(state))
            if zip_code: search_addr_parts.append(str(zip_code))
            
            search_address = ', '.join(search_addr_parts) if search_addr_parts else 'No Address'
            
            # Highlight matching address parts by comparing to pharmacy address
            highlighted_address = _highlight_address_matches(search_address, pharmacy_details)
            
            # Check validation status using simplified system
            validation_badge = ""
            is_validated = False
            try:
                from utils.validation_local import is_validated_simple
                
                # Check if this result is validated using database JOIN field
                if is_validated_simple(result):
                    validation_badge = " 🔵 **Validated**"
                    is_validated = True
            except Exception:
                pass
            
            # Build title - prioritize validation status over score
            if is_validated:
                # Show validation status instead of score
                expander_title = f"Result {i+1}: {license_info}{validation_badge} | {highlighted_address}"
            else:
                # Show score as usual
                expander_title = f"Result {i+1}: {license_info}{score_text} | {highlighted_address}"
            
            # Open single records, keep multiple records closed for user selection
            should_expand = len(search_results) == 1
            with st.expander(expander_title, expanded=should_expand):
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
    """Get pharmacy information from Supabase API"""
    import sys
    import os
    
    try:
        # Import API client
        sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'api_poc', 'gui'))
        from client import create_client
        
        client = create_client()
        
        # Get all datasets to find the dataset ID
        datasets = client.get_datasets()
        dataset_id = None
        for dataset in datasets:
            if dataset.get('kind') == 'pharmacies' and dataset.get('tag') == pharmacies_dataset:
                dataset_id = dataset.get('id')
                break
        
        if not dataset_id:
            logger.warning(f"Dataset '{pharmacies_dataset}' not found")
            return {}
        
        # Get pharmacies for this dataset
        pharmacies = client.get_pharmacies(dataset_id=dataset_id, limit=9999)
        if pharmacies:
            import pandas as pd
            pharmacies_df = pd.DataFrame(pharmacies)
            
            # Filter by pharmacy name (try exact match first, then partial)
            matching = pharmacies_df[pharmacies_df['name'] == pharmacy_name]
            if matching.empty:
                # Try partial match if exact match fails
                matching = pharmacies_df[pharmacies_df['name'].str.contains(pharmacy_name, case=False, na=False)]
            
            if not matching.empty:
                return matching.iloc[0].to_dict()
            
    except Exception as e:
        logger.warning(f"Failed to get pharmacy info from API: {e}")
    
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
        # Handle both old and new column names for compatibility
        address = result.get('result_address') or result.get('address')
        city = result.get('result_city') or result.get('city')
        state = result.get('result_state') or result.get('state')
        zip_code = result.get('result_zip') or result.get('zip')
        
        if address: search_addr_parts.append(address)
        if city: search_addr_parts.append(city)
        if state: search_addr_parts.append(state)
        if zip_code: search_addr_parts.append(zip_code)
        
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
        screenshot_url = get_image_display_url(
            result.get('screenshot_path'),
            result.get('screenshot_storage_type')
        )
        if screenshot_url:
            try:
                st.image(screenshot_url, caption="Screenshot", width=150)
            except Exception as e:
                st.info("Screenshot not available")
        else:
            st.info("Screenshot not available")
    
    with col3:
        # Validation controls in the detailed view
        st.markdown("**Validation:**")
        display_simple_validation_controls(result, datasets, result_idx)
    
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
    screenshot_url = get_image_display_url(
        result.get('screenshot_path'),
        result.get('screenshot_storage_type')
    )
    if screenshot_url:
        with st.expander("📷 View Full Size Screenshot (for comparison with data above)", expanded=False):
            st.markdown("**Use this to verify the search result data matches the screenshot:**")
            try:
                st.image(screenshot_url, caption="Full Size Search Screenshot", use_container_width=True)
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

# Complex comparison function removed - using simple validation display instead

def display_simple_validation_controls(result: pd.Series, datasets: Dict, result_idx: int) -> None:
    """Simple validation controls with database write + reload"""
    
    pharmacy_name = result.get('search_name', '') or result.get('pharmacy_name', '')
    search_state = result.get('search_state', '')
    license_number = result.get('license_number', '') or ''
    
    # Get current validation status using database JOIN field
    from utils.validation_local import is_validated_simple
    is_record_validated = is_validated_simple(result)
    
    # Check if validation system is locked
    system_locked = st.session_state.get('validation_system_locked', True)
    
    if system_locked:
        st.info("🔒 Unlock validation in sidebar to make changes")
        if is_record_validated:
            st.markdown("🔵 **Validated**")
        else:
            st.markdown("⚪ **Not Validated**")
        return
    
    # Simple single validation toggle
    validated = st.checkbox(
        "✅ Validate",
        value=is_record_validated,
        key=f"validate_{result_idx}",
        help="Mark this search result as validated"
    )
    
    if validated != is_record_validated:
        # Get client from session state
        client = st.session_state.get('api_client')
        if license_number:
            # For records with license numbers, validate as present
            toggle_validation_simple(pharmacy_name, search_state, license_number, 
                            'present' if validated else 'remove', client=client, result_data=result)
        else:
            # For empty records, validate as empty
            toggle_validation_simple(pharmacy_name, search_state, '', 
                            'empty' if validated else 'remove', client=client, result_data=result)

def toggle_validation_simple(pharmacy_name: str, state_code: str, license_number: str, action: str, client=None, result_data=None):
    """Simple validation toggle - API-based operation + reload"""
    try:
        # Use provided client or get from session state
        if client is None:
            client = st.session_state.get('api_client')
            if client is None:
                st.error("API client not available")
                return
        
        # Get current dataset info
        loaded_tags = st.session_state.get('loaded_tags', {})
        validated_tag = loaded_tags.get('validated')
        
        # Auto-create validation dataset if needed
        if not validated_tag:
            validated_tag = f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            create_result = client.create_dataset(
                kind='validated',
                tag=validated_tag,
                description=f"Auto-created validation dataset for {pharmacy_name}",
                created_by='gui_user'
            )
            
            if create_result.get('success'):
                dataset_id = create_result.get('dataset_id')
                actual_tag = create_result.get('tag')  # May be different if made unique
                st.info(f"✨ Created validation dataset: {actual_tag}")
                
                # Update session state to use new dataset
                st.session_state.loaded_tags['validated'] = actual_tag
                st.session_state.selected_datasets['validated'] = actual_tag
                
                # Clear cache to refresh dataset lists
                if hasattr(st, 'cache_data'):
                    st.cache_data.clear()
            else:
                st.error(f"Failed to create validation dataset: {create_result.get('error', 'Unknown error')}")
                return
        else:
            # Get existing dataset ID via API
            all_datasets = client.get_datasets()
            dataset_id = None
            for dataset in all_datasets:
                if dataset.get('kind') == 'validated' and dataset.get('tag') == validated_tag:
                    dataset_id = dataset.get('id')
                    break
        
        if not dataset_id:
            st.error(f"Could not find validation dataset: {validated_tag}")
            return
            
        # Perform API operation
        if action in ['present', 'empty']:
            # Prepare search result snapshot if result data is available
            search_result_snapshot = None
            if result_data is not None:
                # Extract snapshot fields from result data - use comprehensive results field names
                search_result_snapshot = {}
                snapshot_fields = [
                    'license_status', 'license_name', # 'license_type', # TODO: Add column to DB first
                    'result_address', 'result_city', 'result_state', 'result_zip', 
                    'issue_date', 'expiration_date', 'result_status'
                ]
                for field in snapshot_fields:
                    if field in result_data:
                        search_result_snapshot[field] = result_data[field]
            
            result = client.create_validation_record(
                dataset_id=dataset_id,
                pharmacy_name=pharmacy_name,
                state_code=state_code,
                license_number=license_number if action == 'present' else '',
                override_type=action,
                reason=f"GUI validation toggle - {action}",
                validated_by='gui_user',
                search_result_snapshot=search_result_snapshot
            )
            success = result.get('success')
            if not success:
                st.error(f"Validation failed: {result.get('error', 'Unknown error')}")
                return
                
        else:  # remove
            result = client.delete_validation_record(
                dataset_id=dataset_id,
                pharmacy_name=pharmacy_name,
                state_code=state_code,
                license_number=license_number if license_number else None
            )
            success = result.get('success')
            if not success:
                st.error(f"Remove failed: {result.get('error', 'Unknown error')}")
                return
        
        if success:
            # FULL RELOAD - no cache patching needed
            reload_comprehensive_results(client=client)
            st.rerun()
                
    except Exception as e:
        st.error(f"Validation action failed: {e}")

def display_validation_status(row: pd.Series) -> str:
    """Display validation status using database JOIN fields"""
    override_type = row.get('override_type')
    
    if override_type == 'present':
        return "🔵 **Validated Present**"
    elif override_type == 'empty':
        return "🔵 **Validated Empty**"
    else:
        return "⚪ **Not Validated**"

def get_validation_controls(row: pd.Series, result_idx: int):
    """Simple validation controls using database fields"""
    pharmacy_name = row.get('pharmacy_name')
    search_state = row.get('search_state') 
    license_number = row.get('license_number', '') or ''
    override_type = row.get('override_type')
    
    # Check if validation system is locked
    system_locked = st.session_state.get('validation_system_locked', True)
    
    if system_locked:
        st.info("🔒 Unlock validation in sidebar to make changes")
        return
    
    # Present validation toggle
    if license_number:
        is_present_validated = (override_type == 'present')
        validated = st.checkbox(
            "✅ Validate Present",
            value=is_present_validated,
            key=f"validate_present_{result_idx}",
            help="Mark this search result as validated"
        )
        
        if validated != is_present_validated:
            action = 'present' if validated else 'remove'
            client = st.session_state.get('api_client')
            toggle_validation_simple(pharmacy_name, search_state, license_number, action, client=client, result_data=row)
    
    # Empty validation toggle  
    is_empty_validated = (override_type == 'empty')
    validated_empty = st.checkbox(
        "🔵 Validate Empty",
        value=is_empty_validated,
        key=f"validate_empty_{result_idx}",
        help="Mark this pharmacy-state as having no valid license"
    )
    
    if validated_empty != is_empty_validated:
        action = 'empty' if validated_empty else 'remove'
        client = st.session_state.get('api_client')
        toggle_validation_simple(pharmacy_name, search_state, '', action, client=client, result_data=row)

def reload_comprehensive_results(client=None):
    """Reload comprehensive results with fresh validation data"""
    # Use provided client or get from session state
    if client is None:
        client = st.session_state.get('api_client')
        if client is None:
            st.error("API client not available")
            return
    
    # Get tags from selected_datasets (which includes newly created validation datasets)
    selected_datasets = st.session_state.get('selected_datasets', {})
    states_tag = selected_datasets.get('states')
    pharmacies_tag = selected_datasets.get('pharmacies') 
    validated_tag = selected_datasets.get('validated', '')
    
    if not states_tag or not pharmacies_tag:
        st.error("Cannot reload: missing required dataset selections")
        return
    
    # Get fresh data from API (includes updated validation JOINs)
    results = client.get_comprehensive_results(states_tag, pharmacies_tag, validated_tag)
    
    if isinstance(results, dict) and 'error' in results:
        st.error(f"Failed to reload data: {results['error']}")
        return
    
    # Update session state with new data
    st.session_state.comprehensive_results = pd.DataFrame(results)
    
    # Also update loaded_tags to keep everything in sync
    st.session_state.loaded_tags = {
        'states': states_tag,
        'pharmacies': pharmacies_tag,
        'validated': validated_tag
    }
    
    # Update loaded_data structure too
    if 'loaded_data' in st.session_state:
        st.session_state.loaded_data['loaded_tags'] = st.session_state.loaded_tags

def display_detailed_validation_controls(result: pd.Series, datasets: Dict, result_idx: int) -> None:
    """Display reactive validation controls with instant updates"""
    
    pharmacy_name = result.get('search_name', '') or result.get('pharmacy_name', '')
    search_state = result.get('search_state', '')
    license_number = result.get('license_number', '') or ''
    
    # Get search record ID for validation tracking
    search_record_id = result.get('result_id') or result.get('latest_result_id') or 'N/A'
    
    # Get current validation status from local state
    try:
        from utils.validation_local import get_validation_status, initialize_loaded_data_state
        
        # Ensure session state is initialized
        initialize_loaded_data_state()
        
        current_validation = get_validation_status(pharmacy_name, search_state, license_number)
        is_validated = current_validation is not None
        validation_available = True
        
        
        # Try to get validation record ID
        if current_validation:
            try:
                from utils.database import DatabaseManager
                db = DatabaseManager(use_production=True, allow_fallback=False)
                validated_tag = st.session_state.loaded_data['loaded_tags'].get('validated', 'None')
                
                if license_number:
                    validation_sql = """
                    SELECT vo.id, vo.license_status, vo.license_name, vo.address 
                    FROM validated_overrides vo
                    JOIN datasets d ON vo.dataset_id = d.id
                    WHERE d.tag = %s AND vo.pharmacy_name = %s 
                      AND vo.state_code = %s AND vo.license_number = %s
                    """
                    validation_df = db.execute_query(validation_sql, [validated_tag, pharmacy_name, search_state, license_number])
                else:
                    validation_sql = """
                    SELECT vo.id, vo.license_status, vo.license_name, vo.address 
                    FROM validated_overrides vo
                    JOIN datasets d ON vo.dataset_id = d.id
                    WHERE d.tag = %s AND vo.pharmacy_name = %s 
                      AND vo.state_code = %s AND vo.license_number IS NULL
                    """
                    validation_df = db.execute_query(validation_sql, [validated_tag, pharmacy_name, search_state])
                
                if not validation_df.empty:
                    validation_record = validation_df.iloc[0]
                else:
                    validation_record = None
            except Exception as e:
                validation_record = None
        
        # Debug: Print current search result data for comparison
        
    except Exception as e:
        # If local validation fails, default to not validated
        current_validation = None
        is_validated = False
        validation_available = False
    
    # Check if validation system is locked (from sidebar)
    system_locked = st.session_state.get('validation_system_locked', True)
    
    
    if system_locked:
        st.info("🔒 Unlock validation in sidebar to make changes")
        if is_validated:
            override_type = current_validation.get('override_type')
            status_icon = "✅" if override_type == 'present' else "❌"
            st.markdown(f"{status_icon} **{override_type.title()}**")
        else:
            st.markdown("⚪ **Not Validated**")
        
        # Show validation snapshot even when locked (read-only)
        if is_validated:
            
            present_condition = license_number and current_validation and current_validation.get('override_type') == 'present'
            empty_condition = current_validation and current_validation.get('override_type') == 'empty'
            
            
            if present_condition:
                display_validation_snapshot_section(pharmacy_name, search_state, license_number, result)
            elif empty_condition:
                display_validation_snapshot_section(pharmacy_name, search_state, '', result)
        
        return
    
    # Validation toggle for search results with license numbers
    if license_number:
        validated = st.checkbox(
            "✅ Validated",
            value=is_validated and current_validation.get('override_type') == 'present',
            key=f"validate_present_{result_idx}",
            help="Mark this search result as validated"
        )
        
        if validated and not (is_validated and current_validation and current_validation.get('override_type') == 'present'):
            # User just checked - validate as present (blocking write)
            try:
                from utils.validation_local import set_validation_status
                if set_validation_status(pharmacy_name, search_state, license_number, 'present'):
                    st.rerun()  # Immediate refresh after successful write
            except Exception as e:
                st.error(f"Failed to validate: {e}")
            
        elif not validated and (is_validated and current_validation and current_validation.get('override_type') == 'present'):
            # User just unchecked - remove validation (blocking write)
            try:
                from utils.validation_local import remove_validation_status
                if remove_validation_status(pharmacy_name, search_state, license_number):
                    st.rerun()  # Immediate refresh after successful removal
            except Exception as e:
                st.error(f"Failed to remove validation: {e}")
    
    # Empty validation (state-level) check
    if validation_available:
        try:
            empty_validation = get_validation_status(pharmacy_name, search_state, '')
            is_empty_validated = empty_validation and empty_validation.get('override_type') == 'empty'
        except Exception:
            empty_validation = None
            is_empty_validated = False
    else:
        empty_validation = None
        is_empty_validated = False
    
    validated_empty = st.checkbox(
        "🔵 Validated as Empty",
        value=is_empty_validated,
        key=f"validate_empty_{result_idx}",
        help="Mark this pharmacy-state combination as having no valid license"
    )
    
    if validated_empty and not is_empty_validated:
        # User just checked - validate as empty (blocking write)
        try:
            from utils.validation_local import set_validation_status
            if set_validation_status(pharmacy_name, search_state, '', 'empty'):
                st.rerun()  # Immediate refresh after successful write
        except Exception as e:
            st.error(f"Failed to validate as empty: {e}")
        
    elif not validated_empty and is_empty_validated:
        # User just unchecked - remove empty validation (blocking write)  
        try:
            from utils.validation_local import remove_validation_status
            if remove_validation_status(pharmacy_name, search_state, ''):
                st.rerun()  # Immediate refresh after successful removal
        except Exception as e:
            st.error(f"Failed to remove empty validation: {e}")
    
    # Display validation snapshot comparison if validated
    
    if is_validated:
        # Debug info with record IDs
        debug_mode = st.session_state.get('debug_mode', False)
        if debug_mode:
            search_record_id = result.get('result_id') or result.get('latest_result_id') or 'N/A'
            
            # Try to get validation record ID
            validation_record_id = 'N/A'
            if current_validation:
                try:
                    from utils.database import DatabaseManager
                    db = DatabaseManager(use_production=True, allow_fallback=False)
                    validated_tag = st.session_state.loaded_data['loaded_tags'].get('validated', 'None')
                    
                    if license_number:
                        validation_sql = """
                        SELECT vo.id FROM validated_overrides vo
                        JOIN datasets d ON vo.dataset_id = d.id
                        WHERE d.tag = %s AND vo.pharmacy_name = %s 
                          AND vo.state_code = %s AND vo.license_number = %s
                        """
                        validation_df = db.execute_query(validation_sql, [validated_tag, pharmacy_name, search_state, license_number])
                    else:
                        validation_sql = """
                        SELECT vo.id FROM validated_overrides vo
                        JOIN datasets d ON vo.dataset_id = d.id
                        WHERE d.tag = %s AND vo.pharmacy_name = %s 
                          AND vo.state_code = %s AND vo.license_number IS NULL
                        """
                        validation_df = db.execute_query(validation_sql, [validated_tag, pharmacy_name, search_state])
                    
                    if not validation_df.empty:
                        validation_record_id = validation_df.iloc[0]['id']
                except Exception as e:
                    validation_record_id = f'Error: {str(e)}'
            
        
        # Show snapshot section for present validations (with license number)
        present_condition = license_number and current_validation and current_validation.get('override_type') == 'present'
        empty_condition = current_validation and current_validation.get('override_type') == 'empty'
        
        
        if present_condition:
            display_validation_snapshot_section(pharmacy_name, search_state, license_number, result)
        # Show for empty validations too (they may have snapshot data)
        elif empty_condition:
            display_validation_snapshot_section(pharmacy_name, search_state, '', result)

def display_validation_snapshot_section(pharmacy_name: str, search_state: str, license_number: str, current_result: pd.Series) -> None:
    """Simple validation display - just dump both records with their IDs"""
    
    # Show validation snapshot comparison
    
    # Check if there's a validation record
    try:
        from utils.validation_local import get_validation_status
        validation = get_validation_status(pharmacy_name, search_state, license_number)
        if not validation:
            return
    except Exception:
        return
    
    # Add separator and section header
    st.markdown("---")
    st.markdown("**📋 Validation Data**")
    
    # Get record IDs - comprehensive results uses 'result_id' field
    search_record_id = current_result.get('result_id') or current_result.get('id') or 'N/A'
    
    # Get validation record and data
    validation_record_id = 'N/A'
    validated_data = None
    try:
        from utils.database import DatabaseManager
        db = DatabaseManager(use_production=True, allow_fallback=False)
        validated_tag = st.session_state.loaded_data['loaded_tags'].get('validated')
        
        if validated_tag:
            if license_number:
                validation_sql = """
                SELECT vo.* FROM validated_overrides vo 
                JOIN datasets d ON vo.dataset_id = d.id 
                WHERE d.tag = %s AND vo.pharmacy_name = %s AND vo.state_code = %s AND vo.license_number = %s
                """
                validation_df = db.execute_query(validation_sql, [validated_tag, pharmacy_name, search_state, license_number])
            else:
                validation_sql = """
                SELECT vo.* FROM validated_overrides vo 
                JOIN datasets d ON vo.dataset_id = d.id 
                WHERE d.tag = %s AND vo.pharmacy_name = %s AND vo.state_code = %s AND vo.license_number IS NULL
                """
                validation_df = db.execute_query(validation_sql, [validated_tag, pharmacy_name, search_state])
            
            if not validation_df.empty:
                validated_data = validation_df.iloc[0]
                validation_record_id = validated_data['id']
    except Exception as e:
        st.error(f"Error fetching validation data: {e}")
        return
    
    # Display basic info
    override_type = validation.get('override_type', 'Unknown')
    validated_by = validation.get('validated_by', 'Unknown')
    validated_at = validation.get('validated_at', 'Unknown')
    
    st.info(f"Validated as **{override_type}** by {validated_by} at {validated_at}")
    st.caption(f"Search Record ID: {search_record_id} | Validation Record ID: {validation_record_id}")
    
    # Create two columns for side-by-side record dumps
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Current Search Data:**")
        # Simple field dump - use result_* field names from comprehensive results
        display_fields = [
            ('license_name', 'license_name'),
            ('license_status', 'license_status'), 
            ('result_address', 'address'),
            ('result_city', 'city'),
            ('result_state', 'state'),
            ('result_zip', 'zip'),
            ('issue_date', 'issue_date'),
            ('expiration_date', 'expiration_date')
        ]
        for result_field, display_name in display_fields:
            value = current_result.get(result_field, 'N/A')
            st.write(f"**{display_name}:** {value}")
    
    with col2:
        st.markdown("**Validated Snapshot:**")
        if validated_data is not None:
            # Simple field dump - validated data uses unprefixed field names
            validated_fields = [
                ('license_name', 'license_name'),
                ('license_status', 'license_status'),
                ('address', 'address'),
                ('city', 'city'),
                ('state', 'state'),
                ('zip', 'zip'),
                ('issue_date', 'issue_date'),
                ('expiration_date', 'expiration_date')
            ]
            for field, display_name in validated_fields:
                value = validated_data.get(field, 'N/A')
                st.write(f"**{display_name}:** {value}")
        else:
            st.write("No snapshot data available")

def handle_validation_toggle(result: pd.Series, datasets: Dict, action: str) -> bool:
    """
    Handle validation toggle actions - actually create/remove validation records
    
    Returns:
        True if action was successful, False otherwise
    """
    
    if result is None:
        st.error("Validation action failed: No result data provided")
        return False
    
    if datasets is None:
        st.error("Validation action failed: No dataset information provided")
        return False
    
    pharmacy_name = result.get('search_name', 'Unknown')
    state = result.get('search_state', 'Unknown')  # Use search_state, not result state
    license_num = result.get('license_number', '') or ''
    
    try:
        # Use provided client or get from session state
        client = st.session_state.get('api_client')
        if client is None:
            st.error("API client not available")
            return False
        
        if action == 'present':
            # Determine dataset to use
            validated_tag = datasets.get('validated')
            dataset_id = None
            
            if not validated_tag:
                # Create new validation dataset via API
                validated_tag = f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                create_result = client.create_dataset(
                    kind='validated',
                    tag=validated_tag,
                    description=f"Auto-created validation dataset for {pharmacy_name} - {state}",
                    created_by='gui_user'
                )
                
                if create_result.get('success'):
                    dataset_id = create_result.get('dataset_id')
                    actual_tag = create_result.get('tag')  # May be different if made unique
                    st.info(f"✨ Created validation dataset: {actual_tag}")
                    
                    # Update session state to use new dataset
                    st.session_state.selected_datasets['validated'] = actual_tag
                    
                    # Update the local datasets variable for the rest of this function
                    datasets = st.session_state.selected_datasets.copy()
                    
                    # Clear cache to refresh dataset lists
                    if hasattr(st, 'cache_data'):
                        st.cache_data.clear()
                else:
                    st.error(f"Failed to create validation dataset: {create_result.get('error', 'Unknown error')}")
                    return False
            else:
                # Get existing dataset ID via API
                all_datasets = client.get_datasets()
                for dataset in all_datasets:
                    if dataset.get('kind') == 'validated' and dataset.get('tag') == validated_tag:
                        dataset_id = dataset.get('id')
                        break
                
                if not dataset_id:
                    st.error(f"Validation dataset '{validated_tag}' not found")
                    return False
            
            # Create validation record via API with snapshot
            # Prepare search result snapshot
            search_result_snapshot = {}
            snapshot_fields = [
                'license_status', 'license_name', 'license_type', 'result_address', 
                'result_city', 'result_state', 'result_zip', 'issue_date', 
                'expiration_date', 'result_status'
            ]
            for field in snapshot_fields:
                if field in result:
                    search_result_snapshot[field] = result[field]
            
            result = client.create_validation_record(
                dataset_id=dataset_id,
                pharmacy_name=pharmacy_name,
                state_code=state,
                license_number=license_num,
                override_type='present',
                reason=f"Manual validation via GUI - marked as present",
                validated_by='gui_user',
                search_result_snapshot=search_result_snapshot
            )
            
            if result.get('success'):
                st.success(f"✅ Validated {pharmacy_name} - {state} - {license_num} as PRESENT")
                
                # Reload comprehensive results to include the new validation data
                reload_comprehensive_results(client=client)
                return True
            else:
                st.error(f"Failed to create validation record: {result.get('error', 'Unknown error')}")
                return False
            
        elif action == 'empty':
            # Determine dataset to use
            validated_tag = datasets.get('validated')
            dataset_id = None
            
            if not validated_tag:
                # Create new validation dataset via API
                validated_tag = f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                create_result = client.create_dataset(
                    kind='validated',
                    tag=validated_tag,
                    description=f"Auto-created validation dataset for {pharmacy_name} - {state}",
                    created_by='gui_user'
                )
                
                if create_result.get('success'):
                    dataset_id = create_result.get('dataset_id')
                    actual_tag = create_result.get('tag')  # May be different if made unique
                    st.info(f"✨ Created validation dataset: {actual_tag}")
                    
                    # Update session state to use new dataset
                    st.session_state.selected_datasets['validated'] = actual_tag
                    
                    # Update the local datasets variable for the rest of this function
                    datasets = st.session_state.selected_datasets.copy()
                    
                    # Clear cache to refresh dataset lists
                    if hasattr(st, 'cache_data'):
                        st.cache_data.clear()
                else:
                    st.error(f"Failed to create validation dataset: {create_result.get('error', 'Unknown error')}")
                    return False
            else:
                # Get existing dataset ID via API
                all_datasets = client.get_datasets()
                for dataset in all_datasets:
                    if dataset.get('kind') == 'validated' and dataset.get('tag') == validated_tag:
                        dataset_id = dataset.get('id')
                        break
                
                if not dataset_id:
                    st.error(f"Validation dataset '{validated_tag}' not found")
                    return False
            
            # Create validation record via API with snapshot
            # Prepare search result snapshot
            search_result_snapshot = {}
            snapshot_fields = [
                'license_status', 'license_name', 'license_type', 'result_address', 
                'result_city', 'result_state', 'result_zip', 'issue_date', 
                'expiration_date', 'result_status'
            ]
            for field in snapshot_fields:
                if field in result:
                    search_result_snapshot[field] = result[field]
            
            result = client.create_validation_record(
                dataset_id=dataset_id,
                pharmacy_name=pharmacy_name,
                state_code=state,
                license_number='',  # Empty for 'empty' validations
                override_type='empty',
                reason=f"Manual validation via GUI - marked as empty",
                validated_by='gui_user',
                search_result_snapshot=search_result_snapshot
            )
            
            if result.get('success'):
                st.success(f"✅ Validated {pharmacy_name} - {state} as EMPTY")
                
                # Reload comprehensive results to include the new validation data
                reload_comprehensive_results(client=client)
                return True
            else:
                st.error(f"Failed to create validation record: {result.get('error', 'Unknown error')}")
                return False
            
        elif action == 'remove':
            validated_tag = datasets.get('validated')
            if not validated_tag:
                st.error("No validation dataset selected")
                return False
            
            # Get dataset ID via API
            all_datasets = client.get_datasets()
            dataset_id = None
            for dataset in all_datasets:
                if dataset.get('kind') == 'validated' and dataset.get('tag') == validated_tag:
                    dataset_id = dataset.get('id')
                    break
            
            if not dataset_id:
                st.error(f"Validation dataset '{validated_tag}' not found")
                return False
            
            # Remove validation record via API
            result = client.delete_validation_record(
                dataset_id=dataset_id,
                pharmacy_name=pharmacy_name,
                state_code=state,
                license_number=license_num if license_num else None
            )
            
            if result.get('success'):
                st.success(f"🗑️ Removed validation for {pharmacy_name} - {state} - {license_num}")
                
                # Reload comprehensive results to include the updated validation data
                reload_comprehensive_results(client=client)
                return True
            else:
                st.warning(f"Failed to remove validation: {result.get('error', 'Unknown error')}")
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