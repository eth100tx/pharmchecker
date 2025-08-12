# PharmChecker Validation Specification

## Overview
This document specifies the complete validation system logic, database interactions, and API flows for PharmChecker. Validation allows manual override of search results and empty records using natural keys (pharmacy names + state codes/license numbers) without internal ID dependencies.

## Core Principles

### 1. Natural Key Design
- **No Internal ID Dependencies**: `validated_overrides` uses `pharmacy_name`, `state_code`, and `license_number` as natural keys
- **Dataset Independence**: Validation datasets can be applied to any search dataset via tags  
- **Switchable Validation**: Users can change validation datasets to apply different validation rules to the same search data

### 2. Validation Types (override_type field values)
- **"present"**: Confirms a license exists for a pharmacy in a state with a specific license number
- **"empty"**: Confirms no license exists for a pharmacy in a state (no license number required)

## User Validation Cases

From the user perspective, there are only **2 cases** based on what they see:

### Case 1: Empty Results - "Validate as Empty"

**Scenario**: No search results found OR no data loaded for this pharmacy/state combination.

**User Sees**: 
- "No search results available" message in detailed view
- OR "No Data Loaded" status in results matrix

**User Action**: Click "Validate as Empty" button in Pharmacy Info section

**GUI Button Text**: "Validate as Empty"

**Database Operations**:
1. **Lookup Key**: `(pharmacy_name, state_code, NULL)` 
2. **API Call**: `ValidatedImporter.create_validation_record()`
   - `pharmacy_name`: From pharmacy record
   - `state_code`: Target state being validated
   - `license_number`: `NULL` (empty validation)
   - `override_type`: "empty"
   - Snapshot: Minimal data (no search result to snapshot)
3. **Database INSERT**:
   ```sql
   INSERT INTO validated_overrides (
       dataset_id, pharmacy_name, state_code, license_number,
       override_type, reason, validated_by, validated_at
   ) VALUES (dataset_id, 'BPI Labs', 'FL', NULL, 'empty', reason, user, now())
   ```

**Result**:
- Record inserted with `override_type = "empty"` and `license_number = NULL`
- Status shows 🔵 "Validated Empty" in results matrix

---

### Case 2: Search Results with License Number - "Validate"

**Scenario**: User has search results showing license data and wants to validate it as correct.

**User Sees**: 
- Search result with license number, name, address, dates, etc.
- All the license information is displayed

**User Action**: Click "Validate" toggle on search result

**GUI Button Text**: "Validate"

**Preconditions**:
- Search result exists with `pharmacy_name`, `state_code`, and `license_number`
- License number is not empty/null

**Database Operations**:
1. **Lookup Key**: `(pharmacy_name, state_code, license_number)`
2. **API Call**: `ValidatedImporter.create_validation_record()`
   - `pharmacy_name`: From search result
   - `state_code`: From search result  
   - `license_number`: From search result (must be non-empty)
   - `override_type`: "present"
   - Snapshot: Captures current search result data
3. **Database INSERT**:
   ```sql
   INSERT INTO validated_overrides (
       dataset_id, pharmacy_name, state_code, license_number,
       license_status, license_name, address, city, state, zip,
       issue_date, expiration_date, result_status,
       override_type, reason, validated_by, validated_at
   ) VALUES (...) 
   ON CONFLICT (dataset_id, pharmacy_name, state_code, license_number) 
   DO UPDATE SET ...
   ```

**Result**: 
- Record inserted with `override_type = "present"`
- Status shows 🔵 "Validated" in results matrix
- Snapshot preserves search result state at validation time

---

### Case 3: No Validation Dataset Selected - Auto-Create

**Scenario**: User wants to validate (either case 1 or 2) but no validation dataset is currently selected.

**User Sees**: 
- Current Dataset Context shows "Validated: Not selected"

**User Action**: Click "Validate" or "Validate as Empty" with no validation dataset selected

**GUI Response**: Auto-create workflow
1. **Generate Dataset Tag**: `validation_YYYYMMDD_HHMMSS` (e.g., `validation_20250810_153132`)
2. **Create Dataset**: Call `ValidatedImporter.create_dataset()`
3. **Update GUI**: 
   - Show success message: "✨ Created validation dataset: {tag}"
   - Update session state: `st.session_state.selected_datasets['validated'] = tag`
   - Clear dataset cache to refresh selectors
