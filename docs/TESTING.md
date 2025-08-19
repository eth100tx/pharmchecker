# PharmChecker Testing Guide

## Overview

PharmChecker includes comprehensive testing capabilities to ensure system reliability and data accuracy. This guide covers all testing procedures from development through production deployment.

**Backend Support:** PharmChecker now uses Supabase exclusively for simplified deployment and management. All testing procedures assume Supabase backend.

## Test Suite Components

### 1. System Test (`system_test.py`)

Complete end-to-end validation of the entire workflow.

**What it tests:**
- Database initialization
- Pharmacy data import
- State search import
- Score computation
- Results aggregation
- Expected vs. actual outcomes

**Run the test:**
```bash
python system_test.py
```

### 2. Export/Import Round-Trip Tests (`unit_tests/test_export_import.py`)

Validates CSV export/import functionality for all dataset types.

**What it tests:**
- Pharmacy CSV export/import cycle
- States CSV export/import cycle  
- Validated CSV export/import cycle
- Data integrity across round-trips
- Schema validation

**Run the tests:**
```bash
# Test specific dataset type
python unit_tests/test_export_import.py --type pharmacies --tag pharmacies_sample_data
python unit_tests/test_export_import.py --type states --tag states_sample_data
python unit_tests/test_export_import.py --type validated --tag validated_sample_data

# Run comprehensive tests
python unit_tests/test_export_import.py --type all
```

**Expected output:**
```
PharmChecker End-to-End System Test
==================================================
✅ Clean existing test data
✅ Import pharmacy data
✅ Import state search data
✅ Query initial results
✅ Run scoring engine
✅ Query final results

Overall Success: ✅ PASS
```

**Test Data:**
- 3 test pharmacies with known addresses
- 5 search results with varying matches
- Expected scores: 96.5 (match), 66.5 (weak), 39.4 (no match)

### 3. Scoring Test (`test_scoring.py`)

Validates the address matching algorithm accuracy.

**What it tests:**
- Street address normalization
- City/state/ZIP matching
- Score calculation formula
- Edge cases (suites, abbreviations)

**Run the test:**
```bash
python test_scoring.py
```

**Test Cases:**
```python
# Perfect match
assert score("123 Main St", "123 Main Street") >= 95

# Same street, different city  
assert 60 <= score("123 Main St, Orlando", "123 Main St, Tampa") <= 70

# Completely different
assert score("123 Main St", "456 Oak Ave") < 40
```

### 4. GUI Test (`test_gui.py`)

Tests Streamlit interface components.

**What it tests:**
- Dataset loading
- Results display
- Filter functionality
- Export capabilities
- Session management

**Run the test:**
```bash
python test_gui.py
```

## Manual Testing Procedures

### Quick Test Data Setup

All test datasets can be imported automatically:

```bash
# Import all sample datasets for testing
make import_sample_data

# Import individual datasets
make import_pharmacies_sample_data
make import_states_sample_data  
make import_validated_sample_data

# Check status
make status
```

### Data Import Testing

#### Test Pharmacy CSV Import
```bash
# Prepare test CSV
cat > test_pharmacies.csv << EOF
name,address,city,state,zip,state_licenses
"Test Pharmacy 1","123 Main St","Orlando","FL","32801","[\"FL\",\"GA\"]"
"Test Pharmacy 2","456 Oak Ave","Miami","FL","33101","[\"FL\"]"
EOF

# Import with API importer (simplified - no batch size needed)
python -m imports.api_importer pharmacies test_pharmacies.csv "test_$(date +%s)" --backend supabase

# Verify import
make status
```

#### Test States CSV Import
```bash
# Export existing states data to create test CSV
python -c "
import sys
sys.path.append('api_poc/gui')
from client import create_client
from config import use_cloud_database
import pandas as pd

client = create_client(prefer_supabase=use_cloud_database())
data = client.get_search_results(dataset_id=YOUR_DATASET_ID, limit=100)
df = pd.DataFrame(data)
df.to_csv('test_states.csv', index=False)
print(f'Exported {len(df)} records')
"

# Import CSV
python -m imports.api_importer states test_states.csv "test_states_$(date +%s)" --backend supabase
```

#### Test Validated CSV Import  
```bash
# Prepare test CSV
cat > test_validated.csv << EOF
pharmacy_name,state_code,override_type,reason,validated_by
"Test Pharmacy","FL","present","License verified","test_user"
"Test Pharmacy","GA","empty","No license in Georgia","test_user"
EOF

# Import
python -m imports.api_importer validated test_validated.csv "test_validated_$(date +%s)" --backend supabase
```

#### Test Production Scrape Import
```bash
# Import large datasets using the resilient importer (production method)
python imports/resilient_importer.py \
    --states-dir "/path/to/scraped/data" \
    --tag "production_test" \
    --backend supabase \
    --max-workers 8 \
    --debug-log

# Note: This is the only importer that uses batch processing for performance
```

