"""
Supabase Management component for the API POC GUI
"""
import streamlit as st
import pandas as pd
from typing import List, Dict, Any


def render_supabase_manager(client):
    """Render the Supabase management interface"""
    st.header("☁️ Supabase Management")
    
    # Backend info
    backend_info = client.get_backend_info()
    
    # Connection status
    st.subheader("Connection Status")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**PostgREST (Local)**")
        if backend_info.get("postgrest_available", False):
            st.success("✅ Connected")
        else:
            st.error("❌ Not available")
    
    with col2:
        st.write("**Supabase (Cloud)**")
        if backend_info.get("supabase_available", False):
            st.success("✅ Connected")
        else:
            st.error("❌ Not available")
    
    # Active backend
    st.info(f"**Active Backend:** {client.get_active_backend()}")
    
    # Backend switching
    st.subheader("Backend Selection")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Use PostgREST (Local)", disabled=not backend_info.get("postgrest_available", False)):
            if client.switch_backend(use_supabase=False):
                st.success("Switched to PostgREST")
                st.rerun()
            else:
                st.error("Failed to switch to PostgREST")
    
    with col2:
        if st.button("Use Supabase (Cloud)", disabled=not backend_info.get("supabase_available", False)):
            if client.switch_backend(use_supabase=True):
                st.success("Switched to Supabase")
                st.rerun()
            else:
                st.error("Failed to switch to Supabase")
    
    # Supabase-specific features
    if client.supabase_client and backend_info.get("supabase_available", False):
        render_supabase_features(client)
    else:
        st.warning("Supabase features not available. Check connection configuration and credentials in .env file.")


def render_supabase_features(client):
    """Render Supabase-specific features"""
    
    # Project Information
    st.subheader("☁️ Supabase Project Information")
    
    if st.button("Load Project Info"):
        try:
            info = client.supabase_client.get_project_info()
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Project URL:**")
                st.code(info.get("url", "Not available"))
            
            with col2:
                st.write("**Connection Status:**")
                status = info.get("connection_status", "Unknown")
                if status == "Connected":
                    st.success(f"✅ {status}")
                else:
                    st.error(f"❌ {status}")
            
            st.write("**Anonymous Key:**")
            st.code(info.get("anon_key", "Not available"))
            
            st.write("**Client Library:**")
            st.info(info.get("client_library", "Unknown"))
            
            # Test basic table access
            st.write("**Basic Table Test:**")
            datasets = client.supabase_client.get_datasets_via_rest()
            if datasets and not any("error" in str(d) for d in datasets):
                st.success(f"✅ Successfully fetched {len(datasets)} datasets")
                if datasets:
                    st.write("Sample dataset:")
                    st.json(datasets[0])
            else:
                st.error(f"❌ Failed to fetch datasets: {datasets}")
        
        except Exception as e:
            st.error(f"Error loading project info: {e}")
    
    # Database Operations
    st.subheader("🔧 Database Operations")
    
    st.info("💡 Note: Advanced features like schema setup and TypeScript generation require Supabase CLI or management console.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Test Table Access"):
            with st.spinner("Testing table access..."):
                try:
                    tables = ["datasets", "pharmacies", "search_results"]
                    results = {}
                    
                    for table in tables:
                        data = client.supabase_client.get_table_data_via_rest(table, limit=1)
                        if data and not any("error" in str(d) for d in data):
                            results[table] = f"✅ {len(data)} records accessible"
                        else:
                            results[table] = f"❌ Error: {data}"
                    
                    st.write("**Table Access Test Results:**")
                    for table, result in results.items():
                        st.write(f"• {table}: {result}")
                
                except Exception as e:
                    st.error(f"Test error: {e}")
    
    with col2:
        if st.button("Test RPC Functions"):
            with st.spinner("Testing RPC functions..."):
                try:
                    # Test if we can call the comprehensive results function
                    result = client.supabase_client.call_rpc_function("get_all_results_with_context", {
                        "p_states_tag": "test", 
                        "p_pharmacies_tag": "test",
                        "p_validated_tag": ""
                    })
                    
                    if isinstance(result, dict) and "error" in result:
                        st.error(f"RPC test failed: {result['error']}")
                    else:
                        st.success("✅ RPC functions are accessible")
                        st.info(f"Test result type: {type(result)}")
                
                except Exception as e:
                    st.error(f"RPC test error: {e}")
    
    # Advanced Features  
    st.subheader("🚀 Advanced Features")
    
    st.info("💡 Advanced management features like branches, logs, and advisors require Supabase management console or CLI access.")
    
    # Raw SQL Interface
    st.subheader("💾 Raw SQL Interface")
    
    with st.expander("Execute Custom SQL"):
        st.warning("⚠️ Be careful with SQL execution. This runs directly on Supabase.")
        
        sql_query = st.text_area(
            "SQL Query", 
            value="SELECT * FROM datasets LIMIT 5;",
            height=100,
            help="Enter SQL query to execute"
        )
        
        if st.button("Execute SQL"):
            if sql_query.strip():
                try:
                    with st.spinner("Executing SQL..."):
                        result = client.supabase_client.execute_sql(sql_query)
                    
                    if isinstance(result, dict) and "error" in result:
                        st.error(f"SQL Error: {result['error']}")
                    elif isinstance(result, list):
                        st.success(f"Query executed successfully! ({len(result)} rows returned)")
                        
                        if result:
                            df = pd.DataFrame(result)
                            st.dataframe(df, use_container_width=True)
                        else:
                            st.info("Query returned no rows")
                    else:
                        st.success("Query executed successfully!")
                        st.json(result)
                
                except Exception as e:
                    st.error(f"Execution error: {e}")
            else:
                st.warning("Please enter a SQL query")


def render_migration_interface(client):
    """Render migration management interface"""
    st.subheader("📋 Migration Management")
    
    # Create new migration
    with st.expander("Create New Migration"):
        migration_name = st.text_input("Migration Name", placeholder="add_new_table")
        migration_sql = st.text_area(
            "Migration SQL", 
            placeholder="CREATE TABLE example (id SERIAL PRIMARY KEY);",
            height=150
        )
        
        if st.button("Apply Migration"):
            if migration_name and migration_sql:
                try:
                    result = client.supabase_client.apply_migration(migration_name, migration_sql)
                    
                    if isinstance(result, dict) and "error" in result:
                        st.error(f"Migration failed: {result['error']}")
                    else:
                        st.success("Migration applied successfully!")
                        st.json(result)
                
                except Exception as e:
                    st.error(f"Migration error: {e}")
            else:
                st.warning("Please provide both migration name and SQL")


def render_backend_comparison(client):
    """Render comparison between PostgREST and Supabase"""
    st.subheader("🔄 Backend Comparison")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**PostgREST (Local)**")
        st.write("✅ Fast local development")
        st.write("✅ No network latency")
        st.write("✅ Full control")
        st.write("❌ No cloud features")
        st.write("❌ Manual scaling")
    
    with col2:
        st.write("**Supabase (Cloud)**")
        st.write("✅ Cloud hosting")
        st.write("✅ Built-in auth & storage")
        st.write("✅ Real-time features")
        st.write("✅ Branch management")
        st.write("❌ Network dependency")
        st.write("❌ Usage costs")