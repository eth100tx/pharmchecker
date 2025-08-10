#!/usr/bin/env python3
"""
Test script to verify address display is working correctly
"""

import pandas as pd
from utils.database import DatabaseManager

def test_address_display():
    """Test that addresses are displayed correctly in detail view"""
    
    print("=== Testing Address Display Fix ===\n")
    
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
    
    # Find a combination with multiple results to test
    result_counts = comprehensive_df.groupby(['pharmacy_name', 'search_state']).size().reset_index(name='count')
    multi_result_combos = result_counts[result_counts['count'] > 1]
    
    if multi_result_combos.empty:
        test_pharmacy = result_counts.iloc[0]['pharmacy_name']
        test_state = result_counts.iloc[0]['search_state']
    else:
        test_pharmacy = multi_result_combos.iloc[0]['pharmacy_name']
        test_state = multi_result_combos.iloc[0]['search_state']
    
    print(f"Testing address display for {test_pharmacy}/{test_state}")
    
    # Filter for detail view
    detail_df = db.filter_for_detail(comprehensive_df, test_pharmacy, test_state)
    print(f"Detail results: {len(detail_df)} records")
    
    if detail_df.empty:
        print("No detail data available")
        return False
    
    # Test the address extraction logic (simulating the display function)
    print("\nTesting address extraction for each result:")
    
    for i, (_, result) in enumerate(detail_df.iterrows()):
        print(f"\n--- Result {i+1} ---")
        
        # Test new column mapping (what we fixed)
        address = result.get('result_address') or result.get('address')
        city = result.get('result_city') or result.get('city')
        state = result.get('result_state') or result.get('state')
        zip_code = result.get('result_zip') or result.get('zip')
        
        addr_parts = []
        if address: addr_parts.append(address)
        if city: addr_parts.append(city)
        if state: addr_parts.append(state)
        if zip_code: addr_parts.append(zip_code)
        
        full_address = ', '.join(addr_parts) if addr_parts else 'N/A'
        
        print(f"License #: {result.get('license_number', 'N/A')}")
        print(f"Status: {result.get('license_status', 'N/A')}")
        print(f"Address: {full_address}")
        print(f"Score: {result.get('score_overall', 'N/A')}")
        
        # Check if we have valid data
        if full_address == 'N/A':
            print("❌ PROBLEM: No address data found")
            print(f"   result_address: {result.get('result_address')}")
            print(f"   result_city: {result.get('result_city')}")
            print(f"   result_state: {result.get('result_state')}")
            print(f"   result_zip: {result.get('result_zip')}")
        else:
            print("✅ Address data looks good")
    
    # Check if all results have unique data
    print(f"\n--- Summary ---")
    unique_licenses = detail_df['license_number'].nunique()
    unique_addresses = detail_df['result_address'].nunique()
    total_records = len(detail_df)
    
    print(f"Total records: {total_records}")
    print(f"Unique licenses: {unique_licenses}")
    print(f"Unique addresses: {unique_addresses}")
    
    if unique_licenses == total_records and unique_addresses > 1:
        print("✅ SUCCESS: All records have unique data")
        return True
    elif unique_licenses < total_records:
        print("❌ PROBLEM: Duplicate license numbers found")
        return False
    else:
        print("ℹ️ INFO: Results look correct (some addresses may be the same)")
        return True

if __name__ == "__main__":
    success = test_address_display()
    exit(0 if success else 1)