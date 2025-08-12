# PharmChecker PostgREST Development Plan

## Executive Summary

Build a REST API using PostgREST that automatically generates endpoints from the existing PostgreSQL schema, plus a simple Streamlit GUI for basic database operations (import/export). This provides immediate API access while preserving all existing functionality.

## Why PostgREST?

- **Instant API**: Automatically generates REST endpoints from PostgreSQL schema
- **Zero Code**: No custom endpoint development needed
- **SQL Functions**: Direct access to existing `get_all_results_with_context()` function
- **RLS Ready**: Built-in Row Level Security support for multi-tenant
- **Fast Setup**: Can be running in minutes vs. weeks for custom API

## Target Architecture

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│  Simple GUI         │    │    PostgREST        │    │   PostgreSQL        │
│  (Streamlit)        │◄──►│   Auto-Generated    │◄──►│   (Existing)        │
│                     │    │   REST API          │    │                     │
│ /api_poc/gui/       │    │                     │    │ - Existing Schema   │
│ ├── app.py          │    │ Port 3000           │    │ - Functions         │
│ ├── client.py       │    │ /datasets           │    │ - Data              │
│ └── components/     │    │ /search_results     │    │ - MCP Access        │
└─────────────────────┘    │ /rpc/get_all_...   │    └─────────────────────┘
                           └─────────────────────┘
```

## Project Structure

```
pharmchecker/
├── api_poc/                    # New development directory
│   ├── postgrest/              # PostgREST configuration
│   │   ├── postgrest.conf     # PostgREST config file
│   │   ├── docker-compose.yml # PostgREST + local setup
│   │   └── schema.sql         # Any additional views/functions
│   │
│   ├── gui/                   # Simple Streamlit interface
│   │   ├── app.py            # Main app (dataset ops + API testing)
│   │   ├── client.py         # PostgREST API client
│   │   ├── config.py         # Configuration
│   │   ├── components/       # UI components
│   │   │   ├── dataset_table.py
│   │   │   ├── export_tool.py
│   │   │   └── api_tester.py
│   │   └── requirements.txt  # GUI dependencies
│   │
│   ├── .env.example          # Environment template
│   └── README.md             # Setup instructions
│
├── [existing files unchanged]
```

## PostgREST Endpoints (Auto-Generated)

### Tables (CRUD operations)
```
GET    /datasets              # List all datasets
GET    /datasets?kind=eq.pharmacies  # Filter datasets
POST   /datasets              # Create dataset
PATCH  /datasets?id=eq.1      # Update dataset

GET    /pharmacies            # List pharmacies
GET    /pharmacies?dataset_id=eq.1  # Filter by dataset

GET    /search_results        # List search results  
GET    /search_results?dataset_id=eq.2&search_state=eq.FL

GET    /validated_overrides   # List validations
POST   /validated_overrides   # Create validation
```

### Functions (RPC calls)
```
POST   /rpc/get_all_results_with_context
       Body: {"p_states_tag": "states_jan_2024", "p_pharmacies_tag": "pharmacies_jan_2024"}

POST   /rpc/check_validation_consistency  
       Body: {"p_states_tag": "states_jan_2024", "p_pharmacies_tag": "pharmacies_jan_2024", "p_validated_tag": "validated_jan_2024"}
```

### Views (Custom queries)
```
GET    /dataset_summary       # Custom view with stats
GET    /pharmacy_state_matrix # Aggregated view for matrix display
```

## Implementation Plan

### Phase 1: PostgREST Setup (Day 1)

#### 1. PostgREST Configuration
- [ ] Create `/api_poc/postgrest/postgrest.conf`
- [ ] Configure database connection (reuse existing credentials)
- [ ] Set up schema and role permissions
- [ ] Configure CORS for local development

#### 2. Docker Setup
- [ ] Create `docker-compose.yml` for PostgREST
- [ ] Configure PostgreSQL connection to existing database
- [ ] Test PostgREST startup and basic endpoints

#### 3. Database Preparation
- [ ] Ensure existing schema works with PostgREST
- [ ] Create any needed views for common queries
- [ ] Test existing functions via RPC endpoints

### Phase 2: API Testing & Documentation (Day 2)

#### 1. Endpoint Validation
- [ ] Test all auto-generated table endpoints
- [ ] Test RPC calls to existing functions
- [ ] Verify filtering and pagination work
- [ ] Document actual endpoint URLs and parameters

#### 2. Custom Views (if needed)
- [ ] Create view for dataset summaries
- [ ] Create view for matrix display data
- [ ] Test view performance vs. direct function calls

### Phase 3: Simple GUI (Day 3-4)

#### 1. API Client
- [ ] Create `gui/client.py` with PostgREST wrapper
- [ ] Implement GET/POST methods for common operations
- [ ] Add error handling and retries
- [ ] Test with PostgREST endpoints

#### 2. Basic Streamlit App
- [ ] Create main app with dataset operations
- [ ] Add dataset listing and basic info display
- [ ] Add simple export functionality for tables
- [ ] Add API endpoint testing interface

#### 3. Core Operations
- [ ] Import data via existing import scripts (not API)
- [ ] Export data via API endpoints
- [ ] Basic validation operations via API
- [ ] Test comprehensive results via RPC calls

### Phase 4: Polish & Documentation (Day 5)

#### 1. Testing
- [ ] Test all endpoints with real data
- [ ] Verify data consistency
- [ ] Test error handling

#### 2. Documentation
- [ ] Document PostgREST setup process
- [ ] Document available endpoints
- [ ] Create usage examples

## PostgREST Configuration

### postgrest.conf
```ini
# postgrest.conf
db-uri = "postgresql://postgres:password@localhost:5432/pharmchecker"
db-schema = "public"
db-anon-role = "postgres"
db-pool = 10

