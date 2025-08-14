#!/usr/bin/env python3
"""
Test the image display helper function
"""

import sys
import os
sys.path.append('.')
from utils.display import get_image_display_url

def test_image_display():
    """Test converting SHA256 storage paths to displayable URLs"""
    
    # Test with a real Supabase storage path
    test_path = "sha256/69/b1/69b1db6459a8172fec447cae5f7f830e4cd375160109d175a3e5fc6af9667a3c.png"
    test_storage_type = "supabase"
    
    print(f"Testing image display URL generation...")
    print(f"Storage path: {test_path}")
    print(f"Storage type: {test_storage_type}")
    
    try:
        url = get_image_display_url(test_path, test_storage_type)
        
        if url:
            print(f"✅ Generated URL: {url[:100]}...")
            return True
        else:
            print("❌ No URL generated")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == '__main__':
    success = test_image_display()
    if success:
        print("\n🎉 Image display helper function works!")
    else:
        print("\n❌ Image display helper function failed")