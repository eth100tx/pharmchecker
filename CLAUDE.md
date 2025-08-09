# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PharmChecker is a lightweight internal tool for verifying pharmacy licenses across U.S. states through manual review of automated search results. This repository contains comprehensive implementation documentation and database configurations.

## Key Design Principles

- **Dataset Independence**: Pharmacies, state searches, and validated overrides can be imported and combined in any order
- **Natural Key Linking**: Cross-dataset relationships use pharmacy names and license numbers, not internal IDs
- **Multi-User Support**: Multiple users can work with different dataset combinations simultaneously
- **Lazy Scoring**: Address match scores computed on-demand when needed
- **Manual Control**: All refresh and recalculation actions are explicit
- **Validation as Snapshot**: Validated overrides capture the full search result at validation time

## Database Access

This project uses MCP (Model Context Protocol) servers to connect to PostgreSQL databases:

- **postgres-prod**: Production database at `localhost:5432/pharmchecker`
- **postgres-sbx**: Sandbox database at `localhost:5432/testing_sandbox_db`
- **supabase**: Supabase project integration (requires project-ref configuration)

Use the MCP tools (`mcp__postgres-prod__query`, `mcp__postgres-sbx__query`, `mcp__supabase__*`) to interact with databases.

## Core Architecture Components

1. **PostgreSQL Database** - Stores all datasets and computed scores
2. **Import Scripts** - Load pharmacies, state searches, and validated overrides  
3. **Scoring Engine** - Computes address match scores on-demand
4. **Streamlit UI** - Review interface with GitHub authentication
5. **Storage Layer** - Local filesystem (dev) or Supabase Storage (production)

## Database Schema (Optimized)

### Core Tables
- `datasets` - Versioned datasets (states, pharmacies, validated)
- `pharmacies` - Pharmacy master records with state licenses
- `search_results` - **MERGED TABLE**: Search parameters + results with automatic deduplication
- `match_scores` - Computed address match scores (lazy calculation)
- `validated_overrides` - Manual validation snapshots
- `images` - Screenshot storage metadata
- `app_users` - User allowlist for authentication

**Key Optimization**: The original separate `searches` and `search_results` tables have been merged into a single `search_results` table. This eliminates timing conflicts and provides automatic deduplication on `(dataset_id, search_state, license_number)` with latest timestamp winning.

### Key Functions
- `get_results_matrix(states_tag, pharmacies_tag, validated_tag)` - Main view combining all data
- `find_missing_scores(states_tag, pharmacies_tag)` - Identifies pairs needing scoring

## Implementation Architecture

The system follows a versioned dataset approach where:
- Data imports are tagged (e.g., "2024-01-15", "pilot-test")
- No global "active" state - views are generated for specific tag combinations  
- Scoring is computed lazily only for needed pharmacy/state pairs
- Manual validations create complete snapshots of search results

## Implementation Status

### ✅ COMPLETED (Core System Operational)
- **Database Infrastructure**: Optimized PostgreSQL schema with merged tables
- **Import System**: Complete pharmacy and state search importers with error handling
- **Screenshot Management**: Automatic screenshot indexing and metadata storage
- **Development Tools**: Makefile with convenient commands, status utilities
- **Data Processing**: Sample data successfully imported (pharmacies + state searches + screenshots)

### 🚧 IN DEVELOPMENT  
- **Address Scoring Engine**: `scoring_plugin.py` for smart address matching
- **Lazy Scoring System**: `imports/scoring.py` for on-demand score computation

### 📋 PENDING
- **Streamlit UI**: `app.py` web interface for review and validation
- **Validated Overrides**: `imports/validated.py` for manual validation management

## Development Commands

Use the Makefile for convenient development operations:

```bash
# Database status and management
make status           # Show current database state
make clean_states     # Clean search data (keep pharmacies)
make clean_all        # Full database reset
make setup           # Initialize/reset database

# Data import  
make import_test_states    # Import data/states_baseline
make import_test_states2   # Import data/states_baseline2
make import_pharmacies     # Import pharmacy data
make dev                  # Full workflow: pharmacies + both state datasets

# Development workflow
make reload          # Clean states + import baseline
make test           # Run import tests
```

