#!/usr/bin/env python3
"""
Test direct import to Supabase using the new SHA256 image system
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from imports.states import StateImporter

load_dotenv()

def test_supabase_import():
    """Test importing states directly to Supabase with new image system"""
    
    print("🧪 Testing Supabase Import with SHA256 Images")
    print("=" * 50)
    
    # Initialize with Supabase backend
    importer = StateImporter(backend='supabase')
    
    # Test with a single JSON file first
    test_data_dir = Path('data/states_baseline')
    
    if not test_data_dir.exists():
        print(f"❌ Test data directory not found: {test_data_dir}")
        return False
    
    # Find the first parse JSON file
    json_files = list(test_data_dir.glob('**/*_parse.json'))
    if not json_files:
        print(f"❌ No *_parse.json files found in {test_data_dir}")
        return False
    
    test_file = json_files[0]
    print(f"📁 Testing with file: {test_file.name}")
    
    # Import single file
    try:
        success = importer.import_json(
            filepath=str(test_file),
            tag='sha256_test',
            screenshot_dir=None,  # No screenshots for this test
            created_by='test_user',
            description='SHA256 system test'
        )
        
        if success:
            print("✅ Import successful!")
            return True
        else:
            print("❌ Import failed")
            return False
            
    except Exception as e:
        print(f"❌ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_supabase_import()
    if success:
        print("\n🎉 Direct Supabase import with SHA256 system works!")
    else:
        print("\n❌ Direct import test failed")