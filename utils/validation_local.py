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
            'comprehensive_results': None,
            'validations': {},  # Key: (pharmacy_name, state_code, license_number)
            'loaded_tags': None,
            'last_load_time': None
        }

def get_validation_status(pharmacy_name: str, state_code: str, license_number: str = '') -> Optional[Dict]:
    """Get current validation status from session state"""
    initialize_loaded_data_state()
    
    key = (pharmacy_name, state_code, license_number)
    result = st.session_state.loaded_data['validations'].get(key, None)
    
    # Debug: Log when validation status is requested
    if result:
        logger.debug(f"Found validation for {pharmacy_name}-{state_code}-{license_number}: {result['override_type']}")
    else:
        logger.debug(f"No validation found for {pharmacy_name}-{state_code}-{license_number}")
        # Debug: Show what validations we do have
        available_keys = list(st.session_state.loaded_data['validations'].keys())[:5]  # First 5 keys
        logger.debug(f"Available validation keys (sample): {available_keys}")
    
    return result

def set_validation_status(pharmacy_name: str, state_code: str, license_number: str, 
                         override_type: str, reason: str = "GUI validation") -> bool:
    """Set validation status in session state and write directly to database"""
    initialize_loaded_data_state()
    
    key = (pharmacy_name, state_code, license_number)
    
    # Write to database first (blocking)
    success = write_validation_to_db(pharmacy_name, state_code, license_number, override_type, reason)
    
    if success:
        # Update local state only after successful DB write
        validation_record = {
            'override_type': override_type,
            'reason': reason,
            'validated_by': 'gui_user',
            'validated_at': datetime.now()
        }
        st.session_state.loaded_data['validations'][key] = validation_record
    
    return success

def remove_validation_status(pharmacy_name: str, state_code: str, license_number: str = '') -> bool:
    """Remove validation status from session state and database"""
    initialize_loaded_data_state()
    
    key = (pharmacy_name, state_code, license_number)
    
    # Remove from database first (blocking)
    success = remove_validation_from_db(pharmacy_name, state_code, license_number)
    
    if success and key in st.session_state.loaded_data['validations']:
        # Update local state only after successful DB removal
        del st.session_state.loaded_data['validations'][key]
    
    return success

def calculate_status_with_local_validation(row: pd.Series) -> str:
    """Calculate status bucket using local validation state"""
    pharmacy_name = row['pharmacy_name']
    search_state = row['search_state'] 
    license_number = row.get('license_number', '') or ''
    
    # Check local validation state first
    validation = get_validation_status(pharmacy_name, search_state, license_number)
    if validation:
        if validation['override_type'] == 'present':
            return 'validated'  # Show as validated status
        elif validation['override_type'] == 'empty':
            return 'validated'  # Show as validated status
    
    # Check for empty validation (state-level)
    empty_validation = get_validation_status(pharmacy_name, search_state, '')
    if empty_validation and empty_validation['override_type'] == 'empty':
        return 'validated'  # State validated as empty
    
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

def write_validation_to_db(pharmacy_name: str, state_code: str, license_number: str, 
                          override_type: str, reason: str = "GUI validation") -> bool:
    """Write validation directly to database (blocking operation)"""
    try:
        from imports.validated import ValidatedImporter
        
        with ValidatedImporter() as importer:
            loaded_tags = st.session_state.loaded_data['loaded_tags']
            validated_tag = loaded_tags.get('validated')
            
            # Auto-create validation dataset if needed
            if not validated_tag:
                validated_tag = f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                dataset_id = importer.create_dataset('validated', validated_tag, 
                                                   "GUI-created validation dataset", 'gui_user')
                # Update session state with new tag
                st.session_state.loaded_data['loaded_tags']['validated'] = validated_tag
            else:
                # Get existing dataset ID
                with importer.conn.cursor() as cur:
                    cur.execute("SELECT id FROM datasets WHERE kind = 'validated' AND tag = %s", [validated_tag])
                    result = cur.fetchone()
                    dataset_id = result[0] if result else None
                    
            if not dataset_id:
                st.error(f"Could not find or create validation dataset: {validated_tag}")
                return False
            
            # Simple blocking write
            success = importer.create_validation_record(
                dataset_id, pharmacy_name, state_code, license_number,
                override_type, reason, 'gui_user'
            )
            
            if success:
                st.success("✅ Validation saved to database")
            else:
                st.error("❌ Failed to save validation")
                
            return success
            
    except Exception as e:
        st.error(f"Database write failed: {e}")
        return False

