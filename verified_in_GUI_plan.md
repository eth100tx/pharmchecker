# GUI-Based Validation Plan

## Overview

This plan outlines moving validation functionality from database-driven to GUI-driven architecture, enabling instant UI updates without page refreshes while maintaining data persistence.

## Current Architecture Analysis

### Current System Components

#### 1. Database-Driven Validation (`imports/validated.py`)
- **ValidatedImporter**: Handles CRUD operations for validation records
- **Database Storage**: `validated_overrides` table with natural key constraints
- **Snapshot System**: Captures search result state at validation time
- **Transaction Management**: Commit/rollback for data consistency

#### 2. GUI Integration (`app.py`)
- **Validation Manager Page**: Form-based validation creation (lines 611-716)
- **Results Matrix**: Shows validation status from database queries (lines 229-366)
- **Detail View Controls**: Toggle validation on individual search results (lines 356-361)
- **Session State**: Tracks selected datasets, but not validation state

#### 3. Display Components (`utils/display.py`)
- **Detailed Validation Controls**: `display_detailed_validation_controls()` (lines 768+)
- **Active Database Lookup**: Queries validation status for each result display
- **Lock System**: Global validation system lock/unlock toggle

#### 4. Database Functions (`utils/database.py`)
- **Results Loading**: `get_comprehensive_results()` includes validation status
- **Matrix Generation**: Aggregation includes validation in status calculation
- **Live Queries**: Each detail view queries current validation state

### Current Data Flow

```
User Action → Database Query → Database Write → Page Refresh → Updated Display
```

**Issues with Current Approach:**
1. Every validation action requires page refresh
2. Multiple database queries for validation status checks
3. No immediate visual feedback
4. Complex state synchronization between matrix and detail views

## Proposed Architecture: GUI-Based Validation

### New Data Flow

```
Load Data → Session Cache → Local State Changes → Immediate UI Update → Async DB Sync
```

### Core Principles

1. **Session-Based Data Loading**: Load once, work locally
2. **Immediate UI Feedback**: Validation changes instantly visible
3. **Asynchronous Persistence**: Background database writes
4. **Local State Management**: GUI maintains validation state
5. **Optimistic Updates**: UI updates immediately, handle failures gracefully

## Implementation Plan

### Phase 1: Session-Based Data Architecture

#### 1.1 Enhanced Session State Management

**File: `app.py`**

Add to session state initialization:
```python
def initialize_session_state():
    # Existing state...
    if 'loaded_data' not in st.session_state:
        st.session_state.loaded_data = {
            'comprehensive_results': None,
            'validations': {},  # Key: (pharmacy_name, state_code, license_number)
            'loaded_tags': None,
            'last_load_time': None
        }
```

#### 1.2 Load Button and Tag Triplet Management

**New Function: `load_dataset_combination()`**
```python
def load_dataset_combination(pharmacies_tag: str, states_tag: str, validated_tag: str = None):
    """Load complete dataset combination into session state"""
    with st.spinner("Loading dataset combination..."):
        db = get_database_manager()
        
        # Load all data at once
        comprehensive_results = db.get_comprehensive_results(
            states_tag, pharmacies_tag, validated_tag, filter_to_loaded_states=False
        )
        
        # Parse validation state into local dictionary
        validations = {}
        for _, row in comprehensive_results.iterrows():
            if pd.notna(row.get('validation_override_type')):
                key = (row['pharmacy_name'], row['search_state'], 
                       row.get('license_number', '') or '')
                validations[key] = {
                    'override_type': row['validation_override_type'],
                    'reason': row.get('validation_reason', ''),
                    'validated_by': row.get('validation_validated_by', ''),
                    'validated_at': row.get('validation_validated_at')
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
        
        # Ready to work with loaded data locally
```

#### 1.3 Dataset Manager Update

**Replace Current Dataset Manager with Load-Based Approach**

- Replace individual dataset selectors with tag triplet selection
- Add prominent "Load Data" button
- Show current loaded tags and record counts
- Display "Data Loaded" vs "No Data Loaded" status clearly

### Phase 2: Local Validation State Management

#### 2.1 Validation State Functions

**New Functions in `utils/validation_local.py`**
```python
def get_validation_status(pharmacy_name: str, state_code: str, license_number: str = '') -> Dict:
    """Get current validation status from session state"""
    key = (pharmacy_name, state_code, license_number)
    return st.session_state.loaded_data['validations'].get(key, None)

def set_validation_status(pharmacy_name: str, state_code: str, license_number: str, 
                         override_type: str, reason: str = "GUI validation") -> bool:
    """Set validation status in session state and write directly to database"""
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
    key = (pharmacy_name, state_code, license_number)
    
    # Remove from database first (blocking)
    success = remove_validation_from_db(pharmacy_name, state_code, license_number)
    
    if success and key in st.session_state.loaded_data['validations']:
        # Update local state only after successful DB removal
        del st.session_state.loaded_data['validations'][key]
    
    return success
```