4. **Proceed with Validation**: Continue with normal validation workflow (Case 1 or 2)

**Database Operations**:
1. **Create Dataset**:
   ```sql
   INSERT INTO datasets (kind, tag, description, created_by, created_at)
   VALUES ('validated', 'validation_20250810_153132', 'Auto-created validation dataset', 'gui_user', now())
   ```
2. **Get Dataset ID**: Retrieve newly created `dataset_id`
3. **Create Validation Record**: Proceed with normal validation record creation

**Result**:
- New validation dataset created and selected
- Validation record created in new dataset
- GUI shows updated dataset context with new validation dataset
- User can continue validating other records into the same dataset

---

### Error Case: Search Results Without License Number

**Scenario**: Search result exists but has no license number.

**User Action**: Click "Validate" toggle on search result without license number

**API Response**: **ERROR**
- Message: "Cannot validate without license number. Use 'Validate as Empty' instead."
- No database operation performed

**Rationale**: Present validation requires a specific license number. Without it, user should use empty validation instead.

---

## Unvalidation (Removal) Cases

### Case A: Remove Present Validation

**User Action**: Click "Validate" toggle to OFF on previously validated search result

**Database Operations**:
1. **Lookup Key**: `(dataset_id, pharmacy_name, state_code, license_number)`
   - Uses the exact license number from the search result
2. **API Call**: `ValidatedImporter.remove_validation_record()`
3. **Database DELETE**:
   ```sql
   DELETE FROM validated_overrides 
   WHERE dataset_id = ? AND pharmacy_name = ? AND state_code = ? AND license_number = ?
   ```

**Debug Info**: Log should show:
```
Attempting to remove present validation: {pharmacy_name} - {state_code} - {license_number}
Dataset: {validated_tag} (ID: {dataset_id})
Query: DELETE FROM validated_overrides WHERE dataset_id = {dataset_id} AND pharmacy_name = '{pharmacy_name}' AND state_code = '{state_code}' AND license_number = '{license_number}'
Found {rowcount} records to delete
Result: {success/failure}
```

---

### Case B: Remove Empty Validation

**User Action**: Click "Validate as Empty" toggle to OFF

**Database Operations**:
1. **Lookup Key**: `(dataset_id, pharmacy_name, state_code, NULL)`
   - Specifically looks for `license_number IS NULL`
2. **API Call**: `ValidatedImporter.remove_validation_record()`
3. **Database DELETE**:
   ```sql
   DELETE FROM validated_overrides 
   WHERE dataset_id = ? AND pharmacy_name = ? AND state_code = ? AND license_number IS NULL
   ```

**Debug Info**: Log should show:
```
Attempting to remove empty validation: {pharmacy_name} - {state_code}
Dataset: {validated_tag} (ID: {dataset_id})
Query: DELETE FROM validated_overrides WHERE dataset_id = {dataset_id} AND pharmacy_name = '{pharmacy_name}' AND state_code = '{state_code}' AND license_number IS NULL
Found {rowcount} records to delete
Result: {success/failure}
```

---

## Database Schema Requirements

### validated_overrides Table Structure
```sql
CREATE TABLE validated_overrides (
  id               SERIAL PRIMARY KEY,
  dataset_id       INT NOT NULL REFERENCES datasets(id),
  
  -- Natural key fields
  pharmacy_name    TEXT NOT NULL,
  state_code       CHAR(2) NOT NULL, 
  license_number   TEXT,  -- NULL for empty validations
  
  -- Snapshot fields (from search_results at validation time)
  license_status   TEXT,
  license_name     TEXT,
  address          TEXT,
  city             TEXT,
  state            TEXT,
  zip              TEXT,
  issue_date       DATE,
  expiration_date  DATE,
  result_status    TEXT,
  
  -- Validation metadata
  override_type    TEXT NOT NULL CHECK (override_type IN ('present','empty')),
  reason           TEXT,
  validated_by     TEXT,
  validated_at     TIMESTAMP NOT NULL DEFAULT now(),
  
  -- Natural key constraint
  CONSTRAINT unique_validated_override UNIQUE (dataset_id, pharmacy_name, state_code, license_number)
);
```

