# PharmChecker Architecture

## System Overview

PharmChecker is a three-tier application for pharmacy license verification:

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Data Sources  │────▶│  Import System   │────▶│   PostgreSQL    │
│  (CSV/JSON)     │     │  (Python)        │     │   Database      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                           │
                                                           ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Web UI        │◀────│  Scoring Engine  │◀────│   Database      │
│  (Streamlit)    │     │  (Lazy Compute)  │     │   Functions     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

## Core Design Principles

1. **Dataset Independence**: Any combination of pharmacy, state search, and validation datasets can be loaded together
2. **Natural Key Linking**: Uses pharmacy names and license numbers for relationships (no hardcoded IDs)
3. **Lazy Computation**: Address scores calculated on-demand when first needed
4. **Comprehensive Results**: Single database query returns all data for client-side processing
5. **Versioned Datasets**: Multiple versions of data can coexist with tags (e.g., "jan_2024", "feb_2024")

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

### Base Import Pattern
All importers inherit from `BaseImporter`:
```python
class BaseImporter:
    def create_dataset(kind, tag, description)
    def batch_insert(table, records, batch_size=1000)
    def handle_duplicates(on_conflict_action)
```

### Import Flow
1. **Validation**: Check file format and required fields
2. **Dataset Creation**: Create versioned dataset with unique tag
3. **Data Processing**: Transform and normalize records
4. **Batch Insert**: Efficient bulk inserts with conflict handling
5. **Cleanup**: Handle errors and rollback if needed

### Importer Classes

- **PharmacyImporter**: CSV → pharmacies table
- **StateImporter**: JSON directory → search_results table  
- **ScoringEngine**: Compute scores → match_scores table
- **ValidatedImporter**: CSV → validated_overrides table

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
   - System identifies missing scores
   - Lazy computation on first access
   - Permanent cache in database

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
- PostgreSQL 13+ with pg_trgm extension
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