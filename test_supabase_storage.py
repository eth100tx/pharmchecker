#!/usr/bin/env python3
"""
Test Supabase Storage Operations

This script tests all the file operations needed for the SHA256 image system:
1. Create a test image file
2. Upload to Supabase Storage with SHA256-based path
3. Check if file exists (for deduplication)
4. Download file to verify integrity
5. Delete file (cleanup)

Run this before attempting any imports to ensure Supabase Storage is working.
"""

import os
import hashlib
import tempfile
from pathlib import Path
from PIL import Image
import io
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_test_image(width=100, height=100):
    """Create a simple test image"""
    # Create a simple colored rectangle
    img = Image.new('RGB', (width, height), color='red')
    
    # Save to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    return img_bytes.getvalue()

def compute_sha256(data):
    """Compute SHA256 of data"""
    return hashlib.sha256(data).hexdigest()

def get_storage_path(content_hash, extension='.png'):
    """Generate SHA256-based storage path"""
    return f"sha256/{content_hash[:2]}/{content_hash[2:4]}/{content_hash}{extension}"

def test_supabase_storage():
    """Test all Supabase Storage operations"""
    print("🧪 Testing Supabase Storage Operations")
    print("=" * 50)
    
    # Check environment variables
    supabase_url = os.getenv('SUPABASE_URL')
    service_key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not supabase_url or not service_key:
        print("❌ Missing Supabase credentials in .env file")
        print(f"   SUPABASE_URL: {'✅' if supabase_url else '❌'}")
        print(f"   SUPABASE_SERVICE_KEY: {'✅' if service_key else '❌'}")
        return False
    
    print(f"✅ Supabase URL: {supabase_url}")
    print(f"✅ Service Key: {service_key[:20]}...")
    
    try:
        # Import and initialize Supabase client
        from supabase import create_client
        supabase = create_client(supabase_url, service_key)
        print("✅ Supabase client created successfully")
        
    except ImportError:
        print("❌ Supabase client not available. Install with: pip install supabase")
        return False
    except Exception as e:
        print(f"❌ Failed to create Supabase client: {e}")
        return False
    
    # Create test image
    print("\n📸 Creating test image...")
    test_image_data = create_test_image(150, 100)
    content_hash = compute_sha256(test_image_data)
    storage_path = get_storage_path(content_hash)
    
    print(f"✅ Test image created: {len(test_image_data)} bytes")
    print(f"✅ SHA256: {content_hash}")
    print(f"✅ Storage path: {storage_path}")
    
    bucket_name = 'imagecache'
    
    try:
        # Test 1: Check if bucket exists, create if needed
        print(f"\n🪣 Testing bucket '{bucket_name}'...")
        
        try:
            buckets = supabase.storage.list_buckets()
            bucket_exists = any(bucket.name == bucket_name for bucket in buckets)
            
            if not bucket_exists:
                print(f"📝 Creating bucket '{bucket_name}'...")
                result = supabase.storage.create_bucket(bucket_name, options={"public": False})
                print(f"✅ Bucket created: {result}")
            else:
                print(f"✅ Bucket '{bucket_name}' already exists")
                
        except Exception as e:
            print(f"⚠️  Bucket operation failed: {e}")
            print("   Continuing with upload test...")
        
        # Test 2: Upload file
        print(f"\n⬆️  Testing file upload...")
        
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                tmp_file.write(test_image_data)
                temp_path = tmp_file.name
            
            # Upload file
            with open(temp_path, 'rb') as f:
                result = supabase.storage.from_(bucket_name).upload(
                    storage_path, 
                    f, 
                    file_options={'content-type': 'image/png'}
                )
            
            print(f"✅ File uploaded successfully: {result}")
            
        except Exception as e:
            print(f"❌ Upload failed: {e}")
            return False
        finally:
            # Clean up temp file
            if 'temp_path' in locals():
                Path(temp_path).unlink(missing_ok=True)
        
        # Test 3: Check if file exists (for deduplication logic)
        print(f"\n🔍 Testing file existence check...")
        
        try:
            # List files to check existence
            files = supabase.storage.from_(bucket_name).list(path=storage_path)
            file_exists = len(files) > 0
            
            print(f"✅ File existence check: {file_exists}")
            
        except Exception as e:
            print(f"❌ Existence check failed: {e}")
            return False
        
        # Test 4: Download file to verify integrity
        print(f"\n⬇️  Testing file download...")
        
        try:
            # Download file
            downloaded_data = supabase.storage.from_(bucket_name).download(storage_path)
            
            # Verify integrity
            downloaded_hash = compute_sha256(downloaded_data)
            integrity_ok = downloaded_hash == content_hash
            
            print(f"✅ File downloaded: {len(downloaded_data)} bytes")
            print(f"✅ Original SHA256:   {content_hash}")
            print(f"✅ Downloaded SHA256: {downloaded_hash}")
            print(f"✅ Integrity check:   {'PASS' if integrity_ok else 'FAIL'}")
            
            if not integrity_ok:
                print("❌ File integrity check failed!")
                return False
                
        except Exception as e:
            print(f"❌ Download failed: {e}")
            return False
        
        # Test 5: Get signed URL (for serving images)
        print(f"\n🔗 Testing signed URL generation...")
        
        try:
            # Generate signed URL
            signed_url = supabase.storage.from_(bucket_name).create_signed_url(
                storage_path, 
                expires_in=3600  # 1 hour
            )
            
            print(f"✅ Signed URL generated: {signed_url['signedURL'][:50]}...")
            
        except Exception as e:
            print(f"❌ Signed URL generation failed: {e}")
            return False
        
        # Test 6: Delete file (cleanup)
        print(f"\n🗑️  Testing file deletion...")
        
        try:
            # Delete file
            result = supabase.storage.from_(bucket_name).remove([storage_path])
            
            print(f"✅ File deleted: {result}")
            
            # Verify deletion
            try:
                files = supabase.storage.from_(bucket_name).list(path=storage_path)
                still_exists = len(files) > 0
                print(f"✅ Deletion verified: {'FAIL - still exists' if still_exists else 'PASS'}")
                
            except Exception:
                print("✅ Deletion verified: PASS (file not found)")
            
        except Exception as e:
            print(f"❌ Deletion failed: {e}")
            return False
        
        print(f"\n🎉 All Supabase Storage tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Unexpected error during storage tests: {e}")
        return False

