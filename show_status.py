#!/usr/bin/env python3
"""
Show database status - datasets and data counts
"""
import os
import argparse
from dotenv import load_dotenv
from supabase import create_client

# Load environment first
load_dotenv()

def get_supabase_connection():
    """Get Supabase client connection"""
    url = os.getenv('SUPABASE_URL')
    service_key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not url or not service_key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env file")
    
    return create_client(url, service_key)

def show_status():
    """Show database status"""
    
    try:
        supabase = get_supabase_connection()
        
        # Show datasets
        print("Datasets:")
        datasets_response = supabase.table('datasets').select('tag, kind, description, created_at').order('created_at', desc=True).execute()
        datasets = datasets_response.data
        
        if not datasets:
            print("  (no datasets)")
        else:
            for row in datasets:
                tag = row['tag']
                kind = row['kind'] 
                description = row.get('description', '')
                created_at = row['created_at']
                desc_short = description[:50] + "..." if description and len(description) > 50 else description or ""
                print(f"  {tag} ({kind}) - {desc_short}")
        
        # Show data counts
        print("\nData Counts:")
        
        pharmacy_response = supabase.table('pharmacies').select('id', count='exact').execute()
        pharmacy_count = pharmacy_response.count if hasattr(pharmacy_response, 'count') else 0
        print(f"  Pharmacies: {pharmacy_count}")
        
        results_response = supabase.table('search_results').select('id', count='exact').execute()
        result_count = results_response.count if hasattr(results_response, 'count') else 0
        print(f"  Search Results: {result_count}")
        
        # Count unique searches using RPC call for complex query
        try:
            unique_searches_response = supabase.rpc('count_unique_searches').execute()
            search_count = unique_searches_response.data if unique_searches_response.data else 0
        except:
            # Fallback: get all search results and count unique combinations in Python
            all_results = supabase.table('search_results').select('search_name, search_state').execute()
            unique_combinations = set()
            for result in all_results.data:
                unique_combinations.add((result['search_name'], result['search_state']))
            search_count = len(unique_combinations)
        
        print(f"  Unique Searches: {search_count}")
        
        images_response = supabase.table('image_assets').select('content_hash', count='exact').execute()
        image_count = images_response.count if hasattr(images_response, 'count') else 0
        print(f"  Image Assets: {image_count}")
        
        # Show search breakdown if we have searches
        if search_count > 0:
            print("\nSearch Breakdown:")
            # Get search breakdown using RPC or fallback to Python aggregation
            try:
                breakdown_response = supabase.rpc('get_search_breakdown').execute()
                breakdown_data = breakdown_response.data
                for row in breakdown_data:
                    print(f"  {row['search_name']} in {row['search_state']}: {row['result_count']} results")
            except:
                # Fallback: aggregate in Python
                all_results = supabase.table('search_results').select('search_name, search_state').execute()
                breakdown = {}
                for result in all_results.data:
                    key = (result['search_name'], result['search_state'])
                    breakdown[key] = breakdown.get(key, 0) + 1
                
                for (name, state), count in sorted(breakdown.items()):
                    print(f"  {name} in {state}: {count} results")
        
    except Exception as e:
        print(f"❌ Error checking status: {e}")

def main():
    parser = argparse.ArgumentParser(description='Show PharmChecker database status')
    show_status()

if __name__ == "__main__":
    main()