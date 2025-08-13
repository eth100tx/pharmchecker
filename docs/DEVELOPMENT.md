# PharmChecker Development Guide

## Development Setup

### Prerequisites

1. **Database Backend** (Choose one)
   
   **Option A: PostgreSQL 13+ (Local Development)**
   ```bash
   # macOS
   brew install postgresql@14
   brew services start postgresql@14
   
   # Ubuntu/Debian
   sudo apt-get install postgresql-13 postgresql-contrib-13
   
   # Enable pg_trgm extension
   psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
   ```
   
   **Option B: Supabase (Cloud Development)**
   - Create account at https://supabase.com
   - Create new project
   - Note your project URL and service key

2. **Python 3.8+**
   ```bash
   python3 --version  # Verify 3.8 or higher
   ```

3. **Git**
   ```bash
   git --version
   ```

### Initial Setup

1. **Clone Repository**
   ```bash
   git clone [repository-url]
   cd pharmchecker
   ```

2. **Create Virtual Environment** (Recommended)
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` with your settings:
   
   **For PostgreSQL:**
   ```env
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=pharmchecker
   DB_USER=postgres
   DB_PASSWORD=yourpassword
   
   # Development settings
   LOGGING_LEVEL=DEBUG
   AUTH_MODE=local
   DEFAULT_USER_EMAIL=dev@localhost
   DEFAULT_USER_ROLE=admin
   ```
   
   **For Supabase:**
   ```env
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_SERVICE_KEY=your_service_key_jwt
   
   # Development settings
   LOGGING_LEVEL=DEBUG
   AUTH_MODE=local
   DEFAULT_USER_EMAIL=dev@localhost
   DEFAULT_USER_ROLE=admin
   ```

5. **Initialize Database**
   ```bash
   # Auto-detect backend from .env
   python setup.py
   
   # Or force specific backend
   python setup.py --backend postgresql
   python setup.py --backend supabase
   ```
   
   **Note for Supabase**: After running setup, you'll need to manually execute the consolidated SQL file in your Supabase Dashboard.
   
   This will:
   - Create database if not exists (PostgreSQL only)
   - Apply all database migrations automatically
   - Create migration tracking table
   - Set up tables, functions, and indexes
   - Create default admin user (PostgreSQL only)

6. **Verify Installation**
   ```bash
   python system_test.py
   ```
   
   Expected output:
   ```
   ✅ Clean existing test data
   ✅ Import pharmacy data
   ✅ Import state search data
   ✅ Query initial results
   ✅ Run scoring engine
   ✅ Query final results
   Overall Success: ✅ PASS
   ```

## Database Migration System

PharmChecker uses a unified migration system that works with both PostgreSQL and Supabase. All database schema changes go through versioned migration files.

### Migration Directory Structure
```
migrations/
├── migrate.py                        # Migration runner
├── migrations/                       # Individual migration files
├── supabase_setup_consolidated.sql   # Complete Supabase setup
└── MIGRATION_GUIDE.md               # Detailed migration guide
```

### Common Migration Commands
```bash
# Check migration status
python migrations/migrate.py --status --target local

# Apply migrations to PostgreSQL
python migrations/migrate.py --target local

# For Supabase: Use consolidated SQL file in Dashboard
cat migrations/supabase_setup_consolidated.sql
```

### Creating New Migrations
When you need to modify the database schema:

1. **Create new migration file** with timestamp:
   ```bash
   touch migrations/migrations/$(date +"%Y%m%d%H%M%S")_your_change.sql
   ```

2. **Write migration SQL** using safe patterns:
   ```sql
   CREATE TABLE IF NOT EXISTS new_table (
     id SERIAL PRIMARY KEY,
     name TEXT NOT NULL
   );
   ```

3. **Test migration locally**:
   ```bash
   python migrations/migrate.py --target local
   ```

4. **Update consolidated file** for Supabase users

**Important**: Never edit `schema.sql` or `functions_comprehensive.sql` directly. Use the migration system.

## Development Workflow

### Using the Makefile

The Makefile provides convenient commands for common tasks:

```bash
# Database operations
make setup          # Initialize/reset database
make status         # Show current database state
make clean_all      # Complete database reset
make clean_states   # Remove search data only

