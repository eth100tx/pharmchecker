# PharmChecker GUI Implementation Guide

## Overview

The PharmChecker GUI is a Streamlit-based web interface that provides comprehensive pharmacy license verification functionality. This guide covers everything needed to understand, implement, and maintain the system.

## System Architecture

### Core Components

```
PharmChecker GUI Architecture
├── Database Layer (PostgreSQL)
│   ├── Core Tables: datasets, pharmacies, search_results, match_scores, validated_overrides, images
│   ├── Database Functions: get_all_results_with_context()
│   └── MCP Integration: postgres-prod, postgres-sbx connections
├── Application Layer (Python/Streamlit)
│   ├── app.py: Main Streamlit application
│   ├── utils/database.py: Database manager with SQLAlchemy + MCP
│   ├── utils/display.py: UI components and formatting
│   ├── utils/validation_local.py: Session-based validation state management
│   └── imports/validated.py: Database validation operations
├── Configuration Layer
│   ├── config.py: Database and environment configuration
│   ├── .env: Environment variables (local/Supabase)
│   └── schema.sql: Database schema definition
└── Data Layer
    ├── Image Cache: Organized screenshot storage
    ├── Import System: Pharmacy/states data loaders
    └── Storage: Local filesystem or Supabase Storage
```

## Database Architecture

### Key Design Principles

- **Three-Tag System**: Users select pharmacies, states, and validated datasets independently
- **Dataset Versioning**: All data is tagged and versioned, no global "active" state
- **Natural Key Relationships**: Uses pharmacy names + license numbers, not internal IDs
- **Comprehensive Results**: Single-query approach with client-side aggregation
- **Read-Only Core Data**: Pharmacies and states datasets are read-only; only validated is writable

### Essential Database Function

The GUI relies on one primary database function:

```sql
-- functions_comprehensive.sql
get_all_results_with_context(states_tag, pharmacies_tag, validated_tag)
```

**What it returns:**
- ALL search results for selected dataset combination
- Pharmacy context (name, address, licensed states)  
- Search result details (license numbers, addresses, dates)
- Match scores (overall, street, city-state-zip)
- Validation overrides (present/empty validations)
- Screenshot paths and metadata
- Complete context for both aggregation and detail views

**Key benefit:** Single database call replaces multiple queries, with client-side processing for both matrix and detail views.

### Database Tables Overview

```sql
-- Core tables (read-only in GUI)
datasets          -- Versioned dataset management
pharmacies        -- Master pharmacy records
search_results    -- State board search results (merged table design)
match_scores      -- Address matching scores (lazy computation)
images           -- Screenshot metadata

-- Writable table (GUI can modify)
validated_overrides  -- Manual validation records with snapshots
```

## Configuration System

### Environment Variables (.env)

The system supports both local PostgreSQL and Supabase configurations:

```bash
# Database Configuration (Required)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=pharmchecker
DB_USER=postgres
DB_PASSWORD=your_password

# Storage Configuration
STORAGE_TYPE=local              # or 'supabase'
DATA_DIR=data
SUPABASE_URL=your_supabase_url  # if using Supabase
SUPABASE_KEY=your_supabase_key  # if using Supabase

# Application Configuration
STREAMLIT_PORT=8501
STREAMLIT_HOST=0.0.0.0
LOGGING_LEVEL=INFO
```

### Database Connection Architecture

**For Application Code:**
```python
# config.py - Standard SQLAlchemy connections
from sqlalchemy import create_engine
engine = create_engine(f"postgresql://{user}:{password}@{host}:{port}/{database}")
```

**For Claude Development (MCP Tools):**
```python
# utils/database.py - MCP integration for Claude debugging only
mcp__postgres_prod__query({"sql": "SELECT ..."})  # Production access
mcp__postgres_sbx__query({"sql": "SELECT ..."})   # Sandbox access
```

**Important**: MCP tools are exclusively for Claude development/debugging. The actual GUI application uses standard SQLAlchemy connections.

## GUI Application Structure

### Main Application (app.py)

**Core Pages:**
1. **Dataset Manager** - Three-tag selection and data loading
2. **Results Matrix** - Aggregated pharmacy-state results view
3. **Scoring Manager** - Address matching score management  
4. **Pharmacy Details** - Individual pharmacy information
5. **Search Details** - Individual search result details
6. **Validation Manager** - Manual validation interface

**Key Features:**
- **Session State Management**: Loaded data cached for performance
- **Real-time Validation**: Immediate UI updates with database persistence
- **Comprehensive Filtering**: State, status, score range filters
- **Export Functionality**: CSV download with timestamps
- **Debug Mode**: Technical field display for development