#### 2.2 Status Calculation with Local State

**Update Status Bucket Logic**
```python
def calculate_status_with_local_validation(row: pd.Series) -> str:
    """Calculate status bucket using local validation state"""
    pharmacy_name = row['pharmacy_name']
    search_state = row['search_state'] 
    license_number = row.get('license_number', '') or ''
    
    # Check local validation state first
    validation = get_validation_status(pharmacy_name, search_state, license_number)
    if validation:
        if validation['override_type'] == 'present':
            return 'match'  # Validated as present
        elif validation['override_type'] == 'empty':
            return 'no match'  # Validated as empty
    
    # Check for empty validation (state-level)
    empty_validation = get_validation_status(pharmacy_name, search_state, '')
    if empty_validation and empty_validation['override_type'] == 'empty':
        return 'no match'  # State validated as empty
    
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
```

### Phase 3: Instant UI Updates

#### 3.1 Reactive Validation Controls

**New Component: `display_reactive_validation_controls()`**
```python
def display_reactive_validation_controls(result: pd.Series, result_idx: int) -> None:
    """Display validation controls with instant updates"""
    
    pharmacy_name = result.get('search_name', '')
    search_state = result.get('search_state', '')
    license_number = result.get('license_number', '') or ''
    
    # Get current validation status from local state
    current_validation = get_validation_status(pharmacy_name, search_state, license_number)
    is_validated = current_validation is not None
    
    # Validation toggle for search results with license numbers
    if license_number:
        validated = st.checkbox(
            "✅ Validated",
            value=is_validated and current_validation.get('override_type') == 'present',
            key=f"validate_present_{result_idx}",
            disabled=st.session_state.get('validation_system_locked', True),
            help="Mark this search result as validated"
        )
        
        if validated and not (is_validated and current_validation.get('override_type') == 'present'):
            # User just checked - validate as present (blocking write)
            if set_validation_status(pharmacy_name, search_state, license_number, 'present'):
                st.rerun()  # Immediate refresh after successful write
            
        elif not validated and (is_validated and current_validation.get('override_type') == 'present'):
            # User just unchecked - remove validation (blocking write)
            if remove_validation_status(pharmacy_name, search_state, license_number):
                st.rerun()  # Immediate refresh after successful removal
    
    # Empty validation (state-level) check
    empty_validation = get_validation_status(pharmacy_name, search_state, '')
    is_empty_validated = empty_validation and empty_validation.get('override_type') == 'empty'
    
    validated_empty = st.checkbox(
        "🔵 Validated as Empty",
        value=is_empty_validated,
        key=f"validate_empty_{result_idx}",
        disabled=st.session_state.get('validation_system_locked', True),
        help="Mark this pharmacy-state combination as having no valid license"
    )
    
    if validated_empty and not is_empty_validated:
        # User just checked - validate as empty (blocking write)
        if set_validation_status(pharmacy_name, search_state, '', 'empty'):
            st.rerun()  # Immediate refresh after successful write
        
    elif not validated_empty and is_empty_validated:
        # User just unchecked - remove empty validation (blocking write)  
        if remove_validation_status(pharmacy_name, search_state, ''):
            st.rerun()  # Immediate refresh after successful removal
```

#### 3.2 Status Display Updates

**Matrix and Detail Views Use Local State**
- Replace database status with `calculate_status_with_local_validation()`
- Show real-time validation status changes
- Display "pending sync" indicator for unsaved changes

#### 3.3 Complete Warning System Implementation

