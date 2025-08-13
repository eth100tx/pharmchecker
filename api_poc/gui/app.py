"""
PostgREST API POC GUI for PharmChecker
Simple Streamlit interface for testing the PostgREST API
"""
import streamlit as st
import pandas as pd
import sys
import os

# Add the current directory to path for imports
sys.path.append(os.path.dirname(__file__))

from client import create_client
from components.dataset_explorer import render_dataset_explorer
from components.api_tester import render_api_tester, render_quick_queries
from components.comprehensive_results import render_comprehensive_results
from components.supabase_manager import render_supabase_manager
from components.data_manager import render_data_manager


def main():
    """Main Streamlit application"""
    st.set_page_config(
        page_title="PharmChecker API POC",
        page_icon="🏥",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🏥 PharmChecker PostgREST API POC")
    st.write("Simple GUI for testing the PostgREST API and database operations")
    
    # Initialize client
    if 'client' not in st.session_state:
        # Use environment variable to determine backend
        import sys, os
        sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        from config import use_cloud_database
        st.session_state.client = create_client(prefer_supabase=use_cloud_database())
    
    # Force refresh client if it doesn't have the new methods (for development)
    if not hasattr(st.session_state.client, 'delete_dataset') or not hasattr(st.session_state.client, 'get_table_counts'):
        # Use environment variable to determine backend
        import sys, os
        sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        from config import use_cloud_database
        st.session_state.client = create_client(prefer_supabase=use_cloud_database())
    
    client = st.session_state.client
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    
    # Connection status
    with st.sidebar:
        st.subheader("Connection Status")
        if st.button("Test Connection"):
            if client.test_connection():
                st.success("✅ Connected")
            else:
                st.error("❌ Disconnected")
        
        st.write(f"**API URL:** {client.get_active_api_url()}")
    
    # Page selection
    pages = {
        "🏠 Overview": "overview",
        "📊 Dataset Explorer": "datasets", 
        "🏥 Comprehensive Results": "comprehensive",
        "📂 Data Manager": "data_manager",
        "🔧 API Testing": "api_test",
        "☁️ Supabase Manager": "supabase"
    }
    
    selected_page = st.sidebar.radio("Select Page", list(pages.keys()))
    page_key = pages[selected_page]
    
    # Render selected page
    if page_key == "overview":
        render_overview_page(client)
    elif page_key == "datasets":
        render_dataset_explorer(client)
    elif page_key == "comprehensive":
        render_comprehensive_results(client)
    elif page_key == "data_manager":
        render_data_manager(client)
    elif page_key == "api_test":
        render_api_testing_page(client)
    elif page_key == "supabase":
        render_supabase_manager(client)


def render_overview_page(client):
    """Render the overview page"""
    st.header("📋 Overview")
    
    st.write("""
    This is a proof-of-concept GUI for testing both PostgREST and Supabase integration with PharmChecker.
    
    **Features:**
    - 📊 **Dataset Explorer**: Browse and export datasets 
    - 🏥 **Comprehensive Results**: Call the main function that powers the existing GUI
    - 📂 **Data Manager**: Import/export data and transfer between backends
    - 🔧 **API Testing**: Test raw PostgREST endpoints interactively
    - ☁️ **Supabase Manager**: Manage cloud database, branches, and migrations
    
    **Dual Backend Support**: Works with both local PostgREST and cloud Supabase.
    """)
    
    # Backend status
    backend_info = client.get_backend_info()
    st.subheader("Backend Status")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Active Backend", client.get_active_backend())
    
    with col2:
        postgrest_status = "✅ Available" if backend_info.get("postgrest_available") else "❌ Unavailable"
        st.metric("PostgREST", postgrest_status)
    
    with col3:
        supabase_status = "✅ Available" if backend_info.get("supabase_available") else "❌ Unavailable"
        st.metric("Supabase", supabase_status)
    
    # Quick stats
    st.subheader("Quick Stats")
    
    try:
        # Test connection and get basic info
        if client.test_connection():
            st.success("✅ API is accessible")
            
            # Get dataset counts
            datasets = client.get_datasets()
            if datasets:
                import pandas as pd
                df = pd.DataFrame(datasets)
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Datasets", len(df))
                
                with col2:
                    pharmacy_count = len(df[df['kind'] == 'pharmacies'])
                    st.metric("Pharmacy Datasets", pharmacy_count)
                
                with col3:
                    states_count = len(df[df['kind'] == 'states'])
                    st.metric("States Datasets", states_count)
                
                # Recent datasets
                st.subheader("Recent Datasets")
                try:
                    # Convert created_at to datetime for sorting
                    df['created_at_dt'] = pd.to_datetime(df['created_at'])
                    recent = df.nlargest(5, 'created_at_dt')[['tag', 'kind', 'created_at', 'created_by']]
                    st.dataframe(recent, use_container_width=True)
                except Exception as e:
                    # Fallback: just show first 5 datasets
                    st.warning(f"Could not sort by date: {e}")
                    recent = df.head(5)[['tag', 'kind', 'created_at', 'created_by']]
                    st.dataframe(recent, use_container_width=True)
            else:
                st.warning("No datasets found")
        else:
            st.error("❌ Cannot connect to API")
            st.write("**Troubleshooting:**")
            st.write("1. Make sure PostgREST is running: `./postgrest postgrest.conf`")
            st.write("2. Check the database connection in `postgrest.conf`")
            st.write("3. Verify the API URL is correct")
    
    except Exception as e:
        st.error(f"Error getting overview data: {e}")
    
    # Quick actions
    st.subheader("Quick Actions")
    render_quick_queries(client)
    
    # Instructions
    st.subheader("Getting Started")
    
    with st.expander("📖 How to Use This GUI"):
        st.write("""
        **1. Dataset Explorer**
        - Browse all available datasets
        - View data previews
        - Export tables to CSV
        
        **2. Comprehensive Results**  
        - Call the main `get_all_results_with_context()` function
        - Select pharmacy and states datasets
        - View results with filtering and analysis
        
        **3. API Testing**
        - Test raw PostgREST endpoints
        - Send custom HTTP requests
        - View API schema and documentation
        """)
    
    with st.expander("🔧 PostgREST Setup"):
        st.code("""
# Start PostgREST (in api_poc/postgrest/ directory)
./postgrest postgrest.conf

# Test API is working
curl http://localhost:3000/datasets
        """)


def render_api_testing_page(client):
    """Render the API testing page"""
    render_api_tester(client)


if __name__ == "__main__":
    main()