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
from utils.image_storage import create_image_storage

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
                             description: str = None) -> bool:
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
                'state_licenses': state_licenses,  # Send as array, not JSON string
                'additional_info': additional_info if additional_info else None
            }
            
            # Remove None values for cleaner API calls
            pharmacy = {k: v for k, v in pharmacy.items() if v is not None and v != ''}
            pharmacies.append(pharmacy)
        
        # Import pharmacies one by one for better error reporting
        imported_count = 0
        for i, pharmacy in enumerate(pharmacies):
            try:
                response = self.session.post(f"{self.api_url}/pharmacies", json=[pharmacy])
                response.raise_for_status()
                imported_count += 1
                print(f"📥 Imported pharmacy {i+1}/{len(pharmacies)}: {pharmacy['name']}")
                
            except requests.exceptions.RequestException as e:
                print(f"❌ Failed to import pharmacy {i+1} ({pharmacy.get('name', 'Unknown')}): {e}")
                if hasattr(e, 'response') and e.response:
                    print(f"Error details: {e.response.text}")
                    print(f"Failed pharmacy data: {json.dumps(pharmacy, indent=2)}")
                # Continue with other records instead of stopping
                
        print(f"✅ Successfully imported {imported_count}/{len(pharmacies)} pharmacies to {self.backend}")
        return imported_count > 0  # Success if at least one record imported
    
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
        
        # Create image storage handler for processing images during JSON parsing
        storage = create_image_storage(self.backend)
        
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
                
                # Process corresponding PNG file immediately to get image_hash
                image_hash = None
                png_filename = json_file.stem.replace('_parse', '') + '.png'
                png_file = json_file.parent / png_filename
                if png_file.exists():
                    try:
                        # Compute hash and store image if needed
                        content_hash = storage.compute_sha256(png_file)
                        
                        # Check if asset already exists
                        existing_asset = self._check_image_asset_exists(content_hash)
                        
                        if not existing_asset:
                            # Store image and create asset record
                            content_hash, storage_path, img_metadata = storage.store_image(png_file)
                            
                            # Create new asset record
                            asset_data = {
                                'content_hash': content_hash,
                                'storage_path': storage_path,
                                'storage_type': storage.backend_type,
                                'file_size': img_metadata['file_size'],
                                'content_type': img_metadata['content_type'],
                                'width': img_metadata.get('width'),
                                'height': img_metadata.get('height')
                            }
                            
                            success = self._create_image_asset(asset_data)
                            if success:
                                print(f"📥 Created new image asset: {content_hash[:8]}...")
                                image_hash = content_hash
                            else:
                                print(f"❌ Failed to create asset for {content_hash[:8]}...")
                        else:
                            # Update access tracking for existing asset
                            self._update_image_access(content_hash)
                            print(f"♻️  Image asset exists (deduplicated): {content_hash[:8]}...")
                            image_hash = content_hash
                        
                    except Exception as e:
                        print(f"⚠️  Failed to process image {png_file}: {e}")
                        image_hash = None
                
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
                        'raw': json.dumps(data),
                        'image_hash': image_hash  # Include image_hash from the start
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
                            'raw': json.dumps(data),
                            'image_hash': image_hash  # Include image_hash from the start
                        })
                
            except Exception as e:
                print(f"⚠️  Failed to process {json_file}: {e}")
                continue
        
        # Import search results in batches (images already processed and included)
        if search_results:
            total_imported = 0
            for i in range(0, len(search_results), batch_size):
                batch = search_results[i:i + batch_size]
                
                # Clean up None values (but keep image_hash if it's None)
                cleaned_batch = []
                for result in batch:
                    cleaned_result = {k: v for k, v in result.items() if v is not None and v != ''}
                    # Always include image_hash field, even if None
                    if 'image_hash' in result:
                        cleaned_result['image_hash'] = result['image_hash']
                    cleaned_batch.append(cleaned_result)
                
                try:
                    response = self.session.post(f"{self.api_url}/search_results", json=cleaned_batch)
                    response.raise_for_status()
                    
                    imported_count = len(response.json()) if response.json() else len(batch)
                    total_imported += imported_count
                    print(f"📥 Imported batch {i//batch_size + 1}: {imported_count} search results with images")
                    
                except requests.exceptions.RequestException as e:
                    print(f"❌ Failed to import search results batch {i//batch_size + 1}: {e}")
                    if hasattr(e, 'response') and e.response:
                        print(f"Error details: {e.response.text}")
                    return False
            
            print(f"✅ Successfully imported {total_imported} search results with images to {self.backend}")
        
        return True
    
    def import_states_csv(self, csv_path: str, tag: str, created_by: str = None,
                         description: str = None) -> bool:
        """Import states search results from CSV file via API"""
        
        csv_path = Path(csv_path)
        if not csv_path.exists():
            print(f"❌ CSV file not found: {csv_path}")
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
        
        try:
            # Read CSV file
            df = pd.read_csv(csv_path)
            print(f"📊 Found {len(df)} records in CSV")
            
            # Validate required columns
            required_cols = ['search_name', 'search_state']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                print(f"❌ Missing required columns: {missing_cols}")
                return False
            
            # Convert DataFrame to search results format
            search_results = []
            for _, row in df.iterrows():
                # Convert row to dict and clean up None/NaN values
                result = {
                    'dataset_id': dataset_id,
                    'search_name': row.get('search_name'),
                    'search_state': row.get('search_state'),
                    'search_ts': row.get('search_ts'),
                    'license_number': row.get('license_number'),
                    'license_status': row.get('license_status'),
                    'license_name': row.get('license_name'),
                    'license_type': row.get('license_type'),
                    'address': row.get('address'),
                    'city': row.get('city'),
                    'state': row.get('state'),
                    'zip': row.get('zip'),
                    'issue_date': row.get('issue_date'),
                    'expiration_date': row.get('expiration_date'),
                    'result_status': row.get('result_status', 'found'),
                    'meta': row.get('meta'),
                    'raw': row.get('raw'),
                    'image_hash': row.get('image_hash')
                }
                
                # Clean up None/NaN values
                cleaned_result = {}
                for k, v in result.items():
                    if pd.notna(v) and v != '' and v is not None:
                        cleaned_result[k] = v
                    elif k in ['dataset_id', 'search_name', 'search_state', 'result_status']:
                        # Required fields
                        cleaned_result[k] = v if v is not None else ''
                
                search_results.append(cleaned_result)
            
            # Import search results one by one for better error reporting
            imported_count = 0
            for i, result in enumerate(search_results):
                try:
                    response = self.session.post(f"{self.api_url}/search_results", json=[result])
                    response.raise_for_status()
                    imported_count += 1
                    print(f"📥 Imported search result {i+1}/{len(search_results)}: {result.get('search_name', 'Unknown')}")
                    
                except requests.exceptions.RequestException as e:
                    print(f"❌ Failed to import search result {i+1}: {e}")
                    if hasattr(e, 'response') and e.response:
                        print(f"Error details: {e.response.text}")
                    # Continue with other records
                    
            print(f"✅ Successfully imported {imported_count}/{len(search_results)} search results from CSV to {self.backend}")
            return imported_count > 0
            
        except Exception as e:
            print(f"❌ Failed to process CSV file: {e}")
            return False
    
    def import_validated_csv(self, csv_path: str, tag: str, created_by: str = None,
                            description: str = None) -> bool:
        """Import validated overrides from CSV file via API"""
        
        csv_path = Path(csv_path)
        if not csv_path.exists():
            print(f"❌ CSV file not found: {csv_path}")
            return False
        
        # Create or get dataset for validated overrides
        dataset_id = self.get_or_create_dataset(
            kind='validated',
            tag=tag,
            description=description,
            created_by=created_by
        )
        
        if not dataset_id:
            return False
        
        try:
            # Read CSV file
            df = pd.read_csv(csv_path)
            print(f"📊 Found {len(df)} records in CSV")
            
            # Validate required columns
            required_cols = ['pharmacy_name', 'state_code', 'override_type', 'reason', 'validated_by']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                print(f"❌ Missing required columns: {missing_cols}")
                return False
            
            # Convert DataFrame to validated overrides format
            validated_overrides = []
            for _, row in df.iterrows():
                # Convert row to dict and clean up None/NaN values
                override = {
                    'dataset_id': dataset_id,
                    'pharmacy_name': row.get('pharmacy_name'),
                    'state_code': row.get('state_code'),
                    'override_type': row.get('override_type'),
                    'reason': row.get('reason'),
                    'validated_by': row.get('validated_by'),
                    'validated_at': row.get('validated_at'),  # Optional
                    'notes': row.get('notes')  # Optional
                }
                
                # Clean up None/NaN values
                cleaned_override = {}
                for k, v in override.items():
                    if pd.notna(v) and v != '' and v is not None:
                        cleaned_override[k] = v
                    elif k in ['dataset_id', 'pharmacy_name', 'state_code', 'override_type', 'reason', 'validated_by']:
                        # Required fields
                        cleaned_override[k] = v if v is not None else ''
                
                validated_overrides.append(cleaned_override)
            
            # Import validated overrides one by one for better error reporting
            imported_count = 0
            for i, override in enumerate(validated_overrides):
                try:
                    response = self.session.post(f"{self.api_url}/validated_overrides", json=[override])
                    response.raise_for_status()
                    imported_count += 1
                    print(f"📥 Imported validation {i+1}/{len(validated_overrides)}: {override.get('pharmacy_name', 'Unknown')}")
                    
                except requests.exceptions.RequestException as e:
                    print(f"❌ Failed to import validation {i+1}: {e}")
                    if hasattr(e, 'response') and e.response:
                        print(f"Error details: {e.response.text}")
                    # Continue with other records
                    
            print(f"✅ Successfully imported {imported_count}/{len(validated_overrides)} validated overrides from CSV to {self.backend}")
            return imported_count > 0
            
        except Exception as e:
            print(f"❌ Failed to process CSV file: {e}")
            return False

    def _check_image_asset_exists(self, content_hash: str) -> bool:
        """Check if image asset already exists"""
        try:
            response = self.session.get(
                f"{self.api_url}/image_assets",
                params={'content_hash': f'eq.{content_hash}', 'select': 'content_hash'}
            )
            response.raise_for_status()
            return len(response.json()) > 0
        except Exception as e:
            print(f"⚠️  Error checking asset existence: {e}")
            return False

    def _create_image_asset(self, asset_data: Dict) -> bool:
        """Create new image asset record"""
        try:
            response = self.session.post(f"{self.api_url}/image_assets", json=asset_data)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"❌ Failed to create image asset: {e}")
            return False

    def _update_image_access(self, content_hash: str) -> bool:
        """Update access tracking for existing image"""
        try:
            # For now, just do a simple increment - the exact syntax may vary by API
            response = self.session.patch(
                f"{self.api_url}/image_assets",
                params={'content_hash': f'eq.{content_hash}'},
                json={'last_accessed': datetime.now().isoformat()}
            )
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"⚠️  Failed to update access tracking: {e}")
            return False


