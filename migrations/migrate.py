#!/usr/bin/env python3
"""
PharmChecker Supabase Schema Documentation Tool

This script provides information about Supabase schema setup and verification.
Since Supabase requires manual SQL execution via the dashboard, this tool 
helps manage the setup process.
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SupabaseSchemaManager:
    def __init__(self):
        self.migrations_dir = Path(__file__).parent / 'migrations'
        self.consolidated_sql = Path(__file__).parent / 'supabase_setup_consolidated.sql'
        
    def show_setup_instructions(self):
        """Show manual Supabase setup instructions"""
        print("\n" + "="*80)
        print("🗄️  SUPABASE SCHEMA SETUP INSTRUCTIONS")
        print("="*80)
        print("\nPharmChecker uses Supabase as the database backend.")
        print("Schema setup requires manual SQL execution via Supabase Dashboard.\n")
        
        print("📋 SETUP STEPS:")
        print("-" * 40)
        print("1. Go to https://supabase.com/dashboard")
        print("2. Select your PharmChecker project")
        print("3. Open 'SQL Editor' in the left sidebar")
        print("4. Click '+ New query'")
        print("5. Copy and paste the consolidated schema (see below)")
        print("6. Click 'Run' to execute\n")
        
        if self.consolidated_sql.exists():
            print(f"📄 CONSOLIDATED SCHEMA FILE:")
            print(f"   {self.consolidated_sql}")
            print(f"   Copy the entire contents of this file to Supabase SQL Editor\n")
        else:
            print("❌ Consolidated schema file not found!")
            print(f"   Expected: {self.consolidated_sql}\n")
            
        print("🔍 VERIFICATION:")
        print("-" * 40)
        print("After setup, verify by running:")
        print("   python setup.py")
        print("   python system_test.py\n")
        
        print("📚 SCHEMA COMPONENTS:")
        print("-" * 40)
        self._list_migration_files()
        
    def _list_migration_files(self):
        """List available migration files"""
        if not self.migrations_dir.exists():
            print("❌ Migrations directory not found!")
            return
            
        migration_files = sorted(self.migrations_dir.glob("*.sql"))
        if not migration_files:
            print("❌ No migration files found!")
            return
            
        for i, file_path in enumerate(migration_files, 1):
            file_size = file_path.stat().st_size
            print(f"   {i}. {file_path.name} ({file_size:,} bytes)")
    
    def verify_supabase_connection(self):
        """Verify Supabase configuration and connection"""
        print("\n" + "="*60)
        print("🔍 SUPABASE CONNECTION VERIFICATION")
        print("="*60)
        
        # Check environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_anon_key = os.getenv('SUPABASE_ANON_KEY')
        supabase_service_key = os.getenv('SUPABASE_SERVICE_KEY')
        
        print("\n📋 Environment Variables:")
        print(f"   SUPABASE_URL: {'✅ Set' if supabase_url else '❌ Missing'}")
        print(f"   SUPABASE_ANON_KEY: {'✅ Set' if supabase_anon_key else '❌ Missing'}")
        print(f"   SUPABASE_SERVICE_KEY: {'✅ Set' if supabase_service_key else '❌ Missing'}")
        
        if not (supabase_url and supabase_anon_key):
            print("\n❌ Missing required Supabase credentials!")
            print("   Please set SUPABASE_URL and SUPABASE_ANON_KEY in your .env file")
            return False
            
        # Test connection
        try:
            from supabase import create_client
            
            # Use service key if available, otherwise anon key
            api_key = supabase_service_key or supabase_anon_key
            client = create_client(supabase_url, api_key)
            
            # Test basic connectivity
            response = client.table('datasets').select('*').limit(1).execute()
            
            print(f"\n✅ Connection successful!")
            print(f"   URL: {supabase_url}")
            print(f"   Using: {'Service Key' if supabase_service_key else 'Anon Key'}")
            
            # Check for core tables
            core_tables = ['datasets', 'pharmacies', 'search_results', 'match_scores', 'validated_overrides']
            print(f"\n📊 Core Tables Check:")
            
            table_status = {}
            for table in core_tables:
                try:
                    response = client.table(table).select('*').limit(1).execute()
                    table_status[table] = '✅ Exists'
                except Exception as e:
                    if 'does not exist' in str(e).lower():
                        table_status[table] = '❌ Missing'
                    else:
                        table_status[table] = f'⚠️  Error: {str(e)[:30]}...'
            
            for table, status in table_status.items():
                print(f"   {table}: {status}")
                
            missing_tables = [table for table, status in table_status.items() if '❌' in status]
            if missing_tables:
                print(f"\n❌ Schema setup incomplete. Missing tables: {', '.join(missing_tables)}")
                print("   Run schema setup instructions above.")
                return False
            else:
                print(f"\n✅ Schema verification passed!")
                return True
                
        except ImportError:
            print(f"\n❌ Supabase client not installed!")
            print("   Run: pip install supabase")
            return False
        except Exception as e:
            print(f"\n❌ Connection failed: {e}")
            return False
    
    def show_migration_status(self):
        """Show current migration status for documentation"""
        print("\n" + "="*60)
        print("📋 MIGRATION STATUS (Documentation Only)")
        print("="*60)
        print("\nFor Supabase, migrations are applied manually via SQL Dashboard.")
        print("This tool provides documentation and verification only.\n")
        
        # List available migrations
        self._list_migration_files()
        
        print(f"\n📄 For complete setup, use:")
        if self.consolidated_sql.exists():
            print(f"   {self.consolidated_sql}")
        else:
            print("   Individual migration files listed above")
            
        print(f"\n🔍 To verify setup:")
        print(f"   python migrations/migrate.py --verify")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='PharmChecker Supabase Schema Manager')
    parser.add_argument('--status', action='store_true', 
                       help='Show migration status and setup documentation')
    parser.add_argument('--verify', action='store_true',
                       help='Verify Supabase connection and schema')
    parser.add_argument('--instructions', action='store_true', 
                       help='Show detailed setup instructions')
    
    args = parser.parse_args()
    
    manager = SupabaseSchemaManager()
    
    if args.verify:
        success = manager.verify_supabase_connection()
        sys.exit(0 if success else 1)
    elif args.status:
        manager.show_migration_status()
    elif args.instructions:
        manager.show_setup_instructions()
    else:
        # Default: show instructions
        manager.show_setup_instructions()

if __name__ == '__main__':
    main()