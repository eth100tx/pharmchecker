# PharmChecker Dual Backend API POC

Proof-of-concept implementation supporting both PostgREST (local) and Supabase (cloud) backends with a unified GUI.

## Overview

This POC provides:
- **Dual Backend Support** - Works with both local PostgREST and cloud Supabase
- **PostgREST API** exposing all database tables as REST endpoints  
- **Supabase Integration** via REST API and Python client library
- **Unified Streamlit GUI** for database operations and API testing
- **Backend Switching** - Seamlessly switch between local and cloud backends
- **API client wrapper** for easier Python integration

## Quick Start

### 1. Start PostgREST API

```bash
cd api_poc/postgrest
./postgrest postgrest.conf
```

The API will be available at http://localhost:3000

### 2. Start GUI

```bash
cd api_poc/gui
pip install -r requirements.txt
streamlit run app.py
```

The GUI will be available at http://localhost:8501

## Directory Structure

```
api_poc/
├── postgrest/
│   ├── postgrest.conf          # PostgREST configuration
│   ├── postgrest               # PostgREST binary
│   └── README.md               # PostgREST setup instructions
├── gui/
│   ├── app.py                  # Main Streamlit application
│   ├── client.py               # PostgREST API client wrapper
│   ├── components/             # GUI components
│   │   ├── dataset_explorer.py # Dataset browsing interface
│   │   ├── api_tester.py       # API testing tools
│   │   └── comprehensive_results.py # Main results interface
│   └── requirements.txt        # Python dependencies
├── .env.example               # Environment variables template
└── README.md                  # This file
```

## Features

### PostgREST API

- **All tables accessible** via REST endpoints (GET, POST, PATCH, DELETE)
- **RPC functions** available at `/rpc/function_name`
- **Comprehensive results** via `/rpc/get_all_results_with_context`
- **OpenAPI schema** at `/` for documentation
- **Filtering and pagination** built-in

### GUI Features

1. **Overview Dashboard**
   - Backend status (PostgREST + Supabase)
   - Active backend indicator
   - Quick stats and connection testing
   - Backend switching controls

2. **Dataset Explorer**
   - Browse all datasets by type (pharmacies, states, validated)
   - Works with both PostgREST and Supabase backends
   - View data previews with configurable limits
   - Export any table to CSV with filtering
   - Dataset metadata and statistics

3. **Comprehensive Results** 
   - Call the main `get_all_results_with_context()` function
   - Select pharmacy/states/validated dataset tags
   - Automatic backend routing (local or cloud)
   - View results with filtering and analysis
   - Match score analysis and visualization

4. **API Testing**
   - Test any PostgREST endpoint interactively
   - Custom HTTP requests with headers and body
   - View response data as JSON or tables
   - Browse API schema and available endpoints

5. **Supabase Manager**
   - Backend connection testing
   - Project information display
   - Table and RPC function testing
   - Raw SQL execution interface
   - Backend switching controls

6. **Export Capabilities**
   - Export filtered data to CSV
   - Download files directly from browser
   - Works with both backends

## API Examples

### Get datasets
```bash
curl http://localhost:3000/datasets
```

### Get pharmacies from specific dataset
```bash
curl "http://localhost:3000/pharmacies?dataset_id=eq.3&limit=10"
```

### Call comprehensive results function
```bash
curl "http://localhost:3000/rpc/get_all_results_with_context?p_states_tag=states_baseline&p_pharmacies_tag=test_pharmacies&p_validated_tag="
```

### Export table as CSV
```bash
curl -H "Accept: text/csv" "http://localhost:3000/datasets" > datasets.csv
```

## Python Client Usage

```python
from client import create_client

# Create unified client (defaults to PostgREST)
client = create_client()

# Check backend status
print("Backend info:", client.get_backend_info())
print("Active backend:", client.get_active_backend())

# Test connection
if client.test_connection():
    print("Active backend is accessible")

# Get datasets (from active backend)
datasets = client.get_datasets()

# Switch to Supabase backend
if client.switch_backend(use_supabase=True):
    print("Switched to Supabase")
    
    # Get datasets from Supabase
    datasets_sb = client.get_datasets()
    print(f"Supabase datasets: {len(datasets_sb)}")

# Get comprehensive results (uses active backend)
results = client.get_comprehensive_results(
    states_tag="states_baseline",
    pharmacies_tag="test_pharmacies", 
    validated_tag=""
)

# Direct Supabase operations
if client.supabase_client:
    # Test REST API call
    data = client.supabase_client.get_table_data_via_rest("datasets", limit=5)
    
    # Execute SQL
    result = client.supabase_client.execute_sql("SELECT COUNT(*) FROM datasets")
```

## Configuration

### PostgREST Configuration

Edit `postgrest/postgrest.conf`:

```ini
db-uri = "postgres://user:pass@localhost:5432/pharmchecker"
db-schemas = "public" 
db-anon-role = "postgres"
server-port = 3000
```

### Database Connection

The API connects to your existing PharmChecker database using the same credentials. No schema changes required.

## Development Notes

- **No impact on existing code** - everything is in the `api_poc/` directory
- **Uses existing database** - connects to current PostgreSQL setup
- **Preserves existing functions** - `get_all_results_with_context()` works via RPC
- **Local development focus** - no Docker required

## Troubleshooting

### PostgREST won't start
- Check database connection in `postgrest.conf`
- Verify PostgreSQL is running
- Check port 3000 is available

### GUI connection error
- Make sure PostgREST is running on port 3000
- Check `client.py` has correct API URL
- Test API directly: `curl http://localhost:3000/`

### Missing data
- Ensure you have imported test data: `make dev`
- Check dataset tags match what's in database
- Verify database permissions for postgres user

## Success Criteria ✅

- [x] PostgREST API accessible at http://localhost:3000
- [x] All major tables available via REST endpoints  
- [x] `get_all_results_with_context()` function callable via `/rpc/get_all_results_with_context`
- [x] Simple GUI working at http://localhost:8501
- [x] Can export data and test API endpoints through GUI
- [x] No impact on existing Streamlit app

## Next Steps

1. **Performance testing** with larger datasets
2. **Authentication** integration (JWT tokens)
3. **Advanced filtering** and search capabilities
4. **Real-time updates** via PostgreSQL LISTEN/NOTIFY
5. **Integration** with existing workflow tools