# PharmChecker Architecture

## System Overview

PharmChecker is a cloud-native application for pharmacy license verification:

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Data Sources  │────▶│  Import System   │────▶│    Supabase     │
│  (CSV/JSON)     │     │  (Python)        │     │   Database      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                           │
                                                           ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Web UI        │◀────│ Client-Side      │◀────│   Supabase      │
│  (Streamlit)    │     │ Scoring Engine   │     │   REST API      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

## Core Design Principles

1. **Dataset Independence**: Any combination of pharmacy, state search, and validation datasets can be loaded together
2. **Natural Key Linking**: Uses pharmacy names and license numbers for relationships (no hardcoded IDs)
3. **Transparent Client-Side Scoring**: Address scores calculated transparently via client-side `scoring_plugin.py`
4. **API-First Architecture**: All operations via Supabase REST API, no complex database functions
5. **Comprehensive Results**: Single database query returns all data for client-side processing  
6. **Versioned Datasets**: Multiple versions of data can coexist with tags (e.g., "jan_2024", "feb_2024")
7. **Simplified I/O**: All CSV imports use one-record-at-a-time approach for reliability and error reporting
8. **Cloud-Native**: Supabase backend eliminates infrastructure management

## Database Schema

### Core Tables

#### `datasets`
Manages versioned data imports:
- `kind`: Type of dataset ('pharmacies', 'states', 'validated')
- `tag`: Version identifier (e.g., "jan_2024")
- Unique constraint on (kind, tag) prevents duplicates

#### `pharmacies`
Master pharmacy records:
- `name`: Exact pharmacy name used for searching
- `state_licenses`: JSONB array of state codes ["TX", "FL"]
- Address components for scoring
- Links to dataset via `dataset_id`

#### `search_results` (Optimized Merged Table)
Combined search parameters and results:
- Search metadata (name, state, timestamp)
- Result data (license number, status, address)
- Unique on (dataset_id, search_state, license_number)
- Latest timestamp wins for duplicates

#### `match_scores`
Computed address matching scores:
- Links pharmacy to search result
- Overall score plus component scores
- Computed lazily by scoring engine
- Cached permanently once calculated

#### `validated_overrides`
Manual validation records:
- Snapshot of search result at validation time
- Override type: 'present' (confirmed) or 'empty' (no license)
- Audit fields (who, when, why)

### Key Database Function

**`get_all_results_with_context()`**

Primary interface between database and GUI:
```sql
-- Returns comprehensive data without aggregation
SELECT pharmacy_id, pharmacy_name, search_state, 
       result_id, license_number, score_overall,
       override_type, screenshot_path, ...
FROM comprehensive_view
ORDER BY pharmacy_name, search_state, timestamp DESC
```

Benefits:
- Single query for all data (no N+1 queries)
- Client-side aggregation for flexibility
- Full result caching in session state
- 20x faster detail views

## Import System Architecture

### Unified API Importer (`imports/api_importer.py`)

All CSV imports use a single simplified API-based importer:

```python
class APIImporter:
    def __init__(self, backend='supabase')  # Supabase only
    def import_pharmacies_csv(csv_path, tag, created_by, description)
    def import_states_csv(csv_path, tag, created_by, description) 
    def import_validated_csv(csv_path, tag, created_by, description)
```

### Simplified Import Flow

1. **Dataset Creation**: Create versioned dataset via Supabase API
2. **CSV Processing**: Read and validate required columns
3. **One-by-One Import**: Insert records individually for better error reporting
4. **Progress Reporting**: Show detailed progress and specific error messages
5. **Graceful Failure**: Continue processing even if individual records fail

### Import Methods by Data Type

#### 1. CSV Imports (Simplified, Reliable)
- **Pharmacy CSV**: `python -m imports.api_importer pharmacies file.csv tag`
- **States CSV**: `python -m imports.api_importer states file.csv tag`  
- **Validated CSV**: `python -m imports.api_importer validated file.csv tag`
- **Batch Size**: Always 1 (one record at a time for reliability)
- **Error Handling**: Continues on failure, reports specific issues

#### 2. Production Scrape Import (High Performance)
- **Resilient Importer**: `python imports/resilient_importer.py --states-dir path --tag name`
- **Batch Processing**: Uses configurable batch sizes for large datasets  
- **Image Handling**: Processes and uploads screenshots with deduplication
- **Resume Capability**: Can resume interrupted imports

### Import Architecture Benefits

- **Supabase-Only**: Simplified deployment with cloud database
- **Better Error Reporting**: Shows exactly which record failed and why
- **GUI Integration**: Direct integration with Streamlit interface
- **Simplified Interface**: No complex batch size configuration needed
- **Reliable**: One-by-one processing prevents bulk failures

## API-First Scoring Architecture

### Client-Side Transparent Scoring

**Design Goal**: Cloud-compatible scoring without complex database functions

**Key Principles**:
- ✅ **No database-side Python execution** - pure Supabase compatibility
- ✅ **Client-side plugin execution** - `scoring_plugin.py` runs in GUI 
- ✅ **REST API operations only** - standard Supabase table endpoints
- ✅ **Transparent to users** - scoring happens automatically when needed
- ✅ **One-time computation** - results cached permanently per dataset pair

### Scoring Workflow

```
1. User requests comprehensive results
2. Client: GET /match_scores?states_dataset_id=eq.X&pharmacies_dataset_id=eq.Y (check count)
3. If count = 0:
   a. Client: GET /rpc/get_all_results_with_context (get pairs needing scores)
   b. Client: Run scoring_plugin.py locally on missing pairs  
   c. Client: POST /match_scores (insert computed scores)
4. Client: GET /rpc/get_all_results_with_context (return complete results)
```