def remove_validation_from_db(pharmacy_name: str, state_code: str, license_number: str = '') -> bool:
    """Remove validation directly from database (blocking operation)"""
    try:
        from imports.validated import ValidatedImporter
        
        with ValidatedImporter() as importer:
            validated_tag = st.session_state.loaded_data['loaded_tags'].get('validated')
            if not validated_tag:
                return True  # Nothing to remove
                
            # Get dataset ID
            with importer.conn.cursor() as cur:
                cur.execute("SELECT id FROM datasets WHERE kind = 'validated' AND tag = %s", [validated_tag])
                result = cur.fetchone()
                dataset_id = result[0] if result else None
                
            if not dataset_id:
                return True  # Dataset doesn't exist, consider success
            
            # Simple blocking delete
            success = importer.remove_validation_record(
                dataset_id, pharmacy_name, state_code, license_number
            )
            
            if success:
                st.success("✅ Validation removed from database") 
            else:
                st.info("ℹ️ No validation record found to remove")
                
            return True  # Consider both success and "not found" as success
            
    except Exception as e:
        st.error(f"Database delete failed: {e}")
        return False

def load_dataset_combination(pharmacies_tag: str, states_tag: str, validated_tag: Optional[str] = None) -> bool:
    """Load complete dataset combination into session state"""
    initialize_loaded_data_state()
    
    with st.spinner("Loading dataset combination..."):
        try:
            from utils.database import get_database_manager
            db = get_database_manager()
            
            # Load all data at once
            comprehensive_results = db.get_comprehensive_results(
                states_tag, pharmacies_tag, validated_tag, filter_to_loaded_states=False
            )
            
            # Parse validation state into local dictionary
            validations = {}
            
            # Debug: Check for validation columns
            validation_columns = [col for col in comprehensive_results.columns if 'validation' in col.lower() or 'override' in col.lower()]
            logger.info(f"Found validation columns: {validation_columns}")
            
            for _, row in comprehensive_results.iterrows():
                # Try multiple possible column names for validation override type
                override_type = (row.get('validation_override_type') or 
                               row.get('override_type') or 
                               row.get('validated_override_type'))
                
                if pd.notna(override_type):
                    key = (row['pharmacy_name'], row['search_state'], 
                           row.get('license_number', '') or '')
                    validations[key] = {
                        'override_type': override_type,
                        'reason': (row.get('validation_reason') or 
                                 row.get('reason') or 
                                 row.get('validated_reason', '')),
                        'validated_by': (row.get('validation_validated_by') or 
                                       row.get('validated_by') or 
                                       row.get('validated_validated_by', '')),
                        'validated_at': (row.get('validation_validated_at') or 
                                       row.get('validated_at') or 
                                       row.get('validated_validated_at'))
                    }
            
            # Store in session state
            st.session_state.loaded_data = {
                'comprehensive_results': comprehensive_results,
                'validations': validations,
                'loaded_tags': {
                    'pharmacies': pharmacies_tag,
                    'states': states_tag, 
                    'validated': validated_tag
                },
                'last_load_time': datetime.now()
            }
            
            # Success message with detailed validation info
            record_count = len(comprehensive_results)
            validation_count = len(validations)
            
            if validation_count > 0:
                # Show some validation details for debugging
                sample_validations = list(validations.items())[:3]  # First 3 validations
                validation_details = []
                for (pharm, state, lic), val in sample_validations:
                    validation_details.append(f"{pharm}-{state}-{lic or 'EMPTY'}: {val['override_type']}")
                
                st.success(f"✅ Loaded {record_count} records with {validation_count} validations")
                st.info(f"Sample validations: {'; '.join(validation_details)}")
            else:
                st.success(f"✅ Loaded {record_count} records with {validation_count} validations")
            
            return True
            
        except Exception as e:
            st.error(f"Failed to load dataset combination: {e}")
            return False

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
        'validations': {},
        'loaded_tags': None,
        'last_load_time': None
    }
    st.info("🗑️ Cleared loaded data")