def main():
    """Command line interface for API importer"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Import data via REST API')
    subparsers = parser.add_subparsers(dest='command', help='Import command')
    
    # Pharmacies import
    pharmacy_parser = subparsers.add_parser('pharmacies', help='Import pharmacies from CSV')
    pharmacy_parser.add_argument('csv_file', help='Path to pharmacy CSV file')
    pharmacy_parser.add_argument('tag', help='Dataset tag/version')
    pharmacy_parser.add_argument('--backend', choices=['supabase'], 
                                default='supabase', help='Backend to use (Supabase only)')
    pharmacy_parser.add_argument('--created-by', default=None, help='Who is importing this data')
    pharmacy_parser.add_argument('--description', default=None, help='Dataset description')
    
    # States import
    states_parser = subparsers.add_parser('states', help='Import states from directory or CSV')
    states_parser.add_argument('states_path', help='Path to states directory or CSV file')
    states_parser.add_argument('tag', help='Dataset tag/version')
    states_parser.add_argument('--backend', choices=['supabase'], 
                              default='supabase', help='Backend to use (Supabase only)')
    states_parser.add_argument('--created-by', default=None, help='Who is importing this data')
    states_parser.add_argument('--description', default=None, help='Dataset description')
    
    # Validated import
    validated_parser = subparsers.add_parser('validated', help='Import validated overrides from CSV')
    validated_parser.add_argument('csv_file', help='Path to validated CSV file')
    validated_parser.add_argument('tag', help='Dataset tag/version')
    validated_parser.add_argument('--backend', choices=['supabase'], 
                                 default='supabase', help='Backend to use (Supabase only)')
    validated_parser.add_argument('--created-by', default=None, help='Who is importing this data')
    validated_parser.add_argument('--description', default=None, help='Dataset description')
    
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
            description=args.description
        )
    elif args.command == 'states':
        # Auto-detect if path is CSV file or directory
        states_path = Path(args.states_path)
        if states_path.is_file() and states_path.suffix.lower() == '.csv':
            # CSV file
            success = importer.import_states_csv(
                csv_path=args.states_path,
                tag=args.tag,
                created_by=args.created_by,
                description=args.description
            )
        elif states_path.is_dir():
            # Directory
            success = importer.import_states_directory(
                states_dir=args.states_path,
                tag=args.tag,
                created_by=args.created_by,
                description=args.description,
                batch_size=args.batch_size
            )
        else:
            print(f"❌ Invalid states path: {args.states_path} (must be CSV file or directory)")
            exit(1)
    elif args.command == 'validated':
        success = importer.import_validated_csv(
            csv_path=args.csv_file,
            tag=args.tag,
            created_by=args.created_by,
            description=args.description
        )
    else:
        print(f"Unknown command: {args.command}")
        exit(1)
    
    exit(0 if success else 1)


if __name__ == '__main__':
    main()