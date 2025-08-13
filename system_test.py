#!/usr/bin/env python3
"""
PharmChecker End-to-End System Test

This script performs a complete system test following the normal workflow:
1. Clean existing test data
2. Import pharmacy data 
3. Import state search data
4. Query results (initially no scores)
5. Run lazy scoring engine
6. Query results with scores
7. Generate comprehensive report

This tests the complete lazy scoring workflow as it would be used in production.
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Add imports to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.append(os.path.join('api_poc', 'gui'))

from config import use_cloud_database
from client import create_client
from imports.pharmacies import PharmacyImporter
from imports.states import StateImporter
from imports.scoring import ScoringEngine

PHARMACIES_TAG = "system_test_pharmacies"
STATES_TAG = "system_test_states"

class SystemTest:
    """Complete PharmChecker system test"""
    
    def __init__(self):
        self.client = create_client(prefer_supabase=use_cloud_database())
        self.test_results = {
            'start_time': datetime.now(),
            'steps': [],
            'errors': [],
            'success': True
        }
    
    def aggregate_results_matrix(self, comprehensive_results: List[Dict]) -> List[Dict]:
        """
        Aggregate comprehensive results into matrix format for compatibility.
        Groups by (pharmacy_name, search_state) and creates summary records.
        """
        # Group by (pharmacy_name, search_state)
        grouped = {}
        for row in comprehensive_results:
            key = (row['pharmacy_name'], row['search_state'])
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(row)
        
        # Create matrix records
        matrix_results = []
        for (pharmacy_name, search_state), group in grouped.items():
            # Take the first row for pharmacy info
            first_row = group[0]
            
            # Find best match score from all results
            scores = [r['score_overall'] for r in group if r['score_overall'] is not None]
            best_score = max(scores) if scores else None
            
            # Count results
            total_results = len([r for r in group if r['result_id'] is not None])
            
            # Determine status bucket based on best score and validations
            status_bucket = 'no data'
            if any(r['override_type'] for r in group):
                status_bucket = 'validated'
            elif best_score is not None:
                if best_score >= 85:
                    status_bucket = 'match'
                elif best_score >= 60:
                    status_bucket = 'weak match'
                else:
                    status_bucket = 'no match'
            elif total_results > 0:
                status_bucket = 'no match'
            
            # Find the result with the best score for detailed info
            best_result = None
            if scores:
                best_result = max([r for r in group if r['score_overall'] is not None], key=lambda x: x['score_overall'])
            elif group:
                best_result = group[0]  # Take first result for license info
                
            matrix_results.append({
                'pharmacy_name': pharmacy_name,
                'search_state': search_state,
                'score_overall': best_score,
                'score_street': best_result['score_street'] if best_result else None,
                'score_city_state_zip': best_result['score_city_state_zip'] if best_result else None,
                'status_bucket': status_bucket,
                'result_count': total_results,
                'license_number': best_result['license_number'] if best_result else None,
                'license_status': best_result['license_status'] if best_result else None,
                'license_name': best_result['license_name'] if best_result else None,
                'warnings': [],  # Placeholder for compatibility
                'pharmacy_dataset_id': first_row['pharmacy_dataset_id'],
                'states_dataset_id': first_row['states_dataset_id']
            })
        
        return matrix_results
    
    def log_step(self, step: str, success: bool = True, details: str = ""):
        """Log a test step"""
        step_info = {
            'step': step,
            'success': success,
            'details': details,
            'timestamp': datetime.now()
        }
        self.test_results['steps'].append(step_info)
        
        status = "✅" if success else "❌"
        print(f"{status} {step}")
        if details:
            print(f"   {details}")
        if not success:
            self.test_results['success'] = False
            self.test_results['errors'].append(step_info)
    
    def clean_test_data(self):
        """Remove any existing test data"""
        try:
            # Use client to get existing datasets and clean them up
            datasets = self.client.get_datasets()
            
            # Find test datasets
            test_tags = [PHARMACIES_TAG, STATES_TAG]
            
            for kind in ['pharmacies', 'states']:
                if kind in datasets:
                    for tag in datasets[kind]:
                        if tag in test_tags:
                            # Clean up dataset via API (if such functionality exists)
                            # For now, let's use the raw SQL capability if available
                            try:
                                self.client._delete_dataset(kind, tag)
                            except AttributeError:
                                # If client doesn't have delete capability, log and continue
                                self.log_step(f"Clean {kind} {tag}", True, f"Skipped - no delete capability")
            
            self.log_step("Clean existing test data", True, f"Cleaned up any existing system test data")
            
        except Exception as e:
            self.log_step("Clean existing test data", False, f"Error: {e}")
    
    def update_database_functions(self):
        """Update database functions - skipped in API mode"""
        # Database functions should already be set up via migrations
        self.log_step("Update database functions", True, "Skipped - functions managed via migrations in API mode")
    
    def import_pharmacy_data(self):
        """Import test pharmacy data"""
        try:
            # Create a small test pharmacy dataset
            test_pharmacy_data = [
                {
                    'name': 'Test Pharmacy A',
                    'address': '123 Main Street',
                    'suite': 'Suite 100',
                    'city': 'Houston',
                    'state': 'TX',
                    'zip': '77001',
                    'state_licenses': ['TX', 'FL']
                },
                {
                    'name': 'Test Pharmacy B', 
                    'address': '456 Oak Avenue',
                    'city': 'Tampa',
                    'state': 'FL',
                    'zip': '33601',
                    'state_licenses': ['FL', 'GA']
                },
                {
                    'name': 'Test Pharmacy C',
                    'address': '789 Pine Road',
                    'city': 'Atlanta', 
                    'state': 'GA',
                    'zip': '30301',
                    'state_licenses': ['GA', 'TX']
                }
            ]
            
            # Write to temporary CSV
            import tempfile
            import csv
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
                writer = csv.DictWriter(f, fieldnames=['name', 'address', 'suite', 'city', 'state', 'zip', 'state_licenses'])
                writer.writeheader()
                
                for pharm in test_pharmacy_data:
                    row = pharm.copy()
                    row['state_licenses'] = json.dumps(pharm['state_licenses'])
                    writer.writerow(row)
                
                temp_csv = f.name
            
            # Import using PharmacyImporter - let it auto-detect backend
            with PharmacyImporter() as importer:
                success = importer.import_csv(
                    filepath=temp_csv,
                    tag=PHARMACIES_TAG,
                    created_by='system_test',
                    description='System test pharmacy data'
                )
            
            os.unlink(temp_csv)
            
            if success:
                self.log_step("Import pharmacy data", True, f"Imported {len(test_pharmacy_data)} test pharmacies")
            else:
                self.log_step("Import pharmacy data", False, "Import failed")
                
        except Exception as e:
            self.log_step("Import pharmacy data", False, f"Error: {e}")
    
    def import_state_data(self):
        """Import test state search data"""
        try:
            # Create test state search results
            test_results = [
                # Perfect match for Test Pharmacy A
                {
                    'search_name': 'Test Pharmacy A',
                    'search_state': 'TX',
                    'search_ts': '2024-01-15T10:00:00',
                    'license_number': 'TX12345',
                    'license_status': 'Active',
                    'license_name': 'Test Pharmacy A LLC',
                    'address': '123 Main Street',
                    'city': 'Houston',
                    'state': 'TX',
                    'zip': '77001',
                    'issue_date': '2020-01-01',
                    'expiration_date': '2025-12-31',
                    'result_status': 'results_found'
                },
                # Similar but not exact match for Test Pharmacy A
                {
                    'search_name': 'Test Pharmacy A',
                    'search_state': 'FL',
                    'search_ts': '2024-01-15T10:05:00',
                    'license_number': 'FL98765',
                    'license_status': 'Active',
                    'license_name': 'Test Pharmacy A Inc',
                    'address': '123 Main St',  # Abbreviated
                    'city': 'Miami',  # Different city
                    'state': 'FL',
                    'zip': '33101',
                    'issue_date': '2021-06-01',
                    'expiration_date': '2026-05-31',
                    'result_status': 'results_found'
                },
                # Perfect match for Test Pharmacy B
                {
                    'search_name': 'Test Pharmacy B',
                    'search_state': 'FL',
                    'search_ts': '2024-01-15T11:00:00',
                    'license_number': 'FL55555',
                    'license_status': 'Active',
                    'license_name': 'Test Pharmacy B',
                    'address': '456 Oak Avenue',
                    'city': 'Tampa',
                    'state': 'FL',
                    'zip': '33601',
                    'issue_date': '2019-03-15',
                    'expiration_date': '2024-03-14',
                    'result_status': 'results_found'
                },
                # No match scenario for Test Pharmacy C
                {
                    'search_name': 'Test Pharmacy C',
                    'search_state': 'GA',
                    'search_ts': '2024-01-15T12:00:00',
                    'license_number': 'GA99999',
                    'license_status': 'Active',
                    'license_name': 'Different Pharmacy Name',
                    'address': '999 Different Street',
                    'city': 'Savannah',
                    'state': 'GA',
                    'zip': '31401',
                    'issue_date': '2022-08-01',
                    'expiration_date': '2027-07-31',
                    'result_status': 'results_found'
                },
                # No results found case
                {
                    'search_name': 'Test Pharmacy C',
                    'search_state': 'TX',
                    'search_ts': '2024-01-15T12:30:00',
                    'license_number': None,
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
            ]
            
            # Use StateImporter for proper API handling
            with StateImporter() as importer:
                # Create temporary JSON files for each result
                import tempfile
                temp_dir = tempfile.mkdtemp()
                
                try:
                    # Group by search name and state
                    grouped_results = {}
                    for result in test_results:
                        key = (result['search_name'], result['search_state'])
                        if key not in grouped_results:
                            grouped_results[key] = []
                        grouped_results[key].append(result)
                    
                    # Create JSON files for each search
                    json_files = []
                    for (search_name, search_state), results in grouped_results.items():
                        # Convert to StateImporter expected format
                        json_data = {
                            'metadata': {
                                'search_name': search_name,
                                'search_state': search_state,
                                'search_timestamp': results[0]['search_ts']
                            },
                            'results': []
                        }
                        
                        for result in results:
                            if result['license_number']:  # Only add results with data
                                json_data['results'].append({
                                    'license_number': result['license_number'],
                                    'license_status': result['license_status'],
                                    'license_name': result['license_name'],
                                    'address': result['address'],
                                    'city': result['city'],
                                    'state': result['state'],
                                    'zip': result['zip'],
                                    'issue_date': result['issue_date'],
                                    'expiration_date': result['expiration_date']
                                })
                            else:
                                # No results found case
                                json_data['metadata']['result_status'] = 'no_results_found'
                        
                        # Write JSON file
                        json_file = os.path.join(temp_dir, f"{search_name}_{search_state}.json")
                        with open(json_file, 'w') as f:
                            json.dump(json_data, f, indent=2)
                        json_files.append(json_file)
                    
                    # Import the directory
                    success = importer.import_directory(
                        directory_path=temp_dir,
                        tag=STATES_TAG,
                        created_by='system_test',
                        description='System test state search data'
                    )
                    
                finally:
                    # Clean up temp files
                    import shutil
                    shutil.rmtree(temp_dir)
            
            self.log_step("Import state search data", True, f"Imported {len(test_results)} search results")
            
        except Exception as e:
            self.log_step("Import state search data", False, f"Error: {e}")
    
    def check_missing_scores(self) -> Dict:
        """Check for missing scores (should find pairs that need scoring)"""
        try:
            with ScoringEngine() as engine:  # Let engine auto-detect backend
                missing_pairs = engine.find_missing_scores(STATES_TAG, PHARMACIES_TAG, limit=100)
                
                self.log_step("Check missing scores", True, 
                             f"Found {len(missing_pairs)} pharmacy/result pairs that need scores")
                
                return {
                    'missing_pairs': missing_pairs,
                    'count': len(missing_pairs)
                }
                
        except Exception as e:
            self.log_step("Check missing scores", False, f"Error: {e}")
            return {'missing_pairs': [], 'count': 0}

    def query_initial_results(self) -> List[Dict]:
        """Query initial results (should show no scores)"""
        try:
            # Use client to get comprehensive results
            comprehensive_results = self.client.get_comprehensive_results(
                states_tag=STATES_TAG,
                pharmacies_tag=PHARMACIES_TAG,
                validated_tag=None
            )
            
            # Convert to list of dicts for compatibility (client returns list directly)
            results_list = comprehensive_results if isinstance(comprehensive_results, list) else []
            
            # Aggregate into matrix format for compatibility
            results = self.aggregate_results_matrix(results_list)
            
            # Count how many have scores
            with_scores = len([r for r in results if r['score_overall'] is not None])
            without_scores = len(results) - with_scores
            
            self.log_step("Query initial results", True, 
                         f"Found {len(results)} pharmacy/state combinations, {without_scores} without scores")
            
            return results
            
        except Exception as e:
            self.log_step("Query initial results", False, f"Error: {e}")
            return []
    
    def run_scoring_engine(self) -> Dict:
        """Run the lazy scoring engine"""
        try:
            with ScoringEngine() as engine:  # Let engine auto-detect backend
                # Get statistics before
                stats_before = engine.get_scoring_stats(STATES_TAG, PHARMACIES_TAG)
                
                if 'error' in stats_before:
                    self.log_step("Run scoring engine", False, f"Stats error: {stats_before['error']}")
                    return {}
                
                # Run scoring
                result = engine.compute_scores(STATES_TAG, PHARMACIES_TAG, batch_size=10)
                
                # Get statistics after
                stats_after = engine.get_scoring_stats(STATES_TAG, PHARMACIES_TAG)
                
                self.log_step("Run scoring engine", True, 
                             f"Computed {result['scores_computed']} scores in {result['batches_processed']} batches")
                
                return {
                    'before': stats_before,
                    'result': result,
                    'after': stats_after
                }
                
        except Exception as e:
            self.log_step("Run scoring engine", False, f"Error: {e}")
            return {}
    
    def verify_scores_computed(self) -> Dict:
        """Verify that scores have been computed for all viable pairs"""
        try:
            with ScoringEngine() as engine:  # Let engine auto-detect backend
                missing_pairs = engine.find_missing_scores(STATES_TAG, PHARMACIES_TAG, limit=100)
                
                # For API mode, we'll assume missing pairs are actually missing
                # since "no results found" cases shouldn't be in the missing pairs list
                viable_missing = missing_pairs  # In API mode, assume all missing are viable
                
                success = len(viable_missing) == 0
                message = f"Found {len(missing_pairs)} total pairs without scores"
                if len(viable_missing) > 0:
                    message += f" ({len(viable_missing)} viable pairs still need scoring)"
                
                self.log_step("Verify scores computed", success, message)
                
                return {
                    'remaining_missing': missing_pairs,
                    'viable_missing': viable_missing,
                    'count': len(missing_pairs),
                    'viable_count': len(viable_missing),
                    'all_computed': success
                }
                
        except Exception as e:
            self.log_step("Verify scores computed", False, f"Error: {e}")
            return {'remaining_missing': [], 'viable_missing': [], 'count': 0, 'viable_count': 0, 'all_computed': False}
    
    def query_final_results(self) -> List[Dict]:
        """Query final results (should show computed scores)"""
        try:
            # Use client to get comprehensive results
            comprehensive_results = self.client.get_comprehensive_results(
                states_tag=STATES_TAG,
                pharmacies_tag=PHARMACIES_TAG,
                validated_tag=None
            )
            
            # Convert to list of dicts for compatibility (client returns list directly)
            results_list = comprehensive_results if isinstance(comprehensive_results, list) else []
            
            # Aggregate into matrix format for compatibility
            results = self.aggregate_results_matrix(results_list)
            # Sort by score
            results.sort(key=lambda x: (x['pharmacy_name'], x['search_state'], x['score_overall'] or -1), reverse=True)
            
            # Count scores by status bucket
            status_counts = {}
            for result in results:
                bucket = result['status_bucket']
                status_counts[bucket] = status_counts.get(bucket, 0) + 1
            
            self.log_step("Query final results", True, 
                         f"Found {len(results)} results with status distribution: {status_counts}")
            
            return results
            
        except Exception as e:
            self.log_step("Query final results", False, f"Error: {e}")
            return []
    
    def generate_report(self, initial_results: List[Dict], final_results: List[Dict], scoring_stats: Dict):
        """Generate comprehensive test report"""
        print("\n" + "="*80)
        print("PHARMCHECKER SYSTEM TEST REPORT")
        print("="*80)
        
        # Test Summary
        print(f"\nTest Summary:")
        print(f"  Pharmacy Tag: {PHARMACIES_TAG}")
        print(f"  States Tag: {STATES_TAG}")
        print(f"  Start Time: {self.test_results['start_time']}")
        print(f"  Duration: {datetime.now() - self.test_results['start_time']}")
        print(f"  Overall Success: {'✅ PASS' if self.test_results['success'] else '❌ FAIL'}")
        print(f"  Steps Completed: {len([s for s in self.test_results['steps'] if s['success']])}/{len(self.test_results['steps'])}")
        
        if self.test_results['errors']:
            print(f"  Errors: {len(self.test_results['errors'])}")
            for error in self.test_results['errors']:
                print(f"    - {error['step']}: {error['details']}")
        
        # Data Summary
        print(f"\nData Summary:")
        print(f"  Pharmacies: 3 test pharmacies imported")
        print(f"  Search Results: 5 search results imported")
        print(f"  Initial Matrix Rows: {len(initial_results)}")
        print(f"  Final Matrix Rows: {len(final_results)}")
        
        # Scoring Summary
        if scoring_stats.get('result'):
            result = scoring_stats['result']
            print(f"\nScoring Summary:")
            print(f"  Scores Computed: {result['scores_computed']}")
            print(f"  Processing Batches: {result['batches_processed']}")
            print(f"  Processing Errors: {result['errors']}")
            print(f"  Processing Time: {result.get('duration', 'N/A')} seconds")
        
        if scoring_stats.get('after', {}).get('score_distribution'):
            dist = scoring_stats['after']['score_distribution']
            print(f"  Score Distribution:")
            print(f"    Matches (≥85): {dist['match_count']}")
            print(f"    Weak Matches (60-84): {dist['weak_count']}")
            print(f"    No Matches (<60): {dist['no_match_count']}")
            if dist['avg_score']:
                print(f"    Average Score: {dist['avg_score']:.1f}")
                print(f"    Score Range: {dist['min_score']:.1f} - {dist['max_score']:.1f}")
        
        # Detailed Results
        print(f"\nDetailed Results:")
        print("-" * 80)
        
        for result in final_results:
            status_icon = {
                'match': '✅',
                'weak match': '⚠️', 
                'no match': '❌',
                'no data': '📭'
            }.get(result['status_bucket'], '❓')
            
            print(f"{status_icon} {result['pharmacy_name']} → {result['search_state']}")
            print(f"   Status: {result['status_bucket']}")
            
            if result['score_overall'] is not None:
                print(f"   Overall Score: {result['score_overall']:.1f}")
                print(f"   Street Score: {result['score_street']:.1f}")
                print(f"   City/State/ZIP Score: {result['score_city_state_zip']:.1f}")
            else:
                print(f"   Score: No score computed")
            
            if result['license_number']:
                print(f"   License: {result['license_number']} ({result['license_status']})")
            else:
                print(f"   License: No results found")
            
            if result['warnings']:
                print(f"   Warnings: {', '.join(result['warnings'])}")
            
            print()
        
        # Expected vs Actual Results
        print("Expected Results Analysis:")
        print("-" * 40)
        
        expected_perfect = [r for r in final_results if 'Test Pharmacy A' in r['pharmacy_name'] and r['search_state'] == 'TX']
        if expected_perfect and expected_perfect[0]['score_overall'] and expected_perfect[0]['score_overall'] >= 85:
            print("✅ Perfect match correctly identified (Test Pharmacy A → TX)")
        else:
            print("❌ Perfect match not identified correctly")
        
        expected_weak = [r for r in final_results if 'Test Pharmacy A' in r['pharmacy_name'] and r['search_state'] == 'FL']  
        if expected_weak and expected_weak[0]['score_overall'] and 60 <= expected_weak[0]['score_overall'] < 85:
            print("✅ Weak match correctly identified (Test Pharmacy A → FL)")
        else:
            print("❌ Weak match not identified correctly")
        
        expected_no_match = [r for r in final_results if 'Test Pharmacy C' in r['pharmacy_name'] and r['search_state'] == 'GA']
        if expected_no_match and (expected_no_match[0]['score_overall'] is None or expected_no_match[0]['score_overall'] < 60):
            print("✅ No match correctly identified (Test Pharmacy C → GA)")  
        else:
            print("❌ No match not identified correctly")
        
        print("\n" + "="*80)
    
    def run_full_test(self):
        """Run the complete end-to-end system test following app.py workflow"""
        print("PharmChecker End-to-End System Test")
        print("="*50)
        
        # Step 1: Clean existing data
        self.clean_test_data()
        
        # Step 2: Import pharmacy data (separate tag)
        self.import_pharmacy_data()
        
        # Step 3: Import state search data (separate tag)  
        self.import_state_data()
        
        # Step 4: Check missing scores (should find pairs that need scoring)
        missing_info = self.check_missing_scores()
        
        # Step 5: Query initial results (no scores)
        initial_results = self.query_initial_results()
        
        # Step 6: Run scoring engine
        scoring_stats = self.run_scoring_engine()
        
        # Step 7: Verify scores computed (should find no remaining missing scores)
        verification_info = self.verify_scores_computed()
        
        # Step 8: Query final results (with scores)
        final_results = self.query_final_results()
        
        # Step 9: Generate comprehensive report
        self.generate_report(initial_results, final_results, scoring_stats)
        
        # Step 10: Clean up test data
        print(f"\nCleaning up test data (tags: {PHARMACIES_TAG}, {STATES_TAG})...")
        self.clean_test_data()
        
        return self.test_results

def main():
    """Main entry point"""
    test = SystemTest()
    results = test.run_full_test()
    
    # Exit with appropriate code
    sys.exit(0 if results['success'] else 1)

if __name__ == "__main__":
    main()