server-host = "127.0.0.1"
server-port = 3000

# Enable RPC calls to functions
db-root-spec = "root"

# CORS for local development
server-cors-allowed-origins = "*"
```

### docker-compose.yml
```yaml
version: '3'
services:
  postgrest:
    image: postgrest/postgrest
    ports:
      - "3000:3000"
    environment:
      PGRST_DB_URI: postgresql://postgres:password@host.docker.internal:5432/pharmchecker
      PGRST_DB_SCHEMAS: public
      PGRST_DB_ANON_ROLE: postgres
      PGRST_SERVER_PORT: 3000
    depends_on:
      - postgres

  # Optional: if you want PostgREST to manage its own PostgreSQL
  # postgres:
  #   image: postgres:13
  #   environment:
  #     POSTGRES_DB: pharmchecker
  #     POSTGRES_USER: postgres
  #     POSTGRES_PASSWORD: password
  #   volumes:
  #     - postgres_data:/var/lib/postgresql/data
  #   ports:
  #     - "5432:5432"
```

## Key PostgREST Features We'll Use

### 1. Automatic CRUD
```http
# Get all datasets
GET http://localhost:3000/datasets

# Filter datasets by kind
GET http://localhost:3000/datasets?kind=eq.pharmacies

# Get dataset with specific tag
GET http://localhost:3000/datasets?kind=eq.pharmacies&tag=eq.jan_2024
```

### 2. Function Calls
```http
# Call existing comprehensive results function
POST http://localhost:3000/rpc/get_all_results_with_context
Content-Type: application/json

{
  "p_states_tag": "states_jan_2024",
  "p_pharmacies_tag": "pharmacies_jan_2024", 
  "p_validated_tag": "validated_jan_2024"
}
```

### 3. Complex Filtering
```http
# Get search results for specific state with scores
GET http://localhost:3000/search_results?search_state=eq.FL&select=*,match_scores(*)
```

### 4. Aggregation via Views
```sql
-- Create view for matrix display
CREATE VIEW pharmacy_state_matrix AS
SELECT 
  pharmacy_name,
  search_state,
  COUNT(*) as result_count,
  MAX(score_overall) as best_score,
  STRING_AGG(DISTINCT license_number, ',') as license_numbers
FROM get_all_results_with_context('states_jan_2024', 'pharmacies_jan_2024', NULL)
GROUP BY pharmacy_name, search_state;
```

```http
GET http://localhost:3000/pharmacy_state_matrix?search_state=eq.FL
```

## Simple GUI Features

### Dataset Operations
- List all datasets with basic stats
- Export dataset contents as CSV
- Import new data (using existing import scripts)

### API Testing Interface  
- Test PostgREST endpoints interactively
- View raw JSON responses
- Test function calls with parameters

### Basic Data Export
- Export comprehensive results via API
- Export specific tables
- Download as CSV/JSON

## Benefits of This Approach

### Immediate Value
- **5 minutes to working API**: PostgREST setup is extremely fast
- **Zero custom code**: API endpoints generated automatically
- **Full schema access**: Every table and function immediately available
- **Standard REST**: Uses conventional HTTP methods and status codes

### Future-Proof
- **FastAPI later**: Can add custom FastAPI endpoints alongside PostgREST
- **Authentication ready**: PostgREST supports JWT and RLS
- **Production ready**: PostgREST is used in production by many companies
- **GraphQL option**: PostgQL can add GraphQL on top of PostgREST

### Low Risk
- **No schema changes**: Works with existing database as-is
- **No data migration**: Uses existing tables and functions
- **Parallel operation**: Existing Streamlit app continues working
- **Easy rollback**: Can disable PostgREST without affecting anything

## Success Criteria

1. **PostgREST running**: API accessible at http://localhost:3000
2. **All tables accessible**: Can read/write all major tables via API
3. **Functions working**: Can call `get_all_results_with_context()` via RPC
4. **GUI functional**: Basic operations working through PostgREST API
5. **Data consistency**: API returns same data as direct DB queries
6. **Documentation complete**: Setup and usage documented

## Next Steps After POC

Once PostgREST POC is working:

1. **Add Authentication**: JWT tokens for secure access
2. **Custom Endpoints**: Add FastAPI for complex business logic
3. **Enhanced GUI**: Build full-featured frontend using API
4. **Production Deploy**: Configure for production environment
5. **Integration**: Enable third-party systems to use API

This approach gets us a working API in days instead of weeks, with a clear path to enhance it over time.