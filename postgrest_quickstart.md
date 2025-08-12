# PostgREST Quick Start Guide

## Overview
Get PharmChecker REST API running in 10 minutes using PostgREST with your existing PostgreSQL database.

## Prerequisites
- Existing PostgreSQL database with PharmChecker schema
- Docker and Docker Compose installed
- Database credentials from your .env file

## Step 1: Create PostgREST Configuration

Create the API POC directory structure:

```bash
mkdir -p api_poc/postgrest
mkdir -p api_poc/gui/components
cd api_poc
```

### Create postgrest.conf
```bash
cat > postgrest/postgrest.conf << 'EOF'
# Database connection (update with your credentials)
db-uri = "postgresql://postgres:12@localhost:5432/pharmchecker"
db-schemas = "public"
db-anon-role = "postgres"
db-pool = 10

# Server configuration
server-host = "0.0.0.0"
server-port = 3000

# CORS for local development
server-cors-allowed-origins = "*"

# Enable function calls
db-root-spec = "root"
EOF
```

### Create docker-compose.yml
```bash
cat > postgrest/docker-compose.yml << 'EOF'
version: '3.8'

services:
  postgrest:
    image: postgrest/postgrest:v12.0.2
    ports:
      - "3000:3000"
    environment:
      # Update these with your actual database credentials
      PGRST_DB_URI: postgresql://postgres:12@host.docker.internal:5432/pharmchecker
      PGRST_DB_SCHEMAS: public
      PGRST_DB_ANON_ROLE: postgres
      PGRST_SERVER_PORT: 3000
      PGRST_SERVER_CORS_ALLOWED_ORIGINS: "*"
      PGRST_DB_ROOT_SPEC: root
    volumes:
      - ./postgrest.conf:/etc/postgrest/postgrest.conf
    restart: unless-stopped

# Optional: Add postgres service if you want containerized database
#  postgres:
#    image: postgres:13
#    environment:
#      POSTGRES_DB: pharmchecker
#      POSTGRES_USER: postgres
#      POSTGRES_PASSWORD: 12
#    ports:
#      - "5432:5432"
#    volumes:
#      - postgres_data:/var/lib/postgresql/data

# volumes:
#   postgres_data:
EOF
```

## Step 2: Update Database Connection

Edit `postgrest/postgrest.conf` and `postgrest/docker-compose.yml` with your actual database credentials from `.env`:

```bash
# Check your current database config
cat ../config.py | grep DB_CONFIG -A 10

# Update the connection strings in both files with your:
# - DB_HOST
# - DB_PORT  
# - DB_NAME
# - DB_USER
# - DB_PASSWORD
```

## Step 3: Start PostgREST

```bash
cd postgrest
docker-compose up -d

# Check if it's running
curl http://localhost:3000/
```

You should see a JSON response with available endpoints.

## Step 4: Test Basic Endpoints

### List all datasets
```bash
curl "http://localhost:3000/datasets"
```

### Get pharmacies data
```bash
curl "http://localhost:3000/pharmacies?limit=5"
```

### Call the comprehensive results function
```bash
curl -X POST "http://localhost:3000/rpc/get_all_results_with_context" \
  -H "Content-Type: application/json" \
  -d '{
    "p_states_tag": "states_baseline", 
    "p_pharmacies_tag": "pharmacies_new", 
    "p_validated_tag": null
  }'
```

## Step 5: Create Simple GUI

### Create API client
```bash
cat > gui/client.py << 'EOF'
"""
Simple PostgREST API client for PharmChecker
"""
import requests
import pandas as pd
from typing import Optional, Dict, Any, List
import json

class PostgRESTClient:
    def __init__(self, base_url: str = "http://localhost:3000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
    
    def get_datasets(self, kind: Optional[str] = None) -> List[Dict]:
        """Get all datasets, optionally filtered by kind"""
        url = f"{self.base_url}/datasets"
        params = {}
        if kind:
            params['kind'] = f"eq.{kind}"
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    
    def get_comprehensive_results(self, states_tag: str, pharmacies_tag: str, 
                                validated_tag: Optional[str] = None) -> pd.DataFrame:
        """Call the comprehensive results function"""
        url = f"{self.base_url}/rpc/get_all_results_with_context"
        
        payload = {
            "p_states_tag": states_tag,
            "p_pharmacies_tag": pharmacies_tag,
            "p_validated_tag": validated_tag
        }
        
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        
        data = response.json()
        return pd.DataFrame(data) if data else pd.DataFrame()
    
    def get_table_data(self, table_name: str, limit: int = 100, 
                      filters: Optional[Dict] = None) -> pd.DataFrame:
        """Get data from any table"""
        url = f"{self.base_url}/{table_name}"
        params = {"limit": str(limit)}
        
        if filters:
            for key, value in filters.items():
                params[key] = f"eq.{value}"
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        return pd.DataFrame(data) if data else pd.DataFrame()
    
    def export_table_csv(self, table_name: str, filename: str, 
                        filters: Optional[Dict] = None):
        """Export table data to CSV"""
        df = self.get_table_data(table_name, limit=10000, filters=filters)
        df.to_csv(filename, index=False)
        return len(df)
EOF
```