### API Endpoints Used

**Required Database Functions**:
- `get_all_results_with_context()` - Single comprehensive results query

**Standard Table Operations**:
- `GET /match_scores` - Check existence, retrieve scores
- `POST /match_scores` - Insert computed scores  
- `DELETE /match_scores` - Clear scores for testing
- `GET /datasets` - Get dataset metadata

**No Complex RPC Functions Needed** - keeps database cloud-compatible

## Complete I/O Architecture (7 Paths)

PharmChecker implements 7 distinct I/O paths for comprehensive data management:

### 1. Production Scrape Import (Directory → Database)
- **Purpose**: High-performance import of scraped state board data  
- **Implementation**: `imports/resilient_importer.py`
- **Input**: Directory structure with JSON files + PNG screenshots
- **Features**: Batch processing, image deduplication, resume capability
- **Usage**: `python imports/resilient_importer.py --states-dir path --tag name`

### 2-4. CSV Export Paths (Database → CSV)
All exports via Streamlit GUI "Export Data" section:

- **Pharmacy Export**: All pharmacy data excluding internal fields
- **States Export**: All search results with metadata  
- **Validated Export**: All validation overrides
- **Implementation**: Direct API calls via `client.get_*()` methods
- **Format**: Clean CSV with user-friendly column names

### 5-7. CSV Import Paths (CSV → Database)  
All imports via unified `imports/api_importer.py`:

- **Pharmacy CSV Import**: `python -m imports.api_importer pharmacies file.csv tag`
- **States CSV Import**: `python -m imports.api_importer states file.csv tag`
- **Validated CSV Import**: `python -m imports.api_importer validated file.csv tag`
- **Processing**: One record at a time for detailed error reporting
- **Integration**: Available via GUI "Import Data" section

### I/O Design Principles

1. **Simplicity Over Performance**: CSV imports use single-record processing for reliability
2. **Production vs. Development**: Scrape importer uses batch processing for large datasets
3. **Unified Interface**: All CSV operations use same API importer with consistent CLI
4. **Error Transparency**: Detailed progress reporting and specific failure messages
5. **GUI Integration**: All I/O operations accessible through web interface

### Error Handling Strategy

```python
# CSV Import: Continue on individual failures
for record in records:
    try:
        import_single_record(record)
        print(f"✅ Imported {record['name']}")
    except Exception as e:
        print(f"❌ Failed {record['name']}: {e}")
        # Continue with next record

# Result: Partial success with detailed error reporting
```

## Scoring Algorithm

### Address Matching Components

**Overall Score = 70% Street + 30% City/State/ZIP**

#### Street Matching (70% weight)
- Fuzzy string matching using RapidFuzz
- Normalization: St→Street, Ave→Avenue, N→North
- Suite/unit handling with bonus/penalty

#### City/State/ZIP (30% weight)
- Exact match after normalization
- State name → abbreviation conversion
- ZIP limited to first 5 digits

### Score Thresholds
- **Match**: ≥ 85 (high confidence)
- **Weak Match**: 60-84 (needs review)
- **No Match**: < 60 (likely different)

### Lazy Computation Strategy
1. GUI requests results for dataset combination
2. System checks for missing scores
3. Scoring engine computes in batches
4. Scores cached permanently in database

## Web Interface Architecture

### Streamlit Application Structure
```
app.py (main)
├── utils/
│   ├── database.py      # DB operations, caching
│   ├── display.py       # UI components, charts
│   ├── validation_local.py  # Session state management
│   ├── auth.py          # Authentication
│   └── session.py       # Dataset selection persistence
```

### Session State Management
- Comprehensive results cached after first query
- Dataset selections persisted across pages
- Validation state maintained locally
- User preferences stored in session

### Performance Optimizations
- Results cached at multiple levels
- Single database query per view
- Client-side filtering and aggregation
- Lazy loading of screenshots

## Data Flow

### Import → Score → Review → Validate

1. **Import Phase**
   - Load pharmacy CSV with state licenses
   - Import state search JSON with results
   - Data stored in versioned datasets

2. **Scoring Phase**
   - User selects dataset combination
   - Client checks score existence via REST API
   - **Transparent client-side computation** using `scoring_plugin.py`
   - Results inserted via REST API, cached permanently in database

3. **Review Phase**
   - Comprehensive results loaded once
   - Client-side filtering and display
   - Detail views without new queries

4. **Validation Phase**
   - Manual overrides with reasons
   - Snapshot of current result state
   - Audit trail maintained

## Screenshot Management

### Storage Architecture
```
image_cache/
├── <states_tag>/
│   ├── FL/
│   │   ├── pharmacy_name.timestamp.png
│   └── PA/
│       ├── pharmacy_name.timestamp.png
```

### Image Table Limitations
Current issue: Images linked to dataset + search metadata, not individual results
- Causes: Duplicate displays when joining
- Workaround: Query without image JOIN
- Future fix: Add search_result_id foreign key

## Authentication & Security

### Local Development Mode
- Default admin user from .env
- No external authentication required
- Session-based state management

### Production Mode (GitHub OAuth)
- User allowlist in app_users table
- GitHub OAuth integration
- Role-based access (admin/user)

## Deployment Considerations

### Database Requirements
- Supabase cloud database
- Connection pooling for multi-user
- Regular VACUUM for performance

### Scaling Strategies
- Horizontal scaling of Streamlit instances
- Database read replicas for queries
- CDN for screenshot delivery
- Background job queue for scoring

### Monitoring Points
- Dataset import success/failure
- Scoring computation time
- Query performance metrics
- User session analytics