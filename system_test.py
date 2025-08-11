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

from config import get_db_config
from imports.pharmacies import PharmacyImporter
from imports.states import StateImporter
from imports.scoring import ScoringEngine
import psycopg2
from psycopg2.extras import RealDictCursor

TEST_TAG = "system_test"

class SystemTest:
    """Complete PharmChecker system test"""
    
    def __init__(self):
        self.db_config = get_db_config()
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
            with psycopg2.connect(**self.db_config) as conn:
                with conn.cursor() as cur:
                    # Delete in dependency order
                    cur.execute("DELETE FROM match_scores WHERE states_dataset_id IN (SELECT id FROM datasets WHERE tag = %s) OR pharmacies_dataset_id IN (SELECT id FROM datasets WHERE tag = %s)", (TEST_TAG, TEST_TAG))
                    cur.execute("DELETE FROM search_results WHERE dataset_id IN (SELECT id FROM datasets WHERE tag = %s)", (TEST_TAG,))
                    cur.execute("DELETE FROM pharmacies WHERE dataset_id IN (SELECT id FROM datasets WHERE tag = %s)", (TEST_TAG,))
                    cur.execute("DELETE FROM validated_overrides WHERE dataset_id IN (SELECT id FROM datasets WHERE tag = %s)", (TEST_TAG,))
                    cur.execute("DELETE FROM images WHERE dataset_id IN (SELECT id FROM datasets WHERE tag = %s)", (TEST_TAG,))
                    cur.execute("DELETE FROM datasets WHERE tag = %s", (TEST_TAG,))
                    
                    rows_deleted = cur.rowcount
                conn.commit()
            
            self.log_step("Clean existing test data", True, f"Cleaned up any existing {TEST_TAG} data")
            
        except Exception as e:
            self.log_step("Clean existing test data", False, f"Error: {e}")
    
    def update_database_functions(self):
        """Update database functions to work with optimized schema"""
        try:
            with open('functions_optimized.sql', 'r') as f:
                sql = f.read()
            
            with psycopg2.connect(**self.db_config) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                conn.commit()
            
            self.log_step("Update database functions", True, "Functions updated for optimized schema")
            
        except Exception as e:
            self.log_step("Update database functions", False, f"Error: {e}")
    
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
            
            # Import using PharmacyImporter
            with PharmacyImporter(self.db_config) as importer:
                success = importer.import_csv(
                    filepath=temp_csv,
                    tag=TEST_TAG,
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
            
            # Import directly to database (simulating StateImporter functionality)
            with psycopg2.connect(**self.db_config) as conn:
                with conn.cursor() as cur:
                    # Create states dataset
                    cur.execute("""
                        INSERT INTO datasets (kind, tag, description, created_by)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (kind, tag) DO UPDATE 
                        SET description = EXCLUDED.description
                        RETURNING id
                    """, ('states', TEST_TAG, 'System test state search data', 'system_test'))
                    
                    dataset_id = cur.fetchone()[0]
                    
                    # Insert search results
                    for result in test_results:
                        from datetime import datetime as dt
                        
                        # Parse search_ts if it's a string
                        search_ts = result['search_ts']
                        if isinstance(search_ts, str):
                            search_ts = dt.fromisoformat(search_ts.replace('Z', '+00:00'))
                        
                        cur.execute("""
                            INSERT INTO search_results 
                            (dataset_id, search_name, search_state, search_ts, 
                             license_number, license_status, license_name,
                             address, city, state, zip, issue_date, expiration_date, result_status)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            dataset_id,
                            result['search_name'],
                            result['search_state'], 
                            search_ts,
                            result['license_number'],
                            result['license_status'],
                            result['license_name'],
                            result['address'],
                            result['city'],
                            result['state'],
                            result['zip'],
                            result['issue_date'],
                            result['expiration_date'],
                            result['result_status']
                        ))
                
                conn.commit()
            
            self.log_step("Import state search data", True, f"Imported {len(test_results)} search results")
            
        except Exception as e:
            self.log_step("Import state search data", False, f"Error: {e}")
    
    def query_initial_results(self) -> List[Dict]:
        """Query initial results (should show no scores)"""
        try:
            with psycopg2.connect(**self.db_config) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT * FROM get_all_results_with_context(%s, %s, %s)
                        ORDER BY pharmacy_name, search_state
                    """, (TEST_TAG, TEST_TAG, None))
                    
                    comprehensive_results = cur.fetchall()
            
            # Aggregate into matrix format for compatibility
            results = self.aggregate_results_matrix(comprehensive_results)
            
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
            with ScoringEngine(self.db_config) as engine:
                # Get statistics before
                stats_before = engine.get_scoring_stats(TEST_TAG, TEST_TAG)
                
                if 'error' in stats_before:
                    self.log_step("Run scoring engine", False, f"Stats error: {stats_before['error']}")
                    return {}
                
                # Run scoring
                result = engine.compute_scores(TEST_TAG, TEST_TAG, batch_size=10)
                
                # Get statistics after
                stats_after = engine.get_scoring_stats(TEST_TAG, TEST_TAG)
                
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
    
    def query_final_results(self) -> List[Dict]:
        """Query final results (should show computed scores)"""
        try:
            with psycopg2.connect(**self.db_config) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT * FROM get_all_results_with_context(%s, %s, %s)
                        ORDER BY pharmacy_name, search_state
                    """, (TEST_TAG, TEST_TAG, None))
                    
                    comprehensive_results = cur.fetchall()
            
            # Aggregate into matrix format for compatibility
            results = self.aggregate_results_matrix(comprehensive_results)
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
        print(f"  Tag: {TEST_TAG}")
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
        """Run the complete end-to-end system test"""
        print("PharmChecker End-to-End System Test")
        print("="*50)
        
        # Step 1: Clean existing data
        self.clean_test_data()
        
        # Step 2: Database functions already updated externally
        
        # Step 3: Import pharmacy data
        self.import_pharmacy_data()
        
        # Step 4: Import state search data
        self.import_state_data()
        
        # Step 5: Query initial results (no scores)
        initial_results = self.query_initial_results()
        
        # Step 6: Run scoring engine
        scoring_stats = self.run_scoring_engine()
        
        # Step 7: Query final results (with scores)
        final_results = self.query_final_results()
        
        # Step 8: Generate comprehensive report
        self.generate_report(initial_results, final_results, scoring_stats)
        
        return self.test_results

def main():
    """Main entry point"""
    test = SystemTest()
    results = test.run_full_test()
    
    # Exit with appropriate code
    sys.exit(0 if results['success'] else 1)

if __name__ == "__main__":
    main()