### Create simple Streamlit app
```bash
cat > gui/app.py << 'EOF'
"""
Simple PharmChecker API GUI
Basic database operations and API testing
"""
import streamlit as st
import pandas as pd
from client import PostgRESTClient
import json

st.set_page_config(
    page_title="PharmChecker API",
    page_icon="💊",
    layout="wide"
)

st.title("PharmChecker API Interface")
st.caption("PostgREST-powered database operations")

# Initialize client
client = PostgRESTClient()

# Test API connection
try:
    datasets = client.get_datasets()
    st.success(f"✅ Connected to PostgREST API - Found {len(datasets)} datasets")
except Exception as e:
    st.error(f"❌ Cannot connect to API: {e}")
    st.stop()

# Sidebar navigation
page = st.sidebar.selectbox("Choose Operation", [
    "Dataset Explorer",
    "Table Export", 
    "API Testing",
    "Comprehensive Results"
])

if page == "Dataset Explorer":
    st.header("Dataset Explorer")
    
    # Show all datasets
    datasets_df = pd.DataFrame(datasets)
    if not datasets_df.empty:
        st.subheader("Available Datasets")
        st.dataframe(datasets_df, use_container_width=True)
        
        # Dataset details
        selected_kind = st.selectbox("Filter by kind:", 
                                   ["All"] + list(datasets_df['kind'].unique()))
        
        if selected_kind != "All":
            filtered_datasets = client.get_datasets(kind=selected_kind)
            st.subheader(f"{selected_kind.title()} Datasets")
            st.dataframe(pd.DataFrame(filtered_datasets), use_container_width=True)
    else:
        st.warning("No datasets found")

elif page == "Table Export":
    st.header("Table Export")
    
    # Table selection
    tables = ["datasets", "pharmacies", "search_results", "validated_overrides", "match_scores"]
    selected_table = st.selectbox("Select table to export:", tables)
    
    # Optional filters
    st.subheader("Filters (optional)")
    col1, col2 = st.columns(2)
    
    filters = {}
    if selected_table == "pharmacies":
        with col1:
            dataset_id = st.text_input("Dataset ID:")
            if dataset_id:
                filters['dataset_id'] = dataset_id
    elif selected_table == "search_results":
        with col1:
            dataset_id = st.text_input("Dataset ID:")
            if dataset_id:
                filters['dataset_id'] = dataset_id
        with col2:
            search_state = st.text_input("State Code:")
            if search_state:
                filters['search_state'] = search_state
    
    # Export button
    if st.button("Export to CSV"):
        try:
            filename = f"{selected_table}_export.csv"
            count = client.export_table_csv(selected_table, filename, filters)
            st.success(f"✅ Exported {count} records to {filename}")
            
            # Show preview
            df = pd.read_csv(filename)
            st.subheader("Preview")
            st.dataframe(df.head(10), use_container_width=True)
            
        except Exception as e:
            st.error(f"Export failed: {e}")

elif page == "API Testing":
    st.header("API Testing")
    
    # Raw endpoint testing
    st.subheader("Test Raw Endpoints")
    
    endpoint = st.text_input("Endpoint (after /)", value="datasets")
    method = st.selectbox("Method:", ["GET", "POST"])
    
    if method == "GET":
        if st.button("Send Request"):
            try:
                response = client.session.get(f"{client.base_url}/{endpoint}")
                st.code(f"Status: {response.status_code}")
                st.json(response.json())
            except Exception as e:
                st.error(f"Request failed: {e}")
    
    elif method == "POST":
        body = st.text_area("Request Body (JSON):", value='{}')
        if st.button("Send Request"):
            try:
                data = json.loads(body) if body.strip() else {}
                response = client.session.post(f"{client.base_url}/{endpoint}", json=data)
                st.code(f"Status: {response.status_code}")
                st.json(response.json())
            except Exception as e:
                st.error(f"Request failed: {e}")

elif page == "Comprehensive Results":
    st.header("Comprehensive Results")
    
    # Get available datasets for selection
    datasets_df = pd.DataFrame(datasets)
    
    if not datasets_df.empty:
        pharmacy_datasets = datasets_df[datasets_df['kind'] == 'pharmacies']['tag'].tolist()
        states_datasets = datasets_df[datasets_df['kind'] == 'states']['tag'].tolist()
        validated_datasets = ['None'] + datasets_df[datasets_df['kind'] == 'validated']['tag'].tolist()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            pharmacies_tag = st.selectbox("Pharmacies Dataset:", pharmacy_datasets)
        with col2:
            states_tag = st.selectbox("States Dataset:", states_datasets)  
        with col3:
            validated_tag = st.selectbox("Validated Dataset:", validated_datasets)
            validated_tag = None if validated_tag == 'None' else validated_tag
        
        if st.button("Load Comprehensive Results"):
            try:
                with st.spinner("Loading comprehensive results..."):
                    results_df = client.get_comprehensive_results(
                        states_tag, pharmacies_tag, validated_tag
                    )
                
                if not results_df.empty:
                    st.success(f"✅ Loaded {len(results_df)} result records")
                    
                    # Show summary
                    st.subheader("Summary")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Results", len(results_df))
                    with col2:
                        unique_pharmacies = results_df['pharmacy_name'].nunique()
                        st.metric("Unique Pharmacies", unique_pharmacies)
                    with col3:
                        unique_states = results_df['search_state'].nunique()
                        st.metric("States", unique_states)
                    with col4:
                        scored_results = results_df['score_overall'].notna().sum()
                        st.metric("Scored Results", scored_results)
                    
                    # Show data
                    st.subheader("Results Data")
                    st.dataframe(results_df.head(100), use_container_width=True)
                    
                    # Export option
                    if st.button("Export Results to CSV"):
                        filename = f"comprehensive_results_{states_tag}_{pharmacies_tag}.csv"
                        results_df.to_csv(filename, index=False)
                        st.success(f"✅ Exported to {filename}")
                        
                else:
                    st.warning("No results found for selected datasets")
                    
            except Exception as e:
                st.error(f"Failed to load results: {e}")
    else:
        st.warning("No datasets available")

# Footer
st.markdown("---")
st.caption("PostgREST API running on http://localhost:3000")
EOF
```

