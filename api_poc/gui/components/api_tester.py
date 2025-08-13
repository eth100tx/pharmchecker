"""
API Testing component for the API POC GUI
"""
import streamlit as st
import json
import requests
from typing import Dict, Any


def render_api_tester(client):
    """Render the API testing interface"""
    st.header("🔧 API Testing")
    
    # Connection test
    st.subheader("Connection Test")
    col1, col2 = st.columns([1, 3])
    
    with col1:
        if st.button("Test Connection"):
            if client.test_connection():
                st.success("✅ API is accessible")
            else:
                st.error("❌ API connection failed")
    
    with col2:
        st.info(f"Testing connection to: {client.base_url}")
    
    # Raw endpoint testing
    st.subheader("Raw Endpoint Testing")
    
    # Predefined endpoints
    endpoints = {
        "List Datasets": "/datasets",
        "List Pharmacies": "/pharmacies?limit=10", 
        "List Search Results": "/search_results?limit=10",
        "Schema": "/",
        "Comprehensive Results": "/rpc/get_all_results_with_context?p_states_tag=states_baseline&p_pharmacies_tag=test_pharmacies&p_validated_tag="
    }
    
    selected_endpoint = st.selectbox("Select Predefined Endpoint", list(endpoints.keys()))
    endpoint_url = endpoints[selected_endpoint]
    
    # Custom endpoint
    st.write("Or enter custom endpoint:")
    custom_endpoint = st.text_input("Custom Endpoint", value=endpoint_url, help="Enter endpoint path starting with /")
    
    # HTTP method
    method = st.radio("HTTP Method", ["GET", "POST"], horizontal=True)
    
    # Request body for POST
    request_body = None
    if method == "POST":
        st.subheader("Request Body (JSON)")
        body_text = st.text_area("JSON Body", value='{}', height=100)
        try:
            request_body = json.loads(body_text) if body_text.strip() else None
        except json.JSONDecodeError:
            st.error("Invalid JSON in request body")
            return
    
    # Headers
    with st.expander("Request Headers (Optional)"):
        custom_headers = st.text_area("Additional Headers (JSON format)", value='{}', height=80)
        try:
            headers = json.loads(custom_headers) if custom_headers.strip() else {}
        except json.JSONDecodeError:
            st.error("Invalid JSON in headers")
            headers = {}
    
    # Execute request
    if st.button("Send Request", type="primary"):
        try:
            url = f"{client.base_url}{custom_endpoint}"
            
            # Prepare headers
            request_headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            request_headers.update(headers)
            
            # Make request
            with st.spinner("Sending request..."):
                if method == "GET":
                    response = requests.get(url, headers=request_headers)
                else:  # POST
                    response = requests.post(url, headers=request_headers, json=request_body)
            
            # Display response
            st.subheader("Response")
            
            # Response status
            if response.status_code < 400:
                st.success(f"Status: {response.status_code} {response.reason}")
            else:
                st.error(f"Status: {response.status_code} {response.reason}")
            
            # Response headers
            with st.expander("Response Headers"):
                st.json(dict(response.headers))
            
            # Response body
            st.subheader("Response Body")
            
            try:
                if response.headers.get('content-type', '').startswith('application/json'):
                    response_json = response.json()
                    
                    # Show formatted JSON
                    st.json(response_json)
                    
                    # If it's a list, show count and offer to view as table
                    if isinstance(response_json, list) and len(response_json) > 0:
                        st.caption(f"Returned {len(response_json)} items")
                        
                        if st.checkbox("View as Table"):
                            import pandas as pd
                            try:
                                df = pd.DataFrame(response_json)
                                st.dataframe(df, use_container_width=True)
                            except Exception as e:
                                st.error(f"Could not convert to table: {e}")
                
                else:
                    # Non-JSON response
                    st.text(response.text)
                    
            except json.JSONDecodeError:
                st.text("Response body:")
                st.code(response.text)
        
        except requests.exceptions.RequestException as e:
            st.error(f"Request failed: {e}")
        except Exception as e:
            st.error(f"Error: {e}")
    
    # API Schema viewer
    st.subheader("API Schema")
    if st.button("Load Schema"):
        try:
            schema = client.get_table_schema()
            
            # Extract table names from paths
            paths = schema.get('paths', {})
            tables = []
            rpc_functions = []
            
            for path in paths.keys():
                if path.startswith('/rpc/'):
                    rpc_functions.append(path[5:])  # Remove '/rpc/' prefix
                elif path != '/' and not path.startswith('/rpc/'):
                    tables.append(path[1:])  # Remove leading '/'
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Available Tables:**")
                for table in sorted(set(tables)):
                    st.write(f"• {table}")
            
            with col2:
                st.write("**Available RPC Functions:**")
                for func in sorted(set(rpc_functions)):
                    st.write(f"• {func}")
            
            # Full schema in expander
            with st.expander("Full OpenAPI Schema"):
                st.json(schema)
                
        except Exception as e:
            st.error(f"Failed to load schema: {e}")


def render_quick_queries(client):
    """Render quick query buttons for common operations"""
    st.subheader("Quick Queries")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📋 List All Tables", use_container_width=True):
            try:
                schema = client.get_table_schema()
                paths = schema.get('paths', {})
                tables = [path[1:] for path in paths.keys() 
                         if path != '/' and not path.startswith('/rpc/')]
                
                st.write("**Available Tables:**")
                for table in sorted(set(tables)):
                    st.write(f"• {table}")
            except Exception as e:
                st.error(f"Error: {e}")
    
    with col2:
        if st.button("🔢 Count Records", use_container_width=True):
            try:
                tables = ['datasets', 'pharmacies', 'search_results', 'validated_overrides']
                
                st.write("**Record Counts:**")
                for table in tables:
                    try:
                        # Use Prefer header to get count
                        url = f"{client.base_url}/{table}"
                        headers = {'Prefer': 'count=exact'}
                        response = requests.head(url, headers=headers)
                        
                        count_range = response.headers.get('Content-Range', '')
                        if '/' in count_range:
                            count = count_range.split('/')[-1]
                            st.write(f"• {table}: {count}")
                        else:
                            st.write(f"• {table}: Unable to get count")
                    except:
                        st.write(f"• {table}: Error")
            except Exception as e:
                st.error(f"Error: {e}")
    
    with col3:
        if st.button("🏥 Sample Data", use_container_width=True):
            try:
                # Get one record from each main table
                tables = ['datasets', 'pharmacies', 'search_results']
                
                for table in tables:
                    try:
                        data = client.get_table_data(table, limit=1)
                        if data:
                            st.write(f"**Sample {table}:**")
                            st.json(data[0])
                        else:
                            st.write(f"**{table}:** No data")
                    except:
                        st.write(f"**{table}:** Error getting sample")
            except Exception as e:
                st.error(f"Error: {e}")