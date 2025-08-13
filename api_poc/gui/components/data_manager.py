"""
Data Import/Export Manager component for the API POC GUI
"""
import streamlit as st
import pandas as pd
import os
import sys
import tempfile
from typing import List, Dict, Any
from pathlib import Path
import json

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def render_data_manager(client):
    """Render the data import/export manager interface"""
    st.header("📂 Data Import/Export Manager")
    
    st.write("Import and export data between local files, PostgREST, and Supabase backends.")
    
    # Backend selection for operations
    st.subheader("🎯 Target Backend")
    
    backend_info = client.get_backend_info()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write(f"**Current Backend:** {client.get_active_backend()}")
    
    with col2:
        if st.button("Switch to PostgREST", disabled=not backend_info.get("postgrest_available")):
            if client.switch_backend(use_supabase=False):
                st.success("Switched to PostgREST")
                st.rerun()
    
    with col3:
        if st.button("Switch to Supabase", disabled=not backend_info.get("supabase_available")):
            if client.switch_backend(use_supabase=True):
                st.success("Switched to Supabase")
                st.rerun()
    
    # Tabs for different operations
    tab1, tab2, tab3 = st.tabs(["📥 Import Data", "📤 Export Data", "🔄 Transfer Data"])
    
    with tab1:
        render_import_interface(client)
    
    with tab2:
        render_export_interface(client)
    
    with tab3:
        render_transfer_interface(client)


def render_import_interface(client):
    """Render the data import interface"""
    st.subheader("📥 Import Data")
    
    st.write(f"**Target Backend:** {client.get_active_backend()}")
    
    # Import type selection
    import_type = st.selectbox("Select Data Type", ["Pharmacies", "States", "Validated Overrides"])
    
    if import_type == "Pharmacies":
        render_pharmacy_import(client)
    elif import_type == "States":
        st.info("🚧 States import coming soon - use existing system for now")
    elif import_type == "Validated Overrides":
        st.info("🚧 Validated overrides import coming soon")


def render_pharmacy_import(client):
    """Render pharmacy import interface"""
    st.write("**Import Pharmacies from CSV**")
    
    # File upload
    uploaded_file = st.file_uploader(
        "Choose CSV file", 
        type=['csv'],
        help="Upload a pharmacy CSV file in the standard format"
    )
    
    if uploaded_file:
        # Preview file
        try:
            df = pd.read_csv(uploaded_file)
            
            st.write("**File Preview:**")
            st.dataframe(df.head(), use_container_width=True)
            
            st.write(f"**File Info:** {len(df)} rows, {len(df.columns)} columns")
            
            # Check required columns
            required_cols = ['name']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                st.error(f"Missing required columns: {missing_cols}")
                return
            else:
                st.success("✅ File format appears valid")
            
            # Import configuration
            st.subheader("Import Configuration")
            
            col1, col2 = st.columns(2)
            
            with col1:
                tag = st.text_input(
                    "Dataset Tag", 
                    value=f"imported_{uploaded_file.name.split('.')[0]}",
                    help="Unique identifier for this dataset"
                )
            
            with col2:
                created_by = st.text_input(
                    "Created By",
                    value="gui_user",
                    help="Who is importing this data"
                )
            
            description = st.text_area(
                "Description",
                value=f"Imported from {uploaded_file.name} via GUI",
                help="Description of this dataset"
            )
            
            # Preview what will be imported
            if st.checkbox("Show detailed preview"):
                st.write("**Sample Records:**")
                preview_df = df.head(10)
                st.dataframe(preview_df, use_container_width=True)
                
                # Check state_licenses column format
                if 'state_licenses' in df.columns:
                    st.write("**State Licenses Format Check:**")
                    sample_licenses = df['state_licenses'].dropna().head(3)
                    for idx, license_val in sample_licenses.items():
                        try:
                            if isinstance(license_val, str) and license_val.strip():
                                parsed = json.loads(license_val)
                                st.write(f"Row {idx}: {license_val} → {parsed} ✅")
                            else:
                                st.write(f"Row {idx}: Empty/null ✅")
                        except json.JSONDecodeError as e:
                            st.error(f"Row {idx}: Invalid JSON format: {license_val}")
            
            # Import button
            if st.button("🚀 Import Data", type="primary", disabled=not tag.strip()):
                with st.spinner(f"Importing data to {client.get_active_backend()}..."):
                    try:
                        # Save uploaded file to temporary location
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp_file:
                            df.to_csv(tmp_file.name, index=False)
                            temp_path = tmp_file.name
                        
                        try:
                            # Import via the existing importer
                            success = import_pharmacy_data(
                                client, 
                                temp_path, 
                                tag.strip(), 
                                created_by.strip() or "gui_user",
                                description.strip()
                            )
                            
                            if success:
                                st.success(f"✅ Successfully imported {len(df)} pharmacies!")
                                st.info(f"Dataset tag: '{tag}' in {client.get_active_backend()}")
                                
                                # Show next steps
                                st.write("**Next Steps:**")
                                st.write("• Go to Dataset Explorer to view the imported data")
                                st.write("• Use Comprehensive Results to analyze the data")
                                
                            else:
                                st.error("❌ Import failed - check logs for details")
                        
                        finally:
                            # Clean up temp file
                            try:
                                os.unlink(temp_path)
                            except:
                                pass
                    
                    except Exception as e:
                        st.error(f"Import error: {e}")
        
        except Exception as e:
            st.error(f"Error reading file: {e}")


