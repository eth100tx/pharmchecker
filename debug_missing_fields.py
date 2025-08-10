#!/usr/bin/env python3
"""
Debug script to identify missing search_name and image fields
"""

import pandas as pd
from utils.database import DatabaseManager

def debug_missing_fields():
    """Debug missing search name and image fields"""
    
    print("=== Debugging Missing Search Name and Images ===\n")
    
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
    
    # Check what columns we have
    print(f"\nColumns in comprehensive results:")
    for i, col in enumerate(comprehensive_df.columns):
        print(f"  {i+1:2}. {col}")
    
    # Look for search name related fields
    search_name_fields = [col for col in comprehensive_df.columns if 'search' in col.lower() and 'name' in col.lower()]
    name_fields = [col for col in comprehensive_df.columns if 'name' in col.lower()]
    
    print(f"\nSearch name related fields: {search_name_fields}")
    print(f"All name fields: {name_fields}")
    
    # Look for image related fields  
    image_fields = [col for col in comprehensive_df.columns if any(word in col.lower() for word in ['image', 'screenshot', 'photo', 'picture'])]
    print(f"Image related fields: {image_fields}")
    
    # Test with a specific record
    first_record = comprehensive_df.iloc[0]
    print(f"\nFirst record key fields:")
    print(f"  pharmacy_name: {first_record.get('pharmacy_name')}")
    print(f"  search_state: {first_record.get('search_state')}")
    print(f"  result_id: {first_record.get('result_id')}")
    
    # Check if search_name exists
    search_name_value = first_record.get('search_name')
    print(f"  search_name: {search_name_value}")
    
    if pd.isna(search_name_value) or search_name_value is None:
        print("  ❌ PROBLEM: search_name is missing from comprehensive results")
    else:
        print("  ✅ search_name is available")
    
    # Compare with old approach to see what's missing
    print(f"\n--- Comparing with OLD approach ---")
    
    # Get first pharmacy-state combination to test
    test_pharmacy = first_record['pharmacy_name']
    test_state = first_record['search_state']
    
    try:
        old_detail_df = db.get_search_results(test_pharmacy, test_state, states_tag)
        print(f"Old approach - Detail results: {len(old_detail_df)} records")
        
        if not old_detail_df.empty:
            print("Old approach columns:")
            for i, col in enumerate(old_detail_df.columns):
                print(f"  {i+1:2}. {col}")
            
            print(f"\nOld approach first record key fields:")
            old_first = old_detail_df.iloc[0]
            print(f"  search_name: {old_first.get('search_name')}")
            print(f"  screenshot_path: {old_first.get('screenshot_path')}")
            print(f"  screenshot_storage_type: {old_first.get('screenshot_storage_type')}")
            print(f"  screenshot_file_size: {old_first.get('screenshot_file_size')}")
            
    except Exception as e:
        print(f"Error with old approach: {e}")
    
    # Check what the comprehensive function should include
    print(f"\n--- Analysis ---")
    print("Missing fields in comprehensive function:")
    
    expected_fields = [
        'search_name',  # The name used in the search 
        'screenshot_path',  # Path to screenshot
        'screenshot_storage_type',  # Storage type
        'screenshot_file_size',  # File size
        'license_name',  # License name
        'license_type'   # License type
    ]
    
    for field in expected_fields:
        if field not in comprehensive_df.columns:
            print(f"  ❌ Missing: {field}")
        else:
            print(f"  ✅ Present: {field}")
    
    return True

if __name__ == "__main__":
    debug_missing_fields()