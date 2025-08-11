# PharmChecker Validation Internal Dataflow Documentation (SIMPLIFIED)

## Overview

This document provides the **simplified** technical dataflow for the PharmChecker validation system after removing architectural complexities. The GUI is now a simple viewer with minimal state management.

## High-Level Flow Summary (Simplified)

```
Raw Datasets → Load from Database → Simple Validation Lookup → Display Results → User Toggle → DB Write + Reload
```

## Core Data Structures (Simplified)

### 1. Database Tables

**`validated_overrides` Table (Source of Truth):**
```sql
id               SERIAL PRIMARY KEY
dataset_id       INT (references datasets.id)
pharmacy_name    TEXT NOT NULL
state_code       CHAR(2) NOT NULL
license_number   TEXT (NULL for empty validations)
license_status   TEXT (snapshot data)
license_name     TEXT (snapshot data)
address          TEXT (snapshot data)
city             TEXT (snapshot data)
state            TEXT (snapshot data)  
zip              TEXT (snapshot data)
issue_date       DATE (snapshot data)
expiration_date  DATE (snapshot data)
result_status    TEXT (snapshot data)
override_type    TEXT ('present' or 'empty')
reason           TEXT
validated_by     TEXT
validated_at     TIMESTAMP
```

**Natural Key:** `(dataset_id, pharmacy_name, state_code, license_number)`

**Note:** Snapshot fields preserved for warning detection - comparing current search results vs validation snapshot.

### 2. Session State Structure (Simplified)

**`st.session_state.loaded_data`:**
```python
{
    'comprehensive_results': pd.DataFrame,  # Search results + pharmacies (cached until reload)
    'pharmacies_data': pd.DataFrame,        # Pharmacy records (cached until reload)
    'validations_data': pd.DataFrame,       # Validation overrides (cached until reload)
    'loaded_tags': {
        'pharmacies': str,
        'states': str, 
        'validated': str|None
    },
    'last_load_time': datetime
}
```

## Simplified Dataflow Steps

### Step 1: Dataset Loading (Simplified)
**Process:**
1. User selects three dataset tags (pharmacies, states, validated)
2. System loads three separate datasets and caches until reload:
   - `get_all_results_with_context(states, pharmacies, None)` - search results + pharmacies
   - `get_pharmacies(pharmacies_tag)` - pharmacy records  
   - `get_validations(validated_tag)` - validation override records
3. Store all three DataFrames in session state (cached until reload)
4. **No database JOINs for validation** - validation logic done in GUI

**Database Queries (Keep Existing):**
- Search results: `get_all_results_with_context()` unchanged
- Pharmacies: Standard pharmacy query unchanged  
- Validations: `SELECT * FROM validated_overrides WHERE dataset_id = ?`

### Step 2: Simple Validation Status Check
**Process:** Single function to check validation status using cached data
```python
def is_validated(pharmacy_name: str, state_code: str, license_number: str = '') -> bool:
    """Simple validation check using cached validation data"""
    validations_data = st.session_state.loaded_data.get('validations_data')
    if validations_data is None or validations_data.empty:
        return False
    
    # Check cached validation data
    if license_number:  # Present validation
        matches = validations_data[
            (validations_data['pharmacy_name'] == pharmacy_name) &
            (validations_data['state_code'] == state_code) &
            (validations_data['license_number'] == license_number)
        ]
    else:  # Empty validation  
        matches = validations_data[
            (validations_data['pharmacy_name'] == pharmacy_name) &
            (validations_data['state_code'] == state_code) &
            (validations_data['license_number'].isna())
        ]
    
    return not matches.empty
```

### Step 3: Warning Generation (Load Only - Required)
**Process:** 
1. Called once when data is first loaded (required, not optional)
2. Compare validation snapshots vs current search results using cached data
3. Display warnings in GUI warning section
4. **No warning indicators on validation icons** - just section display
5. **Warning types:**
   - Empty validation + search results found → Warning
   - Present validation + data changed since validation → Info  
   - Present validation + search results missing → Warning
   - Pharmacy not in current dataset → Error

