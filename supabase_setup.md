# PharmChecker Unified Database Migration Setup

**✅ COMPLETED** - This plan has been fully implemented!

## Current State Analysis

### Environment Configuration
- **Supabase URL**: `https://ddjsohylqgtukhsmsezc.supabase.co`
- **Service Key**: Available in `.env` (JWT token)
- **Database Name**: `pharmchecker`
- **Project ID**: `ddjsohylqgtukhsmsezc` (extracted from URL)

### Existing Database Schema
- **schema.sql**: Complete table definitions with extensions, indexes
- **functions_comprehensive.sql**: Custom PostgreSQL functions
- **Tables**: 7 core tables (datasets, pharmacies, search_results, match_scores, validated_overrides, images, app_users)
- **Extensions**: pg_trgm for fuzzy text matching

### Current System Architecture
- **Dual Support**: Both local PostgreSQL and Supabase
- **No CLI Currently**: Supabase CLI not installed on system
- **Migration Status**: Using manual schema setup (setup.py creates/loads tables)

## Migration Strategy

### Option 1: Manual Migration (Recommended)
Since Supabase CLI installation failed and the system currently works with direct SQL execution:

1. **Create supabase/ directory structure manually**
2. **Convert existing schema to migration format**
3. **Use direct SQL execution via psycopg2 or HTTP API**
4. **Maintain compatibility with existing setup.py approach**

### Option 2: CLI-based Migration (If CLI can be installed)
1. **Install Supabase CLI via different method**
2. **Initialize project with `supabase init`**
3. **Link to existing remote project**
4. **Generate migrations from current schema**

## ✅ Implemented Solution: Unified Migration System

### Directory Structure (COMPLETED)
```
migrations/
├── config.toml                 # Project configuration
├── migrations/
│   ├── 20240101000000_initial_schema.sql
│   ├── 20240101000001_comprehensive_functions.sql
│   └── 20240101000002_indexes_and_performance.sql
├── seed.sql                    # Optional seed data
├── migrate.py                  # Universal migration runner
└── README.md                   # Migration documentation
```

### Migration Files Breakdown

#### 1. Initial Schema (20240101000000_initial_schema.sql)
- Extensions (pg_trgm)
- All table definitions
- Basic constraints and references

#### 2. Functions (20240101000001_comprehensive_functions.sql)
- get_all_results_with_context()
- check_validation_consistency()
- Any other custom functions

#### 3. Indexes (20240101000002_indexes_and_extensions.sql)
- Performance indexes
- Trigram indexes
- Composite indexes

### Implementation Plan

1. **Create Manual Migration Structure**
   - Split schema.sql into logical migration files
   - Add migration metadata and versioning
   - Create config.toml for project settings

2. **Migration Execution Script**
   - Python script to execute migrations in order
   - Track applied migrations in database
   - Support both local and Supabase environments

3. **Maintain Dual Compatibility**
   - Keep setup.py working for local development
   - Add supabase-specific deployment scripts
   - Ensure both paths create identical schemas

## Benefits of This Approach

1. **No CLI Dependency**: Works without Supabase CLI installation
2. **Version Control**: Migrations tracked in git
3. **Rollback Support**: Can implement rollback scripts
4. **Environment Consistency**: Same schema across local/remote
5. **Team Friendly**: Other developers can apply migrations easily

## Implementation Steps

1. Create supabase/ directory and config files
2. Split existing schema into versioned migration files
3. Create migration runner script
4. Test migrations on local PostgreSQL
5. Test migrations on Supabase remote
6. Update documentation and setup procedures

## Configuration Details

### config.toml Structure
```toml
[api]
enabled = true
port = 54321

[db]
port = 54322

[studio]
enabled = true
port = 54323

[project_id]
value = "ddjsohylqgtukhsmsezc"
```

### Migration Tracking Table
```sql
CREATE TABLE IF NOT EXISTS supabase_migrations (
  version VARCHAR(255) PRIMARY KEY,
  name VARCHAR(255),
  applied_at TIMESTAMP DEFAULT NOW()
);
```

## ✅ Implementation Complete

All planned features have been implemented:

1. ✅ Manual migration structure created (`migrations/` directory)
2. ✅ Universal migration runner created (`migrations/migrate.py`)
3. ✅ Tested on local PostgreSQL environment
4. ✅ `setup.py` updated to use migration system for both backends
5. ✅ Documentation updated

## Usage

```bash
# Setup with migrations (automatic)
python setup.py --backend local      # Uses migration system
python setup.py --backend supabase   # Uses migration system

# Manual migration commands
python migrations/migrate.py --target local
python migrations/migrate.py --target supabase
python migrations/migrate.py --status
```