# PharmChecker API Reference

## Database Functions

### Core Query Function

#### `get_all_results_with_context()`

Returns comprehensive data for a dataset combination without aggregation.

**Parameters:**
- `p_states_tag` (TEXT): Tag for states dataset
- `p_pharmacies_tag` (TEXT): Tag for pharmacies dataset  
- `p_validated_tag` (TEXT, optional): Tag for validation dataset

**Returns:** Table with columns:
```sql
pharmacy_id INT
pharmacy_name TEXT
search_state CHAR(2)
result_id INT
search_name TEXT
license_number TEXT
license_status TEXT
license_name TEXT
license_type TEXT
issue_date DATE
expiration_date DATE
score_overall NUMERIC
score_street NUMERIC
score_city_state_zip NUMERIC
override_type TEXT
validated_license TEXT
result_status TEXT
search_timestamp TIMESTAMP
screenshot_path TEXT
pharmacy_address TEXT
pharmacy_city TEXT
pharmacy_state TEXT
pharmacy_zip TEXT
result_address TEXT
result_city TEXT
result_state TEXT
result_zip TEXT
pharmacy_dataset_id INT
states_dataset_id INT
validated_dataset_id INT
```

**Example:**
```sql
SELECT * FROM get_all_results_with_context(
    'states_jan_2024',
    'pharmacies_2024', 
    'validated_jan'
);
```

### Validation Functions

#### `check_validation_consistency()`

Detects inconsistencies between validations and search data.

**Parameters:**
- `p_states_tag` (TEXT): States dataset tag
- `p_pharmacies_tag` (TEXT): Pharmacies dataset tag
- `p_validated_tag` (TEXT): Validation dataset tag

**Returns:** Table with columns:
- `issue_type` (TEXT): Type of inconsistency
- `pharmacy_name` (TEXT): Affected pharmacy
- `state_code` (CHAR(2)): State code
- `license_number` (TEXT): License number
- `description` (TEXT): Issue description
- `severity` (TEXT): 'error', 'warning', or 'info'

**Issue Types:**
- `empty_validation_with_results`: Marked empty but results exist
- `present_validation_missing_results`: Marked present but no results
- `validated_pharmacy_not_found`: Validated pharmacy not in dataset
- `license_not_claimed`: Validated state not in pharmacy licenses

## Python Import Modules

### Base Importer Class

#### `imports.base.BaseImporter`

Base class for all data importers.

**Methods:**

##### `create_dataset(kind, tag, description, created_by)`
Creates a new versioned dataset.

**Parameters:**
- `kind` (str): 'pharmacies', 'states', or 'validated'
- `tag` (str): Unique version identifier
- `description` (str): Human-readable description
- `created_by` (str): Username or system identifier

**Returns:** 
- `int`: Dataset ID

**Raises:**
- `ValueError`: If tag already exists for kind

##### `batch_insert(table, records, batch_size=1000)`
Efficiently inserts records in batches.

**Parameters:**
- `table` (str): Target table name
- `records` (List[Dict]): Records to insert
- `batch_size` (int): Records per batch

### Pharmacy Importer

#### `imports.pharmacies.PharmacyImporter`

Imports pharmacy data from CSV files.

##### `import_csv(filepath, tag, created_by=None, description=None)`

**Parameters:**
- `filepath` (str): Path to CSV file
- `tag` (str): Dataset version tag
- `created_by` (str): Optional username
- `description` (str): Optional description

**Returns:**
- `bool`: Success status

**CSV Format:**
```csv
name,address,city,state,zip,state_licenses
"Pharmacy A","123 Main St","Orlando","FL","32801","[\"FL\",\"GA\"]"
```

**Required Fields:**
- `name`: Pharmacy name (exact match for searches)
- `state_licenses`: JSON array or comma-separated list

### State Search Importer

#### `imports.states.StateImporter`

Imports state board search results from JSON files.

##### `import_directory(dirpath, tag, created_by=None, description=None)`

**Parameters:**
- `dirpath` (str): Directory containing state folders
- `tag` (str): Dataset version tag
- `created_by` (str): Optional username
- `description` (str): Optional description

**Directory Structure:**
```
dirpath/
├── FL/
│   ├── PharmacyA_01_parse.json
│   ├── PharmacyA_01.png
│   └── PharmacyB_no_results_parse.json
└── PA/
    └── PharmacyA_01_parse.json
```

**JSON Format:**
```json
{
  "metadata": {
    "search_name": "Pharmacy A",
    "search_state": "FL",
    "search_timestamp": "2024-01-15T10:30:00Z",
    "screenshot_path": "PharmacyA_01.png"
  },
  "results": [
    {
      "license_number": "FL12345",
      "license_status": "Active",
      "license_name": "Pharmacy A LLC",
      "license_type": "Community Pharmacy",
      "address": "123 Main St",
      "city": "Orlando",
      "state": "FL",
      "zip": "32801",
      "issue_date": "2020-01-01",
      "expiration_date": "2025-01-01"
    }
  ]
}
```

### Scoring Engine

#### `imports.scoring.ScoringEngine`

Computes address matching scores.

##### `compute_missing_scores(states_tag, pharmacies_tag, batch_size=100)`

**Parameters:**
- `states_tag` (str): States dataset tag
- `pharmacies_tag` (str): Pharmacies dataset tag
- `batch_size` (int): Scores per batch