### Step 4: Results Matrix Display (Simplified)
**Process:**
1. Get comprehensive results from session state  
2. Apply filtering (loaded states, validation enable/disable)
3. **Single status calculation function** using cached validation data
4. Display in dense table with row selection

**Status Calculation Logic (Simplified):**
```python
def calculate_status_simple(row):
    pharmacy_name = row.get('pharmacy_name')
    search_state = row.get('search_state')
    license_number = row.get('license_number', '') or ''
    
    # Check if validated using cached data
    if is_validated(pharmacy_name, search_state, license_number) or \
       is_validated(pharmacy_name, search_state, ''):  # Check empty validation too
        return 'validated'
    
    # Fall back to score-based status
    score = row.get('score_overall')
    if pd.isna(score): return 'no data'
    elif score >= 85: return 'match'
    elif score >= 60: return 'weak match'  
    else: return 'no match'
```

### Step 5: Detailed View Display (Simplified)
**Process:**
1. User selects row from results matrix
2. Display pharmacy info + search results in expandable sections
3. Each search result shows simple validation toggle

**Validation Control Types:**
- **Present Validation:** Checkbox for search results with license numbers  
- **Empty Validation:** Checkbox for pharmacy-state combinations
- **Lock System:** Sidebar lock/unlock controls all validation changes

### Step 6: Validation Toggle Action (Simplified)
**Process:**
1. User clicks validation checkbox
2. **Direct database write** via `ValidatedImporter`  
3. **Reload validation data only** (or full reload if performance not an issue)
4. UI shows updated validation status

**Validation Flow:**
```python
def toggle_validation(pharmacy_name, state_code, license_number, action):
    with ValidatedImporter() as importer:
        if action == 'validate':
            success = importer.create_validation_record(...)
        else:  # unvalidate
            success = importer.remove_validation_record(...)
    
    if success:
        # Option 1: Reload just validation data (optimization)
        reload_validations_only()
        # Option 2: Full reload (simpler, revisit if performance issue)
        load_dataset_combination(current_tags)
        st.rerun()
```

## Simplified Architecture Benefits

### 1. **Single Source of Truth**
- Database is the only state that matters
- No session state caching of validation data
- No synchronization issues between states

### 2. **Single Status Calculation**
- One function: `calculate_status_simple()`
- Status comes from database JOIN, not complex lookups
- Consistent across all UI views

### 3. **Simple Validation Logic**
```python
# Natural database key (same everywhere)
(dataset_id, pharmacy_name, state_code, license_number)

# Simple existence check
EXISTS(SELECT 1 FROM validated_overrides WHERE ...)
```

### 4. **No Warning Complexity**
- Warnings calculated once on load (optional)
- No warning cache or indicator icons
- No dynamic warning updates

### 5. **Simple User Actions**
- User toggles validation → database write → data reload
- Infrequent action, so full reload is acceptable
- No performance optimization complexity

## Data Consistency (Simplified)

### Validation Requirements
1. **Present validations:** Must have non-empty license_number
2. **Empty validations:** Must have license_number = NULL  
3. **Natural key uniqueness:** One validation per key
4. **No snapshot data:** Just override flags

### UI Consistency  
- Single status calculation function ensures consistency
- Database JOIN provides validation status directly
- No caching = no stale data issues

## Implementation Summary

The simplified validation system:

1. **Loads data** via database JOIN including validation status
2. **Displays status** using single calculation function  
3. **Handles toggles** with direct database write + full reload
4. **No caching** - GUI is pure viewer of database state
5. **Optional warnings** calculated once on load, no indicators

**Key Simplifications:**
- ❌ No session state validation cache
- ❌ No warning indicator icons  
- ❌ No complex state synchronization
- ❌ No multiple status calculation functions
- ✅ Simple database queries
- ✅ Single source of truth
- ✅ Consistent status display