### GUI Import/Export Testing

#### Test CSV Export Functionality
1. Open Streamlit app: `streamlit run app.py`
2. Navigate to "Dataset Manager" → "Export Data" 
3. Test each export type:
   - Select dataset and click "📤 Export to CSV"
   - Verify CSV downloads correctly
   - Check column headers and data format
   - Ensure no database-internal fields (id, created_at) are included

#### Test CSV Import Functionality  
1. Navigate to "Dataset Manager" → "Import Data"
2. Test each import type:
   - **Pharmacies**: Upload CSV with columns `[name, address, city, state, zip, state_licenses]`
   - **States**: Upload CSV with columns `[search_name, search_state, ...]` 
   - **Validated**: Upload CSV with columns `[pharmacy_name, state_code, override_type, reason, validated_by]`
3. Verify debug output shows:
   - File info and column validation
   - Import progress for each record
   - Success confirmation

#### Expected Import Behavior
```
DEBUG: File Info
- File name: test_pharmacies.csv
- File size: 1434 bytes
- Target tag: test_123

DEBUG: CSV Data  
- Rows: 6
- Columns: ['name', 'address', 'city', 'state', 'zip', 'state_licenses']

DEBUG: Import Process
- Command: python -m imports.api_importer pharmacies /tmp/file.csv test_123 --backend supabase

DEBUG: Import Results
- Return code: 0
- Output: ✅ Successfully imported 6/6 pharmacies to supabase

✅ Import successful!
```

### GUI Testing Checklist

#### Dataset Loading
- [ ] Can select pharmacy dataset
- [ ] Can select states dataset
- [ ] Can select validation dataset
- [ ] Load button works
- [ ] Shows correct counts

#### Results Display
- [ ] Matrix shows all combinations
- [ ] Status badges display correctly
- [ ] Scores show when available
- [ ] Can expand row for details
- [ ] Screenshots load properly

#### Filtering
- [ ] Search by name works
- [ ] State filter works
- [ ] Status filter works
- [ ] Clear filters resets view

#### Validation
- [ ] Can mark as present
- [ ] Can mark as empty
- [ ] Reason field saves
- [ ] Validation persists

#### Export
- [ ] CSV download works
- [ ] Contains expected columns
- [ ] Filters apply to export

### Performance Testing

#### Load Testing
```python
# Generate large dataset
import pandas as pd
import json

# Create 1000 pharmacies
pharmacies = pd.DataFrame({
    'name': [f'Pharmacy {i}' for i in range(1000)],
    'address': [f'{i} Main St' for i in range(1000)],
    'city': 'TestCity',
    'state': 'FL',
    'zip': '12345',
    'state_licenses': ['["FL","GA","TX"]'] * 1000
})
pharmacies.to_csv('large_pharmacies.csv', index=False)

# Import and measure time
time python -m imports.pharmacies large_pharmacies.csv "load_test"
```

#### Query Performance
```sql
-- Test query performance
EXPLAIN ANALYZE
SELECT * FROM get_all_results_with_context(
    'states_baseline',
    'test_pharmacies',
    NULL
);

-- Check for missing indexes
SELECT schemaname, tablename, indexname, indexdef
FROM pg_indexes
WHERE tablename IN ('search_results', 'pharmacies', 'match_scores')
ORDER BY tablename, indexname;
```

## Validation Testing

### Data Validation Rules

#### Pharmacy Data
```python
def validate_pharmacy_data(df):
    errors = []
    
    # Required fields
    if df['name'].isna().any():
        errors.append("Missing pharmacy names")
    
    # State licenses format
    for idx, licenses in df['state_licenses'].items():
        try:
            if licenses:
                json.loads(licenses)
        except:
            errors.append(f"Invalid JSON at row {idx}")
    
    # State codes valid
    valid_states = ['AL','AK','AZ',...'WY']
    # Check each license is valid state
    
    return errors
```

#### Search Results
```python
def validate_search_results(data):
    errors = []
    
    # Required metadata
    required = ['search_name', 'search_state', 'search_timestamp']
    for field in required:
        if field not in data['metadata']:
            errors.append(f"Missing {field}")
    
    # Valid date formats
    if 'results' in data:
        for result in data['results']:
            if 'expiration_date' in result:
                # Validate date format
                pass
    
    return errors
```

### Score Validation

#### Expected Score Ranges
```python
def validate_score_distribution(scores):
    # Check distribution makes sense
    assert 0 <= min(scores) <= 100
    assert 0 <= max(scores) <= 100
    
    # Typical distribution
    matches = [s for s in scores if s >= 85]
    weak = [s for s in scores if 60 <= s < 85]
    no_match = [s for s in scores if s < 60]
    
    # Log if unusual
    if len(matches) > len(scores) * 0.8:
        print("Warning: Unusually high match rate")
```

## Integration Testing

