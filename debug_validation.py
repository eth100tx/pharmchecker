#!/usr/bin/env python3
"""
Debug script for validation data loading issues
"""

import sys
import os
import pandas as pd

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def debug_comprehensive_results():
    """Debug the comprehensive results query to see what validation columns are available"""
    print("🔍 Debugging comprehensive results query...")
    
    try:
        from utils.database import get_database_manager
        
        db = get_database_manager()
        
        # Use the same parameters that would be used in the GUI
        states_tag = "states_baseline"
        pharmacies_tag = "test_pharmacies (2)"
        validated_tag = "validation_20250810_161816"
        
        print(f"Loading: {pharmacies_tag} + {states_tag} + {validated_tag}")
        
        comprehensive_results = db.get_comprehensive_results(
            states_tag, pharmacies_tag, validated_tag, filter_to_loaded_states=False
        )
        
        print(f"✅ Loaded {len(comprehensive_results)} comprehensive results")
        print(f"📊 Columns: {list(comprehensive_results.columns)}")
        
        # Look for validation-related columns
        validation_columns = [col for col in comprehensive_results.columns if 'validation' in col.lower() or 'override' in col.lower()]
        print(f"🔍 Validation columns: {validation_columns}")
        
        # Check if we have any validation data
        if validation_columns:
            for col in validation_columns:
                non_null_count = comprehensive_results[col].notna().sum()
                print(f"   {col}: {non_null_count} non-null values")
                
                if non_null_count > 0:
                    sample_values = comprehensive_results[col].dropna().head(3).tolist()
                    print(f"   Sample values: {sample_values}")
        
        # Check specific record that should be validated
        belmar_pa_records = comprehensive_results[
            (comprehensive_results['pharmacy_name'] == 'Belmar') & 
            (comprehensive_results['search_state'] == 'PA')
        ]
        
        print(f"\n🎯 Belmar-PA records found: {len(belmar_pa_records)}")
        if not belmar_pa_records.empty:
            print("Belmar-PA record details:")
            for idx, row in belmar_pa_records.head(2).iterrows():
                print(f"  License: {row.get('license_number', 'N/A')}")
                for col in validation_columns:
                    print(f"  {col}: {row.get(col, 'N/A')}")
        
        return comprehensive_results
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def debug_validation_parsing():
    """Debug validation data parsing"""
    print("\n🧪 Testing validation parsing...")
    
    comprehensive_results = debug_comprehensive_results()
    if comprehensive_results is None:
        return
    
    # Parse validation state like the load function does
    validations = {}
    validation_columns = [col for col in comprehensive_results.columns if 'validation' in col.lower() or 'override' in col.lower()]
    
    for _, row in comprehensive_results.iterrows():
        # Try multiple possible column names for validation override type
        override_type = (row.get('validation_override_type') or 
                       row.get('override_type') or 
                       row.get('validated_override_type'))
        
        if pd.notna(override_type):
            key = (row['pharmacy_name'], row['search_state'], 
                   row.get('license_number', '') or '')
            validations[key] = {
                'override_type': override_type,
                'reason': (row.get('validation_reason') or 
                         row.get('reason') or 
                         row.get('validated_reason', '')),
                'validated_by': (row.get('validation_validated_by') or 
                               row.get('validated_by') or 
                               row.get('validated_validated_by', '')),
                'validated_at': (row.get('validation_validated_at') or 
                               row.get('validated_at') or 
                               row.get('validated_validated_at'))
            }
    
    print(f"📝 Parsed {len(validations)} validations")
    
    if validations:
        print("Sample validations:")
        for i, (key, val) in enumerate(list(validations.items())[:5]):
            print(f"  {i+1}. {key[0]}-{key[1]}-{key[2] or 'EMPTY'}: {val['override_type']}")
    else:
        print("⚠️ No validations parsed - check column names")

if __name__ == "__main__":
    debug_validation_parsing()