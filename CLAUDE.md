# CLAUDE.md

Instructions for Claude Code when working with the PharmChecker repository. For full project details, see README.md and docs/.

## Project Context

PharmChecker verifies pharmacy licenses by importing state board search results, computing address match scores, and providing a web interface for manual review. The system is **production-ready** with all core features implemented.

## Critical Technical Details

### Database Schema - IMPORTANT
The system uses an **optimized merged `search_results` table** that combines search parameters and results. This eliminates timing conflicts. Never try to split this back into separate tables.

```sql
-- Merged table with automatic deduplication
UNIQUE(dataset_id, search_state, license_number)
-- Latest timestamp wins for duplicates
```

### Supabase Schema Management
The system uses **Supabase as the exclusive database backend**:
- Schema setup via manual SQL execution in Supabase Dashboard
- Use `migrations/supabase_setup_consolidated.sql` for complete setup
- `migrations/migrate.py` provides documentation and verification tools
- Never modify schema files directly - use Supabase Dashboard SQL Editor

### MCP Database Access (Claude Only) 
When debugging, use MCP tools - the application itself uses Supabase REST API:
- `mcp__supabase__*` - Supabase integration (read-only)
- Application uses: Supabase Python client with REST API endpoints

## Core Commands

```bash
# Database setup and verification
python setup.py                              # Verify Supabase connection
python migrations/migrate.py --status        # Show schema documentation
python migrations/migrate.py --verify        # Verify Supabase schema setup

# Quick development workflow
make dev              # Import all test data
make status           # Check database state
python system_test.py # Verify everything works

# Run application
streamlit run app.py  # Web interface at localhost:8501

# Testing
python test_scoring.py   # Test address matching
python test_gui.py       # Test UI components

# Production data import (Resilient Importer - recommended for 500+ files)
make import_scrape_states         # Import state searches with images (Supabase)

# Legacy data import (for small datasets)
python -m imports.pharmacies <csv> <tag>
python -m imports.states <json_dir> <tag>

# Direct resilient importer usage
python3 imports/resilient_importer.py --states-dir "/path/to/data" --tag "dataset_name"
```

## Key Files to Know

### Core Functionality
- `app.py` - Main Streamlit web interface
- `schema.sql` - Legacy database schema (DO NOT EDIT - use migrations)
- `functions_comprehensive.sql` - Legacy functions (DO NOT EDIT - use migrations)
- `migrations/` - **NEW**: Unified migration system for both backends
- `migrations/migrate.py` - Migration runner
- `migrations/supabase_setup_consolidated.sql` - Complete Supabase setup
- `system_test.py` - End-to-end test (run this to verify changes)

### Import System
- `imports/resilient_importer.py` - **High-performance production importer** (60x faster, handles 500+ files)
- `imports/pharmacies.py` - CSV importer (handles empty state_licenses)
- `imports/states.py` - JSON importer (auto-deduplication, legacy for small datasets)
- `imports/scoring.py` - Lazy scoring engine
- `imports/validated.py` - Validation importer (framework ready, not fully implemented)

### Scoring Algorithm
- `scoring_plugin.py` - Address matching (70% street, 30% city/state/zip)
- Thresholds: ≥85 = match, 60-84 = weak match, <60 = no match
- Expected accuracy: 96.5% for exact matches

## Common Tasks

### Import New Data

**For Production (500+ files) - Use Resilient Importer:**
```bash
# Import state searches with images (recommended)
make import_scrape_states                    # Supabase backend

# Direct usage with options
python3 imports/resilient_importer.py \
    --states-dir "/path/to/data" \
    --tag "Aug-04-scrape" \
    --batch-size 25 \
    --max-workers 16 \
    --debug-log
```

**For Small Datasets - Legacy Importers:**
```python
# Pharmacies with automatic tag versioning
from imports.pharmacies import PharmacyImporter
importer = PharmacyImporter()
importer.import_csv('data.csv', 'jan_2024')  # Creates unique version if tag exists

# State searches with deduplication (small datasets only)
from imports.states import StateImporter
importer = StateImporter()
importer.import_directory('FL_searches/', 'fl_jan_2024')
```

### Compute Missing Scores
```python
from imports.scoring import ScoringEngine
engine = ScoringEngine()
engine.compute_missing_scores('states_tag', 'pharmacies_tag', batch_size=100)
```

### Query Comprehensive Results
```sql
SELECT * FROM get_all_results_with_context(
    'states_tag',
    'pharmacies_tag',
    'validated_tag'  -- Optional
);
```

## Architecture Principles

1. **Dataset Versioning**: All data tagged (e.g., "jan_2024"), no global "active" state
2. **Natural Keys**: Uses pharmacy names + license numbers, not internal IDs
3. **Lazy Computation**: Scores computed on-demand, cached permanently
4. **Comprehensive Results**: Single query returns all data for client-side processing
5. **Session Caching**: Results cached in Streamlit session state

## Known Issues & Workarounds

### Images Table Issue
Images link to dataset + search metadata, not individual results. This causes duplicates when joining.
**Workaround**: Query without image JOIN, handle screenshots separately.

### GUI Filtering
Default view filters to show only pharmacy-state combinations with search data. For small test data sets without this, you'd see 100+ rows of "no data". "no data" rows will decrease in production.

## Testing Requirements

Maintain sn used system tests:
1. Run `python system_test.py` - Must show "✅ PASS"
2. Verify GUI loads: `streamlit run app.py`

## Import Data Formats

### Pharmacy CSV
```csv
name,address,city,state,zip,state_licenses
"Pharmacy A","123 Main St","Orlando","FL","32801","[\"FL\",\"GA\"]"
```

### State Search JSON
```json
{
  "metadata": {
    "search_name": "Pharmacy A",
    "search_state": "FL",
    "search_timestamp": "2024-01-15T10:00:00Z"
  },
  "results": [{
    "license_number": "FL12345",
    "license_status": "Active",
    "address": "123 Main St",
    "city": "Orlando",
    "state": "FL",
    "zip": "32801"
  }]
}
```


## Recent Important Changes

1. **Empty State Licenses**: Now supported - `[]` is valid
2. **Auto-versioning**: Same tag creates "(2)", "(3)" versions
3. **Comprehensive Results**: Replaced aggregated queries with single query + client processing
4. **Validation System**: Fully implemented in GUI, `imports/validated.py` framework ready

## Documentation Structure

- `README.md` - Quick start and overview
- `docs/ARCHITECTURE.md` - System design
- `docs/DEVELOPMENT.md` - Setup and workflow
- `docs/USER_GUIDE.md` - Web interface usage
- `docs/API_REFERENCE.md` - Functions and modules
- `docs/TESTING.md` - Test procedures
- `docs/TROUBLESHOOTING.md` - Common issues

## Do's and Don'ts

✅ DO:
- Run `system_test.py` after changes
- Use the migration system for all database changes
- Use existing import patterns
- Keep the merged search_results table
- Use lazy scoring
- Cache results in session
- Use `python setup.py` for new database setup
- Use `migrations/migrate.py` for Supabase schema documentation and verification
- Use consolidated SQL file for Supabase setup

❌ DON'T:
- Edit `schema.sql` or `functions_comprehensive.sql` directly (LEGACY FILES)
- Split search_results table
- Add global "active" flags
- Compute all scores upfront
- Query database repeatedly for same data
- Use SUPABASE_ANON_KEY for admin operations (use SERVICE_KEY)
- Bypass the migration system for schema changes
- Mix direct SQL edits with migration system