**Returns:**
- `Dict`: Statistics about scoring operation
  - `total_computed`: Number of scores computed
  - `total_errors`: Number of failures
  - `average_score`: Mean score
  - `processing_time`: Total seconds

##### `score_addresses(pharm_addr, pharm_city, pharm_state, pharm_zip, result_addr, result_city, result_state, result_zip)`

**Parameters:**
- All parameters are strings representing address components

**Returns:**
- `Dict` with keys:
  - `overall`: Combined score (0-100)
  - `street`: Street match score (0-100)
  - `city_state_zip`: Location score (0-100)
  - `metadata`: Scoring details

### Validation Importer

#### `imports.validated.ValidatedImporter`

Imports manual validation decisions.

##### `import_csv(filepath, tag, created_by=None)`

**CSV Format:**
```csv
pharmacy_name,state_code,license_number,override_type,reason
"Pharmacy A","FL","FL12345","present","Verified via screenshot"
"Pharmacy B","PA","","empty","No results found, confirmed"
```

**Required Fields:**
- `pharmacy_name`: Exact pharmacy name
- `state_code`: Two-letter state code
- `override_type`: 'present' or 'empty'
- `reason`: Explanation for override

## GUI Utility Functions

### Database Utilities

#### `utils.database.get_database_manager()`

Returns singleton database manager instance.

**Methods:**
- `execute_query(query, params)`: Run SQL query
- `get_datasets(kind)`: List datasets by type
- `invalidate_cache()`: Clear query cache

#### `utils.database.query_with_cache(query, params, ttl=300)`

Execute query with caching.

**Parameters:**
- `query` (str): SQL query
- `params` (tuple): Query parameters
- `ttl` (int): Cache time-to-live in seconds

### Display Components

#### `utils.display.display_results_table(df, key="results")`

Render interactive results table.

**Parameters:**
- `df` (DataFrame): Results dataframe
- `key` (str): Unique component key

#### `utils.display.create_status_distribution_chart(df)`

Create pie chart of status distribution.

**Returns:**
- `plotly.Figure`: Interactive chart object

#### `utils.display.format_status_badge(status, score=None)`

Format status with emoji and color.

**Parameters:**
- `status` (str): 'match', 'weak match', 'no match', 'no data'
- `score` (float): Optional score to display

**Returns:**
- `str`: Formatted HTML string

### Session Management

#### `utils.session.auto_restore_dataset_selection()`

Restore previous dataset selections from session.

#### `utils.session.save_dataset_selection(pharmacies_tag, states_tag, validated_tag)`

Save current dataset selection to session.

## Data Formats

### Status Classifications

```python
def get_status_bucket(score, override_type=None):
    if override_type:
        return 'validated'
    elif score is None:
        return 'no data'
    elif score >= 85:
        return 'match'
    elif score >= 60:
        return 'weak match'
    else:
        return 'no match'
```

### Score Calculation

```python
def calculate_overall_score(street_score, city_state_zip_score):
    return (street_score * 0.7) + (city_state_zip_score * 0.3)
```

### Address Normalization

```python
def normalize_address(address):
    # Convert abbreviations
    replacements = {
        'St': 'Street',
        'Ave': 'Avenue',
        'Rd': 'Road',
        'Dr': 'Drive',
        'Ln': 'Lane',
        'Ct': 'Court',
        'N': 'North',
        'S': 'South',
        'E': 'East',
        'W': 'West'
    }
    # Apply replacements
    # Remove extra spaces
    # Convert to uppercase
    return normalized_address
```

## Environment Variables

### Required Variables

```bash
DB_HOST=localhost           # PostgreSQL host
DB_PORT=5432               # PostgreSQL port
DB_NAME=pharmchecker       # Database name
DB_USER=postgres           # Database user
DB_PASSWORD=password       # Database password
```

### Optional Variables

```bash
LOGGING_LEVEL=INFO         # DEBUG, INFO, WARNING, ERROR
AUTH_MODE=local           # local or github
STORAGE_TYPE=local        # local or supabase
BATCH_SIZE=1000          # Import batch size
SCORING_BATCH_SIZE=100   # Scoring batch size
CACHE_TTL=300           # Query cache TTL in seconds
```

## Error Codes

### Import Errors

- `IMP001`: File not found
- `IMP002`: Invalid CSV format
- `IMP003`: Missing required field
- `IMP004`: Duplicate dataset tag
- `IMP005`: Database connection error

### Scoring Errors

- `SCR001`: Missing pharmacy address
- `SCR002`: Missing result address
- `SCR003`: Invalid address format
- `SCR004`: Scoring computation failed

### Validation Errors

- `VAL001`: Invalid override type
- `VAL002`: Pharmacy not found
- `VAL003`: Duplicate validation
- `VAL004`: Invalid state code

## Performance Considerations

### Query Optimization

```sql
-- Use indexes for common queries
CREATE INDEX ix_results_lookup 
ON search_results(dataset_id, search_name, search_state);

-- Vacuum regularly
VACUUM ANALYZE search_results;
```

### Batch Processing

```python
# Optimal batch sizes
IMPORT_BATCH_SIZE = 1000    # For data import
SCORING_BATCH_SIZE = 100    # For scoring computation
EXPORT_BATCH_SIZE = 5000    # For CSV export
```

### Caching Strategy

```python
# Cache levels
SESSION_CACHE_TTL = 3600    # User session data
QUERY_CACHE_TTL = 300       # Database queries
DATASET_CACHE_TTL = 300     # Dataset lists
```