### Key Constraints
- **Present Validations**: `(dataset_id, pharmacy_name, state_code, license_number)` where `license_number` is NOT NULL
- **Empty Validations**: `(dataset_id, pharmacy_name, state_code, NULL)` where `license_number` IS NULL
- **One Empty Per Pharmacy/State**: Only one empty validation allowed per `(dataset_id, pharmacy_name, state_code)` with NULL license_number

---

## API Functions Specification

### ValidatedImporter.create_validation_record()
```python
def create_validation_record(
    dataset_id: int,
    pharmacy_name: str, 
    state_code: str,
    license_number: str,  # Empty string for empty validations -> converted to NULL
    override_type: str,   # 'present' or 'empty'
    reason: str,
    validated_by: str
) -> bool
```

**Logic**:
1. If `override_type == 'present'` and `license_number` is empty: **RAISE ERROR**
2. If `override_type == 'empty'`: Set `license_number = NULL` in database
3. Get search result snapshot (if exists)
4. INSERT with ON CONFLICT handling
5. COMMIT transaction

### ValidatedImporter.remove_validation_record()
```python
def remove_validation_record(
    dataset_id: int,
    pharmacy_name: str,
    state_code: str, 
    license_number: str  # Empty string for empty validations
) -> bool
```

**Logic**:
1. If `license_number` is empty string: Query with `license_number IS NULL`
2. If `license_number` has value: Query with exact match
3. Log detailed debug info including dataset tag and expected record details
4. DELETE matching record
5. COMMIT transaction
6. Return success/failure with detailed logging

---

## Warning System

The warning system maps the 2x2 matrix of validation types vs search result status:

| Validation Type | Search Results Status | Warning |
|----------------|----------------------|---------|
| "empty" | Not Found | ✅ Working as intended |
| "empty" | Found | ⚠️ **Warning Case 1** |
| "present" | Found | **Check Case 2** |
| "present" | Not Found | ⚠️ **Warning Case 3** |

### Warning Case 1: Empty Validation + Search Results Found
**Trigger**: `override_type = "empty"` AND search results exist for this pharmacy/state

**Warning Message**: 
```
⚠️ Search success for a record "Validated as Empty"
Validated: {pharmacy_name}, {state_code} 
Found: {license_number}, {license_name}, {address}
```

**Action**: Review if empty validation is still correct given new search results.

---

### Warning Case 2: Present Validation + Search Results Found - Check for Changes  
**Trigger**: `override_type = "present"` AND search results exist AND snapshot differs from current

**Warning Message**:
```
📝 Search results changed since validation
Validated: {pharmacy_name}, {state_code}, {license_number}
Changes: address ({old_address} → {new_address}), license_status ({old_status} → {new_status})
```

**Logic**: Compare validation snapshot fields against current search result fields:
- `address`, `license_status`, `license_name`, `issue_date`, `expiration_date`, etc.
- Only show fields that actually changed

**Action**: Review if validation is still accurate given field changes.

---

### Warning Case 3: Present Validation + No Search Results
**Trigger**: `override_type = "present"` AND no search results found for this pharmacy/state/license combination

**Warning Message**:
```
⚠️ Validated license not found in search results  
Validated: {pharmacy_name}, {state_code}, {license_number}
```

**Action**: Search data may have been updated or license may have been removed.

---

### Warning Case 4: Pharmacy Not in Current Dataset
**Trigger**: Validation references pharmacy not in current pharmacy dataset

**Warning Message**:
```
❌ Validated pharmacy not in current pharmacy dataset
Validated: {pharmacy_name}
```

**Action**: Check if correct pharmacy dataset is selected.

---

## GUI Integration Points

### Results Matrix Display
- **Status Priority**: Validation status overrides search status
  - `override_type = 'present'` → 🔵 "Validated"
  - `override_type = 'empty'` → 🔵 "Validated Empty"
- **Warnings**: Display alongside status with appropriate icons

### Detail View Controls
- **Search Records**: "Validate" toggle (simplified from "Validate as Present")
- **Empty Records**: "Validate as Empty" button in Pharmacy Info section
- **Lock System**: All validation controls disabled when locked

### Dataset Management  
- **Auto-Creation**: Create `validation_YYYYMMDD_HHMMSS` datasets when needed
- **Session State**: Update selected validation dataset after creation
- **Cache Management**: Clear dataset cache to refresh selectors

---

## Error Handling

### User Errors
1. **Present validation without license number**: Clear error message directing to empty validation
2. **No validation dataset selected**: Auto-create with timestamp
3. **Database connection issues**: Graceful degradation with error messages

