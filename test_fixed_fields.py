#!/usr/bin/env python3
"""
Test the fixed search_name and image fields
"""

import pandas as pd
from utils.database import DatabaseManager

def test_fixed_fields():
    """Test that search_name and image fields are now working"""
    
    print("=== Testing Fixed Search Name and Image Fields ===\n")
    
    # Initialize database manager
    db = DatabaseManager(use_production=True, allow_fallback=False)
    
    # Get datasets
    datasets = db.get_datasets()
    if not datasets.get('states') or not datasets.get('pharmacies'):
        print("No datasets available")
        return False
    
    states_tag = datasets['states'][0] 
    pharmacies_tag = datasets['pharmacies'][0]
    validated_tag = datasets['validated'][0] if datasets['validated'] else None
    
    print(f"Using datasets: states='{states_tag}', pharmacies='{pharmacies_tag}'")
    
    # Get comprehensive results
    comprehensive_df = db.get_comprehensive_results(states_tag, pharmacies_tag, validated_tag, filter_to_loaded_states=True)
    print(f"Comprehensive results: {len(comprehensive_df)} records")
    
    if comprehensive_df.empty:
        print("No data available")
        return False
    
    # Find records with actual search results (not null result_id)
    records_with_results = comprehensive_df[comprehensive_df['result_id'].notna()]
    print(f"Records with search results: {len(records_with_results)}")
    
    if records_with_results.empty:
        print("No records with search results found")
        return False
    
    # Test the first few records with results
    print(f"\n--- Testing first 3 records with search results ---")
    
    for i, (_, record) in enumerate(records_with_results.head(3).iterrows()):
        print(f"\n=== Record {i+1} ===")
        print(f"Pharmacy: {record.get('pharmacy_name')}")
        print(f"State: {record.get('search_state')}")
        print(f"Result ID: {record.get('result_id')}")
        print(f"Search Name: {record.get('search_name')}")
        print(f"License #: {record.get('license_number')}")
        print(f"License Name: {record.get('license_name')}")
        print(f"License Type: {record.get('license_type')}")
        print(f"License Status: {record.get('license_status')}")
        print(f"Screenshot Path: {record.get('screenshot_path')}")
        print(f"Screenshot Type: {record.get('screenshot_storage_type')}")
        print(f"Screenshot Size: {record.get('screenshot_file_size')}")
        
        # Check for issues
        issues = []
        if pd.isna(record.get('search_name')) or record.get('search_name') is None:
            issues.append("search_name is None")
        if pd.isna(record.get('screenshot_path')) or record.get('screenshot_path') is None:
            issues.append("screenshot_path is None")
            
        if issues:
            print(f"❌ Issues: {', '.join(issues)}")
        else:
            print(f"✅ All fields look good")
    
    # Test the display logic for the first record with results
    test_record = records_with_results.iloc[0]
    print(f"\n--- Testing Display Logic ---")
    print(f"Test record: {test_record.get('pharmacy_name')}/{test_record.get('search_state')}")
    
    # Simulate the display_enhanced_search_result_detail function
    search_name = test_record.get('search_name', 'N/A')
    search_state = test_record.get('search_state', 'N/A') 
    license_number = test_record.get('license_number', 'N/A')
    license_status = test_record.get('license_status', 'N/A')
    
    print(f"Display values:")
    print(f"  Search Name: {search_name}")
    print(f"  Search State: {search_state}")
    print(f"  License #: {license_number}")
    print(f"  Status: {license_status}")
    
    if search_name == 'N/A':
        print("❌ PROBLEM: Search name is still showing as N/A")
        return False
    else:
        print("✅ SUCCESS: Search name is displaying correctly")
    
    # Test image handling
    screenshot_path = test_record.get('screenshot_path')
    if screenshot_path:
        print(f"  Screenshot: {screenshot_path}")
        print("✅ SUCCESS: Screenshot path is available")
    else:
        print("ℹ️ INFO: No screenshot path for this record (may be normal)")
    
    return True

if __name__ == "__main__":
    success = test_fixed_fields()
    exit(0 if success else 1)