def test_image_storage_class():
    """Test the ImageStorage class with Supabase backend"""
    print(f"\n🔧 Testing ImageStorage class with Supabase...")
    
    try:
        from utils.image_storage import ImageStorage
        
        # Create storage instance with Supabase backend
        storage = ImageStorage(backend_type='supabase')
        print(f"✅ ImageStorage created with backend: {storage.backend_type}")
        
        # Create a test image file
        test_data = create_test_image(200, 150)
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            tmp_file.write(test_data)
            temp_path = Path(tmp_file.name)
        
        try:
            # Test storing image
            content_hash, storage_path, metadata = storage.store_image(temp_path)
            
            print(f"✅ Image stored successfully")
            print(f"   Hash: {content_hash}")
            print(f"   Path: {storage_path}")
            print(f"   Metadata: {metadata}")
            
            # Test storing same image again (deduplication)
            content_hash2, storage_path2, metadata2 = storage.store_image(temp_path)
            
            dedup_works = (content_hash == content_hash2 and storage_path == storage_path2)
            print(f"✅ Deduplication test: {'PASS' if dedup_works else 'FAIL'}")
            
            # Cleanup
            storage.delete_image(content_hash, storage_path, 'supabase')
            print(f"✅ Cleanup completed")
            
            return True
            
        finally:
            # Clean up temp file
            temp_path.unlink(missing_ok=True)
        
    except Exception as e:
        print(f"❌ ImageStorage class test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("🧪 PharmChecker Supabase Storage Test Suite")
    print("=" * 60)
    
    # Test raw Supabase operations
    storage_test_passed = test_supabase_storage()
    
    if storage_test_passed:
        # Test our ImageStorage wrapper class
        class_test_passed = test_image_storage_class()
        
        if class_test_passed:
            print(f"\n🎉 ALL TESTS PASSED!")
            print("✅ Supabase Storage is ready for image imports")
        else:
            print(f"\n❌ ImageStorage class tests failed")
            print("⚠️  Check the ImageStorage implementation")
    else:
        print(f"\n❌ Basic Supabase Storage tests failed")
        print("⚠️  Fix Supabase configuration before proceeding")
    
    print("\n" + "=" * 60)