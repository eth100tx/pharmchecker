#!/usr/bin/env python3
"""
Clean all data from PharmChecker database tables.
Removes all records from datasets, search_results, pharmacies, and validated_overrides.
Preserves schema and functions.
"""

import os
import sys
import argparse
from dotenv import load_dotenv
from supabase import create_client

# Load environment
load_dotenv()

def get_supabase_connection():
    """Get Supabase client connection"""
    url = os.getenv('SUPABASE_URL')
    service_key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not url or not service_key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env file")
    
    return create_client(url, service_key)

def clean_data_tables():
    """Clean all data tables in the correct order to avoid FK constraint violations."""
    try:
        supabase = get_supabase_connection()
        
        # Order matters: delete child tables first to avoid FK violations
        tables = ['validated_overrides', 'search_results', 'pharmacies', 'datasets']
        
        for table in tables:
            # Get count before deletion
            count_response = supabase.table(table).select('id', count='exact').execute()
            count = count_response.count if hasattr(count_response, 'count') else 0
            
            # Delete all records
            delete_response = supabase.table(table).delete().neq('id', 0).execute()
            print(f'  ✅ Cleared {table} ({count} records)')
        
        print('✅ All data tables cleared successfully')
        return True
        
    except Exception as e:
        print(f'❌ Error: {e}')
        return False


def main():
    parser = argparse.ArgumentParser(description='Clean all data from PharmChecker database')
    parser.add_argument('--backend', choices=['supabase'], default='supabase',
                       help='Database backend (only supabase supported)')
    
    args = parser.parse_args()
    
    success = clean_data_tables()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()