### System Errors
1. **Transaction failures**: Full rollback with error logging
2. **Constraint violations**: Handle gracefully with user feedback
3. **Missing datasets**: Auto-recovery or clear error messages

---

## Testing Scenarios

### Happy Path Tests
1. **Present Validation Flow**: Search record → validate → verify database → unvalidate → verify removal
2. **Empty Validation Flow**: No search record → validate empty → verify database → unvalidate → verify removal  
3. **Dataset Auto-Creation**: No validation dataset → validate → verify new dataset created and selected

### Edge Case Tests
1. **License Number Edge Cases**: Empty strings, nulls, whitespace
2. **Validation Conflicts**: Multiple validations for same pharmacy/state
3. **Dataset Switching**: Apply validation dataset to different search data
4. **Transaction Failures**: Network issues, constraint violations

### Error Case Tests
1. **Invalid Present Validation**: Try to validate present without license number
2. **Missing Data**: Pharmacy not found, invalid state codes
3. **Permission Issues**: Database access problems

This specification ensures robust validation handling with clear separation of concerns and comprehensive error handling.

---

## Implementation Learnings and Fixes

### Critical Bugs Discovered During Implementation

#### 1. Database Transaction Missing Commit
**Issue**: `ValidatedImporter.create_validation_record()` was missing `self.conn.commit()`
- **Symptom**: Success message shown but no record in database
- **Root Cause**: Database transactions not committed
- **Fix**: Added `self.conn.commit()` after INSERT and `self.conn.rollback()` in exception handler
- **Impact**: Validation records now properly persist to database

#### 2. Empty Validation Removal Logic Error
**Issue**: `remove_validation_record()` used `license_number = NULL` instead of `license_number IS NULL`
- **Symptom**: "No validation found to remove" for empty validations
- **Root Cause**: SQL `= NULL` never matches, should use `IS NULL`
- **Fix**: Added conditional logic for empty vs present validation removal:
  ```sql
  -- Empty validation removal
  WHERE license_number IS NULL
  -- Present validation removal  
  WHERE license_number = 'actual_value'
  ```

#### 3. Wrong State Field Used for Present Validations
**Issue**: Used `result.get('state')` instead of `result.get('search_state')`
- **Symptom**: Beaker PA search created validation for TX instead of PA
- **Root Cause**: Confused license registration state with search conducted state
- **Fix**: Changed to `result.get('search_state')` for validation context
- **Impact**: Validations now correctly track search context, not license location

#### 4. Detailed View Missing Validation Status
**Issue**: Detailed view showed "Not Validated" despite records existing in database
- **Symptom**: Results matrix showed validation, detailed view showed "Not Validated"
- **Root Cause**: `get_search_results()` doesn't JOIN with validated_overrides table
- **Fix**: Added active validation lookup in `display_detailed_validation_controls()`:
  ```python
  validation_sql = """
  SELECT vo.override_type, vo.dataset_id, d.tag
  FROM validated_overrides vo
  JOIN datasets d ON vo.dataset_id = d.id
  WHERE d.tag = %s AND vo.pharmacy_name = %s AND vo.state_code = %s
    AND (%s = '' AND vo.license_number IS NULL OR vo.license_number = %s)
  """
  ```

### Enhanced Debug Logging Implementation

**Added comprehensive logging per specification**:
```python
self.logger.info(f"Attempting to remove empty validation: {pharmacy_name} - {state_code}")
self.logger.info(f"Dataset: {dataset_tag} (ID: {dataset_id})")
self.logger.info(f"Query: {debug_query}")
self.logger.info(f"Found {rowcount} records to delete")
self.logger.info(f"Result: {success/failure}")
```

### License Number Validation Enhancement

**Added input validation per specification**:
```python
if override_type == 'present' and (not license_number or license_number.strip() == ''):
    raise ValueError("Cannot validate as present without license number. Use 'Validate as Empty' instead.")
```

### GUI Debug Features

**Added debug dataset information display**:
- Shows validation dataset tag and ID when `debug_mode = True`
- Helps troubleshoot which validation dataset is being used
- Format: `✅ Present (Dataset: validation_20250810_161816, ID: 19)`

### Key Architecture Insights

