# PharmChecker 🏥

PharmChecker is a lightweight internal tool for verifying pharmacy licenses across U.S. states through manual review of automated search results.

## Features

- **Versioned Datasets**: Import and combine pharmacy, state search, and validation data in any order
- **Optimized Database**: Merged table structure with automatic deduplication
- **Lazy Scoring**: Address match scores computed on-demand when needed *(in development)*
- **Multi-User Support**: Multiple users can work with different dataset combinations
- **Streamlit UI**: Web interface for reviewing results and creating validations *(in development)*
- **Screenshot Integration**: Store and display state board search screenshots
- **Flexible Storage**: Local filesystem or Supabase storage support

## Implementation Status

✅ **COMPLETED**: Core data infrastructure with optimized database schema  
✅ **COMPLETED**: Import system for pharmacies and state search results  
✅ **COMPLETED**: Screenshot handling and metadata management  
✅ **COMPLETED**: Development tools and repository organization  

🚧 **IN PROGRESS**: Address scoring engine (next priority)  
📋 **PENDING**: Streamlit UI and validated overrides importer

## Quick Start

### 1. Prerequisites

- Python 3.8+
- PostgreSQL 13+ (with trigram extension support)
- Git

### 2. Install

```bash
git clone <your-repo-url>
cd pharmchecker
pip install -r requirements.txt
```

### 3. Setup

```bash
# Run the setup script - it will guide you through configuration
python setup.py
```

The setup script will:
- Check for `.env` file (create from `.env.example` if needed)
- Install Python dependencies  
- Create database and tables
- Set up data directories
- Run verification tests

### 4. Development Commands

Use the convenient Makefile commands for development:

```bash
# Quick database status check
make status

# Clean and import test data  
make clean_states import_test_states

# Full development workflow
make dev  # Imports pharmacies + both state datasets

# Database management
make clean_all    # Full reset
make setup       # Initialize database
```

### 5. Run the Application (Coming Soon)

```bash
streamlit run app.py  # UI implementation in progress
```

## Data Import

### Import Pharmacies

```python
from imports.pharmacies import PharmacyImporter
from config import get_db_config

with PharmacyImporter(get_db_config()) as importer:
    success = importer.import_csv(
        filepath='data/pharmacies.csv',
        tag='2024-01-15',
        created_by='admin',
        description='Initial pharmacy dataset'
    )
```

### Import State Search Results  

```python
from imports.states import StateImporter

with StateImporter() as importer:
    # Import directory of JSON files with automatic screenshot handling
    success = importer.import_directory(
        directory_path='data/states_baseline', 
        tag='states_baseline',
        created_by='admin',
        description='Baseline state search data'
    )
```

### Import Validated Overrides (Coming Soon)

```python
from imports.validated import ValidatedImporter

with ValidatedImporter() as importer:
    success = importer.import_csv(
        filepath='data/validations.csv',
        tag='2024-01-15', 
        created_by='admin'
    )
```

*Note: ValidatedImporter implementation is pending - deferred until baseline system is operational.*

## Data Formats

### Pharmacy CSV Format

```csv
name,alias,address,suite,city,state,zip,state_licenses,npi_number
Empower Pharmacy,Empower,123 Main St,Suite 100,Houston,TX,77001,"[""TX"",""FL"",""CA""]",1234567890
```

Required columns: `name`, `state_licenses`

### State Search JSON Format

Individual JSON files per search (e.g., `Belmar_01_parse.json`):

```json
{
  "search_name": "Belmar Pharmacy",
  "search_state": "FL",
  "search_ts": "2024-08-05T14:30:22.123Z",
  "result_status": "results_found",
  "license_number": "PH9876",
  "license_status": "Active",  
  "license_name": "Belmar Compounding Pharmacy",
  "address": "8280 NORTHLAKE BLVD",
  "city": "WEST PALM BEACH",
  "state": "FL",
  "zip": "33409",
  "issue_date": "2015-03-01",
  "expiration_date": "2025-02-28",
  "screenshot_path": "data/states_baseline/FL/Belmar_01.png"
}
```

For empty results: `Pharmacy_no_results_parse.json` with `"result_status": "no_results_found"`

### Validation Override CSV Format

```csv
pharmacy_name,state_code,license_number,override_type,reason,validated_by
Empower Pharmacy,TX,12345,present,Verified active license,admin
MedPoint Compounding,FL,,empty,No FL license found,admin
```

## Scoring System

PharmChecker uses address matching to score how well state board results match pharmacy records:

- **Street Score (70% weight)**: Fuzzy matching of address with abbreviation normalization
- **City/State/ZIP Score (30% weight)**: Exact matching of location components  
- **Overall Score**: Weighted combination, scaled 0-100

Status buckets:
- **Match**: Score ≥ 85
- **Weak Match**: Score 60-84  
- **No Match**: Score < 60
- **No Data**: No search conducted or no results

## Architecture

### Core Components

1. **PostgreSQL Database** - Stores versioned datasets and computed scores
   - **Optimized Schema**: Merged search_results table eliminates timing conflicts
   - **Automatic Deduplication**: ON CONFLICT handling for data integrity
2. **Import Scripts** - Load different data types with validation and error recovery
3. **Scoring Engine** - Computes address match scores on-demand *(in development)*
4. **Streamlit UI** - Review interface with authentication *(in development)*
5. **Storage Layer** - Local filesystem or cloud storage for screenshots

### Key Design Principles

- **Dataset Independence**: Data can be imported in any order
- **Natural Key Linking**: Uses pharmacy names/license numbers vs internal IDs  
- **Lazy Scoring**: Only computes scores when needed for specific dataset combinations
- **Validation Snapshots**: Captures complete search result state during validation

## Configuration

Set these environment variables in `.env`:

```bash
# Database
DB_HOST=localhost
DB_PORT=5432  
DB_NAME=pharmchecker
DB_USER=postgres
DB_PASSWORD=your_password

# Storage 
STORAGE_TYPE=local  # or 'supabase'
DATA_DIR=data

# Streamlit
STREAMLIT_PORT=8501
```

## Development

### Project Structure

```
pharmchecker/
├── imports/              # Data import modules
│   ├── base.py          # Base importer class with batch operations  
│   ├── pharmacies.py    # Pharmacy CSV importer
│   ├── states.py        # State search JSON importer (with deduplication)
│   └── validated.py     # Validation override importer (pending)
├── scoring_plugin.py     # Address matching algorithm (pending)
├── app.py               # Streamlit UI application (pending)
├── config.py            # Configuration management
├── setup.py             # Database setup script
├── schema.sql           # Optimized database schema (merged tables)
├── functions.sql        # Database functions (updated for merged schema)
├── Makefile             # Development commands
├── show_status.py       # Database status utility
├── clean_search_db.py   # Database cleaning utility  
├── tmp/                 # Temporary files (migration scripts, tests)
└── data/                # Data directory
    ├── states_baseline/ # Sample state search data
    ├── states_baseline2/# Additional sample data  
    └── pharmacies_new.csv # Sample pharmacy data
```

### Database Functions

- `get_results_matrix(states_tag, pharmacies_tag, validated_tag)` - Main results view
- `find_missing_scores(states_tag, pharmacies_tag)` - Identifies scoring gaps

## License

[Your License Here]