### Data Flow Architecture

```
1. User Selection → Dataset Manager
   ↓
2. Load Dataset Combination → validation_local.py
   ↓  
3. Database Query → get_all_results_with_context()
   ↓
4. Session State Cache → st.session_state.loaded_data
   ↓
5. Client-side Processing → database.py aggregation methods
   ↓
6. UI Rendering → display.py components
   ↓
7. User Interactions → Validation updates → Database writes
```

### Database Manager (utils/database.py)

**Primary Class:**
```python
class DatabaseManager:
    def __init__(self, use_production: bool = True, allow_fallback: bool = False)
    
    # Core Methods:
    def get_comprehensive_results() -> pd.DataFrame     # Single query for all data
    def aggregate_for_matrix() -> pd.DataFrame          # Client-side aggregation
    def filter_for_detail() -> pd.DataFrame            # Client-side filtering
    def execute_query() -> pd.DataFrame                 # Direct SQL execution
```

**Architecture Benefits:**
- **Single Query Performance**: One database call vs multiple round-trips
- **Client-side Processing**: Fast filtering/aggregation without database load  
- **Caching**: Results cached in Streamlit session state
- **Flexibility**: Easy to extend with new aggregation methods

### Validation System

**Two-tier Architecture:**

**1. Session State (utils/validation_local.py):**
```python
# In-memory validation tracking
st.session_state.loaded_data['validations'] = {
    ('pharmacy_name', 'state_code', 'license_number'): {
        'override_type': 'present'|'empty',
        'reason': 'validation reason',
        'validated_by': 'user_id',
        'validated_at': datetime
    }
}
```

**2. Database Persistence (imports/validated.py):**
```python
class ValidatedImporter:
    def create_validation_record()  # Create validation with snapshot
    def remove_validation_record()  # Remove validation
    def get_search_result_snapshot() # Capture current search state
```

**Validation Flow:**
1. User clicks validation checkbox → UI change
2. Session state updated → Immediate visual feedback  
3. Database write attempted → Persistent storage
4. Success/failure → User notification
5. Page refresh → Consistent state

## Image Cache System

### Automatic Screenshot Management

**Import-time Processing:**
```python
# During states data import (imports/states.py)
if screenshot_path in search_result:
    cached_path = f"image_cache/{states_tag}/{state}/{search_name}.{timestamp}.png"
    copy_file(original_screenshot, cached_path)
    create_image_record(search_result_id, cached_path, metadata)
```

**Organization Structure:**
```
image_cache/
├── states_baseline/
│   ├── FL/
│   │   ├── Belmar_01.20250803_1403.png
│   │   └── Empower_02.20250803_1404.png
│   └── PA/
│       └── Belmar_01.20250803_1405.png
└── states_baseline2/
    └── FL/
        └── Custom_Search.20250804_0900.png
```

**Key Features:**
- **Deduplication**: Timestamp-based filenames prevent overwrites
- **Shared Images**: Multiple search results can reference same cached file
- **Metadata Tracking**: File size, storage type, organized paths in database
- **Automatic Cleanup**: Cache cleaned when search data is reset
- **Cloud Ready**: Paths organized for Supabase Storage upload

### Image Integration in GUI

```python
# utils/display.py - Screenshot display
def display_enhanced_search_result_detail():
    # Small thumbnail in sidebar
    st.image(result['screenshot_path'], width=150)
    
    # Full-size expandable view
    with st.expander("📷 View Full Size Screenshot"):
        st.image(result['screenshot_path'], use_container_width=True)
```

## Implementation Details

### Three-Tag Selection System

**User Interface:**
```python
# app.py - Dataset Manager
col1, col2, col3 = st.columns(3)
with col1:
    selected_pharmacy = st.selectbox("Pharmacies:", pharmacy_options)
with col2:
    selected_states = st.selectbox("States:", states_options)  
with col3:
    selected_validated = st.selectbox("Validated:", validated_options)
```

**Database Query:**
```python
# Single comprehensive query with all three tags
results = db.get_comprehensive_results(
    states_tag=selected_states,
    pharmacies_tag=selected_pharmacy, 
    validated_tag=selected_validated
)
```

**Data Processing:**
```python
# Client-side aggregation for matrix view
matrix_df = db.aggregate_for_matrix(results)

# Client-side filtering for detail view
detail_df = db.filter_for_detail(results, pharmacy_name, state)
```

### Read-Only vs Writable Data