# Data import
make import_pharmacies     # Import test pharmacy data
make import_test_states    # Import FL/PA search results
make import_test_states2   # Import additional test data
make dev                   # Full workflow: clean + import all

# Testing
make test           # Run basic import tests
```

### Manual Data Import

```bash
# Import pharmacy CSV
python -m imports.pharmacies data/pharmacies.csv "tag_name" \
    --created_by="developer" \
    --description="January 2024 pharmacy list"

# Import state search results
python -m imports.states data/FL_searches/ "fl_jan_2024" \
    --created_by="developer" \
    --description="Florida January searches"

# Import validation overrides
python -m imports.validated data/validations.csv "validated_jan_2024"
```

### Running the Application

```bash
# Start Streamlit server
streamlit run app.py

# With custom port
streamlit run app.py --server.port 8502

# With debugging
LOGGING_LEVEL=DEBUG streamlit run app.py
```

## Code Structure

### Directory Layout

```
pharmchecker/
├── imports/              # Data import modules
│   ├── base.py          # Base importer class
│   ├── pharmacies.py    # Pharmacy CSV importer
│   ├── states.py        # State JSON importer
│   ├── scoring.py       # Scoring engine
│   └── validated.py     # Validation importer
├── utils/               # GUI utility modules
│   ├── database.py      # Database operations
│   ├── display.py       # UI components
│   ├── auth.py          # Authentication
│   └── session.py       # Session management
├── data/                # Test data files
├── docs/                # Documentation
├── app.py               # Main Streamlit application
├── schema.sql           # Database schema
├── functions_comprehensive.sql  # DB functions
└── system_test.py       # End-to-end test
```

### Key Classes and Functions

#### Import System
```python
# Base class for all importers
class BaseImporter:
    def create_dataset(kind, tag, description)
    def batch_insert(table, records)
    def cleanup_on_error()

# Specific importers
PharmacyImporter.import_csv(filepath, tag)
StateImporter.import_directory(dirpath, tag)
ScoringEngine.compute_missing_scores(states_tag, pharmacies_tag)
```

#### Database Operations
```python
# Get comprehensive results
results = get_all_results_with_context(
    states_tag="fl_jan_2024",
    pharmacies_tag="pharmacies_2024",
    validated_tag="validated_jan"
)

# Find missing scores
missing = find_missing_scores(states_tag, pharmacies_tag)
```

#### GUI Components
```python
# Display functions from utils/display.py
display_results_table(dataframe, filters)
display_pharmacy_card(pharmacy_data)
create_status_distribution_chart(results)
create_export_button(dataframe)
```

## Testing

### Running Tests

```bash
# Full system test
python system_test.py

# Test scoring algorithm
python test_scoring.py

# Test GUI components
python test_gui.py

# Quick import test
make test
```

### Test Data

Sample data in `data/` directory:
- `pharmacies_new.csv`: 5 test pharmacies
- `states_baseline/`: FL and PA search results
- `states_baseline2/`: Additional test data with Empower pharmacy

### Writing Tests

Add new tests to appropriate test files:

```python
# test_scoring.py
def test_custom_scoring():
    engine = ScoringEngine()
    score = engine.score_addresses(
        pharm_addr="123 Main St",
        result_addr="123 Main Street"
    )
    assert score >= 90  # Should match
