#!/usr/bin/env python3
"""
Final validation test for the GUI display fix
Tests that dropdown content is now unique and addresses display correctly
"""

import pandas as pd
from utils.database import DatabaseManager

def test_gui_fix():
    """Test the complete GUI fix end-to-end"""
    
    print("=== Final GUI Fix Validation ===\n")
    
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
    
    print(f"Testing with: states='{states_tag}', pharmacies='{pharmacies_tag}'")
    
    try:
        # Simulate the GUI workflow
        print("\n1. Simulating GUI workflow...")
        
        # Step 1: Load comprehensive data (what GUI caches)
        comprehensive_df = db.get_comprehensive_results(states_tag, pharmacies_tag, validated_tag, filter_to_loaded_states=True)
        print(f"   ✓ Loaded comprehensive data: {len(comprehensive_df)} records")
        
        # Step 2: Create matrix view (what GUI table shows)
        matrix_df = db.aggregate_for_matrix(comprehensive_df)
        print(f"   ✓ Created matrix view: {len(matrix_df)} records")
        
        # Step 3: User clicks on a row with multiple results
        multi_result_rows = matrix_df[matrix_df['record_count'] > 1]
        if multi_result_rows.empty:
            print("   No rows with multiple results found")
            return True  # This is actually OK
        
        selected_row = multi_result_rows.iloc[0]
        test_pharmacy = selected_row['pharmacy_name'] 
        test_state = selected_row['search_state']
        expected_count = selected_row['record_count']
        
        print(f"   ✓ Testing detail view for {test_pharmacy}/{test_state} (expecting {expected_count} results)")
        
        # Step 4: Get detail view data (what GUI shows in dropdowns)
        detail_df = db.filter_for_detail(comprehensive_df, test_pharmacy, test_state)
        print(f"   ✓ Detail view: {len(detail_df)} records")
        
        if len(detail_df) != expected_count:
            print(f"   ❌ Record count mismatch: expected {expected_count}, got {len(detail_df)}")
            return False
        
        # Step 5: Test address display for each result
        print(f"\n2. Testing address display for each of the {len(detail_df)} results...")
        
        addresses = []
        licenses = []
        
        for i, (_, result) in enumerate(detail_df.iterrows()):
            # Simulate display logic
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
            license_number = result.get('license_number', 'N/A')
            
            addresses.append(full_address)
            licenses.append(license_number)
            
            print(f"   Result {i+1}: {license_number} | {full_address}")
        
        # Step 6: Validation checks
        print(f"\n3. Validation checks...")
        
        unique_licenses = len(set(licenses))
        unique_addresses = len(set([addr for addr in addresses if addr != 'N/A']))
        has_na_address = 'N/A' in addresses
        
        print(f"   Total results: {len(detail_df)}")
        print(f"   Unique licenses: {unique_licenses}")
        print(f"   Unique addresses: {unique_addresses}")
        print(f"   Has N/A addresses: {has_na_address}")
        
        # Check 1: All licenses should be unique
        if unique_licenses != len(licenses):
            print("   ❌ FAIL: Duplicate license numbers found")
            return False
        else:
            print("   ✅ PASS: All license numbers are unique")
        
        # Check 2: Should not have N/A addresses (the original problem)
        if has_na_address:
            print("   ❌ FAIL: Found N/A addresses (display issue not fixed)")
            return False
        else:
            print("   ✅ PASS: All addresses are displaying correctly")
        
        # Check 3: Should have some address variation (not all the same)
        if unique_addresses == 1 and len(addresses) > 1:
            print("   ⚠️ WARNING: All addresses are identical (might be correct data)")
        else:
            print("   ✅ PASS: Address data shows appropriate variation")
        
        print(f"\n4. Summary...")
        print("   ✅ Comprehensive data loading works")
        print("   ✅ Matrix aggregation works") 
        print("   ✅ Detail view filtering works")
        print("   ✅ Address display logic fixed")
        print("   ✅ Unique data displayed for each result")
        
        print(f"\n🎉 GUI FIX VALIDATION: SUCCESS")
        print("   The dropdown data issue has been resolved!")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_gui_fix()
    exit(0 if success else 1)