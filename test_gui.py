#!/usr/bin/env python3
"""
Test script for PharmChecker GUI
Validates core functionality without requiring database
"""

import sys
import os
import pandas as pd

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.database import DatabaseManager
from utils.display import format_score, format_status_badge, create_status_distribution_chart

def test_database_manager():
    """Test database manager with sample data"""
    print("Testing Database Manager...")
    
    db = DatabaseManager(use_production=False)
    
    # Test datasets
    datasets = db.get_datasets()
    print(f"Available datasets: {datasets}")
    
    # Test dataset stats
    stats = db.get_dataset_stats('pharmacies', '2024-01-15')
    print(f"Dataset stats: {stats}")
    
    # Test results matrix
    results_df = db.get_results_matrix('baseline', '2024-01-15', None)
    print(f"Results matrix shape: {results_df.shape}")
    print(f"Status distribution: {results_df['status_bucket'].value_counts().to_dict()}")
    
    # Test missing scores
    missing_df = db.find_missing_scores('baseline', '2024-01-15')
    print(f"Missing scores: {len(missing_df)} pairs")
    
    # Test scoring statistics
    stats = db.get_scoring_statistics('baseline', '2024-01-15')
    print(f"Scoring stats: {stats}")
    
    print("✅ Database Manager tests passed")

def test_display_utilities():
    """Test display utility functions"""
    print("\nTesting Display Utilities...")
    
    # Test score formatting
    assert format_score(96.5) == "96.5%"
    assert format_score(None) == "No Score"
    
    # Test status badge formatting
    badge = format_status_badge('match')
    assert '✅' in badge and 'Match' in badge
    
    # Test chart creation with sample data
    sample_df = pd.DataFrame({
        'status_bucket': ['match', 'match', 'weak match', 'no match', 'no data']
    })
    
    chart = create_status_distribution_chart(sample_df)
    assert chart is not None
    
    print("✅ Display utilities tests passed")

def test_integration():
    """Test integration between components"""
    print("\nTesting Integration...")
    
    db = DatabaseManager(use_production=False)
    
    # Test full workflow
    datasets = db.get_datasets()
    assert 'pharmacies' in datasets
    assert 'states' in datasets
    
    # Test results matrix retrieval and display
    results_df = db.get_results_matrix('baseline', '2024-01-15', None)
    assert not results_df.empty
    assert 'pharmacy_name' in results_df.columns
    assert 'status_bucket' in results_df.columns
    
    # Test filtering
    matches = results_df[results_df['status_bucket'] == 'match']
    print(f"Found {len(matches)} matches")
    
    print("✅ Integration tests passed")

def main():
    """Run all tests"""
    print("PharmChecker GUI Test Suite")
    print("=" * 40)
    
    try:
        test_database_manager()
        test_display_utilities()
        test_integration()
        
        print("\n🎉 All tests passed! GUI is ready for use.")
        print("\nTo run the GUI:")
        print("  streamlit run app.py")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()