#### 1. Search Context vs License Location
- **Validation Context**: Always use `search_state` (where search was conducted)
- **License Location**: Field `state` in search results (where license is registered)
- **Natural Key**: `(pharmacy_name, search_state, license_number)` for validation

#### 2. NULL Handling in Database
- **Empty Validations**: Store `license_number` as `NULL`
- **Query Logic**: Use `IS NULL` for empty, exact match for present
- **API Interface**: Accept empty string `""`, convert to `NULL` for database

#### 3. Validation Status Display Consistency
- **Results Matrix**: Gets validation data from `get_results_matrix()` (includes JOINs)
- **Detailed View**: Must actively lookup validation status via separate query
- **Solution**: Active lookup ensures consistency across all views

#### 4. Transaction Management
- **Create Operations**: Must include `self.conn.commit()`
- **Error Handling**: Always include `self.conn.rollback()` in exception handlers
- **Testing**: Verify database state after operations, not just return values

### Testing Strategy Learnings

#### Essential Test Cases
1. **End-to-End Workflow**: Create → Verify in DB → Remove → Verify removal
2. **State Field Validation**: Ensure search_state used, not license state
3. **NULL vs Empty String**: Test empty validation creation and removal
4. **Cross-View Consistency**: Test validation status in both matrix and detailed views
5. **Error Cases**: Test present validation without license number

#### Database Verification
```python
# Always verify actual database state, not just API return values
with importer.conn.cursor() as cur:
    cur.execute('SELECT * FROM validated_overrides WHERE ...')
    results = cur.fetchall()
    assert len(results) == expected_count
```

This implementation experience demonstrates the importance of comprehensive testing, proper transaction handling, and careful attention to data model semantics in validation systems.

---

## 2024 GUI Simplification Implementation

### System Architecture Changes

Following validation system simplification in 2024, the architecture was redesigned per `validation_internal_dataflow.md`:

#### Simplified Session State Structure
```python
# Before: Complex validation cache with state synchronization
# After: Simple DataFrames cached until reload
st.session_state.loaded_data = {
    'comprehensive_results': pd.DataFrame,  # Search results + pharmacies
    'pharmacies_data': pd.DataFrame,        # Pharmacy records  
    'validations_data': pd.DataFrame,       # Validation overrides
    'loaded_tags': {...},
    'last_load_time': datetime
}
```

#### Single Validation Check Function
```python
def is_validated(pharmacy_name: str, state_code: str, license_number: str = '') -> bool:
    """Simple validation check using cached validation data"""
    validations_data = st.session_state.loaded_data.get('validations_data')
    if validations_data is None or validations_data.empty:
        return False
    
    # Check cached validation data directly
    if license_number:  # Present validation
        matches = validations_data[
            (validations_data['pharmacy_name'] == pharmacy_name) &
            (validations_data['state_code'] == state_code) &
            (validations_data['license_number'] == license_number)
        ]
    else:  # Empty validation  
        matches = validations_data[
            (validations_data['pharmacy_name'] == pharmacy_name) &
            (validations_data['state_code'] == search_state) &
            (validations_data['license_number'].isna())
        ]
    
    return not matches.empty
```

#### Simplified Status Calculation
```python
def calculate_status_simple(row):
    """Single status calculation function - prioritizes validation over score"""
    pharmacy_name = row.get('pharmacy_name')
    search_state = row.get('search_state')
    license_number = row.get('license_number', '') or ''
    
    # Check if validated using cached data (HIGHEST PRIORITY)
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

### Enhanced Warning System Implementation (2024)

#### Comprehensive Field-Level Change Detection

The warning system was enhanced to provide detailed field-by-field comparison:

**Database Integration**:
```python
def _calculate_warnings(self, row, full_df: pd.DataFrame) -> List[str]:
    """Calculate warnings using cached validation data"""
    # Access validation data from session state
    validations_data = st.session_state.loaded_data.get('validations_data')
    
    # Find matching validation record
    validation_match = validations_data[
        (validations_data['pharmacy_name'] == pharmacy_name) &
        (validations_data['state_code'] == search_state) &
        (validations_data['license_number'] == license_number)
    ]
    
    # Compare snapshot vs current data
    field_comparisons = [
        ('license_status', 'license_status'),
        ('address', 'result_address'),
        ('city', 'result_city'), 
        ('state', 'result_state'),
        ('zip', 'result_zip'),
        ('expiration_date', 'expiration_date')
    ]
    
    changed_fields = []
    for validation_field, current_field in field_comparisons:
        snapshot_value = validation_record.get(validation_field)
        current_value = row.get(current_field)
        
        if str(snapshot_value).strip() != str(current_value).strip():
            changed_fields.append(validation_field)
    
    if changed_fields:
        return [f'Validated data changed: {", ".join(changed_fields)}']