**Read-Only Datasets:**
- **Pharmacies**: Master pharmacy records with addresses and licensed states
- **States**: Search results from state board lookups with screenshots
- **Match Scores**: Computed address matching scores

**Writable Dataset:**
- **Validated Overrides**: Manual validation decisions with snapshots

**Implementation:**
```python
# Only validated dataset supports writes
if action == 'create_validation':
    success = ValidatedImporter().create_validation_record(...)
    if success:
        update_session_state_validation(...)
        st.rerun()  # Refresh UI
```

### Status Calculation Logic

**Status Priority (Highest to Lowest):**
1. **Validated Override** - Manual validation always wins
2. **Score-based Status** - Automated matching scores
3. **No Data** - Missing search results or scores

```python
def calculate_status_with_local_validation(row):
    # Check validation override first
    validation = get_validation_status(pharmacy_name, state, license_number)
    if validation:
        return 'validated'  # Override any score-based status
    
    # Fall back to score-based classification
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

### Comprehensive Results Function Benefits

**Current Architecture:**
```python
# Single comprehensive query approach
all_results = execute_query("SELECT * FROM get_all_results_with_context(...)")
matrix_view = client_side_aggregate(all_results)   # Fast client-side processing
detail_view = client_side_filter(all_results)      # No additional database calls
```

**Architecture Benefits:**
- **Single Database Call**: One query provides all data needed for both matrix and detail views
- **Fast Detail Views**: No additional database round-trips required
- **Simplified Data Flow**: Consistent data model across all UI components  
- **Enhanced Caching**: Full results cached in session state for instant interactions

## Development Workflow

### Local Development Setup

```bash
# 1. Environment Setup
cp .env.example .env
# Edit .env with your database credentials

# 2. Database Setup
python setup.py  # Creates database and tables
make setup      # Alternative: Makefile command

# 3. Import Test Data
make import_pharmacies      # Import pharmacy master data
make import_test_states     # Import state search results
make import_test_states2    # Import additional search data

# 4. Run System Tests
python system_test.py       # End-to-end validation
python test_gui.py         # GUI component tests

# 5. Launch GUI
streamlit run app.py       # Start web interface
```

### Database Management Commands

```bash
# Status and Information
make status                # Show current database state
python show_status.py     # Detailed dataset status

# Data Management  
make clean_states         # Clean search data (keep pharmacies)
make clean_all           # Full database reset
make reload              # Clean + reimport baseline data

# Development Workflow
make dev                 # Full workflow: pharmacies + both state datasets
```

### Testing and Validation

```bash
# System Tests
python system_test.py        # Complete end-to-end validation
python test_scoring.py       # Address matching algorithm tests
python scoring_plugin.py     # Standalone scoring test

# GUI Tests  
python test_gui.py          # UI component validation
```

### Debugging and Development

**Debug Mode Features:**
- Technical field display (record IDs, dataset IDs)
- Validation record comparisons
- Database query logging
- Performance timing
- Session state inspection

**Enable Debug Mode:**
```python
# In GUI - Results Matrix page
debug_mode = st.checkbox("Debug Mode", True)
st.session_state.debug_mode = debug_mode
```

## Production Deployment Considerations

### Database Requirements

**PostgreSQL Extensions:**
```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- Required for fuzzy text matching
```

**Performance Indexes:**
```sql
-- Key indexes for GUI performance (from schema.sql)
CREATE INDEX ix_results_search_name_state ON search_results(dataset_id, search_name, search_state);
CREATE INDEX ix_scores_composite ON match_scores(states_dataset_id, pharmacies_dataset_id, score_overall DESC);  
CREATE INDEX ix_validated_lookup ON validated_overrides(pharmacy_name, state_code);
```

### Environment Configuration

**Local Development:**
```bash
DB_HOST=localhost
STORAGE_TYPE=local
```

**Production Deployment:**
```bash  
DB_HOST=production-postgres-host
STORAGE_TYPE=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
```

### Security Considerations

- **Database Credentials**: Never commit .env files to version control
- **MCP Tools**: Used only for Claude development, not in production
- **Validation Permissions**: Consider implementing user authentication
- **Image Storage**: Configure appropriate access controls for screenshots

## API Surface and Key Functions

### Core GUI Functions

**Dataset Management:**
```python
get_database_manager()                    # Get database manager instance
load_dataset_combination()               # Load three-tag combination
is_data_loaded()                        # Check if data is loaded
get_loaded_tags()                       # Get current dataset tags
```

**Data Retrieval:**
```python
db.get_comprehensive_results()          # Single comprehensive query
db.aggregate_for_matrix()              # Client-side matrix aggregation  
db.filter_for_detail()                 # Client-side detail filtering
db.execute_query()                      # Direct SQL execution
```

**Validation Management:**
```python
get_validation_status()                 # Check validation state
set_validation_status()                 # Create validation
remove_validation_status()              # Remove validation
calculate_status_with_local_validation() # Status with validation override
```

**UI Components:**
```python
display_dense_results_table()          # Main results table with selection
display_row_detail_section()           # Detailed pharmacy/search view
display_enhanced_search_result_detail() # Individual result with validation
format_smart_status_badge()            # Status display with validation
```

### Database Functions (SQL)

**Core Function:**
```sql
-- Returns all data for client-side processing
SELECT * FROM get_all_results_with_context(states_tag, pharmacies_tag, validated_tag);
```

**Legacy Functions (maintained for compatibility):**
```sql
SELECT * FROM get_results_matrix(states_tag, pharmacies_tag, validated_tag);
SELECT * FROM find_missing_scores(states_tag, pharmacies_tag);
```

## Common Implementation Patterns

### Loading Data Pattern

```python
def render_dataset_manager():
    # 1. Show current state
    if is_data_loaded():
        loaded_tags = get_loaded_tags()
        st.success(f"Loaded: {loaded_tags}")
    
    # 2. Dataset selection
    selected_pharmacy = st.selectbox("Pharmacies:", pharmacy_options)
    selected_states = st.selectbox("States:", states_options)
    selected_validated = st.selectbox("Validated:", validated_options)
    
    # 3. Load combination
    if st.button("Load Data"):
        success = load_dataset_combination(selected_pharmacy, selected_states, selected_validated)
        if success:
            st.rerun()