def render_export_interface(client):
    """Render the data export interface"""
    st.subheader("📤 Export Data")
    
    st.write(f"**Source Backend:** {client.get_active_backend()}")
    
    # Get available datasets
    try:
        datasets = client.get_datasets()
        
        if not datasets:
            st.warning("No datasets found in the current backend")
            return
        
        # Create dataset options
        dataset_options = {}
        for ds in datasets:
            label = f"{ds['tag']} ({ds['kind']}) - {ds.get('description', 'No description')[:50]}"
            dataset_options[label] = ds
        
        # Dataset selection
        selected_label = st.selectbox("Select Dataset to Export", list(dataset_options.keys()))
        
        if selected_label:
            selected_dataset = dataset_options[selected_label]
            
            st.write("**Dataset Details:**")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Kind", selected_dataset['kind'])
            with col2:
                st.metric("Tag", selected_dataset['tag'])
            with col3:
                st.metric("Created", pd.to_datetime(selected_dataset['created_at']).strftime('%Y-%m-%d'))
            
            if selected_dataset.get('description'):
                st.info(f"**Description:** {selected_dataset['description']}")
            
            # Export configuration
            st.subheader("Export Configuration")
            
            col1, col2 = st.columns(2)
            
            with col1:
                export_format = st.selectbox("Export Format", ["CSV", "JSON"])
                limit = st.number_input("Row Limit", min_value=1, max_value=10000, value=1000)
            
            with col2:
                include_metadata = st.checkbox("Include Metadata", value=True)
                if export_format == "CSV":
                    flatten_json = st.checkbox("Flatten JSON columns", value=True, 
                                             help="Convert JSON columns to string representation")
            
            # Preview data
            if st.button("Preview Data"):
                with st.spinner("Loading data preview..."):
                    try:
                        table_name = get_table_name_for_kind(selected_dataset['kind'])
                        preview_data = client.get_table_data(
                            table_name, 
                            limit=min(limit, 10),
                            filters={"dataset_id": f"eq.{selected_dataset['id']}"}
                        )
                        
                        if preview_data:
                            st.write(f"**Preview ({len(preview_data)} of {limit} max rows):**")
                            preview_df = pd.DataFrame(preview_data)
                            st.dataframe(preview_df, use_container_width=True)
                        else:
                            st.warning("No data found for this dataset")
                    
                    except Exception as e:
                        st.error(f"Error loading preview: {e}")
            
            # Export button
            if st.button("📤 Export Data", type="primary"):
                with st.spinner("Exporting data..."):
                    try:
                        exported_data = export_dataset_data(
                            client, 
                            selected_dataset, 
                            limit=limit,
                            include_metadata=include_metadata
                        )
                        
                        if exported_data:
                            # Create download
                            if export_format == "CSV":
                                df = pd.DataFrame(exported_data)
                                if 'flatten_json' in locals() and flatten_json:
                                    # Flatten JSON columns
                                    for col in df.columns:
                                        if df[col].dtype == 'object':
                                            df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, (dict, list)) else x)
                                
                                csv_data = df.to_csv(index=False)
                                filename = f"{selected_dataset['tag']}_{selected_dataset['kind']}.csv"
                                
                                st.download_button(
                                    label=f"Download {filename}",
                                    data=csv_data,
                                    file_name=filename,
                                    mime="text/csv"
                                )
                            
                            else:  # JSON
                                json_data = json.dumps(exported_data, indent=2, default=str)
                                filename = f"{selected_dataset['tag']}_{selected_dataset['kind']}.json"
                                
                                st.download_button(
                                    label=f"Download {filename}",
                                    data=json_data,
                                    file_name=filename,
                                    mime="application/json"
                                )
                            
                            st.success(f"✅ Exported {len(exported_data)} records")
                        
                        else:
                            st.warning("No data to export")
                    
                    except Exception as e:
                        st.error(f"Export error: {e}")
    
    except Exception as e:
        st.error(f"Error loading datasets: {e}")