def generate_validation_warnings(pharmacy_name: str, search_state: str, 
                                search_results: List, pharmacy_exists: bool) -> List[Dict]:
    """Generate all validation warnings per validate_spec.md warning system"""
    warnings = []
    
    # Debug for Belmar PA
    if pharmacy_name == 'Belmar' and search_state == 'PA':
        print(f"🔍 CONSOLE DEBUG: generate_validation_warnings called for Belmar PA")
        print(f"🔍 CONSOLE DEBUG: search_results count: {len(search_results)}")
        print(f"🔍 CONSOLE DEBUG: pharmacy_exists: {pharmacy_exists}")
    
    # Ensure loaded_data is initialized
    initialize_loaded_data_state()
    
    # Warning Case 4: Pharmacy Not in Current Dataset
    if not pharmacy_exists:
        if pharmacy_name == 'Belmar' and search_state == 'PA':
            print(f"🔍 CONSOLE DEBUG: Case 4 - Pharmacy not exists, checking validations...")
        # Check if any validations exist for this pharmacy
        pharmacy_validations = [v for k, v in st.session_state.loaded_data['validations'].items() 
                               if k[0] == pharmacy_name]
        if pharmacy_validations:
            if pharmacy_name == 'Belmar' and search_state == 'PA':
                print(f"🔍 CONSOLE DEBUG: Case 4 - Found validations for missing pharmacy, adding warning")
            warnings.append({
                'type': 'pharmacy_not_found',
                'level': 'error',
                'message': f"❌ Validated pharmacy not in current pharmacy dataset\nValidated: {pharmacy_name}",
                'action': "Check if correct pharmacy dataset is selected."
            })
        else:
            if pharmacy_name == 'Belmar' and search_state == 'PA':
                print(f"🔍 CONSOLE DEBUG: Case 4 - No validations for missing pharmacy, no warning")
        return warnings  # Skip other checks if pharmacy doesn't exist
    else:
        if pharmacy_name == 'Belmar' and search_state == 'PA':
            print(f"🔍 CONSOLE DEBUG: Case 4 - Pharmacy exists, continuing to other checks")
    
    # Warning Case 1: Empty Validation + Search Results Found
    empty_validation = get_validation_status(pharmacy_name, search_state, '')
    if pharmacy_name == 'Belmar' and search_state == 'PA':
        print(f"🔍 CONSOLE DEBUG: Case 1 - empty_validation: {empty_validation}")
    if empty_validation and empty_validation.get('override_type') == 'empty' and search_results:
        # Show details of found results
        found_details = []
        for result in search_results[:3]:  # Show up to 3 results
            license_num = result.get('license_number', 'N/A')
            license_name = result.get('license_name', 'N/A')
            address = result.get('address', 'N/A')
            found_details.append(f"{license_num}, {license_name}, {address}")
        
        warnings.append({
            'type': 'empty_validation_with_results',
            'level': 'warning',
            'message': f"⚠️ Search success for a record \"Validated as Empty\"\nValidated: {pharmacy_name}, {search_state}\nFound: {'; '.join(found_details)}",
            'action': "Review if empty validation is still correct given new search results."
        })
    
    # Warning Case 3: Present Validation + No Search Results  
    # Check all present validations for this pharmacy/state
    if pharmacy_name == 'Belmar' and search_state == 'PA':
        print(f"🔍 CONSOLE DEBUG: Case 3 - Checking present validations for missing results")
    for validation_key, validation in st.session_state.loaded_data['validations'].items():
        if (validation_key[0] == pharmacy_name and validation_key[1] == search_state 
            and validation_key[2] != '' and validation.get('override_type') == 'present'):
            
            license_number = validation_key[2]
            # Check if this validated license exists in search results
            found_in_results = any(r.get('license_number') == license_number for r in search_results)
            if pharmacy_name == 'Belmar' and search_state == 'PA':
                print(f"🔍 CONSOLE DEBUG: Case 3 - Checking validation for license {license_number}, found_in_results: {found_in_results}")
            
            if not found_in_results:
                if pharmacy_name == 'Belmar' and search_state == 'PA':
                    print(f"🔍 CONSOLE DEBUG: Case 3 - Adding warning for missing license {license_number}")
                warnings.append({
                    'type': 'present_validation_not_found',
                    'level': 'warning', 
                    'message': f"⚠️ Validated license not found in search results\nValidated: {pharmacy_name}, {search_state}, {license_number}",
                    'action': "Search data may have been updated or license may have been removed."
                })
    
    # Warning Case 2: Present Validation + Search Results Found - Check for Changes
    if pharmacy_name == 'Belmar' and search_state == 'PA':
        print(f"🔍 CONSOLE DEBUG: Case 2 - Checking search results for data changes")
    for result in search_results:
        license_number = result.get('license_number', '') or ''
        if pharmacy_name == 'Belmar' and search_state == 'PA':
            print(f"🔍 CONSOLE DEBUG: Case 2 - Processing result for license {license_number}")
        if not license_number:
            continue
            
        validation = get_validation_status(pharmacy_name, search_state, license_number)
        if pharmacy_name == 'Belmar' and search_state == 'PA':
            print(f"🔍 CONSOLE DEBUG: Case 2 - License {license_number}, validation: {validation}")
        if validation and validation.get('override_type') == 'present':
            # Compare current result with validation snapshot (stored in database)
            changes = check_validation_snapshot_changes(pharmacy_name, search_state, license_number, result)
            if pharmacy_name == 'Belmar' and search_state == 'PA':
                print(f"🔍 CONSOLE DEBUG: Case 2 - License {license_number}, changes found: {len(changes) if changes else 0}")
                if changes:
                    print(f"🔍 CONSOLE DEBUG: Case 2 - Changes details: {changes}")
            if changes:
                change_details = ', '.join([f"{field} (was: {snapshot_val} → now: {current_val})" for field, snapshot_val, current_val in changes])
                
                # Get debug info if debug mode enabled
                debug_info = ""
                if hasattr(st.session_state, 'debug_mode') and st.session_state.debug_mode:
                    # Add debug information about validation and search record IDs
                    validated_tag = st.session_state.loaded_data['loaded_tags'].get('validated', 'None')
                    search_result_id = result.get('latest_result_id', 'N/A')
                    
                    # Get validation record ID from database
                    validation_id = "N/A"
                    try:
                        from utils.database import DatabaseManager
                        db = DatabaseManager(use_production=True, allow_fallback=False)
                        validation_sql = """
                        SELECT vo.id FROM validated_overrides vo
                        JOIN datasets d ON vo.dataset_id = d.id
                        WHERE d.tag = %s AND vo.pharmacy_name = %s 
                          AND vo.state_code = %s AND vo.license_number = %s
                        """
                        validation_df = db.execute_query(validation_sql, [validated_tag, pharmacy_name, search_state, license_number])
                        if not validation_df.empty:
                            validation_id = validation_df.iloc[0]['id']
                    except Exception:
                        pass
                    
                    debug_info = f"\n\n**Debug Info:**\nValidation Record ID: {validation_id}\nSearch Result ID: {search_result_id}\nValidated Dataset: {validated_tag}"
                
                warnings.append({
                    'type': 'validation_data_changed',
                    'level': 'info',
                    'message': f"📝 Search results changed since validation\nValidated: {pharmacy_name}, {search_state}, {license_number}\nChanges: {change_details}{debug_info}",
                    'action': "Review if validation is still accurate given field changes."
                })
    
    return warnings

