# PharmChecker Migration System Guide

This guide explains how to use the PharmChecker unified migration system that supports both PostgreSQL and Supabase backends.

## Overview

The migration system ensures identical database schemas across environments by using versioned SQL migration files. All database changes must go through this system to maintain consistency.

## Directory Structure

```
migrations/
├── MIGRATION_GUIDE.md                # This guide
├── README.md                         # Basic usage instructions
├── config.toml                       # Migration configuration
├── migrate.py                        # Universal migration runner
├── supabase_setup_consolidated.sql   # Complete Supabase setup (all migrations)
├── migrations/                       # Individual migration files
│   ├── 20240101000000_initial_schema.sql
│   ├── 20240101000001_comprehensive_functions.sql
│   └── 20240101000002_indexes_and_performance.sql
└── seed.sql                          # Optional development seed data
```

## Migration Files

### Naming Convention
Migrations follow the pattern: `YYYYMMDDHHMMSS_descriptive_name.sql`

- **Timestamp**: Ensures chronological ordering
- **Description**: Clear, descriptive name in snake_case

### Migration Content
Each migration should:
- Use `CREATE TABLE IF NOT EXISTS` for safety
- Include proper indexes and constraints
- Be idempotent (safe to run multiple times)
- Include comments explaining purpose

### Example Migration
```sql
-- Migration: Add new feature table
-- Date: 2024-01-15
-- Description: Adds support for feature X

CREATE TABLE IF NOT EXISTS feature_table (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_feature_name ON feature_table(name);
```

## Using the Migration System

### 1. Automatic Setup (Recommended)
```bash
# Auto-detects backend and applies all migrations
python setup.py

# Force specific backend
python setup.py --backend postgresql
python setup.py --backend supabase
```

### 2. Manual Migration Control
```bash
# Check migration status
python migrations/migrate.py --status --target local
python migrations/migrate.py --status --target supabase

# Apply migrations
python migrations/migrate.py --target local              # PostgreSQL only
python migrations/migrate.py --target supabase          # Shows manual instructions
```

### 3. Backend-Specific Instructions

#### PostgreSQL (Automatic)
```bash
python migrations/migrate.py --target local
```
- Connects directly to PostgreSQL
- Applies migrations automatically
- Updates migration tracking table

#### Supabase (Manual)
```bash
# 1. Check what needs to be done
python migrations/migrate.py --target supabase

# 2. Use consolidated file for easy setup
# Copy/paste: migrations/supabase_setup_consolidated.sql
# Into Supabase Dashboard > SQL Editor
```

## Backend Detection

The system detects which backend to use based on environment variables:

### Supabase Detection
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_service_key_jwt
```

### PostgreSQL Detection  
```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=pharmchecker
DB_USER=postgres
DB_PASSWORD=your_password
```

### Override Detection
```bash
python setup.py --backend postgresql  # Force PostgreSQL
python setup.py --backend supabase    # Force Supabase
```

## Migration Tracking

### Migration Table
All applied migrations are tracked in `pharmchecker_migrations`:
```sql
CREATE TABLE pharmchecker_migrations (
  version VARCHAR(255) PRIMARY KEY,     -- Migration filename
  name VARCHAR(255),                    -- Human-readable name
  applied_at TIMESTAMP DEFAULT NOW()    -- When applied
);
```

### Checking Status
```bash
# View applied migrations
python migrations/migrate.py --status --target local

# Example output:
# 📊 Migration Status (local)
# ==================================================
# ✅ Applied | 20240101000000_initial_schema | Initial Schema
# ✅ Applied | 20240101000001_comprehensive_functions | Functions
# ⏳ Pending | 20240101000002_new_feature | New Feature Table
```

## Creating New Migrations

### 1. Create Migration File
```bash
# Create new migration file with timestamp
date +"%Y%m%d%H%M%S"_add_new_feature.sql > migrations/migrations/$(date +"%Y%m%d%H%M%S")_add_new_feature.sql
```

### 2. Write Migration SQL
```sql
-- Migration: Add new feature support
-- Description: Adds tables and indexes for feature X

CREATE TABLE IF NOT EXISTS new_feature (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  data JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_new_feature_name ON new_feature(name);
```

### 3. Test Migration
```bash
# Test on PostgreSQL
python migrations/migrate.py --target local

# Update consolidated file for Supabase
# Add your migration SQL to supabase_setup_consolidated.sql
```

### 4. Update Consolidated File
Add your new migration to `supabase_setup_consolidated.sql`:
```sql
-- =============================================================================
-- MIGRATION 4: Add New Feature
-- =============================================================================

-- Your migration SQL here...

-- Update migration tracking
INSERT INTO pharmchecker_migrations (version, name) VALUES
  ('20240115120000_add_new_feature', 'Add New Feature')
ON CONFLICT (version) DO NOTHING;
```

## Best Practices

### ✅ Do
- **Always use migrations** for schema changes
- **Test locally first** before Supabase
- **Use IF NOT EXISTS** for safety
- **Include descriptive comments** in migrations
- **Keep migrations small and focused** on one change
- **Update consolidated file** when adding migrations

### ❌ Don't
- **Edit `schema.sql` directly** (legacy file)
- **Edit `functions_comprehensive.sql` directly** (legacy file)
- **Skip migration system** for "quick fixes"
- **Delete migration files** once applied
- **Change applied migrations** (create new ones instead)

## Troubleshooting

### Common Issues

#### 1. Migration Already Applied
```
Error: Migration already applied
```
**Solution**: Check status with `--status` flag. Migrations are idempotent.

#### 2. PostgreSQL Connection Failed
```
Error: connection to server failed
```
**Solution**: Check `.env` file database credentials.

#### 3. Supabase Table Not Found
```
Error: Could not find the table
```
**Solution**: Run consolidated SQL file in Supabase Dashboard.

#### 4. Migration Order Issues
```
Error: dependency not found
```
**Solution**: Check migration timestamps. Dependencies must be applied first.

### Recovery Procedures

#### Reset Migration Tracking
```sql
-- CAUTION: Only use if migration tracking is corrupted
DELETE FROM pharmchecker_migrations;
-- Then re-apply all migrations
```

#### Force Re-run Migration
```sql
-- Remove specific migration from tracking
DELETE FROM pharmchecker_migrations WHERE version = '20240101000000_initial_schema';
-- Then re-run migrations
```

## Environment Consistency

### Ensuring Identical Schemas
1. **Use same migration files** across all environments
2. **Apply in same order** (timestamp-based)
3. **Verify with status checks** before deploying
4. **Test system_test.py** after migration changes

### Schema Verification
```bash
# After migrations, verify system works
python system_test.py

# Check specific backend
python setup.py --backend postgresql
python setup.py --backend supabase
```

## Migration Philosophy

The PharmChecker migration system follows these principles:

1. **Schema as Code**: All database changes versioned in git
2. **Environment Parity**: Identical schemas across dev/staging/prod
3. **Forward-Only**: Migrations applied in chronological order
4. **Idempotent Operations**: Safe to run multiple times
5. **Atomic Changes**: Each migration is a complete unit
6. **Audit Trail**: Full history of all schema changes

This ensures reliable, repeatable database deployments across all environments.