### Create requirements.txt
```bash
cat > gui/requirements.txt << 'EOF'
streamlit>=1.28.0
pandas>=1.5.0
requests>=2.28.0
EOF
```

## Step 6: Run the GUI

```bash
cd gui
pip install -r requirements.txt
streamlit run app.py
```

The GUI will open at http://localhost:8501

## Step 7: Test Everything

### 1. Test PostgREST directly
- Visit http://localhost:3000 (should show API root)
- Try http://localhost:3000/datasets

### 2. Test the GUI
- Navigate through different pages
- Try exporting a table
- Test the comprehensive results function

### 3. Verify data consistency
- Compare API results with your existing Streamlit app
- Ensure the comprehensive results function returns expected data

## Troubleshooting

### PostgREST won't start
- Check database credentials in docker-compose.yml
- Ensure PostgreSQL is accessible from Docker (use `host.docker.internal` on Mac/Windows)
- Check Docker logs: `docker-compose logs postgrest`

### API returns empty results
- Verify database connection works
- Check if tables exist: `curl http://localhost:3000/datasets`
- Ensure function exists: `\df get_all_results_with_context` in psql

### Function calls fail
- Verify function exists in database
- Check function parameter types match
- Ensure function has proper permissions

## What You Get

After setup, you'll have:

1. **REST API** at http://localhost:3000 with endpoints for:
   - All tables (CRUD operations)
   - Your SQL functions (via RPC)
   - Filtering and pagination

2. **Simple GUI** at http://localhost:8501 with:
   - Dataset exploration
   - Table export functionality  
   - API testing interface
   - Comprehensive results viewer

3. **Zero code changes** to existing system
   - Original Streamlit app still works
   - Same database, no migration needed
   - Can run both simultaneously

## Next Steps

Once this is working:
1. Add authentication (JWT tokens)
2. Create custom views for complex queries
3. Build enhanced GUI features
4. Add FastAPI for custom business logic
5. Deploy to production

This gives you a working API in under an hour!