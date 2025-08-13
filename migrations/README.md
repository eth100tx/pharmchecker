# PharmChecker Database Migration System

This directory contains the unified database migration system for PharmChecker, supporting both local PostgreSQL and Supabase deployment.

## Directory Structure

- `config.toml` - Database project configuration
- `migrations/` - Versioned database migration files
- `seed.sql` - Optional seed data for development
- `migrate.py` - Universal migration runner script

## Migration Files

Migrations are numbered sequentially and contain:

1. `20240101000000_initial_schema.sql` - Core table definitions and extensions
2. `20240101000001_comprehensive_functions.sql` - Custom PostgreSQL functions  
3. `20240101000002_indexes_and_performance.sql` - Indexes and performance optimizations

## Usage

### Apply Migrations to Supabase

```bash
python migrations/migrate.py --target supabase
```

### Apply Migrations to Local PostgreSQL

```bash
python migrations/migrate.py --target local
```

### Check Migration Status

```bash
python migrations/migrate.py --status
```

## Environment Variables

The migration system uses these environment variables from `.env`:

- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_SERVICE_KEY` - Service role key for admin operations
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` - Local PostgreSQL settings

## Migration Tracking

Migrations are tracked in the `pharmchecker_migrations` table, which is automatically created on first run.

## Integration with setup.py

The `setup.py` script now uses this migration system to ensure both local and Supabase databases are initialized consistently. It automatically detects and applies any pending migrations.