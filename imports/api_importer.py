#!/usr/bin/env python3
"""
API-based importer for PharmChecker
Uses Supabase REST API to import data
"""

import os
import json
import shutil
import pandas as pd
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from utils.image_storage import create_image_storage

load_dotenv()

class APIImporter:
    """Supabase API importer for PharmChecker"""
    
    def __init__(self):
        """Initialize Supabase API importer"""
        self.session = requests.Session()
        
        self.base_url = os.getenv('SUPABASE_URL')
        service_key = os.getenv('SUPABASE_SERVICE_KEY')
        if not self.base_url or not service_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        
        self.api_url = f"{self.base_url}/rest/v1"
        self.session.headers.update({
            'apikey': service_key,
            'Authorization': f'Bearer {service_key}',
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        })
    
    def get_or_create_dataset(self, kind: str, tag: str, description: str = None, created_by: str = None) -> int:
        """Get existing dataset or create new one"""
        # Try to find existing dataset
        response = self.session.get(
            f"{self.api_url}/datasets",
            params={'kind': f'eq.{kind}', 'tag': f'eq.{tag}'}
        )
        response.raise_for_status()
        
        existing = response.json()
        if existing:
            dataset_id = existing[0]['id']
            print(f"📋 Using existing dataset '{tag}' (ID: {dataset_id})")
            return dataset_id
        
        # Create new dataset
        dataset_data = {
            'kind': kind,
            'tag': tag,
            'description': description,
            'created_by': created_by or 'api_importer'
        }
        
        response = self.session.post(f"{self.api_url}/datasets", json=dataset_data)
        response.raise_for_status()
        
        result = response.json()
        dataset_id = result[0]['id']
        print(f"✅ Created dataset '{tag}' (ID: {dataset_id})")
        return dataset_id
    
    def import_pharmacies_csv(self, csv_path: str, tag: str, created_by: str = None, description: str = None) -> bool:
        """Import pharmacies from CSV file"""
        try:
            # Load CSV
            df = pd.read_csv(csv_path)
            print(f"📂 Loaded {len(df)} pharmacies from {csv_path}")
            
            # Validate required columns
            required_columns = ['name', 'address', 'city', 'state', 'zip']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValueError(f"Missing required columns: {missing_columns}")
            
            # Create dataset
            dataset_id = self.get_or_create_dataset('pharmacies', tag, description, created_by)
            
            # Process each pharmacy
            success_count = 0
            error_count = 0
            
            for index, row in df.iterrows():
                try:
                    # Handle state_licenses column (can be empty or JSON array)
                    state_licenses_raw = row.get('state_licenses', '[]')
                    if pd.isna(state_licenses_raw) or state_licenses_raw == '':
                        state_licenses = []
                    elif isinstance(state_licenses_raw, str):
                        # Parse JSON string to Python list
                        try:
                            state_licenses = json.loads(state_licenses_raw)
                        except json.JSONDecodeError as e:
                            # Try to handle Python list syntax by converting to JSON
                            try:
                                # Replace single quotes with double quotes for JSON compliance
                                json_str = state_licenses_raw.replace("'", '"')
                                state_licenses = json.loads(json_str)
                            except json.JSONDecodeError:
                                print(f"⚠️  Invalid JSON in state_licenses for {row['name']}: {e}")
                                print(f"     Raw value: {repr(state_licenses_raw)}")
                                state_licenses = []
                    else:
                        # Already a list or other type
                        state_licenses = list(state_licenses_raw) if state_licenses_raw else []
                    
                    # Handle all fields with proper NaN checking
                    def safe_str(value, default=''):
                        """Convert value to string, handling NaN/None safely"""
                        if pd.isna(value) or value is None:
                            return default
                        return str(value).strip()
                    
                    pharmacy_data = {
                        'dataset_id': dataset_id,
                        'name': safe_str(row['name']),
                        'address': safe_str(row['address']),
                        'city': safe_str(row['city']),
                        'state': safe_str(row['state']),
                        'zip': safe_str(row['zip']),
                        'state_licenses': state_licenses
                    }
                    
                    # Validate required fields are not empty
                    if not pharmacy_data['name']:
                        print(f"⚠️  Skipping pharmacy with empty name at row {index + 2}")
                        continue
                    
                    response = self.session.post(f"{self.api_url}/pharmacies", json=pharmacy_data)
                    response.raise_for_status()
                    
                    success_count += 1
                    if success_count % 10 == 0:
                        print(f"  Imported {success_count}/{len(df)} pharmacies...")
                        
                except Exception as e:
                    error_count += 1
                    print(f"❌ Failed to import pharmacy {row.get('name', 'Unknown')}: {e}")
                    continue
            
            print(f"✅ Import complete: {success_count} success, {error_count} errors")
            return True
            
        except Exception as e:
            print(f"❌ Import failed: {e}")
            return False
    
    def import_states_csv(self, csv_path: str, tag: str, created_by: str = None, description: str = None) -> bool:
        """Import states from CSV file"""
        try:
            # Load CSV
            df = pd.read_csv(csv_path)
            print(f"📂 Loaded {len(df)} state records from {csv_path}")
            
            # Validate required columns
            required_columns = ['search_name', 'search_state']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValueError(f"Missing required columns: {missing_columns}")
            
            # Create dataset
            dataset_id = self.get_or_create_dataset('states', tag, description, created_by)
            
            # Process each record
            success_count = 0
            error_count = 0
            
            for index, row in df.iterrows():
                try:
                    # Handle different column name variations
                    search_timestamp = row.get('search_timestamp') or row.get('search_ts')
                    
                    state_data = {
                        'dataset_id': dataset_id,
                        'search_name': row['search_name'],
                        'search_state': row['search_state'],
                        'search_timestamp': search_timestamp,
                        'license_number': row.get('license_number'),
                        'license_status': row.get('license_status'),
                        'license_type': row.get('license_type'),
                        'license_name': row.get('license_name'),
                        'business_name': row.get('business_name'),
                        'address': row.get('address'),
                        'city': row.get('city'),
                        'state': row.get('state'),
                        'zip': str(row.get('zip', '')) if pd.notna(row.get('zip')) else None
                    }
                    
                    response = self.session.post(f"{self.api_url}/search_results", json=state_data)
                    response.raise_for_status()
                    
                    success_count += 1
                    if success_count % 10 == 0:
                        print(f"  Imported {success_count}/{len(df)} records...")
                        
                except Exception as e:
                    error_count += 1
                    print(f"❌ Failed to import record {index}: {e}")
                    continue
            
            print(f"✅ Import complete: {success_count} success, {error_count} errors")
            return True
            
        except Exception as e:
            print(f"❌ Import failed: {e}")
            return False
    
    def import_validated_csv(self, csv_path: str, tag: str, created_by: str = None, description: str = None) -> bool:
        """Import validated overrides from CSV file"""
        try:
            # Load CSV
            df = pd.read_csv(csv_path)
            print(f"📂 Loaded {len(df)} validated records from {csv_path}")
            
            # Validate required columns - use state_code which is the actual column name
            required_columns = ['pharmacy_name', 'state_code', 'override_type']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValueError(f"Missing required columns: {missing_columns}")
            
            # Create dataset
            dataset_id = self.get_or_create_dataset('validated', tag, description, created_by)
            
            # Process each record
            success_count = 0
            error_count = 0
            
            for index, row in df.iterrows():
                try:
                    # Create complete validated record with snapshot fields
                    validated_data = {
                        'dataset_id': dataset_id,
                        'pharmacy_name': row['pharmacy_name'],
                        'state_code': row['state_code'],  # Use state_code, not search_state
                        'license_number': row.get('license_number', ''),
                        'override_type': row['override_type'],
                        'reason': row.get('reason'),
                        'validated_by': row.get('validated_by', created_by or 'api_importer'),
                        'validated_at': row.get('validated_at', datetime.now().isoformat()),
                        
                        # Snapshot fields from search results
                        'license_status': row.get('license_status'),
                        'license_name': row.get('license_name'),
                        'address': row.get('address'),
                        'city': row.get('city'), 
                        'state': row.get('state'),
                        'zip': row.get('zip'),
                        'issue_date': row.get('issue_date'),
                        'expiration_date': row.get('expiration_date'),
                        'result_status': row.get('result_status')
                    }
                    
                    # Clean up None values and empty strings for optional fields
                    validated_data = {k: v for k, v in validated_data.items() if v is not None and v != ''}
                    
                    response = self.session.post(f"{self.api_url}/validated_overrides", json=validated_data)
                    response.raise_for_status()
                    
                    success_count += 1
                    if success_count % 10 == 0:
                        print(f"  Imported {success_count}/{len(df)} records...")
                        
                except Exception as e:
                    error_count += 1
                    print(f"❌ Failed to import record {index}: {e}")
                    continue
            
            print(f"✅ Import complete: {success_count} success, {error_count} errors")
            return True
            
        except Exception as e:
            print(f"❌ Import failed: {e}")
            return False
    
    def import_states_directory(self, states_dir: str, tag: str, created_by: str = None, description: str = None) -> bool:
        """Import states from directory of JSON files"""
        try:
            states_path = Path(states_dir)
            if not states_path.exists():
                raise ValueError(f"Directory not found: {states_dir}")
            
            json_files = list(states_path.glob("*.json"))
            if not json_files:
                raise ValueError(f"No JSON files found in {states_dir}")
            
            print(f"📂 Found {len(json_files)} JSON files in {states_dir}")
            
            # Create dataset
            dataset_id = self.get_or_create_dataset('states', tag, description, created_by)
            
            # Initialize image storage
            storage = create_image_storage('supabase')
            
            # Process each file
            total_results = 0
            success_files = 0
            error_files = 0
            
            for json_file in json_files:
                try:
                    with open(json_file, 'r') as f:
                        data = json.load(f)
                    
                    metadata = data.get('metadata', {})
                    results = data.get('results', [])
                    
                    if not results:
                        print(f"⚠️  No results in {json_file.name}, skipping")
                        continue
                    
                    # Process each result
                    for result in results:
                        try:
                            search_data = {
                                'dataset_id': dataset_id,
                                'search_name': metadata.get('search_name'),
                                'search_state': metadata.get('search_state'),
                                'search_timestamp': metadata.get('search_timestamp'),
                                'license_number': result.get('license_number'),
                                'license_status': result.get('license_status'),
                                'license_type': result.get('license_type'),
                                'business_name': result.get('business_name'),
                                'address': result.get('address'),
                                'city': result.get('city'),
                                'state': result.get('state'),
                                'zip': result.get('zip')
                            }
                            
                            response = self.session.post(f"{self.api_url}/search_results", json=search_data)
                            response.raise_for_status()
                            
                            total_results += 1
                            
                        except Exception as e:
                            print(f"❌ Failed to import result from {json_file.name}: {e}")
                            continue
                    
                    # Handle screenshot if it exists
                    png_file = json_file.with_suffix('.png')
                    if png_file.exists():
                        try:
                            content_hash, storage_path, metadata_dict = storage.store_image(png_file)
                            
                            asset_data = {
                                'dataset_id': dataset_id,
                                'search_name': metadata.get('search_name'),
                                'search_state': metadata.get('search_state'),
                                'search_timestamp': metadata.get('search_timestamp'),
                                'content_hash': content_hash,
                                'storage_path': storage_path,
                                'storage_type': storage.backend_type,
                                'file_size': metadata_dict['file_size'],
                                'image_width': metadata_dict.get('width'),
                                'image_height': metadata_dict.get('height')
                            }
                            
                            response = self.session.post(f"{self.api_url}/image_assets", json=asset_data)
                            response.raise_for_status()
                            
                        except Exception as e:
                            print(f"❌ Failed to store image {png_file.name}: {e}")
                    
                    success_files += 1
                    if success_files % 10 == 0:
                        print(f"  Processed {success_files}/{len(json_files)} files...")
                    
                except Exception as e:
                    error_files += 1
                    print(f"❌ Failed to process {json_file.name}: {e}")
                    continue
            
            print(f"✅ Import complete: {success_files} files, {total_results} results, {error_files} errors")
            return True
            
        except Exception as e:
            print(f"❌ Import failed: {e}")
            return False


def main():
    """Main CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='PharmChecker API Importer')
    parser.add_argument('data_type', choices=['pharmacies', 'states', 'validated'], 
                       help='Type of data to import')
    parser.add_argument('input_path', help='Path to CSV file or directory')
    parser.add_argument('tag', help='Dataset tag')
    parser.add_argument('--created-by', default='api_importer', help='Who created this dataset')
    parser.add_argument('--description', help='Dataset description')
    
    args = parser.parse_args()
    
    importer = APIImporter()
    
    if args.data_type == 'pharmacies':
        success = importer.import_pharmacies_csv(args.input_path, args.tag, args.created_by, args.description)
    elif args.data_type == 'states':
        # Check if input is CSV or directory
        input_path = Path(args.input_path)
        if input_path.is_file() and input_path.suffix == '.csv':
            success = importer.import_states_csv(args.input_path, args.tag, args.created_by, args.description)
        else:
            success = importer.import_states_directory(args.input_path, args.tag, args.created_by, args.description)
    elif args.data_type == 'validated':
        success = importer.import_validated_csv(args.input_path, args.tag, args.created_by, args.description)
    
    exit(0 if success else 1)


if __name__ == '__main__':
    main()