### Database Integration

#### Test Supabase Connection
```bash
# Test basic connectivity
python -c "
import sys
sys.path.append('api_poc/gui')
from client import create_client
from config import use_cloud_database

client = create_client(prefer_supabase=use_cloud_database())
datasets = client.get_datasets()
print(f'✅ Connected: Found {len(datasets)} datasets')
"

# Test API endpoints
curl -H 'apikey: YOUR_ANON_KEY' 'http://localhost:8000/rest/v1/datasets?select=*'

# Test data flow
python -c "
import sys
sys.path.append('api_poc/gui')  
from client import create_client
from config import use_cloud_database

client = create_client(prefer_supabase=use_cloud_database())
pharmacies = client.get_pharmacies(limit=5)
states = client.get_search_results(limit=5) 
print(f'Pharmacies: {len(pharmacies)}, States: {len(states)}')
"
```

#### Test API Importer
```bash
# Test all three CSV import paths
python -m imports.api_importer pharmacies --help
python -m imports.api_importer states --help  
python -m imports.api_importer validated --help

# Verify simplified interface (no PostgreSQL options)
python -m imports.api_importer pharmacies test.csv test_tag --backend supabase
```

### Screenshot Integration
```bash
# Test local storage
ls -la imagecache/

# Test path resolution
python -c "
from imports.states import StateImporter
imp = StateImporter()
path = imp._organize_screenshot_path('test.png', 'FL', 'test_tag')
print(f'Organized path: {path}')
"
```

## Regression Testing

### Before Each Release

1. **Run Full Test Suite**
   ```bash
   python system_test.py
   python test_scoring.py
   python test_gui.py
   ```

2. **Test Data Migration**
   ```bash
   # Backup current data
   pg_dump -U postgres pharmchecker > backup.sql
   
   # Test on fresh database
   make clean_all
   make setup
   make dev
   ```

3. **Test Scoring Accuracy**
   ```bash
   # Compare scores before/after changes
   python -c "
   from imports.scoring import ScoringEngine
   engine = ScoringEngine()
   
   test_cases = [
       ('123 Main St', '123 Main Street'),
       ('456 Oak Ave', '456 Oak Avenue'),
       ('789 Elm', '789 Elm Street')
   ]
   
   for addr1, addr2 in test_cases:
       score = engine.score_addresses(addr1, '', '', '', addr2, '', '', '')
       print(f'{addr1} vs {addr2}: {score['overall']:.1f}')
   "
   ```

## Troubleshooting Test Failures

### Common Issues

#### Import Test Fails
```
Error: duplicate key value violates unique constraint
```
**Solution:** Use unique tag or clean data first
```bash
make clean
# or
python -m imports.pharmacies data.csv "test_$(date +%s)"
```

#### Scoring Test Fails
```
AssertionError: Expected score >= 85, got 72
```
**Solution:** Check normalization rules
```python
# Debug scoring
from scoring_plugin import PharmacyMatcher
matcher = PharmacyMatcher()
result = matcher.score_addresses(
    pharm_addr="123 Main St",
    result_addr="123 Main Street"
)
print(f"Components: {result}")
```

#### GUI Test Fails
```
StreamlitAPIException: Session state not initialized
```
**Solution:** Ensure proper session initialization
```python
import streamlit as st
if 'initialized' not in st.session_state:
    st.session_state.initialized = True
```

## Continuous Integration

### GitHub Actions Workflow
```yaml
name: PharmChecker Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_PASSWORD: testpass
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.10'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Setup database
      env:
        DB_HOST: localhost
        DB_NAME: pharmchecker
        DB_USER: postgres
        DB_PASSWORD: testpass
      run: |
        python setup.py
    
    - name: Run tests
      run: |
        python system_test.py
        python test_scoring.py
```

## Test Coverage Metrics

### Current Coverage
- Database operations: 95%
- Import functions: 90%
- Scoring algorithm: 100%
- GUI components: 75%
- Validation logic: 85%

### Improving Coverage
```bash
# Install coverage tool
pip install coverage

# Run with coverage
coverage run system_test.py
coverage report -m

# Generate HTML report
coverage html
open htmlcov/index.html
```

## User Acceptance Testing

### Test Scenarios

1. **New Pharmacy Verification**
   - Import new pharmacy list
   - Import state search results
   - Review matches
   - Validate questionable results
   - Export for compliance

2. **Monthly Update**
   - Import updated searches
   - Compare to previous month
   - Identify changes
   - Re-validate if needed

3. **Audit Review**
   - Load historical data
   - Review validation decisions
   - Check for consistency
   - Generate audit report

### UAT Checklist
- [ ] Can complete full workflow
- [ ] Results match expectations
- [ ] Performance acceptable
- [ ] Export format correct
- [ ] Validation saves properly
- [ ] No data loss on refresh
- [ ] Screenshots display correctly
- [ ] Filters work as expected