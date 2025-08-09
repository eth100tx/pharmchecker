#!/usr/bin/env python3
"""
Debug the state import issue
"""

from config import get_db_config
import psycopg2
from datetime import datetime

def debug_import():
    """Debug the state data import"""
    
    # Test data
    test_result = {
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
    }
    
    with psycopg2.connect(**get_db_config()) as conn:
        with conn.cursor() as cur:
            try:
                # Create dataset if not exists
                cur.execute("""
                    INSERT INTO datasets (kind, tag, description, created_by)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (kind, tag) DO UPDATE 
                    SET description = EXCLUDED.description
                    RETURNING id
                """, ('states', 'debug_test', 'Debug test', 'debug'))
                
                dataset_id = cur.fetchone()[0]
                print(f"Dataset ID: {dataset_id}")
                
                # Parse datetime
                search_ts = datetime.fromisoformat(test_result['search_ts'])
                print(f"Parsed timestamp: {search_ts}")
                
                # Try the insert
                print("Attempting insert...")
                print(f"Parameters: {len([dataset_id, test_result['search_name'], test_result['search_state'], search_ts, test_result['license_number'], test_result['license_status'], test_result['license_name'], test_result['address'], test_result['city'], test_result['state'], test_result['zip'], test_result['issue_date'], test_result['expiration_date'], test_result['result_status']])}")
                
                query = """
                    INSERT INTO search_results 
                    (dataset_id, search_name, search_state, search_ts, 
                     license_number, license_status, license_name,
                     address, city, state, zip, issue_date, expiration_date, result_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                params = (
                    dataset_id,
                    test_result['search_name'],
                    test_result['search_state'], 
                    search_ts,
                    test_result['license_number'],
                    test_result['license_status'],
                    test_result['license_name'],
                    test_result['address'],
                    test_result['city'],
                    test_result['state'],
                    test_result['zip'],
                    test_result['issue_date'],
                    test_result['expiration_date'],
                    test_result['result_status']
                )
                
                print(f"Query placeholders: {query.count('%s')}")
                print(f"Parameters count: {len(params)}")
                
                cur.execute(query, params)
                
                conn.commit()
                print("✅ Insert successful!")
                
                # Clean up
                cur.execute("DELETE FROM search_results WHERE dataset_id = %s", (dataset_id,))
                cur.execute("DELETE FROM datasets WHERE id = %s", (dataset_id,))
                conn.commit()
                print("✅ Cleanup successful!")
                
            except Exception as e:
                print(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    debug_import()