def render_transfer_interface(client):
    """Render the data transfer interface between backends"""
    st.subheader("🔄 Transfer Data Between Backends")
    
    backend_info = client.get_backend_info()
    
    # Check if both backends are available
    if not (backend_info.get("postgrest_available") and backend_info.get("supabase_available")):
        st.warning("Both PostgREST and Supabase must be available for data transfer")
        return
    
    st.write("Transfer datasets between local PostgREST and Supabase backends.")
    
    # Source and destination
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Source Backend**")
        source_backend = st.radio("Transfer From", ["PostgREST (Local)", "Supabase (Cloud)"], key="source")
    
    with col2:
        st.write("**Destination Backend**")
        dest_backend = st.radio("Transfer To", ["Supabase (Cloud)", "PostgREST (Local)"], key="dest")
    
    if source_backend == dest_backend.replace(" (Local)", "").replace(" (Cloud)", ""):
        st.error("Source and destination cannot be the same backend")
        return
    
    # Get datasets from source backend
    try:
        # Switch to source backend temporarily
        original_backend = client.get_active_backend()
        use_supabase_for_source = "Supabase" in source_backend
        
        client.switch_backend(use_supabase=use_supabase_for_source)
        source_datasets = client.get_datasets()
        
        # Switch back to original
        client.switch_backend(use_supabase=("Supabase" in original_backend))
        
        if source_datasets:
            # Dataset selection
            dataset_options = {}
            for ds in source_datasets:
                label = f"{ds['tag']} ({ds['kind']}) - {len(str(ds.get('description', ''))[:30])}..."
                dataset_options[label] = ds
            
            selected_label = st.selectbox("Select Dataset to Transfer", list(dataset_options.keys()))
            
            if selected_label:
                selected_dataset = dataset_options[selected_label]
                
                st.write("**Transfer Details:**")
                st.info(f"**From:** {source_backend} → **To:** {dest_backend}")
                st.write(f"**Dataset:** {selected_dataset['tag']} ({selected_dataset['kind']})")
                
                # Transfer options
                new_tag = st.text_input(
                    "New Tag (optional)", 
                    value="", 
                    help="Leave blank to use original tag, or specify new tag for destination"
                )
                
                if st.button("🔄 Transfer Dataset", type="primary"):
                    with st.spinner(f"Transferring dataset from {source_backend} to {dest_backend}..."):
                        try:
                            success = transfer_dataset(
                                client, 
                                selected_dataset, 
                                use_supabase_for_source, 
                                not use_supabase_for_source,
                                new_tag.strip() or selected_dataset['tag']
                            )
                            
                            if success:
                                st.success("✅ Dataset transferred successfully!")
                            else:
                                st.error("❌ Transfer failed")
                        
                        except Exception as e:
                            st.error(f"Transfer error: {e}")
        
        else:
            st.warning(f"No datasets found in {source_backend}")
    
    except Exception as e:
        st.error(f"Error loading source datasets: {e}")


