#!/usr/bin/env python3
"""
API-based importer for PharmChecker
Uses REST APIs to import data to both PostgREST and Supabase backends
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

load_dotenv()

class APIImporter:
    """Unified API importer for both PostgREST and Supabase"""
    
    def __init__(self, backend: str = 'postgresql'):
        """
        Initialize API importer
        
        Args:
            backend: 'postgresql' for PostgREST or 'supabase' for Supabase
        """
        self.backend = backend.lower()
        self.session = requests.Session()
        
        if self.backend == 'supabase':
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
        else:
            # PostgREST local
            self.api_url = "http://localhost:3000"
            self.session.headers.update({
                'Content-Type': 'application/json',
                'Prefer': 'return=representation'
            })
    
    def create_dataset(self, kind: str, tag: str, description: str = None, 
                      created_by: str = None) -> Optional[int]:
        """Create a new dataset and return its ID"""
        data = {
            'kind': kind,
            'tag': tag,
            'description': description or f"{kind} dataset: {tag}",
            'created_by': created_by or os.getenv('USER', 'api_importer')
        }
        
        try:
            response = self.session.post(f"{self.api_url}/datasets", json=data)
            response.raise_for_status()
            
            result = response.json()
            dataset_id = result[0]['id'] if result else None
            print(f"✅ Created dataset '{tag}' (ID: {dataset_id}) in {self.backend}")
            return dataset_id
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to create dataset: {e}")
            if hasattr(e.response, 'text'):
                print(f"Error details: {e.response.text}")
            return None
    
    def get_or_create_dataset(self, kind: str, tag: str, description: str = None,
                             created_by: str = None) -> Optional[int]:
        """Get existing dataset or create new one"""
        # Try to find existing dataset
        try:
            response = self.session.get(
                f"{self.api_url}/datasets",
                params={'kind': f'eq.{kind}', 'tag': f'eq.{tag}', 'limit': '1'}
            )
            response.raise_for_status()
            
            result = response.json()
            if result:
                dataset_id = result[0]['id']
                print(f"📋 Using existing dataset '{tag}' (ID: {dataset_id}) in {self.backend}")
                return dataset_id
                
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Could not check for existing dataset: {e}")
        
        # Create new dataset
        return self.create_dataset(kind, tag, description, created_by)
    
    def import_pharmacies_csv(self, csv_path: str, tag: str, created_by: str = None,
                             description: str = None, batch_size: int = 100) -> bool:
        """Import pharmacies from CSV file via API"""
        
        csv_path = Path(csv_path)
        if not csv_path.exists():
            print(f"❌ CSV file not found: {csv_path}")
            return False
        
        # Create or get dataset
        dataset_id = self.get_or_create_dataset(
            kind='pharmacies',
            tag=tag,
            description=description,
            created_by=created_by
        )
        
        if not dataset_id:
            return False
        
        # Load and process CSV
        try:
            df = pd.read_csv(csv_path)
            print(f"📊 Loaded {len(df)} pharmacies from {csv_path}")
            
        except Exception as e:
            print(f"❌ Failed to read CSV: {e}")
            return False
        
        # Convert DataFrame to API format
        pharmacies = []
        for _, row in df.iterrows():
            # Handle state_licenses JSON conversion
            state_licenses_raw = row.get('state_licenses', '[]')
            if pd.isna(state_licenses_raw) or state_licenses_raw in ['', '[]', 'null']:
                state_licenses = []
            else:
                try:
                    if isinstance(state_licenses_raw, str):
                        state_licenses = json.loads(state_licenses_raw)
                    else:
                        state_licenses = list(state_licenses_raw) if state_licenses_raw else []
                except:
                    state_licenses = []
            
            # Collect additional info (everything not in core schema)
            core_fields = {'name', 'alias', 'address', 'suite', 'city', 'state', 'zip', 'state_licenses', 'id', 'created_at'}
            additional_info = {}
            for col in df.columns:
                if col not in core_fields and not pd.isna(row[col]) and row[col] != '':
                    additional_info[col] = row[col]
            
            pharmacy = {
                'dataset_id': dataset_id,
                'name': str(row['name']).strip(),
                'alias': str(row.get('alias', '')).strip() if not pd.isna(row.get('alias')) else None,
                'address': str(row.get('address', '')).strip() if not pd.isna(row.get('address')) else None,
                'suite': str(row.get('suite', '')).strip() if not pd.isna(row.get('suite')) else None,
                'city': str(row.get('city', '')).strip() if not pd.isna(row.get('city')) else None,
                'state': str(row.get('state', '')).strip()[:2] if not pd.isna(row.get('state')) else None,
                'zip': str(int(row.get('zip', 0))) if not pd.isna(row.get('zip')) and row.get('zip') != '' else None,
                'state_licenses': json.dumps(state_licenses),
                'additional_info': json.dumps(additional_info) if additional_info else None
            }
            
            # Remove None values for cleaner API calls
            pharmacy = {k: v for k, v in pharmacy.items() if v is not None and v != ''}
            pharmacies.append(pharmacy)
        
        # Import in batches
        total_imported = 0
        for i in range(0, len(pharmacies), batch_size):
            batch = pharmacies[i:i + batch_size]
            
            try:
                response = self.session.post(f"{self.api_url}/pharmacies", json=batch)
                response.raise_for_status()
                
                imported_count = len(response.json()) if response.json() else len(batch)
                total_imported += imported_count
                print(f"📥 Imported batch {i//batch_size + 1}: {imported_count} pharmacies")
                
            except requests.exceptions.RequestException as e:
                print(f"❌ Failed to import batch {i//batch_size + 1}: {e}")
                if hasattr(e, 'response') and e.response:
                    print(f"Error details: {e.response.text}")
                    print(f"First item in failed batch: {json.dumps(batch[0], indent=2)}")
                return False
        
        print(f"✅ Successfully imported {total_imported}/{len(pharmacies)} pharmacies to {self.backend}")
        return True
    
    def import_states_directory(self, states_dir: str, tag: str, created_by: str = None,
                               description: str = None, batch_size: int = 50) -> bool:
        """Import states search results and images from directory via API"""
        
        states_dir = Path(states_dir)
        if not states_dir.exists():
            print(f"❌ States directory not found: {states_dir}")
            return False
        
        # Create or get dataset for search results
        dataset_id = self.get_or_create_dataset(
            kind='states',
            tag=tag,
            description=description,
            created_by=created_by
        )
        
        if not dataset_id:
            return False
        
        # Process all JSON files in subdirectories
        search_results = []
        image_records = []
        
        # Find all JSON files
        json_files = list(states_dir.rglob("*_parse.json"))
        print(f"📊 Found {len(json_files)} JSON files to process")
        
        for json_file in json_files:
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                # Extract metadata
                metadata = data.get('metadata', {})
                search_result = data.get('search_result', {})
                
                pharmacy_name = metadata.get('pharmacy_name', 'Unknown')
                search_state = metadata.get('state', 'XX')
                search_timestamp = metadata.get('search_timestamp')
                
                # Convert timestamp if provided
                search_ts = None
                if search_timestamp:
                    try:
                        search_ts = datetime.fromisoformat(search_timestamp.replace('Z', '+00:00'))
                    except:
                        search_ts = None
                
                # Process each license found
                licenses = search_result.get('licenses', [])
                
                if not licenses:
                    # No results found - still create a record with result_status
                    result_status = search_result.get('result_status', 'not_found')
                    search_results.append({
                        'dataset_id': dataset_id,
                        'search_name': pharmacy_name,
                        'search_state': search_state,
                        'search_ts': search_ts.isoformat() if search_ts else None,
                        'license_number': None,
                        'license_status': None,
                        'license_name': None,
                        'license_type': None,
                        'address': None,
                        'city': None,
                        'state': None,
                        'zip': None,
                        'issue_date': None,
                        'expiration_date': None,
                        'result_status': result_status,
                        'meta': json.dumps(metadata),
                        'raw': json.dumps(data)
                    })
                else:
                    # Process each license
                    for license_info in licenses:
                        address_info = license_info.get('address', {})
                        
                        # Parse dates
                        issue_date = license_info.get('issue_date')
                        expiration_date = license_info.get('expiration_date')
                        
                        search_results.append({
                            'dataset_id': dataset_id,
                            'search_name': pharmacy_name,
                            'search_state': search_state,
                            'search_ts': search_ts.isoformat() if search_ts else None,
                            'license_number': license_info.get('license_number'),
                            'license_status': license_info.get('license_status'),
                            'license_name': license_info.get('pharmacy_name'),
                            'license_type': license_info.get('license_type'),
                            'address': address_info.get('street'),
                            'city': address_info.get('city'),
                            'state': address_info.get('state'),
                            'zip': address_info.get('zip_code'),
                            'issue_date': issue_date,
                            'expiration_date': expiration_date,
                            'result_status': search_result.get('result_status', 'found'),
                            'meta': json.dumps(metadata),
                            'raw': json.dumps(data)
                        })
                
                # Handle corresponding PNG file - remove "_parse" from filename
                png_filename = json_file.stem.replace('_parse', '') + '.png'
                png_file = json_file.parent / png_filename
                if png_file.exists():
                    # For now, just record the image path - actual file handling depends on storage strategy
                    image_records.append({
                        'dataset_id': dataset_id,
                        'state': search_state,
                        'search_name': pharmacy_name,
                        'organized_path': str(png_file.relative_to(states_dir)),
                        'storage_type': 'local',
                        'file_size': png_file.stat().st_size
                    })
                
            except Exception as e:
                print(f"⚠️  Failed to process {json_file}: {e}")
                continue
        
        # Import search results in batches
        if search_results:
            total_imported = 0
            for i in range(0, len(search_results), batch_size):
                batch = search_results[i:i + batch_size]
                
                # Clean up None values
                cleaned_batch = []
                for result in batch:
                    cleaned_result = {k: v for k, v in result.items() if v is not None and v != ''}
                    cleaned_batch.append(cleaned_result)
                
                try:
                    response = self.session.post(f"{self.api_url}/search_results", json=cleaned_batch)
                    response.raise_for_status()
                    
                    imported_count = len(response.json()) if response.json() else len(cleaned_batch)
                    total_imported += imported_count
                    print(f"📥 Imported batch {i//batch_size + 1}: {imported_count} search results")
                    
                except requests.exceptions.RequestException as e:
                    print(f"❌ Failed to import search results batch {i//batch_size + 1}: {e}")
                    if hasattr(e, 'response') and e.response:
                        print(f"Error details: {e.response.text}")
                    return False
            
            print(f"✅ Successfully imported {total_imported} search results to {self.backend}")
        
        # Import image records in batches
        if image_records:
            total_images = 0
            for i in range(0, len(image_records), batch_size):
                batch = image_records[i:i + batch_size]
                
                try:
                    response = self.session.post(f"{self.api_url}/images", json=batch)
                    response.raise_for_status()
                    
                    imported_count = len(response.json()) if response.json() else len(batch)
                    total_images += imported_count
                    print(f"📥 Imported image batch {i//batch_size + 1}: {imported_count} image records")
                    
                except requests.exceptions.RequestException as e:
                    print(f"❌ Failed to import image batch {i//batch_size + 1}: {e}")
                    if hasattr(e, 'response') and e.response:
                        print(f"Error details: {e.response.text}")
                    # Don't fail the whole import if images fail
                    print("⚠️  Continuing with search results import despite image errors")
            
            print(f"✅ Successfully imported {total_images} image records to {self.backend}")
        
        return True


def main():
    """Command line interface for API importer"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Import data via REST API')
    subparsers = parser.add_subparsers(dest='command', help='Import command')
    
    # Pharmacies import
    pharmacy_parser = subparsers.add_parser('pharmacies', help='Import pharmacies from CSV')
    pharmacy_parser.add_argument('csv_file', help='Path to pharmacy CSV file')
    pharmacy_parser.add_argument('tag', help='Dataset tag/version')
    pharmacy_parser.add_argument('--backend', choices=['postgresql', 'supabase'], 
                                default='postgresql', help='Backend to use')
    pharmacy_parser.add_argument('--created-by', default=None, help='Who is importing this data')
    pharmacy_parser.add_argument('--description', default=None, help='Dataset description')
    pharmacy_parser.add_argument('--batch-size', type=int, default=100, help='Import batch size')
    
    # States import
    states_parser = subparsers.add_parser('states', help='Import states from directory')
    states_parser.add_argument('states_dir', help='Path to states directory')
    states_parser.add_argument('tag', help='Dataset tag/version')
    states_parser.add_argument('--backend', choices=['postgresql', 'supabase'], 
                              default='postgresql', help='Backend to use')
    states_parser.add_argument('--created-by', default=None, help='Who is importing this data')
    states_parser.add_argument('--description', default=None, help='Dataset description')
    states_parser.add_argument('--batch-size', type=int, default=50, help='Import batch size')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        exit(1)
    
    importer = APIImporter(backend=args.backend)
    
    if args.command == 'pharmacies':
        success = importer.import_pharmacies_csv(
            csv_path=args.csv_file,
            tag=args.tag,
            created_by=args.created_by,
            description=args.description,
            batch_size=args.batch_size
        )
    elif args.command == 'states':
        success = importer.import_states_directory(
            states_dir=args.states_dir,
            tag=args.tag,
            created_by=args.created_by,
            description=args.description,
            batch_size=args.batch_size
        )
    else:
        print(f"Unknown command: {args.command}")
        exit(1)
    
    exit(0 if success else 1)


if __name__ == '__main__':
    main()