#!/usr/bin/env python3
"""
Unit tests for Dataset Manager export/import functionality
"""

import sys
import os
import pandas as pd
import tempfile
import json
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'api_poc', 'gui'))

from client import create_client
# Always use Supabase


class ExportImportTester:
    def __init__(self):
        self.client = create_client()
        self.test_results = []
        
    def log_result(self, test_name, success, message="", details=None):
        """Log a test result"""
        result = {
            'test': test_name,
            'success': success,
            'message': message,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
        if message:
            print(f"   {message}")
        if details and not success:
            print(f"   Details: {details}")
    
    def test_export_pharmacy(self, tag):
        """Test exporting a pharmacy dataset"""
        try:
            print(f"\n=== Testing Export: Pharmacies '{tag}' ===")
            
            # Get dataset ID
            datasets = self.client.get_datasets()
            dataset_id = None
            for d in datasets:
                if d.get('kind') == 'pharmacies' and d.get('tag') == tag:
                    dataset_id = d.get('id')
                    break
            
            if not dataset_id:
                self.log_result(f"export_pharmacy_{tag}", False, f"Dataset '{tag}' not found")
                return None
            
            # Get pharmacy data
            data = self.client.get_pharmacies(dataset_id=dataset_id, limit=9999)
            
            if not data:
                self.log_result(f"export_pharmacy_{tag}", False, "No data returned from API")
                return None
            
            # Convert to DataFrame and CSV (clean format for import)
            df = pd.DataFrame(data)
            
            # Export only essential fields (exclude database internals)
            essential_cols = ['name', 'alias', 'address', 'suite', 'city', 'state', 'zip', 'state_licenses']
            export_cols = [col for col in essential_cols if col in df.columns]
            
            export_df = df[export_cols].copy()
            
            # Clean up complex fields that may cause import issues
            if 'state_licenses' in export_df.columns:
                # Ensure state_licenses is properly formatted (convert lists to JSON strings)
                def clean_state_licenses(x):
                    try:
                        if x is None or pd.isna(x):
                            return '[]'
                        if isinstance(x, (list, tuple)):
                            return str(x)  # Convert list to string representation
                        if x == '' or str(x).lower() == 'nan':
                            return '[]'
                        return str(x)
                    except Exception as e:
                        print(f"Error cleaning state_licenses value {x}: {e}")
                        return '[]'
                export_df['state_licenses'] = export_df['state_licenses'].apply(clean_state_licenses)
                
            # Skip additional_info for now to avoid complex JSON issues
            csv_data = export_df.to_csv(index=False)
            
            self.log_result(f"export_pharmacy_{tag}", True, f"Exported {len(export_df)} records ({len(export_cols)} fields), {len(csv_data)} bytes")
            
            # Return both DataFrame and CSV for testing
            return {'dataframe': df, 'csv': csv_data, 'original_count': len(df)}
            
        except Exception as e:
            self.log_result(f"export_pharmacy_{tag}", False, f"Exception: {e}")
            return None
    
    def test_import_pharmacy(self, csv_data, new_tag):
        """Test importing pharmacy data from CSV"""
        try:
            print(f"\n=== Testing Import: Pharmacies '{new_tag}' ===")
            
            # Write CSV to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp:
                tmp.write(csv_data)
                tmp_path = tmp.name
            
            print(f"Temp file: {tmp_path}")
            
            # Get backend
            backend = self.client.get_active_backend().lower()
            print(f"Backend: {backend}")
            
            # Build and run command
            import subprocess
            cmd = [
                'python', '-m', 'imports.api_importer', 
                'pharmacies', tmp_path, new_tag, '--backend', backend, '--batch-size', '1'
            ]
            
            print(f"Command: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
            
            print(f"Return code: {result.returncode}")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            
            # Clean up temp file
            os.unlink(tmp_path)
            
            if result.returncode != 0:
                self.log_result(f"import_pharmacy_{new_tag}", False, 
                              f"Import failed with code {result.returncode}", 
                              {'stdout': result.stdout, 'stderr': result.stderr})
                return False
            
            # Verify import by checking if dataset exists
            datasets = self.client.get_datasets()
            imported_dataset = None
            for d in datasets:
                if d.get('kind') == 'pharmacies' and d.get('tag') == new_tag:
                    imported_dataset = d
                    break
            
            if not imported_dataset:
                self.log_result(f"import_pharmacy_{new_tag}", False, "Dataset not found after import")
                return False
            
            # Get imported data count
            imported_data = self.client.get_pharmacies(dataset_id=imported_dataset['id'], limit=9999)
            imported_count = len(imported_data) if imported_data else 0
            
            self.log_result(f"import_pharmacy_{new_tag}", True, f"Imported {imported_count} records")
            
            return {
                'dataset_id': imported_dataset['id'],
                'count': imported_count,
                'data': imported_data
            }
            
        except Exception as e:
            self.log_result(f"import_pharmacy_{new_tag}", False, f"Exception: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return False
    
    def test_round_trip_pharmacy(self, original_tag):
        """Test complete export-import round trip for pharmacy data"""
        try:
            print(f"\n=== Testing Round Trip: Pharmacies '{original_tag}' ===")
            
            # Step 1: Export
            export_result = self.test_export_pharmacy(original_tag)
            if not export_result:
                return False
            
            # Step 2: Import with new tag
            import_tag = f"{original_tag}_imported_{int(datetime.now().timestamp())}"
            import_result = self.test_import_pharmacy(export_result['csv'], import_tag)
            if not import_result:
                return False
            
            # Step 3: Compare data
            original_count = export_result['original_count']
            imported_count = import_result['count']
            
            if original_count != imported_count:
                self.log_result(f"roundtrip_pharmacy_{original_tag}", False, 
                              f"Record count mismatch: {original_count} vs {imported_count}")
                return False
            
            # Step 4: Compare actual data
            original_df = export_result['dataframe']
            imported_df = pd.DataFrame(import_result['data'])
            
            # Compare key columns (ignore IDs and timestamps)
            compare_cols = ['name', 'address', 'city', 'state', 'zip']
            available_cols = [col for col in compare_cols if col in original_df.columns and col in imported_df.columns]
            
            original_subset = original_df[available_cols].sort_values(available_cols).reset_index(drop=True)
            imported_subset = imported_df[available_cols].sort_values(available_cols).reset_index(drop=True)
            
            # Check if data matches
            try:
                pd.testing.assert_frame_equal(original_subset, imported_subset, check_dtype=False)
                data_matches = True
            except AssertionError as e:
                data_matches = False
                print(f"Data comparison failed: {e}")
            
            self.log_result(f"roundtrip_pharmacy_{original_tag}", data_matches, 
                          f"Round trip {'successful' if data_matches else 'failed'}: {original_count} records")
            
            return data_matches
            
        except Exception as e:
            self.log_result(f"roundtrip_pharmacy_{original_tag}", False, f"Exception: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return False
    
    def test_export_states(self, tag):
        """Test exporting a states dataset"""
        try:
            print(f"\n=== Testing Export: States '{tag}' ===")
            
            # Get dataset ID
            datasets = self.client.get_datasets()
            dataset_id = None
            for d in datasets:
                if d.get('kind') == 'states' and d.get('tag') == tag:
                    dataset_id = d.get('id')
                    break
            
            if not dataset_id:
                self.log_result(f"export_states_{tag}", False, f"Dataset '{tag}' not found")
                return None
            
            # Get states data
            data = self.client.get_search_results(dataset_id=dataset_id, limit=9999)
            
            if not data:
                self.log_result(f"export_states_{tag}", False, "No data returned from API")
                return None
            
            # Convert to DataFrame and CSV
            df = pd.DataFrame(data)
            csv_data = df.to_csv(index=False)
            
            self.log_result(f"export_states_{tag}", True, f"Exported {len(df)} records, {len(csv_data)} bytes")
            
            return {'dataframe': df, 'csv': csv_data, 'original_count': len(df)}
            
        except Exception as e:
            self.log_result(f"export_states_{tag}", False, f"Exception: {e}")
            return None
    
    def run_comprehensive_tests(self):
        """Run all tests"""
        print("🧪 Starting Comprehensive Export/Import Tests")
        print("=" * 60)
        
        # Get available datasets
        try:
            datasets = self.client.get_datasets()
            pharmacy_datasets = [d['tag'] for d in datasets if d.get('kind') == 'pharmacies']
            states_datasets = [d['tag'] for d in datasets if d.get('kind') == 'states']
            
            print(f"Available datasets:")
            print(f"  Pharmacies: {pharmacy_datasets}")
            print(f"  States: {states_datasets}")
            
            # Test pharmacy round trips
            for tag in pharmacy_datasets[:2]:  # Test first 2 to avoid too much data
                self.test_round_trip_pharmacy(tag)
            
            # Test states export (basic test)
            for tag in states_datasets[:1]:  # Test first 1
                self.test_export_states(tag)
            
        except Exception as e:
            self.log_result("setup", False, f"Failed to get datasets: {e}")
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r['success']])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {passed_tests/total_tests*100:.1f}%" if total_tests > 0 else "No tests run")
        
        if failed_tests > 0:
            print("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  - {result['test']}: {result['message']}")
        
        return failed_tests == 0


def main():
    """Main test runner"""
    print("🔬 PharmChecker Export/Import Unit Tests")
    print("=" * 60)
    
    try:
        tester = ExportImportTester()
        success = tester.run_comprehensive_tests()
        
        if success:
            print("\n🎉 ALL TESTS PASSED!")
            return 0
        else:
            print("\n💥 SOME TESTS FAILED!")
            return 1
            
    except Exception as e:
        print(f"\n💥 TEST SUITE FAILED: {e}")
        import traceback
        print(traceback.format_exc())
        return 1


if __name__ == "__main__":
    exit(main())