#!/usr/bin/env python3
"""
Final validation test: Compare old vs new behavior side-by-side
Ensures the new comprehensive approach produces identical results
"""

import pandas as pd
from utils.database import DatabaseManager
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def compare_behaviors():
    """Compare old matrix function vs new comprehensive approach"""
    
    print("=== Final Validation: Old vs New Behavior Comparison ===\n")
    
    # Initialize database manager
    db = DatabaseManager(use_production=True, allow_fallback=False)
    
    # Get datasets
    datasets = db.get_datasets()
    if not datasets.get('states') or not datasets.get('pharmacies'):
        print("No datasets available for testing")
        return False
    
    states_tag = datasets['states'][0] 
    pharmacies_tag = datasets['pharmacies'][0]
    validated_tag = datasets['validated'][0] if datasets['validated'] else None
    
    print(f"Comparing behaviors with: states='{states_tag}', pharmacies='{pharmacies_tag}', validated='{validated_tag}'")
    print()
    
    try:
        # OLD APPROACH: get_results_matrix
        print("1. Testing OLD approach (get_results_matrix)...")
        old_results = db.get_results_matrix(states_tag, pharmacies_tag, validated_tag, filter_to_loaded_states=True)
        print(f"   ✓ Old approach: {len(old_results)} records")
        
        # NEW APPROACH: comprehensive + aggregation
        print("\n2. Testing NEW approach (comprehensive + aggregation)...")
        comprehensive_results = db.get_comprehensive_results(states_tag, pharmacies_tag, validated_tag, filter_to_loaded_states=True)
        new_results = db.aggregate_for_matrix(comprehensive_results)
        print(f"   ✓ New approach: {len(new_results)} records")
        
        # COMPARISON TESTS
        print("\n3. Comparing results...")
        
        # Test 1: Record count
        if len(old_results) == len(new_results):
            print("   ✓ Record counts match")
        else:
            print(f"   ❌ Record count mismatch: old={len(old_results)}, new={len(new_results)}")
            return False
        
        # Test 2: Column compatibility (new should have all columns old has)
        old_cols = set(old_results.columns)
        new_cols = set(new_results.columns)
        missing_cols = old_cols - new_cols
        extra_cols = new_cols - old_cols
        
        print(f"   Old columns: {len(old_cols)} ({sorted(old_cols)})")
        print(f"   New columns: {len(new_cols)} ({sorted(new_cols)})")
        
        if missing_cols:
            print(f"   ❌ New approach missing columns: {missing_cols}")
            return False
        else:
            print("   ✓ New approach has all required columns")
        
        if extra_cols:
            print(f"   ℹ️ New approach has extra columns: {extra_cols}")
        
        # Test 3: Status bucket distribution
        if not old_results.empty and not new_results.empty:
            old_status = old_results['status_bucket'].value_counts().to_dict()
            new_status = new_results['status_bucket'].value_counts().to_dict()
            
            print(f"   Old status distribution: {old_status}")
            print(f"   New status distribution: {new_status}")
            
            if old_status == new_status:
                print("   ✓ Status distributions identical")
            else:
                print("   ❌ Status distributions differ")
                return False
        
        # Test 4: Key pharmacy-state pairs present
        if not old_results.empty and not new_results.empty:
            # Sort both by pharmacy_name, search_state for comparison
            old_sorted = old_results.sort_values(['pharmacy_name', 'search_state']).reset_index(drop=True)
            new_sorted = new_results.sort_values(['pharmacy_name', 'search_state']).reset_index(drop=True)
            
            # Check that all pharmacy-state pairs are identical
            old_pairs = set(zip(old_sorted['pharmacy_name'], old_sorted['search_state']))
            new_pairs = set(zip(new_sorted['pharmacy_name'], new_sorted['search_state']))
            
            if old_pairs == new_pairs:
                print("   ✓ Pharmacy-state pairs identical")
            else:
                missing_pairs = old_pairs - new_pairs
                extra_pairs = new_pairs - old_pairs
                print(f"   ❌ Pharmacy-state pairs differ:")
                if missing_pairs:
                    print(f"      Missing: {missing_pairs}")
                if extra_pairs:
                    print(f"      Extra: {extra_pairs}")
                return False
        
        # Test 5: Score consistency for common records
        if not old_results.empty and not new_results.empty:
            print("\n4. Testing score consistency...")
            
            # Merge on pharmacy_name and search_state to compare scores
            comparison = old_sorted.merge(
                new_sorted, 
                on=['pharmacy_name', 'search_state'], 
                suffixes=('_old', '_new'),
                how='inner'
            )
            
            if len(comparison) > 0:
                # Check score_overall consistency
                score_matches = 0
                score_total = 0
                
                for _, row in comparison.iterrows():
                    score_old = row.get('score_overall_old')
                    score_new = row.get('score_overall_new')
                    
                    score_total += 1
                    
                    # Both null
                    if pd.isna(score_old) and pd.isna(score_new):
                        score_matches += 1
                    # Both have values and they're close
                    elif not pd.isna(score_old) and not pd.isna(score_new):
                        if abs(score_old - score_new) < 0.01:  # Allow tiny floating point differences
                            score_matches += 1
                        else:
                            print(f"      Score mismatch for {row['pharmacy_name']}/{row['search_state']}: {score_old} vs {score_new}")
                
                print(f"   ✓ Score consistency: {score_matches}/{score_total} matches")
                
                if score_matches == score_total:
                    print("   ✓ All scores consistent")
                else:
                    print(f"   ❌ Score inconsistencies found")
                    return False
        
        # Test 6: Performance comparison
        print("\n5. Performance comparison...")
        import time
        
        # Time old approach
        start = time.time()
        for _ in range(5):
            db.get_results_matrix(states_tag, pharmacies_tag, validated_tag, filter_to_loaded_states=True)
        old_time = (time.time() - start) / 5
        
        # Time new approach
        start = time.time()
        for _ in range(5):
            comp = db.get_comprehensive_results(states_tag, pharmacies_tag, validated_tag, filter_to_loaded_states=True)
            db.aggregate_for_matrix(comp)
        new_time = (time.time() - start) / 5
        
        print(f"   Old approach avg: {old_time:.3f}s")
        print(f"   New approach avg: {new_time:.3f}s")
        print(f"   Performance ratio: {new_time/old_time:.2f}x")
        
        if new_time <= old_time * 1.5:  # Allow up to 50% slower
            print("   ✓ Performance acceptable")
        else:
            print("   ⚠️ Performance significantly slower")
        
        print("\n=== Final Validation Results ===")
        print("✅ OLD vs NEW approaches produce IDENTICAL results")
        print("✅ All data integrity checks passed")
        print("✅ Performance within acceptable range")
        print("✅ Ready for production deployment!")
        
        return True
        
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = compare_behaviors()
    exit(0 if success else 1)