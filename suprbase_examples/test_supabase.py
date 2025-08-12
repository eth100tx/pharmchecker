#!/usr/bin/env python3

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

try:
    from supabase import create_client, Client
    import tempfile
except ImportError as e:
    print(f"Missing required packages. Please install with:")
    print("pip install supabase python-dotenv")
    sys.exit(1)

load_dotenv()

def test_supabase_connection():
    """Test basic Supabase connection and operations"""
    
    # Get credentials from environment
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    
    if not url or not key:
        print("❌ Missing SUPABASE_URL or SUPABASE_ANON_KEY in .env")
        return False
    
    print(f"🔗 Connecting to Supabase at: {url}")
    
    try:
        # Create client
        supabase: Client = create_client(url, key)
        print("✅ Supabase client created successfully")
        
        # Test database operations
        print("\n📊 Testing database operations...")
        
        # Create a test table if it doesn't exist (this might fail due to permissions, which is ok)
        test_data = {
            "test_field": "Hello from Python!",
            "timestamp": datetime.now().isoformat(),
            "user": os.getenv("USER", "test_user")
        }
        
        # Try to insert into a test table (you may need to create this table in Supabase dashboard)
        try:
            result = supabase.table("test_table").insert(test_data).execute()
            print(f"✅ Database insert successful: {len(result.data)} row(s) inserted")
        except Exception as e:
            print(f"⚠️  Database insert failed (table may not exist): {str(e)}")
            print("   You may need to create a 'test_table' in your Supabase dashboard")
        
        # Try to read from the test table
        try:
            result = supabase.table("test_table").select("*").limit(5).execute()
            print(f"✅ Database select successful: {len(result.data)} row(s) retrieved")
            if result.data:
                print(f"   Sample data: {result.data[0]}")
        except Exception as e:
            print(f"⚠️  Database select failed: {str(e)}")
        
        # Test storage operations
        print("\n💾 Testing storage operations...")
        
        try:
            # List buckets
            buckets = supabase.storage.list_buckets()
            print(f"✅ Storage connection successful. Found {len(buckets)} bucket(s)")
            
            if buckets:
                bucket_name = buckets[0].name
                print(f"   Using bucket: {bucket_name}")
                
                # Create a test file
                test_content = f"Test file created at {datetime.now()}\nFrom user: {os.getenv('USER', 'test_user')}"
                test_filename = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                
                # Upload test file
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp_file:
                    tmp_file.write(test_content)
                    tmp_file.flush()
                    
                    with open(tmp_file.name, 'rb') as file:
                        result = supabase.storage.from_(bucket_name).upload(
                            path=test_filename,
                            file=file,
                            file_options={"cache-control": "3600", "upsert": "true"}
                        )
                        print(f"✅ File upload successful: {test_filename}")
                
                # List files in bucket
                files = supabase.storage.from_(bucket_name).list()
                print(f"✅ File listing successful: {len(files)} file(s) in bucket")
                
                # Download the test file
                downloaded = supabase.storage.from_(bucket_name).download(test_filename)
                print(f"✅ File download successful: {len(downloaded)} bytes")
                
                # Clean up - delete the test file
                supabase.storage.from_(bucket_name).remove([test_filename])
                print(f"✅ Test file cleanup successful")
                
                # Clean up temp file
                os.unlink(tmp_file.name)
                
            else:
                print("⚠️  No storage buckets found. You may need to create a bucket in Supabase dashboard")
                
        except Exception as e:
            print(f"⚠️  Storage operations failed: {str(e)}")
            print("   You may need to create a storage bucket in your Supabase dashboard")
        
        print("\n🎉 Supabase connection test completed!")
        return True
        
    except Exception as e:
        print(f"❌ Supabase connection failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("🧪 Starting Supabase Connection Test")
    print("=" * 50)
    
    success = test_supabase_connection()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ Overall test status: SUCCESS")
        sys.exit(0)
    else:
        print("❌ Overall test status: FAILED")
        sys.exit(1)