## Key Files and Components

### Import System (`imports/` directory)
- **`base.py`**: BaseImporter class with batch operations, error handling, dataset management
- **`pharmacies.py`**: PharmacyImporter for CSV pharmacy data with legacy format conversion
- **`states.py`**: StateImporter for JSON search results with deduplication and screenshot handling
- **`validated.py`**: ValidatedImporter (pending implementation)

### Database Management
- **`schema.sql`**: Complete database schema with optimized merged table structure
- **`functions.sql`**: Database functions updated for merged schema
- **`setup.py`**: Automated database initialization and setup
- **`show_status.py`**: Database status utility showing datasets and record counts
- **`clean_search_db.py`**: Utility for cleaning search data while preserving pharmacies

### Configuration and Utilities  
- **`config.py`**: Database connection management with environment variable support
- **`Makefile`**: Development commands for all common operations
- **`.gitignore`**: Configured to exclude temporary files, environment configs

### Data Organization
- **`data/pharmacies_new.csv`**: Sample pharmacy data (5 pharmacies)
- **`data/states_baseline/`**: Sample state search data (FL/PA with screenshots)  
- **`data/states_baseline2/`**: Additional sample data including Empower searches
- **`tmp/`**: Temporary files (migration scripts, conversion tools, test files)

## Status Classification

Results are classified into status buckets:
- **match**: Score ≥ 85 (or validated as present with good score)
- **weak match**: Score 60-84
- **no match**: Score < 60
- **no data**: No search conducted or no results found

## Address Scoring Algorithm (Pending Implementation)

The scoring plugin (`scoring_plugin.py`) will implement:
- Street address matching (70% weight) with fuzzy string matching
- City/State/ZIP matching (30% weight) with exact matching  
- Suite/apartment number consideration
- Normalization of common address abbreviations

## Data Import Patterns

### Pharmacy Data Format
- **Input**: CSV with `name`, `state_licenses` (JSON array), address fields
- **Processing**: Legacy format conversion handled automatically
- **Deduplication**: By pharmacy name within dataset

### State Search Data Format  
- **Input**: Directory of JSON files per search (e.g., `Belmar_01_parse.json`)
- **Automatic Deduplication**: ON CONFLICT handling by `(dataset_id, search_state, license_number)`
- **Screenshot Handling**: Automatic path resolution and metadata storage
- **Result Types**: 
  - `results_found`: Normal search results with license data
  - `no_results_found`: Empty search results (e.g., `Pharmacy_no_results_parse.json`)

### Validated Override Format (Pending)
- **Input**: CSV with pharmacy name, state, license number, override type, reason
- **Types**: `present` (force match) or `empty` (force no match)
- **Snapshot**: Captures complete search result state at validation time

## Technical Implementation Notes

### Database Optimizations
- **Merged Table Benefit**: Eliminates timing conflicts between search metadata and results
- **Automatic Deduplication**: Latest timestamp wins for duplicate search/license combinations
- **Natural Keys**: Uses pharmacy names + license numbers for relationships (not internal IDs)
- **Lazy Computation**: Scores computed only when needed for specific dataset combinations

### MCP Integration
- **Database Operations**: Use `mcp__postgres-prod__query` for production database access
- **Sandbox Testing**: Use `mcp__postgres-sbx__query` for development/testing
- **Supabase Integration**: Optional cloud storage via `mcp__supabase__*` tools

## Next Development Priorities

1. **🔥 IMMEDIATE**: Implement `scoring_plugin.py` - Address matching algorithm
2. **🔥 IMMEDIATE**: Implement `imports/scoring.py` - Lazy scoring engine
3. **Streamlit UI**: Create `app.py` - Web interface for review and validation
4. **Integration Testing**: End-to-end workflow validation
5. **Polish**: Complete `imports/validated.py` - Override management system