def check_validation_snapshot_changes(pharmacy_name: str, search_state: str, 
                                    license_number: str, current_result: Dict) -> List[Tuple[str, str, str]]:
    """Compare current search result with validation snapshot to detect changes"""
    changes = []
    
    # Debug for Belmar PA NP000382
    if pharmacy_name == 'Belmar' and search_state == 'PA' and license_number == 'NP000382':
        print(f"🔍 CONSOLE DEBUG: check_validation_snapshot_changes called for {pharmacy_name} {search_state} {license_number}")
        print(f"🔍 CONSOLE DEBUG: current_result keys: {list(current_result.keys())}")
        print(f"🔍 CONSOLE DEBUG: current_result city: '{current_result.get('result_city', 'N/A')}'")
    
    try:
        # Get validation snapshot from database
        from utils.database import DatabaseManager
        db = DatabaseManager(use_production=True, allow_fallback=False)
        
        validated_tag = st.session_state.loaded_data['loaded_tags'].get('validated')
        if not validated_tag:
            return changes
            
        snapshot_sql = """
        SELECT license_status, license_name, address, city, state, zip,
               issue_date, expiration_date
        FROM validated_overrides vo
        JOIN datasets d ON vo.dataset_id = d.id
        WHERE d.tag = %s AND vo.pharmacy_name = %s 
          AND vo.state_code = %s AND vo.license_number = %s
        """
        
        snapshot_df = db.execute_query(snapshot_sql, [validated_tag, pharmacy_name, search_state, license_number])
        
        if snapshot_df.empty:
            return changes
            
        snapshot = snapshot_df.iloc[0].to_dict()
        
        # Debug for Belmar PA NP000382
        if pharmacy_name == 'Belmar' and search_state == 'PA' and license_number == 'NP000382':
            print(f"🔍 CONSOLE DEBUG: snapshot city: '{snapshot.get('city', 'N/A')}'")
            print(f"🔍 CONSOLE DEBUG: current result_city: '{current_result.get('result_city', 'N/A')}'")
        
        # Compare key fields (current_result_field, snapshot_field) - MISSING CITY!
        compare_fields = [
            ('result_address', 'address'),  # current uses result_address, snapshot uses address
            ('result_city', 'city'),        # ADD MISSING CITY COMPARISON
            ('result_state', 'state'),      # ADD MISSING STATE COMPARISON  
            ('result_zip', 'zip'),          # ADD MISSING ZIP COMPARISON
            ('license_status', 'license_status'), 
            ('license_name', 'license_name'),
            ('issue_date', 'issue_date'),
            ('expiration_date', 'expiration_date')
        ]
        
        for field, snapshot_field in compare_fields:
            snapshot_val = str(snapshot.get(snapshot_field, 'N/A')) if pd.notna(snapshot.get(snapshot_field)) else 'N/A'
            current_val = str(current_result.get(field, 'N/A')) if pd.notna(current_result.get(field)) else 'N/A'
            
            # Per validate_spec.md: Flag ANY change for user review
            if snapshot_val != current_val:
                # Skip only truly identical N/A to N/A (no real change)
                if snapshot_val == 'N/A' and current_val == 'N/A':
                    continue  # No meaningful change
                
                # Report ALL other changes per spec - user should review accuracy
                changes.append((field, snapshot_val, current_val))
                
    except Exception as e:
        # Don't fail on snapshot comparison errors, just log
        logger.warning(f"Error comparing validation snapshot: {e}")
    
    return changes

