#!/usr/bin/env python3
"""
Debug script to examine detail data returned by comprehensive approach
"""

import pandas as pd
from utils.database import DatabaseManager

def debug_detail_data():
    """Debug the detail data to see if it's being duplicated"""
    
    print("=== Debugging Detail Data Issue ===\n")
    
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
    print(f"\n1. Comprehensive results: {len(comprehensive_df)} total records")
    
    if comprehensive_df.empty:
        print("No comprehensive data available")
        return False
    
    # Get matrix view
    matrix_df = db.aggregate_for_matrix(comprehensive_df)
    print(f"2. Matrix view: {len(matrix_df)} aggregated records")
    
    # Pick a pharmacy-state combination that has multiple results
    print("\n3. Looking for pharmacy-state combinations with multiple results...")
    
    result_counts = comprehensive_df.groupby(['pharmacy_name', 'search_state']).size().reset_index(name='count')
    multi_result_combos = result_counts[result_counts['count'] > 1]
    
    if multi_result_combos.empty:
        print("No combinations with multiple results found. Showing all combinations:")
        print(result_counts)
        
        # Pick first combination
        if not result_counts.empty:
            test_pharmacy = result_counts.iloc[0]['pharmacy_name']
            test_state = result_counts.iloc[0]['search_state']
        else:
            print("No data to test with")
            return False
    else:
        print("Combinations with multiple results:")
        print(multi_result_combos)
        # Pick the first one with multiple results
        test_pharmacy = multi_result_combos.iloc[0]['pharmacy_name']
        test_state = multi_result_combos.iloc[0]['search_state']
    
    print(f"\n4. Testing with {test_pharmacy}/{test_state}")
    
    # Filter for detail view (new approach)
    detail_df = db.filter_for_detail(comprehensive_df, test_pharmacy, test_state)
    print(f"\nNew approach - Detail results: {len(detail_df)} records")
    
    if not detail_df.empty:
        print("Columns:", list(detail_df.columns))
        print("\nFirst few records (key fields only):")
        key_cols = ['result_id', 'license_number', 'license_status', 'result_address', 'result_city', 'score_overall']
        available_cols = [col for col in key_cols if col in detail_df.columns]
        print(detail_df[available_cols].head())
        
        print(f"\nUnique values check:")
        if 'license_number' in detail_df.columns:
            unique_licenses = detail_df['license_number'].nunique()
            print(f"  Unique license numbers: {unique_licenses} (total records: {len(detail_df)})")
            if unique_licenses > 1:
                print(f"  License numbers: {detail_df['license_number'].unique()}")
            elif len(detail_df) > 1:
                print(f"  ❌ PROBLEM: {len(detail_df)} records but only {unique_licenses} unique license number")
                print(f"  License number values: {detail_df['license_number'].tolist()}")
        
        if 'result_id' in detail_df.columns:
            unique_result_ids = detail_df['result_id'].nunique()
            print(f"  Unique result IDs: {unique_result_ids} (total records: {len(detail_df)})")
            if unique_result_ids > 1:
                print(f"  Result IDs: {detail_df['result_id'].unique()}")
            elif len(detail_df) > 1:
                print(f"  ❌ PROBLEM: {len(detail_df)} records but only {unique_result_ids} unique result ID")
    
    # Compare with old approach
    print(f"\n5. Comparing with OLD approach...")
    try:
        old_detail_df = db.get_search_results(test_pharmacy, test_state, states_tag)
        print(f"Old approach - Detail results: {len(old_detail_df)} records")
        
        if not old_detail_df.empty:
            print("Old approach columns:", list(old_detail_df.columns))
            old_key_cols = ['id', 'license_number', 'license_status', 'address', 'city', 'score_overall']
            old_available_cols = [col for col in old_key_cols if col in old_detail_df.columns]
            print("Old approach data (first few records):")
            print(old_detail_df[old_available_cols].head())
            
            if 'license_number' in old_detail_df.columns:
                old_unique_licenses = old_detail_df['license_number'].nunique()
                print(f"Old approach unique license numbers: {old_unique_licenses}")
    except Exception as e:
        print(f"Error with old approach: {e}")
    
    print("\n6. Raw comprehensive data for this combination:")
    raw_data = comprehensive_df[
        (comprehensive_df['pharmacy_name'] == test_pharmacy) & 
        (comprehensive_df['search_state'] == test_state)
    ]
    
    if not raw_data.empty:
        display_cols = ['result_id', 'license_number', 'license_status', 'result_address', 'search_timestamp']
        available_display_cols = [col for col in display_cols if col in raw_data.columns]
        print(f"Raw comprehensive data ({len(raw_data)} records):")
        print(raw_data[available_display_cols])
        
        if len(raw_data) > 1:
            # Check if all rows are identical
            duplicated = raw_data.duplicated().sum()
            print(f"\nDuplicate check: {duplicated} out of {len(raw_data)} rows are duplicates")
            
            if duplicated > 0:
                print("❌ PROBLEM: Found duplicate rows in comprehensive data")
                print("Duplicate rows:")
                print(raw_data[raw_data.duplicated(keep=False)][available_display_cols])
    
    return True

if __name__ == "__main__":
    debug_detail_data()