def import_pharmacy_data(client, filepath: str, tag: str, created_by: str, description: str) -> bool:
    """Import pharmacy data using the appropriate importer for the backend"""
    try:
        if client.use_supabase:
            # Use Supabase importer
            from imports.supabase_importer import create_supabase_importer
            
            try:
                supabase_importer = create_supabase_importer(client)
                return supabase_importer.import_pharmacies_csv(
                    filepath=filepath,
                    tag=tag,
                    created_by=created_by,
                    description=description
                )
            except NotImplementedError:
                st.error("Supabase import requires MCP tools context. Please use Claude Code CLI for Supabase imports.")
                return False
            except Exception as e:
                st.error(f"Supabase import failed: {e}")
                return False
        else:
            # Use PostgreSQL importer
            from imports.pharmacies import PharmacyImporter
            
            with PharmacyImporter(backend='postgresql') as importer:
                return importer.import_csv(
                    filepath=filepath,
                    tag=tag,
                    created_by=created_by,
                    description=description
                )
    
    except Exception as e:
        st.error(f"Import failed: {e}")
        return False


def export_dataset_data(client, dataset: Dict, limit: int = 1000, include_metadata: bool = True) -> List[Dict]:
    """Export data for a specific dataset"""
    try:
        table_name = get_table_name_for_kind(dataset['kind'])
        
        data = client.get_table_data(
            table_name,
            limit=limit,
            filters={"dataset_id": f"eq.{dataset['id']}"}
        )
        
        if include_metadata and data:
            # Add dataset metadata to each record
            for record in data:
                record['_dataset_tag'] = dataset['tag']
                record['_dataset_kind'] = dataset['kind']
                record['_dataset_description'] = dataset.get('description', '')
                record['_exported_at'] = pd.Timestamp.now().isoformat()
                record['_exported_from'] = client.get_active_backend()
        
        return data
    
    except Exception as e:
        st.error(f"Export failed: {e}")
        return []


def transfer_dataset(client, dataset: Dict, source_is_supabase: bool, dest_is_supabase: bool, new_tag: str) -> bool:
    """Transfer a dataset between backends"""
    try:
        # Get data from source
        client.switch_backend(use_supabase=source_is_supabase)
        source_data = export_dataset_data(client, dataset, limit=10000, include_metadata=False)
        
        if not source_data:
            st.error("No data found in source dataset")
            return False
        
        # For now, only support transfer TO PostgREST (since Supabase import needs more work)
        if dest_is_supabase:
            st.error("Transfer to Supabase not yet implemented. Use CSV export/import workflow.")
            return False
        
        # Switch to destination backend
        client.switch_backend(use_supabase=dest_is_supabase)
        
        # For pharmacy datasets, use the importer
        if dataset['kind'] == 'pharmacies':
            # Convert data to CSV format and import
            df = pd.DataFrame(source_data)
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp_file:
                df.to_csv(tmp_file.name, index=False)
                temp_path = tmp_file.name
            
            try:
                success = import_pharmacy_data(
                    client, 
                    temp_path, 
                    new_tag,
                    "transfer_user",
                    f"Transferred from {dataset['tag']} in {'Supabase' if source_is_supabase else 'PostgREST'}"
                )
                return success
            finally:
                os.unlink(temp_path)
        
        else:
            st.error(f"Transfer for {dataset['kind']} datasets not yet implemented")
            return False
    
    except Exception as e:
        st.error(f"Transfer failed: {e}")
        return False


def get_table_name_for_kind(kind: str) -> str:
    """Get database table name for dataset kind"""
    mapping = {
        'pharmacies': 'pharmacies',
        'states': 'search_results', 
        'validated': 'validated_overrides'
    }
    return mapping.get(kind, kind)