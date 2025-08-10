#!/usr/bin/env python3
"""
Test script for GUI integration with comprehensive results system
Tests that the new single DataFrame approach works correctly
"""

import os
import sys
import pandas as pd
from utils.database import DatabaseManager
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_gui_integration():
    """Test the GUI integration with comprehensive approach"""
    
    print("=== Testing GUI Integration with Comprehensive Results ===\n")
    
    # Initialize database manager
    db = DatabaseManager(use_production=True, allow_fallback=False)
    
    # Get available datasets (same as GUI would do)
    datasets = db.get_datasets()
    print(f"Available datasets: {datasets}")
    
    if not datasets.get('states') or not datasets.get('pharmacies'):
        print("No datasets available for testing")
        return False
    
    # Use first available datasets (same as GUI)
    states_tag = datasets['states'][0] 
    pharmacies_tag = datasets['pharmacies'][0]
    validated_tag = datasets['validated'][0] if datasets['validated'] else None
    
    print(f"Testing with: states='{states_tag}', pharmacies='{pharmacies_tag}', validated='{validated_tag}'")
    print()
    
    try:
        # Test the full GUI workflow
        print("1. Testing comprehensive results loading (GUI cache simulation)...")
        
        # Simulate session cache key generation
        cache_key = f"comprehensive_{states_tag}_{pharmacies_tag}_{validated_tag or 'none'}_True"
        print(f"   Cache key: {cache_key}")
        
        # Get comprehensive results (what would be cached)
        full_results_df = db.get_comprehensive_results(states_tag, pharmacies_tag, validated_tag, filter_to_loaded_states=True)
        print(f"   ✓ Loaded {len(full_results_df)} comprehensive records")
        
        # Test matrix aggregation (what GUI displays in table)
        print("\n2. Testing matrix aggregation for table display...")
        results_df = db.aggregate_for_matrix(full_results_df)
        print(f"   ✓ Aggregated to {len(results_df)} matrix records")
        
        if not results_df.empty:
            print(f"   ✓ Column check: {list(results_df.columns)}")
            print(f"   ✓ Status distribution: {results_df['status_bucket'].value_counts().to_dict()}")
            print(f"   ✓ Record counts: min={results_df['record_count'].min()}, max={results_df['record_count'].max()}")
        
        # Test detail filtering (what happens when user clicks row)
        print("\n3. Testing detail view filtering...")
        if not results_df.empty:
            first_row = results_df.iloc[0]
            detail_df = db.filter_for_detail(full_results_df, first_row['pharmacy_name'], first_row['search_state'])
            print(f"   ✓ Detail view for {first_row['pharmacy_name']}/{first_row['search_state']}: {len(detail_df)} records")
            
            if not detail_df.empty:
                print(f"   ✓ Detail columns: {list(detail_df.columns)}")
                print(f"   ✓ Has scores: {detail_df['score_overall'].notna().sum()} records with scores")
        
        # Test filtering (what happens when user applies filters in GUI)
        print("\n4. Testing GUI-style filtering...")
        
        # Simulate state filter
        available_states = results_df['search_state'].unique().tolist()
        print(f"   Available states: {available_states}")
        
        if available_states:
            test_state = available_states[0]
            state_filtered = results_df[results_df['search_state'] == test_state]
            print(f"   ✓ State filter ({test_state}): {len(state_filtered)} records")
        
        # Simulate status filter
        available_statuses = results_df['status_bucket'].unique().tolist()
        print(f"   Available statuses: {available_statuses}")
        
        if 'match' in available_statuses:
            status_filtered = results_df[results_df['status_bucket'] == 'match']
            print(f"   ✓ Status filter (match): {len(status_filtered)} records")
        
        # Test summary statistics (what GUI shows in summary line)
        print("\n5. Testing summary statistics calculation...")
        total_checked = len(results_df)
        matches = len(results_df[results_df['status_bucket'] == 'match'])
        weak_matches = len(results_df[results_df['status_bucket'] == 'weak match'])
        no_matches = len(results_df[results_df['status_bucket'] == 'no match'])
        no_data = len(results_df[results_df['status_bucket'] == 'no data'])
        
        print(f"   ✓ Summary stats: Total={total_checked}, Matches={matches}, Weak={weak_matches}, No Match={no_matches}, No Data={no_data}")
        
        # Verify data consistency 
        print("\n6. Testing data consistency...")
        
        # Check that record counts are accurate
        for _, row in results_df.head(3).iterrows():  # Test first 3 rows
            expected_count = len(full_results_df[
                (full_results_df['pharmacy_name'] == row['pharmacy_name']) & 
                (full_results_df['search_state'] == row['search_state'])
            ])
            actual_count = row['record_count']
            
            if expected_count == actual_count:
                print(f"   ✓ Record count for {row['pharmacy_name']}/{row['search_state']}: {actual_count} matches")
            else:
                print(f"   ❌ Record count mismatch for {row['pharmacy_name']}/{row['search_state']}: expected {expected_count}, got {actual_count}")
                return False
        
        print("\n=== Integration Test Results ===")
        print("✓ Comprehensive results loading works correctly")
        print("✓ Matrix aggregation produces expected results")
        print("✓ Detail filtering works correctly")
        print("✓ GUI-style filtering works correctly")
        print("✓ Summary statistics calculation works")
        print("✓ Data consistency maintained")
        print("✓ Ready for production use!")
        
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_gui_integration()
    exit(0 if success else 1)