**Comprehensive Warning Generation per validate_spec.md**
```python
def generate_validation_warnings(pharmacy_name: str, search_state: str, 
                                search_results: List, pharmacy_exists: bool) -> List[Dict]:
    """Generate all validation warnings per validate_spec.md warning system"""
    warnings = []
    
    # Warning Case 4: Pharmacy Not in Current Dataset
    if not pharmacy_exists:
        # Check if any validations exist for this pharmacy
        pharmacy_validations = [v for k, v in st.session_state.loaded_data['validations'].items() 
                               if k[0] == pharmacy_name]
        if pharmacy_validations:
            warnings.append({
                'type': 'pharmacy_not_found',
                'level': 'error',
                'message': f"❌ Validated pharmacy not in current pharmacy dataset\nValidated: {pharmacy_name}",
                'action': "Check if correct pharmacy dataset is selected."
            })
        return warnings  # Skip other checks if pharmacy doesn't exist
    
    # Warning Case 1: Empty Validation + Search Results Found
    empty_validation = get_validation_status(pharmacy_name, search_state, '')
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
    present_validations = [v for k, v in st.session_state.loaded_data['validations'].items() 
                          if k[0] == pharmacy_name and k[1] == search_state and k[2] != '' 
                          and v.get('override_type') == 'present']
    
    for validation_key, validation in st.session_state.loaded_data['validations'].items():
        if (validation_key[0] == pharmacy_name and validation_key[1] == search_state 
            and validation_key[2] != '' and validation.get('override_type') == 'present'):
            
            license_number = validation_key[2]
            # Check if this validated license exists in search results
            found_in_results = any(r.get('license_number') == license_number for r in search_results)
            
            if not found_in_results:
                warnings.append({
                    'type': 'present_validation_not_found',
                    'level': 'warning', 
                    'message': f"⚠️ Validated license not found in search results\nValidated: {pharmacy_name}, {search_state}, {license_number}",
                    'action': "Search data may have been updated or license may have been removed."
                })
    
    # Warning Case 2: Present Validation + Search Results Found - Check for Changes
    for result in search_results:
        license_number = result.get('license_number', '') or ''
        if not license_number:
            continue
            
        validation = get_validation_status(pharmacy_name, search_state, license_number)
        if validation and validation.get('override_type') == 'present':
            # Compare current result with validation snapshot (stored in database)
            changes = check_validation_snapshot_changes(pharmacy_name, search_state, license_number, result)
            if changes:
                change_details = ', '.join([f"{field} ({old} → {new})" for field, old, new in changes])
                warnings.append({
                    'type': 'validation_data_changed',
                    'level': 'info',
                    'message': f"📝 Search results changed since validation\nValidated: {pharmacy_name}, {search_state}, {license_number}\nChanges: {change_details}",
                    'action': "Review if validation is still accurate given field changes."
                })
    
    return warnings

def check_validation_snapshot_changes(pharmacy_name: str, search_state: str, 
                                    license_number: str, current_result: Dict) -> List[Tuple[str, str, str]]:
    """Compare current search result with validation snapshot to detect changes"""
    changes = []
    
    try:
        # Get validation snapshot from database
        from .database import DatabaseManager
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
        
        # Compare key fields
        compare_fields = [
            ('address', 'address'),
            ('license_status', 'license_status'), 
            ('license_name', 'license_name'),
            ('issue_date', 'issue_date'),
            ('expiration_date', 'expiration_date')
        ]
        
        for field, snapshot_field in compare_fields:
            old_val = str(snapshot.get(snapshot_field, 'N/A')) if pd.notna(snapshot.get(snapshot_field)) else 'N/A'
            new_val = str(current_result.get(field, 'N/A')) if pd.notna(current_result.get(field)) else 'N/A'
            
            if old_val != new_val and not (old_val == 'N/A' and new_val == 'N/A'):
                changes.append((field, old_val, new_val))
                
    except Exception as e:
        # Don't fail on snapshot comparison errors, just log
        import logging
        logging.warning(f"Error comparing validation snapshot: {e}")
    
    return changes
```

### Phase 4: Simple Database Writes

#### 4.1 Direct Write System

**Simplified Approach**: Since search_results and pharmacies are read-only after loading, we only need simple blocking writes for validation changes.

**New Functions in `utils/validation_local.py`**
```python
def write_validation_to_db(pharmacy_name: str, state_code: str, license_number: str, 
                          override_type: str, reason: str = "GUI validation") -> bool:
    """Write validation directly to database (blocking operation)"""
    try:
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
```

### Phase 5: Enhanced User Experience

#### 5.1 Simplified Visual Feedback

**Status Indicators**
- ✅ Success messages for completed validations (already shown by write functions)
- ❌ Error messages for failed database operations
- 📊 "Reload Data" button for manual refresh when needed

#### 5.2 Verified Filter Checkbox

**New Filter Option in Results Matrix**
```python
# Add to results matrix filters
show_verified_only = st.checkbox(
    "Show only verified results", 
    False,
    help="Filter to show only validated pharmacy-state combinations"
)

if show_verified_only:
    # Filter to results with local validation status
    filtered_data = filtered_data[
        filtered_data.apply(lambda row: 
            get_validation_status(row['pharmacy_name'], row['search_state'], 
                                row.get('license_number', '') or '') is not None, 
            axis=1)
    ]
```

#### 5.3 Complete Warning System Display