def display_validation_warnings_section():
    """Display comprehensive validation warnings at top of Results Matrix"""
    print("🔍 CONSOLE DEBUG: display_validation_warnings_section called")
    if 'loaded_data' not in st.session_state:
        print("🔍 CONSOLE DEBUG: No loaded_data in session state")
        return
    
    comprehensive_results = st.session_state.loaded_data.get('comprehensive_results')
    if comprehensive_results is None or comprehensive_results.empty:
        print("🔍 CONSOLE DEBUG: No comprehensive_results or empty")
        return
    
    all_warnings = []
    validation_warnings_cache = {}  # Store which validations have warnings
    print(f"🔍 CONSOLE DEBUG: Starting warning generation for {len(comprehensive_results)} comprehensive results")
    
    # Check if we have the required columns for warning analysis
    required_columns = ['pharmacy_name', 'search_state']
    if not all(col in comprehensive_results.columns for col in required_columns):
        return
    
    try:
        # Group results by pharmacy-state for warning analysis
        pharmacy_state_groups = comprehensive_results.groupby(['pharmacy_name', 'search_state'])
        
        for (pharmacy_name, search_state), group in pharmacy_state_groups:
            # Debug for Belmar PA
            if pharmacy_name == 'Belmar' and search_state == 'PA':
                print(f"🔍 CONSOLE DEBUG: Processing Belmar PA in warning generation, group size: {len(group)}")
                print(f"🔍 CONSOLE DEBUG: Group columns: {group.columns.tolist()}")
            
            # Check if pharmacy exists in current dataset
            pharmacy_exists = True  # Default to True if column doesn't exist
            if 'pharmacy_address' in group.columns:
                pharmacy_exists = not group['pharmacy_address'].isna().all()
            
            # Get search results for this pharmacy-state
            search_results = []
            if 'latest_result_id' in group.columns:
                search_results = group[group['latest_result_id'].notna()].to_dict('records')
            elif 'result_id' in group.columns:
                search_results = group[group['result_id'].notna()].to_dict('records')
            
            # Debug for Belmar PA
            if pharmacy_name == 'Belmar' and search_state == 'PA':
                print(f"🔍 CONSOLE DEBUG: Belmar PA search_results count: {len(search_results)}")
                print(f"🔍 CONSOLE DEBUG: Belmar PA pharmacy_exists: {pharmacy_exists}")
            
            # Generate warnings
            warnings = generate_validation_warnings(pharmacy_name, search_state, search_results, pharmacy_exists)
            all_warnings.extend(warnings)
            
            # Debug for Belmar PA
            if pharmacy_name == 'Belmar' and search_state == 'PA':
                print(f"🔍 CONSOLE DEBUG: Belmar PA warnings generated: {len(warnings)}")
            
            # Cache which validations have warnings for quick lookup later
            if warnings:
                # Check what validations exist for this pharmacy/state
                from utils.validation_local import get_validation_status
                
                # Check license-specific validations
                for result in search_results:
                    license_number = result.get('license_number', '') or ''
                    if get_validation_status(pharmacy_name, search_state, license_number):
                        validation_warnings_cache[f"{pharmacy_name}|{search_state}|{license_number}"] = True
                
                # Check state-level empty validation
                if get_validation_status(pharmacy_name, search_state, ''):
                    validation_warnings_cache[f"{pharmacy_name}|{search_state}|"] = True
            
        # Store the warning cache in session state for quick lookups
        st.session_state.validation_warnings_cache = validation_warnings_cache
        
    except Exception as e:
        # If warning generation fails, just skip it silently
        logger.warning(f"Warning generation failed: {e}")
        return
    
    if all_warnings:
        st.subheader("🚨 Validation Warnings")
        
        # Group warnings by level
        error_warnings = [w for w in all_warnings if w['level'] == 'error']
        warning_warnings = [w for w in all_warnings if w['level'] == 'warning']
        info_warnings = [w for w in all_warnings if w['level'] == 'info']
        
        # Display error warnings (expanded by default)
        if error_warnings:
            with st.expander(f"❌ Critical Issues ({len(error_warnings)})", expanded=True):
                for warning in error_warnings:
                    st.error(f"**{warning['message']}**\n\n*Action:* {warning['action']}")
        
        # Display warning warnings (collapsed by default)
        if warning_warnings:
            with st.expander(f"⚠️ Warnings ({len(warning_warnings)})", expanded=False):
                for warning in warning_warnings:
                    st.warning(f"**{warning['message']}**\n\n*Action:* {warning['action']}")
        
        # Display info warnings (collapsed by default)
        if info_warnings:
            with st.expander(f"📝 Information ({len(info_warnings)})", expanded=False):
                for warning in info_warnings:
                    st.info(f"**{warning['message']}**\n\n*Action:* {warning['action']}")
        
        st.markdown("---")