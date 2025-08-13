# PharmChecker 💊

A pharmacy license verification system that imports search results from state boards, automatically scores address matches, and provides a web interface for manual review and validation.

## Overview

PharmChecker streamlines pharmacy license verification across multiple U.S. states by:

- **Importing** pharmacy data (CSV) and state board search results (JSON)
- **Scoring** addresses automatically using fuzzy matching algorithms  
- **Reviewing** results through an interactive Streamlit web dashboard
- **Validating** findings manually with audit trail support
- **Exporting** verified results for compliance reporting

**Key Features:** Dual database support (PostgreSQL/Supabase), unified migration system, dataset versioning, lazy scoring computation, multi-user sessions, natural key linking (no hardcoded IDs), comprehensive validation system with overrides.

## Architecture Overview

```
CSV/JSON Files → Import System → Database (PostgreSQL/Supabase) → Scoring Engine → Web Interface
                                            ↓
                                  Versioned Datasets + Screenshots + Validations
```

- **Dual database support** with PostgreSQL (local) or Supabase (cloud) via unified migration system
- **Lazy scoring system** computes address matches only when needed
- **Multi-user support** with session management and authentication  
- **Natural key linking** using pharmacy names/license numbers (not internal IDs)

## Quick Start

### Prerequisites
- **Database**: PostgreSQL 13+ with `pg_trgm` extension OR Supabase account
- **Runtime**: Python 3.8+
- **Storage**: 2GB free disk space for data and screenshots

### Installation

```bash
# 1. Clone repository
git clone [repository-url]
cd pharmchecker

# 2. Install dependencies  
pip install -r requirements.txt

# 3. Configure database
cp .env.example .env
# Option A: Local PostgreSQL
#   Edit DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
# Option B: Supabase  
#   Edit SUPABASE_URL, SUPABASE_SERVICE_KEY

# 4. Initialize database
python setup.py                       # Auto-detects backend from .env
# OR force specific backend:
python setup.py --backend postgresql  # Force local PostgreSQL
python setup.py --backend supabase    # Force Supabase

# 5. For Supabase: Manual SQL Setup Required
# If using Supabase, run this SQL in your Supabase Dashboard:
# Copy/paste: migrations/supabase_setup_consolidated.sql

# 6. Run system test to verify installation
python system_test.py
```

### Launch Application

```bash
# Import sample data
make dev  # Imports test pharmacies and state search results

# Start web interface
streamlit run app.py
# Opens at http://localhost:8501
```

The web dashboard includes:
- **Dataset Selection** - Load pharmacy, state search, and validation datasets
- **Results Matrix** - Review all pharmacy-state combinations with scores
- **Detail Views** - Examine individual search results and screenshots  
- **Validation Tools** - Mark results as verified with reasons
- **Export Functions** - Download results as CSV for reporting

## Database Migration System

PharmChecker includes a unified migration system that ensures identical database schemas across PostgreSQL and Supabase environments.

### Migration Components

```
migrations/
├── migrate.py                        # Universal migration runner
├── migrations/                       # Versioned migration files
│   ├── 20240101000000_initial_schema.sql
│   ├── 20240101000001_comprehensive_functions.sql
│   └── 20240101000002_indexes_and_performance.sql
├── supabase_setup_consolidated.sql   # Complete Supabase setup (all-in-one)
├── config.toml                       # Migration configuration
└── README.md                         # Migration documentation
```

### Migration Commands

```bash
# Check migration status
python migrations/migrate.py --status --target local     # PostgreSQL
python migrations/migrate.py --status --target supabase  # Supabase (shows manual instructions)

# Apply migrations
python migrations/migrate.py --target local              # PostgreSQL (automatic)
# For Supabase: Use consolidated SQL file in Dashboard

# Setup with migrations (recommended)
python setup.py                                          # Auto-detects and applies migrations
```

### Database Backend Detection

The system automatically detects which database backend to use:

1. **Supabase Detection**: If `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are set
2. **PostgreSQL Detection**: If `DB_HOST` and related PostgreSQL vars are set  
3. **Manual Override**: Use `--backend postgresql` or `--backend supabase`

### Migration Features

- ✅ **Version Tracking**: All migrations tracked in `pharmchecker_migrations` table
- ✅ **Idempotent**: Safe to run multiple times, skips applied migrations
- ✅ **Schema Consistency**: Identical tables, functions, indexes across backends
- ✅ **Atomic Operations**: Each migration runs in a transaction
- ✅ **Rollback Ready**: Migration tracking supports future rollback features

## Project Structure

```
pharmchecker/
├── README.md                   # This file
├── requirements.txt            # Python dependencies
├── setup.py                   # Database initialization (auto-detects backend)
├── app.py                     # Streamlit web interface
├── schema.sql                 # Legacy database schema
├── migrations/                # Unified migration system
│   ├── migrate.py             # Migration runner for both backends
│   ├── migrations/            # Versioned migration files
│   └── supabase_setup_consolidated.sql  # Complete Supabase setup
├── system_test.py             # End-to-end validation
├── imports/                   # Data import system
│   ├── pharmacies.py          # CSV pharmacy importer
│   ├── states.py              # JSON search results importer
│   ├── scoring.py             # Address matching engine
│   └── validated.py           # Manual validation importer
├── utils/                     # GUI utilities
│   ├── database.py            # Database operations
│   └── display.py             # UI components
├── docs/                      # Comprehensive documentation
└── data/                      # Sample data for testing
```

## Typical Workflow

1. **Import pharmacy data**: `python -m imports.pharmacies data/pharmacies.csv "jan_2024"`
2. **Import state searches**: `python -m imports.states data/FL_searches/ "fl_jan_2024"`
3. **Launch web interface**: `streamlit run app.py`
4. **Select datasets**: Choose pharmacy and state datasets in sidebar
5. **Review results**: System auto-computes address match scores (85+ = match)
6. **Validate findings**: Mark verified results with reasons
7. **Export report**: Download CSV with all results and validations

## Key Features

### 🔄 Lazy Scoring System
- Address matching computed automatically when dataset combinations are first accessed
- Intelligent fuzzy matching algorithm with street/city/state/ZIP components
- Results cached permanently for performance

### 📊 Dataset Versioning  
- Import multiple versions of pharmacy, state, and validation data
- Mix and match any combination (e.g., "old pharmacies" + "new searches")
- No global "active" state - users work with specific dataset combinations

### 🌐 Web Interface
- **Streamlit-based** dashboard with real-time updates
- **Interactive filtering** by state, status, score ranges
- **Detail views** with side-by-side address comparisons
- **Screenshot integration** with automatic organization
- **Export functionality** with CSV downloads

### ✅ Validation System
- **Manual overrides** for automated scoring results
- **Two validation types**: "present" (license exists) and "empty" (no license)
- **Audit trail** with reasons, timestamps, user tracking
- **Warning system** detects data changes since validation

## Key Commands

```bash
# Database management
make setup           # Initialize database (uses auto-detection)
python setup.py --backend postgresql  # Force PostgreSQL setup
python setup.py --backend supabase    # Force Supabase setup
make status          # Show current data
make clean_all       # Full reset

# Migration management
python migrations/migrate.py --status          # Check migration status
python migrations/migrate.py --target local    # Apply to PostgreSQL
python migrations/migrate.py --target supabase # Apply to Supabase (manual)

# Development workflow  
make dev            # Import all test data
python system_test.py    # Run end-to-end test

# Data import
python -m imports.pharmacies <csv_file> <tag>
python -m imports.states <json_dir> <tag>
python -m imports.validated <csv_file> <tag>  

# Testing
python test_scoring.py   # Test address matching algorithm
python test_gui.py       # Test web interface components
```

## Documentation

| Document | Description | For |
|----------|-------------|-----|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, database schema, data flow | Developers |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Setup, debugging, contribution guide | Developers |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | Web interface usage, features | End Users |
| [docs/API_REFERENCE.md](docs/API_REFERENCE.md) | Functions, modules, data formats | Integrators |
| [docs/TESTING.md](docs/TESTING.md) | Test procedures, validation | QA Teams |

## System Requirements

### Minimum Requirements
- **Database**: PostgreSQL 13+ with admin access OR Supabase account
- **Runtime**: Python 3.8+ with pip
- **Storage**: 2GB available disk space
- **Memory**: 4GB RAM

### Recommended for Production
- **Database**: PostgreSQL 14+ dedicated instance OR Supabase Pro plan
- **Runtime**: Python 3.10+
- **Storage**: 10GB+ disk space for screenshots
- **Memory**: 8GB+ RAM for large datasets
- **Platform**: Linux or macOS (Windows via WSL2)

## Technology Stack

- **Database**: PostgreSQL 13+ with pg_trgm extension OR Supabase (cloud PostgreSQL)
- **Backend**: Python 3.8+, psycopg2, SQLAlchemy  
- **Web Framework**: Streamlit 1.28+ with Plotly charts
- **Data Processing**: pandas, RapidFuzz (address matching)
- **Dependencies**: python-dotenv, python-slugify
- **Migration System**: Custom unified migration runner for both backends
- **Testing**: Built-in test suite (system_test.py)

## Project Status

✅ **Production Ready** - All core features implemented and tested:
- Database schema with versioned datasets
- Import system for pharmacies and state searches  
- Address scoring engine with 96.5% accuracy for exact matches
- Web interface with full CRUD operations
- Validation system with audit trails
- Export functionality for reporting

## Support

For issues or questions:
1. Check [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for common issues
2. Review the system test output: `python system_test.py`
3. Enable debug mode in `.env`: `LOGGING_LEVEL=DEBUG`