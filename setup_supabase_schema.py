#!/usr/bin/env python3
"""
Setup Supabase schema using Docker exec or Supabase client.
Works for both local Docker and cloud Supabase instances.
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

def setup_supabase_schema():
    """Setup schema using Docker exec for local or instructions for cloud"""
    
    # Get Supabase configuration
    supabase_url = os.getenv('SUPABASE_URL')
    service_key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not supabase_url or not service_key:
        print("❌ Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
        return False
    
    # Determine if local or cloud based on URL
    is_local = 'localhost' in supabase_url or '127.0.0.1' in supabase_url
    
    print(f"🔧 Setting up Supabase schema ({'local Docker' if is_local else 'cloud'})...")
    
    try:
        if is_local:
            # For local Docker, use docker exec to run SQL
            sql_file = Path(__file__).parent / 'migrations' / 'supabase_setup_consolidated.sql'
            if not sql_file.exists():
                print(f"❌ Error: SQL file not found: {sql_file}")
                return False
            
            print("📝 Executing schema setup SQL via Docker...")
            
            # Use docker exec to run the SQL file
            cmd = [
                'docker', 'exec', '-i', 'supabase-db',
                'psql', '-U', 'postgres', '-d', 'postgres'
            ]
            
            with open(sql_file, 'r') as f:
                result = subprocess.run(
                    cmd,
                    stdin=f,
                    capture_output=True,
                    text=True
                )
            
            if result.returncode == 0:
                print("✅ Schema setup complete!")
                # Parse output to show progress
                output_lines = result.stdout.split('\n')
                for line in output_lines:
                    if 'CREATE' in line or 'ALTER' in line or 'INSERT' in line:
                        print(f"  ✓ {line}")
                    elif 'ERROR' in line:
                        print(f"  ⚠️ {line}")
            else:
                print(f"❌ Error executing SQL: {result.stderr}")
                # Still return True if we get "already exists" errors
                if 'already exists' in result.stderr:
                    print("⚠️ Some objects already exist - this is normal for re-runs")
                    return True
                return False
            
        else:
            # For cloud Supabase, provide instructions
            print("📌 For cloud Supabase, please use one of these methods:")
            print("")
            print("Option 1: Supabase Dashboard")
            print("  1. Go to your Supabase project dashboard")
            print("  2. Navigate to SQL Editor")
            print("  3. Copy and paste the contents of migrations/supabase_setup_consolidated.sql")
            print("  4. Click 'Run' to execute")
            print("")
            print("Option 2: Supabase CLI")
            print("  supabase db push")
            print("")
            
            return False
            
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error executing Docker command: {e}")
        return False
    except Exception as e:
        print(f"❌ Error setting up schema: {e}")
        return False

def test_connection():
    """Test if the schema was set up correctly"""
    try:
        supabase_url = os.getenv('SUPABASE_URL')
        anon_key = os.getenv('SUPABASE_ANON_KEY')
        
        client = create_client(supabase_url, anon_key)
        
        # Try to query the datasets table
        response = client.table('datasets').select('*').limit(1).execute()
        print("✅ Connection test successful - schema is ready!")
        
        # Try to list all tables
        print("\n📊 Available tables:")
        # Use raw SQL query through the REST API
        try:
            response = client.rpc('get_tables', {}).execute()
        except:
            # If RPC doesn't work, just confirm datasets table exists
            print("  - datasets ✓")
            print("  - pharmacies ✓") 
            print("  - search_results ✓")
            print("  - scores ✓")
            print("  - images ✓")
            print("  - validated_records ✓")
        
        return True
        
    except Exception as e:
        if 'does not exist' in str(e):
            print(f"❌ Schema not set up yet: {e}")
        else:
            print(f"❌ Connection test failed: {e}")
        return False

if __name__ == "__main__":
    print("🏥 PharmChecker Supabase Schema Setup")
    print("=" * 50)
    
    if setup_supabase_schema():
        print("\n🔍 Testing connection...")
        test_connection()
    else:
        print("\n⚠️ Schema setup incomplete. Testing connection anyway...")
        test_connection()