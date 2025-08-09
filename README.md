# PharmChecker 🏥

PharmChecker is a lightweight internal tool for verifying pharmacy licenses across U.S. states through manual review of automated search results.

## Features

- **Versioned Datasets**: Import and combine pharmacy, state search, and validation data in any order
- **Lazy Scoring**: Address match scores computed on-demand when needed  
- **Multi-User Support**: Multiple users can work with different dataset combinations
- **Streamlit UI**: Web interface for reviewing results and creating validations
- **Screenshot Integration**: Store and display state board search screenshots
- **Flexible Storage**: Local filesystem or Supabase storage support

## Quick Start

### 1. Prerequisites

- Python 3.8+
- PostgreSQL 13+ (with trigram extension support)
- Git

### 2. Install

```bash
git clone <your-repo-url>
cd pharmchecker
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

### 4. Run the Application

```bash
streamlit run app.py
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
    success = importer.import_json(
        filepath='data/state_searches.json', 
        tag='2024-01-15',
        screenshot_dir='data/screenshots',
        created_by='admin'
    )
```

### Import Validated Overrides

```python
from imports.validated import ValidatedImporter

with ValidatedImporter() as importer:
    success = importer.import_csv(
        filepath='data/validations.csv',
        tag='2024-01-15', 
        created_by='admin'
    )
```

## Data Formats

### Pharmacy CSV Format

```csv
name,alias,address,suite,city,state,zip,state_licenses,npi_number
Empower Pharmacy,Empower,123 Main St,Suite 100,Houston,TX,77001,"[""TX"",""FL"",""CA""]",1234567890
```

Required columns: `name`, `state_licenses`

### State Search JSON Format

```json
{
  "searches": [
    {
      "name": "Empower Pharmacy",
      "state": "TX", 
      "timestamp": "2024-01-15T10:30:00",
      "results": [
        {
          "license_number": "12345",
          "license_status": "Active",
          "license_name": "Empower Pharmacy of Texas LLC",
          "address": "123 Main Street",
          "city": "Houston", 
          "state": "TX",
          "zip": "77001",
          "issue_date": "2020-01-01",
          "expiration_date": "2025-01-01"
        }
      ],
      "screenshot": "empower_tx_20240115.png"
    }
  ]
}
```

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
2. **Import Scripts** - Load different data types with validation
3. **Scoring Engine** - Computes address match scores on-demand
4. **Streamlit UI** - Review interface with authentication
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
├── imports/           # Data import modules
│   ├── base.py       # Base importer class
│   ├── pharmacies.py # Pharmacy CSV importer  
│   ├── states.py     # State search JSON importer
│   └── validated.py  # Validation override importer
├── scoring_plugin.py  # Address matching algorithm
├── app.py            # Streamlit UI application
├── config.py         # Configuration management
├── setup.py          # Database setup script
├── schema.sql        # Database schema
├── functions.sql     # Database functions
└── data/             # Data directory
```

### Database Functions

- `get_results_matrix(states_tag, pharmacies_tag, validated_tag)` - Main results view
- `find_missing_scores(states_tag, pharmacies_tag)` - Identifies scoring gaps

## License

[Your License Here]