```

#### Compact GUI Warning Display

**Integrated into Loaded Data Info Box**:
```
Loaded Data: test_pharmacies + states_baseline + validation_20250811_154105 | Validations: 3 | ⚠️ 1 Warnings
```

**Yellow Warning Panels with Expandable Details**:
```
⚠️ Belmar (PA) - Validation data changed
📋 Show details for Belmar PA NP002169

Field Changes Detected:

Address:
🕒 Validated: 2501 LAKEPOINTE PARKWAY    🔍 Current: 2500 LAKEPOINTE PARKWAY

Action Required: Review current search results and update validation if changes are correct, 
or investigate if data changed unexpectedly.
```

#### Real-World Example: Address Change Detection

**Actual Implementation Test Case**:
- **Pharmacy**: Belmar  
- **State**: PA
- **License**: NP002169
- **Detected Change**: Address "2501 LAKEPOINTE PARKWAY" → "2500 LAKEPOINTE PARKWAY"
- **Warning Generated**: "Validated data changed: address"
- **GUI Display**: Side-by-side comparison showing exact difference

### GUI Simplification Benefits Achieved

#### 1. Eliminated Complex State Management
- ❌ Removed: Complex validation cache with synchronization
- ❌ Removed: Multiple status calculation functions  
- ❌ Removed: Warning indicator icons on validation badges
- ✅ Added: Simple cached DataFrames until reload
- ✅ Added: Single source of truth (database)

#### 2. Improved User Experience
- **Results Matrix**: Shows validated status instead of percentage scores for validated records
- **Detail View Titles**: "Result 2: NP000382 - BELMAR PHARMACY 🔵 Validated" instead of "(26.1% match)"
- **Single Validation Toggle**: One "✅ Validate" checkbox instead of separate "Validated" and "Validated as Empty" options
- **Auto-Navigation**: Automatically go to Results Matrix after loading data
- **Smart Expanders**: Single records auto-open, multiple records stay closed for selection

#### 3. Validation Priority Logic
**Matrix Aggregation Priority (Fixed)**:
```python
# Priority 1: Look for validated record first (HIGHEST PRIORITY)
for idx, row in group.iterrows():
    license_number = row.get('license_number', '') or ''
    if is_validated(pharmacy_name, search_state, license_number):
        validated_row = row
        break

# Priority 2: Best score (if no validation)
if validated_row is None:
    best_row = group.loc[scores_filled.idxmax()]
```

### Updated Warning Categories (2024)

#### Category 1: Data Changed Since Validation
**Trigger**: Validation snapshot differs from current search results  
**Display**: `⚠️ Belmar (PA) - Validation data changed`  
**Details**: Field-by-field comparison showing exact changes  
**Action**: Review and re-validate if changes are correct

#### Category 2: Empty Validation but Results Found  
**Trigger**: `override_type = "empty"` but search results now exist  
**Display**: `⚠️ Pharmacy (State) - Validated empty but results now exist`  
**Action**: Update validation since data situation has changed

#### Category 3: Present Validation but Results Missing
**Trigger**: `override_type = "present"` but no search results found  
**Display**: `⚠️ Pharmacy (State) - Validated present but result not found`  
**Action**: Check if license was revoked or moved

### Implementation Verification

**Test Case: Address Change Detection**
```
🔍 Warning check for: Belmar PA NP002169
  📋 Validation data loaded: 3 records
  🔍 Validation matches found: 1
  ✅ Found validation record: present
  🔍 Checking field changes for present validation...
    🔍 address: '2501 LAKEPOINTE PARKWAY' vs '2500 LAKEPOINTE PARKWAY'
      ⚠️ CHANGE DETECTED: '2501 LAKEPOINTE PARKWAY' != '2500 LAKEPOINTE PARKWAY'
  ⚠️ WARNING: Validated data changed: address
```

This comprehensive implementation provides robust validation warnings with precise field-level change detection while maintaining a clean, simplified user interface focused on actionable information.