```

### Results Display Pattern

```python
def render_results_matrix():
    # 1. Check data loaded
    if not is_data_loaded():
        st.warning("Load data first")
        return
    
    # 2. Get comprehensive results
    full_results = get_comprehensive_results()
    
    # 3. Apply filters
    filtered_results = apply_filters(full_results, state_filter, status_filter)
    
    # 4. Aggregate for matrix view
    matrix_df = db.aggregate_for_matrix(filtered_results)
    
    # 5. Display with selection
    selected_row = display_dense_results_table(matrix_df)
    
    # 6. Show detail view if row selected
    if selected_row:
        detail_data = db.filter_for_detail(full_results, selected_row['pharmacy_name'], selected_row['search_state'])
        display_row_detail_section(selected_row, datasets, debug_mode, detail_data)
```

### Validation Update Pattern

```python
def handle_validation_toggle(pharmacy_name, state, license_number, action):
    # 1. Update session state immediately
    if action == 'present':
        st.session_state.loaded_data['validations'][(pharmacy_name, state, license_number)] = {
            'override_type': 'present', 'validated_at': datetime.now()
        }
    
    # 2. Write to database (blocking)
    success = write_validation_to_db(pharmacy_name, state, license_number, action)
    
    # 3. Refresh UI
    if success:
        st.success("Validation saved")
        st.rerun()
    else:
        st.error("Save failed")
```

## Troubleshooting Guide

### Common Issues

**1. "No data loaded" message:**
- Check database connection in .env
- Verify datasets exist: `make status`
- Try reimporting data: `make clean_all && make dev`

**2. Validation not saving:**
- Check validated dataset exists
- Verify database write permissions
- Check logs for constraint violations

**3. Images not displaying:**
- Check image_cache directory exists
- Verify screenshot paths in database
- Check file permissions

**4. Performance issues:**
- Check database indexes exist
- Monitor query execution time
- Consider data volume limits

### Debug Techniques

**1. Enable Debug Mode:**
```python
st.session_state.debug_mode = True
```

**2. Check Session State:**
```python
st.write("Session State:", st.session_state.loaded_data)
```

**3. Monitor Database Queries:**
```python
logger.setLevel(logging.DEBUG)  # in database.py
```

**4. Test Database Functions:**
```sql
-- Test core function directly
SELECT * FROM get_all_results_with_context('states_baseline', 'pharmacies_test', NULL) LIMIT 10;
```

## Summary

The PharmChecker GUI provides a comprehensive interface for pharmacy license verification with:

- **Simple Surface**: Three-tag selection system
- **Powerful Backend**: Single comprehensive database query with client-side processing  
- **Flexible Validation**: Session-based state with database persistence
- **Rich Media**: Automatic screenshot caching and display
- **Production Ready**: Local PostgreSQL or Supabase deployment options

The system successfully balances simplicity for users with comprehensive functionality for developers, making it suitable for both development and production environments.