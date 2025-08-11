#!/usr/bin/env python3
"""
Test validation lookup specifically for the Belmar-PA case
"""

import sys
import os
import pandas as pd
import streamlit as st

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_validation_lookup():
    """Test validation lookup for Belmar-PA-NP000382"""
    print("🧪 Testing validation lookup...")
    
    # Initialize minimal session state
    st.session_state.loaded_data = {
        'comprehensive_results': None,
        'validations': {},
        'loaded_tags': None,
        'last_load_time': None
    }
    
    # Load data like the GUI would
    from utils.validation_local import load_dataset_combination
    
    success = load_dataset_combination(
        "test_pharmacies (2)", 
        "states_baseline", 
        "validation_20250810_161816"
    )
    
    if not success:
        print("❌ Failed to load data")
        return
    
    print("✅ Data loaded successfully")
    
    # Test the specific lookup that's failing
    from utils.validation_local import get_validation_status
    
    # Test cases based on what we expect
    test_cases = [
        ("Belmar", "PA", "NP000382"),  # Should find validation
        ("Belmar", "PA", "NP002169"),  # Should not find validation  
        ("BPI Labs", "FL", ""),        # Should find empty validation
        ("Nonexistent", "XX", "123"),  # Should not find
    ]
    
    for pharmacy_name, search_state, license_number in test_cases:
        print(f"\n🔍 Testing: {pharmacy_name} - {search_state} - {license_number or 'EMPTY'}")
        
        validation = get_validation_status(pharmacy_name, search_state, license_number)
        
        if validation:
            print(f"   ✅ Found: {validation['override_type']}")
        else:
            print(f"   ❌ Not found")
    
    # Show all available validations
    validations = st.session_state.loaded_data['validations']
    print(f"\n📋 All available validations ({len(validations)}):")
    for i, (key, val) in enumerate(validations.items()):
        print(f"   {i+1}. {key[0]} - {key[1]} - {key[2] or 'EMPTY'}: {val['override_type']}")

if __name__ == "__main__":
    test_validation_lookup()