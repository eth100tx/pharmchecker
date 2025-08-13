"""
Dataset Explorer component for the API POC GUI
"""
import streamlit as st
import pandas as pd
from typing import List, Dict, Any


def render_dataset_explorer(client):
    """Render the dataset explorer interface"""
    st.header("📊 Dataset Explorer")
    
    try:
        # Get all datasets
        datasets = client.get_datasets()
        
        if not datasets:
            st.warning("No datasets found in the database.")
            return
        
        df = pd.DataFrame(datasets)
        
        # Display datasets table
        st.subheader("Available Datasets")
        st.dataframe(df, use_container_width=True)
        
        # Dataset selector
        st.subheader("Explore Dataset")
        col1, col2 = st.columns(2)
        
        with col1:
            dataset_options = [f"{row['tag']} ({row['kind']})" for _, row in df.iterrows()]
            selected_dataset = st.selectbox("Select Dataset", dataset_options)
        
        with col2:
            preview_limit = st.number_input("Preview Limit", min_value=10, max_value=1000, value=50)
        
        if selected_dataset:
            # Parse selection
            selected_row = df[df.apply(lambda x: f"{x['tag']} ({x['kind']})" == selected_dataset, axis=1)].iloc[0]
            dataset_id = selected_row['id']
            dataset_kind = selected_row['kind']
            
            st.subheader(f"Dataset Details: {selected_row['tag']}")
            
            # Show dataset metadata
            metadata_cols = st.columns(3)
            with metadata_cols[0]:
                st.metric("Kind", dataset_kind)
            with metadata_cols[1]:
                st.metric("Created By", selected_row.get('created_by', 'Unknown'))
            with metadata_cols[2]:
                st.metric("Created", pd.to_datetime(selected_row['created_at']).strftime('%Y-%m-%d'))
            
            if selected_row.get('description'):
                st.info(f"**Description:** {selected_row['description']}")
            
            # Show data preview based on kind
            if dataset_kind == 'pharmacies':
                st.subheader("Pharmacy Data Preview")
                pharmacies = client.get_pharmacies(dataset_id=dataset_id, limit=preview_limit)
                if pharmacies:
                    pharmacy_df = pd.DataFrame(pharmacies)
                    st.dataframe(pharmacy_df, use_container_width=True)
                    st.caption(f"Showing {len(pharmacies)} records")
                else:
                    st.warning("No pharmacy data found for this dataset.")
            
            elif dataset_kind == 'states':
                st.subheader("Search Results Preview")
                results = client.get_search_results(dataset_id=dataset_id, limit=preview_limit)
                if results:
                    results_df = pd.DataFrame(results)
                    st.dataframe(results_df, use_container_width=True)
                    st.caption(f"Showing {len(results)} records")
                else:
                    st.warning("No search results found for this dataset.")
            
            elif dataset_kind == 'validated':
                st.subheader("Validated Overrides Preview")
                data = client.get_table_data('validated_overrides', 
                                           filters={'dataset_id': f'eq.{dataset_id}'}, 
                                           limit=preview_limit)
                if data:
                    data_df = pd.DataFrame(data)
                    st.dataframe(data_df, use_container_width=True)
                    st.caption(f"Showing {len(data)} records")
                else:
                    st.warning("No validated overrides found for this dataset.")
            
            # Export options
            st.subheader("Export Options")
            if st.button(f"Export {dataset_kind} data to CSV"):
                try:
                    if dataset_kind == 'pharmacies':
                        table = 'pharmacies'
                    elif dataset_kind == 'states':
                        table = 'search_results'
                    elif dataset_kind == 'validated':
                        table = 'validated_overrides'
                    else:
                        st.error(f"Unknown dataset kind: {dataset_kind}")
                        return
                    
                    filename = f"{selected_row['tag']}_{table}.csv"
                    client.export_table_to_csv(
                        table, 
                        filename, 
                        filters={'dataset_id': f'eq.{dataset_id}'}
                    )
                    st.success(f"Data exported to {filename}")
                    
                    # Offer download
                    with open(filename, 'rb') as f:
                        st.download_button(
                            label=f"Download {filename}",
                            data=f.read(),
                            file_name=filename,
                            mime='text/csv'
                        )
                except Exception as e:
                    st.error(f"Export failed: {e}")
            
            # Dataset Management
            st.subheader("Dataset Management")
            st.warning("⚠️ **Use with caution!** These operations cannot be undone.")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Rename Dataset**")
                new_tag = st.text_input(
                    "New Tag Name", 
                    value=selected_row['tag'],
                    help="Enter a new tag name for this dataset"
                )
                
                if st.button(f"🏷️ Rename to '{new_tag}'", disabled=(new_tag == selected_row['tag'] or not new_tag)):
                    if st.session_state.get('confirm_rename') != dataset_id:
                        st.session_state.confirm_rename = dataset_id
                        st.warning("Click again to confirm rename operation")
                    else:
                        with st.spinner("Renaming dataset..."):
                            try:
                                result = client.rename_dataset(dataset_id, new_tag)
                                if result.get('success'):
                                    st.success(result['message'])
                                    st.session_state.confirm_rename = None
                                    st.rerun()  # Refresh the page to show new name
                                else:
                                    st.error(result.get('error', 'Unknown error'))
                            except Exception as e:
                                st.error(f"Rename failed: {e}")
            
            with col2:
                st.write("**Delete Dataset**")
                st.error("This will permanently delete ALL data associated with this dataset!")
                
                if st.button(f"🗑️ Delete '{selected_row['tag']}'"):
                    if st.session_state.get('confirm_delete') != dataset_id:
                        st.session_state.confirm_delete = dataset_id
                        st.error("⚠️ Click again to PERMANENTLY delete this dataset and ALL its data!")
                    else:
                        with st.spinner("Deleting dataset..."):
                            try:
                                # Debug: Check if method exists
                                if not hasattr(client, 'delete_dataset'):
                                    st.error("Error: delete_dataset method not found. Please refresh the page.")
                                    return
                                
                                result = client.delete_dataset(dataset_id)
                                if result.get('success'):
                                    st.success(result['message'])
                                    if 'deleted_counts' in result:
                                        st.info(f"Deleted records: {result['deleted_counts']}")
                                    st.session_state.confirm_delete = None
                                    st.rerun()  # Refresh the page
                                else:
                                    st.error(result.get('error', 'Unknown error'))
                            except AttributeError as e:
                                st.error(f"Method error: {e}. Please refresh the page to reload the client.")
                            except Exception as e:
                                st.error(f"Delete failed: {e}")
    
    except Exception as e:
        st.error(f"Error loading datasets: {e}")


def render_dataset_summary(datasets: List[Dict]) -> None:
    """Render summary statistics about datasets"""
    if not datasets:
        return
    
    df = pd.DataFrame(datasets)
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Datasets", len(df))
    
    with col2:
        pharmacy_count = len(df[df['kind'] == 'pharmacies'])
        st.metric("Pharmacy Datasets", pharmacy_count)
    
    with col3:
        states_count = len(df[df['kind'] == 'states'])
        st.metric("States Datasets", states_count)
    
    # Kind distribution
    if len(df) > 0:
        kind_counts = df['kind'].value_counts()
        st.subheader("Dataset Types")
        for kind, count in kind_counts.items():
            st.write(f"**{kind.title()}**: {count} datasets")