**Top-Level Warnings Section per validate_spec.md**
```python
def display_validation_warnings_section():
    """Display comprehensive validation warnings at top of Results Matrix"""
    if 'loaded_data' not in st.session_state or not st.session_state.loaded_data.get('comprehensive_results'):
        return
    
    all_warnings = []
    comprehensive_results = st.session_state.loaded_data['comprehensive_results']
    
    # Group results by pharmacy-state for warning analysis
    pharmacy_state_groups = comprehensive_results.groupby(['pharmacy_name', 'search_state'])
    
    for (pharmacy_name, search_state), group in pharmacy_state_groups:
        # Check if pharmacy exists in current dataset
        pharmacy_exists = not group['pharmacy_address'].isna().all()
        
        # Get search results for this pharmacy-state
        search_results = group[group['latest_result_id'].notna()].to_dict('records')
        
        # Generate warnings
        warnings = generate_validation_warnings(pharmacy_name, search_state, search_results, pharmacy_exists)
        all_warnings.extend(warnings)
    
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
```

**Warning Integration in Results Matrix**
- Call `display_validation_warnings_section()` at the top of Results Matrix
- Warnings calculated from loaded data using local validation state
- No additional database queries required
- Real-time updates as validation state changes

## Implementation Requirements

### Files to Read/Modify

1. **Core Application (`app.py`)**
   - Session state management enhancement
   - Load button implementation
   - Page integration with local validation

2. **Database Utilities (`utils/database.py`)** 
   - Enhanced data loading functions
   - Local state integration
   - Sync helper functions

3. **Display Components (`utils/display.py`)**
   - Reactive validation controls
   - Status calculation with local state
   - Warning generation and display

4. **Validation Logic (`imports/validated.py`)**
   - Async sync interface
   - Batch operation support
   - Enhanced error handling

5. **New File (`utils/validation_local.py`)**
   - Local state management functions
   - Status calculation logic
   - Warning generation system

### Database Schema Considerations

**Current Schema**: Already supports the validation system
- No schema changes required
- `validated_overrides` table structure remains the same
- Natural key constraints still enforced

**Simplifications**:
- Remove unused database query methods (`get_results_matrix()` legacy function)
- Keep only GUI-required database operations
- Single-record operations only (no batching needed)

### Testing Strategy

#### Unit Tests
- Local state management functions
- Status calculation accuracy
- Direct database write operations
- Warning generation logic

#### Integration Tests  
- End-to-end validation workflows
- Database write consistency
- Session state persistence
- Error handling and recovery

#### User Experience Tests
- Immediate UI feedback verification
- Performance with large datasets
- Manual refresh scenarios
- Data consistency across views

## Migration Strategy

### Phase-by-Phase Rollout

1. **Phase 1**: Implement session-based data loading (non-breaking)
2. **Phase 2**: Add local validation state management (feature flag)
3. **Phase 3**: Replace validation controls with reactive versions
4. **Phase 4**: Implement background sync system
5. **Phase 5**: Full UX enhancements and optimization

### Rollback Plan

- Keep existing database-driven validation as fallback
- Feature flag to switch between old/new systems
- Data consistency verification between approaches
- Easy revert path if issues discovered

## Expected Benefits

### Performance Improvements
- **Eliminate Database Roundtrips**: No per-result validation queries
- **Instant UI Updates**: No page refreshes required
- **Reduced Server Load**: Simple blocking writes instead of complex queries
- **Better Responsiveness**: Local state operations much faster

### User Experience Improvements  
- **Immediate Feedback**: Changes visible instantly
- **Seamless Workflow**: No interruptions from page refreshes
- **Complete Warning System**: All 4 warning cases from validate_spec.md implemented
- **Real-time Status Updates**: Validation status reflects immediately in matrix and details

### System Architecture Improvements
- **Separation of Concerns**: UI state separate from persistence
- **Better Error Handling**: Direct feedback from database operations
- **Simplified Codebase**: Removal of unused legacy database methods
- **Complete Specification Coverage**: Full implementation of validate_spec.md requirements

## Potential Challenges

### Technical Challenges
- **Session Management**: Large datasets in session state memory usage
- **Database Writes**: Ensuring blocking operations don't impact user experience  
- **Error Recovery**: Graceful handling of write failures
- **Data Consistency**: Local state matches database after operations

### User Experience Challenges  
- **Performance Expectations**: Managing user expectations during large data loads
- **Error Communication**: Clear feedback when database operations fail
- **Manual Refresh**: Users understanding when to reload data

### Mitigation Strategies
- Efficient session state management
- Clear error messages with retry options
- Performance monitoring for load operations
- Simple "Reload Data" mechanism

## Success Criteria

1. **Zero Page Refreshes**: Validation actions update UI immediately (except initial load)
2. **Fast Data Loading**: Dataset combination loads in <5 seconds
3. **Reliable Database Writes**: >99% success rate for validation operations
4. **User Satisfaction**: Positive feedback on improved workflow  
5. **Performance Metrics**: Reduced database query load by >50%
6. **Simplified Architecture**: Removal of unused legacy database methods

This plan provides a comprehensive roadmap for implementing GUI-based validation while maintaining data integrity and improving user experience significantly.