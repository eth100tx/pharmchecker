"""
Pharmacy importer for PharmChecker
Imports pharmacy master records from CSV files
"""
import json
import pandas as pd
from typing import Optional, Dict, Any, List
from pathlib import Path
from .base import BaseImporter

class PharmacyImporter(BaseImporter):
    """Importer for pharmacy master records"""
    
    def __init__(self, backend: str = None, db_adapter=None, conn_params=None):
        """
        Initialize pharmacy importer
        
        Args:
            backend: Backend type ('postgresql' or 'supabase')
            db_adapter: Database adapter instance
            conn_params: Database connection parameters
        """
        super().__init__(db_adapter=db_adapter, backend=backend, conn_params=conn_params)
    
    def import_csv(self, filepath: str, tag: str, created_by: str = None,
                   description: str = None) -> bool:
        """
        Import pharmacies from CSV file in new clean format
        
        Expected CSV columns (from pharmacies_new.csv format):
        - id, created_at: Original system identifiers
        - name (required): Exact pharmacy name for searching
        - alias: Alternative name (empty string if none)
        - address: Street address only
        - suite: Suite/unit number (empty if none)
        - city, state, zip: Location components
        - state_licenses (required): JSON array ["TX","FL"] format
        - Additional columns: url, notes, phone, logo_url, etc. (stored in additional_info)
        
        Args:
            filepath: Path to CSV file
            tag: Dataset tag/version
            created_by: Who is importing this data
            description: Optional description
            
        Returns:
            True if successful, False otherwise
        """
        filepath = Path(filepath)
        if not filepath.exists():
            self.logger.error(f"File not found: {filepath}")
            return False
        
        try:
            # Read CSV
            self.logger.info(f"Reading CSV file: {filepath}")
            df = pd.read_csv(filepath)
            
            # Validate required columns
            if 'name' not in df.columns:
                self.logger.error("CSV missing required 'name' column")
                return False
            
            if 'state_licenses' not in df.columns:
                self.logger.error("CSV missing required 'state_licenses' column")
                return False
            
            # Create dataset
            if not description:
                description = f"Pharmacy import from {filepath.name}"
            
            dataset_id = self.create_dataset('pharmacies', tag, description, created_by)
            
            # Process data
            data = []
            errors = []
            
            for idx, row in df.iterrows():
                try:
                    # Parse state_licenses - can be JSON string or comma-separated
                    state_licenses_raw = row.get('state_licenses', '[]')
                    if pd.isna(state_licenses_raw):
                        state_licenses = []
                    elif isinstance(state_licenses_raw, str):
                        # Try JSON first
                        try:
                            state_licenses = json.loads(state_licenses_raw)
                        except json.JSONDecodeError:
                            # Try comma-separated
                            state_licenses = [s.strip().upper() for s in state_licenses_raw.split(',') if s.strip()]
                    elif isinstance(state_licenses_raw, list):
                        state_licenses = state_licenses_raw
                    else:
                        state_licenses = [str(state_licenses_raw)]
                    
                    # Validate state licenses are 2-char codes
                    valid_licenses = []
                    for license_code in state_licenses:
                        if isinstance(license_code, str) and len(license_code) == 2:
                            valid_licenses.append(license_code.upper())
                        else:
                            self.logger.warning(f"Row {idx}: Invalid state license code '{license_code}'")
                    
                    # Allow pharmacies with no state licenses (they just won't match anything)
                    if not valid_licenses:
                        self.logger.info(f"Row {idx}: Pharmacy '{row['name']}' has no valid state licenses (will be imported but won't match searches)")
                    
                    # Collect additional fields not in core schema
                    known_cols = {'name', 'alias', 'address', 'suite', 'city', 'state', 'zip', 'state_licenses'}
                    additional_info = {}
                    
                    for col, val in row.items():
                        if col not in known_cols and pd.notna(val):
                            # Convert to JSON-serializable format
                            if isinstance(val, (int, float, bool)):
                                additional_info[col] = val
                            else:
                                additional_info[col] = str(val)
                    
                    # Build row data
                    row_data = (
                        dataset_id,
                        str(row['name']).strip(),  # Exact string used for searching
                        str(row.get('alias', '')).strip() if not pd.isna(row.get('alias')) else None,
                        str(row.get('address', '')).strip() or None,
                        str(row.get('suite', '')).strip() or None,
                        str(row.get('city', '')).strip() or None,
                        str(row.get('state', '')).strip()[:2].upper() or None,
                        str(row.get('zip', '')).strip() or None,
                        json.dumps(valid_licenses),
                        json.dumps(additional_info) if additional_info else None
                    )
                    
                    data.append(row_data)
                    
                except Exception as e:
                    errors.append(f"Row {idx}: {str(e)}")
                    continue
            
            if not data:
                self.logger.error("No valid pharmacy records found")
                self.cleanup_failed_dataset(dataset_id)
                return False
            
            # Report errors but continue
            if errors:
                self.logger.warning(f"{len(errors)} rows had errors:")
                for error in errors[:10]:  # Show first 10 errors
                    self.logger.warning(f"  {error}")
                if len(errors) > 10:
                    self.logger.warning(f"  ... and {len(errors) - 10} more")
            
            # Batch insert
            columns = [
                'dataset_id', 'name', 'alias', 'address', 'suite', 
                'city', 'state', 'zip', 'state_licenses', 'additional_info'
            ]
            
            inserted_count = self.batch_insert('pharmacies', columns, data)
            
            if inserted_count == 0:
                self.logger.error("No pharmacy records were successfully inserted")
                self.cleanup_failed_dataset(dataset_id)
                return False
            
            self.logger.info(f"Successfully imported {inserted_count} pharmacies with tag '{tag}'")
            
            # Print dataset statistics
            stats = self.get_dataset_stats(dataset_id)
            self.logger.info(f"Dataset statistics: {stats}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Import failed: {str(e)}")
            return False
    
    def validate_csv_format(self, filepath: str) -> Dict[str, Any]:
        """
        Validate CSV format without importing
        
        Args:
            filepath: Path to CSV file
            
        Returns:
            Dictionary with validation results
        """
        results = {
            'valid': False,
            'errors': [],
            'warnings': [],
            'stats': {}
        }
        
        try:
            filepath = Path(filepath)
            if not filepath.exists():
                results['errors'].append(f"File not found: {filepath}")
                return results
            
            df = pd.read_csv(filepath)
            
            # Check required columns
            required_cols = ['name', 'state_licenses']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                results['errors'].append(f"Missing required columns: {missing_cols}")
                return results
            
            # Check optional columns
            optional_cols = ['alias', 'address', 'suite', 'city', 'state', 'zip']
            present_optional = [col for col in optional_cols if col in df.columns]
            results['stats']['optional_columns_present'] = present_optional
            
            # Analyze data quality
            results['stats']['total_rows'] = len(df)
            results['stats']['rows_with_name'] = df['name'].notna().sum()
            results['stats']['rows_with_state_licenses'] = df['state_licenses'].notna().sum()
            
            # Check for duplicate names
            duplicates = df['name'].duplicated().sum()
            if duplicates > 0:
                results['warnings'].append(f"{duplicates} duplicate pharmacy names found")
            
            # Validate state licenses format
            invalid_licenses = 0
            for idx, licenses_raw in df['state_licenses'].items():
                if pd.isna(licenses_raw):
                    invalid_licenses += 1
                    continue
                
                try:
                    if isinstance(licenses_raw, str):
                        # Try JSON
                        try:
                            licenses = json.loads(licenses_raw)
                        except json.JSONDecodeError:
                            # Try comma-separated
                            licenses = [s.strip() for s in licenses_raw.split(',')]
                        
                        # Validate format
                        valid_count = sum(1 for lic in licenses if isinstance(lic, str) and len(lic) == 2)
                        if valid_count == 0:
                            invalid_licenses += 1
                except:
                    invalid_licenses += 1
            
            if invalid_licenses > 0:
                results['warnings'].append(f"{invalid_licenses} rows have invalid state_licenses format")
            
            results['stats']['invalid_license_rows'] = invalid_licenses
            results['valid'] = len(results['errors']) == 0
            
        except Exception as e:
            results['errors'].append(f"Validation error: {str(e)}")
        
        return results
    
    def export_sample_csv(self, output_path: str) -> bool:
        """
        Export a sample CSV format for reference
        
        Args:
            output_path: Where to save the sample CSV
            
        Returns:
            True if successful
        """
        try:
            sample_data = {
                'name': [
                    'Empower Pharmacy',
                    'MedPoint Compounding',
                    'Austin Wellness Pharmacy'
                ],
                'alias': [
                    'Empower',
                    'MedPoint',
                    ''
                ],
                'address': [
                    '123 Main Street',
                    '456 Oak Avenue',
                    '789 Elm Drive'
                ],
                'suite': [
                    'Suite 100',
                    '',
                    'Unit 5'
                ],
                'city': [
                    'Houston',
                    'Dallas', 
                    'Austin'
                ],
                'state': [
                    'TX',
                    'TX',
                    'TX'
                ],
                'zip': [
                    '77001',
                    '75201',
                    '73301'
                ],
                'state_licenses': [
                    '["TX", "FL", "CA"]',
                    '["TX", "OK"]',
                    '["TX"]'
                ],
                'npi_number': [
                    '1234567890',
                    '0987654321',
                    '5555555555'
                ]
            }
            
            df = pd.DataFrame(sample_data)
            df.to_csv(output_path, index=False)
            
            self.logger.info(f"Sample CSV exported to: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to export sample CSV: {e}")
            return False