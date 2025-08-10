"""
Validated overrides importer for PharmChecker
Handles manual validation records with snapshot functionality
"""
import logging
import pandas as pd
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from datetime import datetime
from .base import BaseImporter

class ValidatedImporter(BaseImporter):
    """Importer for validated override records"""
    
    def import_csv(self, filepath: str, tag: str, created_by: str = None,
                   description: str = None) -> bool:
        """
        Import validated overrides from CSV file
        
        Expected CSV columns:
        - pharmacy_name (required): Exact pharmacy name from searches
        - state_code (required): 2-character state code (FL, PA, TX, etc.)
        - license_number: License number if override_type='present', empty if 'empty'
        - override_type (required): Either 'present' or 'empty'
        - reason (required): Human-readable reason for validation decision
        - validated_by (required): Username/identifier of validator
        
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
            self.logger.info(f"Reading validation CSV file: {filepath}")
            df = pd.read_csv(filepath)
            
            # Validate required columns
            required_columns = ['pharmacy_name', 'state_code', 'override_type', 'reason', 'validated_by']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                self.logger.error(f"CSV missing required columns: {missing_columns}")
                return False
            
            # Validate data
            if not self._validate_csv_data(df):
                return False
            
            # Create or update dataset
            dataset_id = self.create_dataset('validated', tag, description, created_by)
            
            # Import validation records with snapshots
            success_count = 0
            for idx, row in df.iterrows():
                try:
                    success = self.create_validation_record(
                        dataset_id=dataset_id,
                        pharmacy_name=row['pharmacy_name'],
                        state_code=row['state_code'],
                        license_number=row.get('license_number', ''),
                        override_type=row['override_type'],
                        reason=row['reason'],
                        validated_by=row['validated_by']
                    )
                    if success:
                        success_count += 1
                    else:
                        self.logger.warning(f"Failed to import validation record at row {idx + 1}")
                        
                except Exception as e:
                    self.logger.error(f"Error importing row {idx + 1}: {e}")
            
            self.conn.commit()
            self.logger.info(f"Successfully imported {success_count}/{len(df)} validation records")
            return success_count > 0
            
        except Exception as e:
            self.logger.error(f"Error importing validation CSV: {e}")
            self.conn.rollback()
            return False
    
    def create_validation_record(self, dataset_id: int, pharmacy_name: str, state_code: str,
                               license_number: str, override_type: str, reason: str,
                               validated_by: str) -> bool:
        """
        Create a single validation record with search result snapshot
        
        This is used both by CSV import and GUI validation creation.
        Creates a snapshot of the current search result state for the given pharmacy/state/license.
        
        Args:
            dataset_id: Target dataset ID
            pharmacy_name: Exact pharmacy name from searches
            state_code: 2-character state code
            license_number: License number (empty string for 'empty' overrides)
            override_type: 'present' or 'empty'
            reason: Validation reason
            validated_by: Validator identifier
            
        Returns:
            True if successful, False otherwise
        """
        # Validate license number requirements per spec
        if override_type == 'present' and (not license_number or license_number.strip() == ''):
            raise ValueError("Cannot validate as present without license number. Use 'Validate as Empty' instead.")
        
        try:
            with self.conn.cursor() as cur:
                # Get search result snapshot for this validation
                snapshot_data = self._get_search_result_snapshot(
                    pharmacy_name, state_code, license_number, override_type
                )
                
                # Insert validation record
                insert_sql = """
                INSERT INTO validated_overrides (
                    dataset_id, pharmacy_name, state_code, license_number,
                    license_status, license_name, address, city, state, zip,
                    issue_date, expiration_date, result_status,
                    override_type, reason, validated_by, validated_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s
                )
                ON CONFLICT (dataset_id, pharmacy_name, state_code, license_number) 
                DO UPDATE SET
                    license_status = EXCLUDED.license_status,
                    license_name = EXCLUDED.license_name,
                    address = EXCLUDED.address,
                    city = EXCLUDED.city,
                    state = EXCLUDED.state,
                    zip = EXCLUDED.zip,
                    issue_date = EXCLUDED.issue_date,
                    expiration_date = EXCLUDED.expiration_date,
                    result_status = EXCLUDED.result_status,
                    override_type = EXCLUDED.override_type,
                    reason = EXCLUDED.reason,
                    validated_by = EXCLUDED.validated_by,
                    validated_at = EXCLUDED.validated_at
                """
                
                cur.execute(insert_sql, [
                    dataset_id, pharmacy_name, state_code, license_number or None,
                    snapshot_data.get('license_status'),
                    snapshot_data.get('license_name'),
                    snapshot_data.get('address'),
                    snapshot_data.get('city'),
                    snapshot_data.get('state'),
                    snapshot_data.get('zip'),
                    snapshot_data.get('issue_date'),
                    snapshot_data.get('expiration_date'),
                    snapshot_data.get('result_status'),
                    override_type, reason, validated_by, datetime.now()
                ])
                
                # Commit the transaction
                self.conn.commit()
                
                self.logger.info(f"Created validation: {pharmacy_name} - {state_code} - {license_number or 'EMPTY'} as {override_type.upper()}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error creating validation record: {e}")
            self.conn.rollback()
            return False
    
    def remove_validation_record(self, dataset_id: int, pharmacy_name: str, 
                               state_code: str, license_number: str) -> bool:
        """
        Remove a validation record (for unvalidation)
        
        Args:
            dataset_id: Dataset ID
            pharmacy_name: Pharmacy name
            state_code: State code
            license_number: License number (empty string for empty validations)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get dataset tag for debug logging
            dataset_tag = "unknown"
            try:
                with self.conn.cursor() as cur:
                    cur.execute("SELECT tag FROM datasets WHERE id = %s", [dataset_id])
                    result = cur.fetchone()
                    if result:
                        dataset_tag = result[0]
            except Exception:
                pass  # Continue with unknown tag
            
            with self.conn.cursor() as cur:
                # Handle empty validation (NULL license_number) vs present validation
                if not license_number or license_number.strip() == '':
                    # Empty validation - use IS NULL
                    delete_sql = """
                    DELETE FROM validated_overrides 
                    WHERE dataset_id = %s AND pharmacy_name = %s AND state_code = %s 
                    AND license_number IS NULL
                    """
                    params = [dataset_id, pharmacy_name, state_code]
                    debug_query = f"DELETE FROM validated_overrides WHERE dataset_id = {dataset_id} AND pharmacy_name = '{pharmacy_name}' AND state_code = '{state_code}' AND license_number IS NULL"
                    self.logger.info(f"Attempting to remove empty validation: {pharmacy_name} - {state_code}")
                else:
                    # Present validation - use exact match
                    delete_sql = """
                    DELETE FROM validated_overrides 
                    WHERE dataset_id = %s AND pharmacy_name = %s AND state_code = %s 
                    AND license_number = %s
                    """
                    params = [dataset_id, pharmacy_name, state_code, license_number]
                    debug_query = f"DELETE FROM validated_overrides WHERE dataset_id = {dataset_id} AND pharmacy_name = '{pharmacy_name}' AND state_code = '{state_code}' AND license_number = '{license_number}'"
                    self.logger.info(f"Attempting to remove present validation: {pharmacy_name} - {state_code} - {license_number}")
                
                # Log debug info per spec
                self.logger.info(f"Dataset: {dataset_tag} (ID: {dataset_id})")
                self.logger.info(f"Query: {debug_query}")
                
                cur.execute(delete_sql, params)
                rowcount = cur.rowcount
                
                self.logger.info(f"Found {rowcount} records to delete")
                
                if rowcount > 0:
                    self.conn.commit()
                    self.logger.info(f"Result: success")
                    return True
                else:
                    self.logger.info(f"Result: failure - no records found")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error removing validation record: {e}")
            self.conn.rollback()
            return False
    
    def _get_search_result_snapshot(self, pharmacy_name: str, state_code: str, 
                                  license_number: str, override_type: str) -> Dict[str, Any]:
        """
        Get search result snapshot for validation record
        
        For 'present' validations, looks up the actual search result.
        For 'empty' validations, returns empty snapshot data.
        
        Args:
            pharmacy_name: Pharmacy name
            state_code: State code
            license_number: License number
            override_type: 'present' or 'empty'
            
        Returns:
            Dictionary with search result snapshot data
        """
        if override_type == 'empty':
            # For empty validations, we don't need search result data
            return {
                'license_status': None,
                'license_name': None,
                'address': None,
                'city': None,
                'state': None,
                'zip': None,
                'issue_date': None,
                'expiration_date': None,
                'result_status': 'no_results_found'
            }
        
        try:
            with self.conn.cursor() as cur:
                # Look for most recent search result for this pharmacy/state/license
                snapshot_sql = """
                SELECT license_status, license_name, address, city, state, zip,
                       issue_date, expiration_date, result_status
                FROM search_results sr
                JOIN datasets d ON sr.dataset_id = d.id
                WHERE sr.search_name = %s 
                  AND sr.search_state = %s 
                  AND sr.license_number = %s
                  AND d.kind = 'states'
                ORDER BY sr.created_at DESC
                LIMIT 1
                """
                
                cur.execute(snapshot_sql, [pharmacy_name, state_code, license_number])
                result = cur.fetchone()
                
                if result:
                    columns = ['license_status', 'license_name', 'address', 'city', 'state', 'zip',
                             'issue_date', 'expiration_date', 'result_status']
                    return dict(zip(columns, result))
                else:
                    # No search result found - this might be a manual validation
                    self.logger.warning(f"No search result found for snapshot: {pharmacy_name} - {state_code} - {license_number}")
                    return {
                        'license_status': None,
                        'license_name': None,
                        'address': None,
                        'city': None,
                        'state': None,
                        'zip': None,
                        'issue_date': None,
                        'expiration_date': None,
                        'result_status': 'manual_validation'
                    }
                    
        except Exception as e:
            self.logger.error(f"Error getting search result snapshot: {e}")
            return {}
    
    def _validate_csv_data(self, df: pd.DataFrame) -> bool:
        """
        Validate CSV data before import
        
        Args:
            df: DataFrame to validate
            
        Returns:
            True if valid, False otherwise
        """
        errors = []
        
        # Check override_type values
        invalid_types = df[~df['override_type'].isin(['present', 'empty'])]
        if not invalid_types.empty:
            errors.append(f"Invalid override_type values found. Must be 'present' or 'empty'. Rows: {invalid_types.index.tolist()}")
        
        # Check state codes (basic validation)
        invalid_states = df[~df['state_code'].str.match(r'^[A-Z]{2}$', na=False)]
        if not invalid_states.empty:
            errors.append(f"Invalid state_code format. Must be 2 uppercase letters. Rows: {invalid_states.index.tolist()}")
        
        # Check for empty required fields
        for col in ['pharmacy_name', 'reason', 'validated_by']:
            empty_values = df[df[col].isna() | (df[col].str.strip() == '')]
            if not empty_values.empty:
                errors.append(f"Empty {col} values found. Rows: {empty_values.index.tolist()}")
        
        # Check license_number consistency with override_type
        present_without_license = df[(df['override_type'] == 'present') & 
                                   (df['license_number'].isna() | (df['license_number'].str.strip() == ''))]
        if not present_without_license.empty:
            errors.append(f"'present' validations missing license_number. Rows: {present_without_license.index.tolist()}")
        
        if errors:
            for error in errors:
                self.logger.error(f"Validation error: {error}")
            return False
        
        return True
    
    def get_validation_stats(self, dataset_id: int) -> Dict[str, Any]:
        """
        Get statistics for a validation dataset
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            Dictionary with validation statistics
        """
        try:
            with self.conn.cursor() as cur:
                stats_sql = """
                SELECT 
                    COUNT(*) as total_validations,
                    COUNT(*) FILTER (WHERE override_type = 'present') as present_count,
                    COUNT(*) FILTER (WHERE override_type = 'empty') as empty_count,
                    COUNT(DISTINCT pharmacy_name) as unique_pharmacies,
                    COUNT(DISTINCT state_code) as unique_states
                FROM validated_overrides
                WHERE dataset_id = %s
                """
                
                cur.execute(stats_sql, [dataset_id])
                result = cur.fetchone()
                
                if result:
                    return {
                        'total_validations': result[0] or 0,
                        'present_count': result[1] or 0,
                        'empty_count': result[2] or 0,
                        'unique_pharmacies': result[3] or 0,
                        'unique_states': result[4] or 0
                    }
                else:
                    return {
                        'total_validations': 0,
                        'present_count': 0,
                        'empty_count': 0,
                        'unique_pharmacies': 0,
                        'unique_states': 0
                    }
                    
        except Exception as e:
            self.logger.error(f"Error getting validation stats: {e}")
            return {}