```

## Debugging

### Enable Debug Logging

In `.env`:
```env
LOGGING_LEVEL=DEBUG
```

Or at runtime:
```bash
LOGGING_LEVEL=DEBUG python app.py
```

### Common Issues and Solutions

#### Database Connection Failed
```
Error: could not connect to database
```
Solution:
- Check PostgreSQL is running: `pg_isready`
- Verify .env credentials
- Check database exists: `psql -U postgres -l`

#### Import Fails with Duplicate Key
```
Error: duplicate key value violates unique constraint
```
Solution:
- Use different tag for dataset
- Or clean existing data: `make clean_states`

#### Scoring Engine Timeout
```
Error: scoring computation timeout
```
Solution:
- Reduce batch size in scoring.py
- Check database indexes exist
- Run VACUUM ANALYZE on tables

#### Streamlit Session Issues
```
Error: session state not found
```
Solution:
- Clear browser cache
- Restart Streamlit server
- Check session.py for errors

### Database Queries for Debugging

```sql
-- Check dataset versions
SELECT kind, tag, created_at, 
       (SELECT COUNT(*) FROM pharmacies WHERE dataset_id = d.id) as count
FROM datasets d WHERE kind = 'pharmacies';

-- Find duplicate search results
SELECT dataset_id, search_state, license_number, COUNT(*)
FROM search_results
GROUP BY dataset_id, search_state, license_number
HAVING COUNT(*) > 1;

-- Check scoring status
SELECT states_dataset_id, pharmacies_dataset_id, 
       COUNT(*) as total_scores,
       AVG(score_overall) as avg_score
FROM match_scores
GROUP BY states_dataset_id, pharmacies_dataset_id;

-- Find unscored combinations
SELECT * FROM find_missing_scores('states_tag', 'pharmacies_tag');
```

## Contributing

### Code Style

- Follow PEP 8 for Python code
- Use type hints for function parameters
- Add docstrings to all public functions
- Keep functions under 50 lines

### Commit Messages

Format: `<type>: <description>`

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `test`: Testing
- `refactor`: Code restructuring
- `chore`: Maintenance

Examples:
```
feat: add CSV export for validation results
fix: handle empty state_licenses array in import
docs: update API reference for scoring engine
```

### Pull Request Process

1. Create feature branch from main
2. Make changes with tests
3. Run `python system_test.py` to verify
4. Update documentation if needed
5. Submit PR with description

## Performance Optimization

### Database Indexes

Critical indexes for performance:
```sql
-- Check existing indexes
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename IN ('pharmacies', 'search_results', 'match_scores');

-- Add missing indexes if needed
CREATE INDEX IF NOT EXISTS ix_results_lookup 
ON search_results(dataset_id, search_name, search_state);
```

### Caching Strategy

1. **Database Results**: Cached in session state
2. **Scoring Results**: Permanently stored in match_scores
3. **Dataset Lists**: Cached with 5-minute TTL
4. **Screenshots**: Browser cached with etags

### Batch Processing

For large imports:
```python
# Adjust batch size in imports/base.py
BATCH_SIZE = 500  # Default is 1000

# Or override in specific importer
importer = PharmacyImporter()
importer.batch_insert(records, batch_size=500)
```

## Deployment Preparation

### Environment Variables

Production `.env`:
```env
# Database
DB_HOST=prod-db.example.com
DB_PORT=5432
DB_NAME=pharmchecker_prod
DB_USER=pharmchecker_app
DB_PASSWORD=<secure_password>

# Authentication
AUTH_MODE=github
GITHUB_CLIENT_ID=<oauth_app_id>
GITHUB_CLIENT_SECRET=<oauth_secret>

# Storage (optional)
STORAGE_TYPE=supabase
SUPABASE_URL=<project_url>
SUPABASE_KEY=<anon_key>

# Logging
LOGGING_LEVEL=INFO
```

### Database Migration

```bash
# Export schema
pg_dump -U postgres -d pharmchecker --schema-only > schema_backup.sql

# Import to production
psql -U prod_user -d pharmchecker_prod < schema.sql
psql -U prod_user -d pharmchecker_prod < functions_comprehensive.sql
```

### Health Checks

Add to monitoring:
- Database connectivity
- Streamlit port availability  
- Disk space for screenshots
- Memory usage
- Query performance