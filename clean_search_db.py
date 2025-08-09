#!/usr/bin/env python3
"""
Clean search database - removes all search-related data while preserving pharmacies
"""
import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg2

# Load environment first
load_dotenv()

def get_db_connection():
    """Get database connection"""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', 5432)),
        database=os.getenv('DB_NAME', 'pharmchecker'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD')
    )

def clean_search_data():
    """Clean all search-related data from database"""
    
    print("🧹 Cleaning search database...")
    
    try:
        conn = get_db_connection()
        
        with conn.cursor() as cur:
            # Check what we have before cleaning
            cur.execute("SELECT COUNT(*) FROM search_results")
            results_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM searches")
            searches_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM images")
            images_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM datasets WHERE kind = 'states'")
            state_datasets_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM pharmacies")
            pharmacy_count = cur.fetchone()[0]
            
            print(f"Before cleaning:")
            print(f"  - Search results: {results_count}")
            print(f"  - Searches: {searches_count}")
            print(f"  - Images: {images_count}")
            print(f"  - State datasets: {state_datasets_count}")
            print(f"  - Pharmacies: {pharmacy_count} (will be preserved)")
            
            if results_count == 0 and searches_count == 0 and images_count == 0:
                print("✅ Database is already clean!")
                return
            
            # Delete in proper order to respect foreign key constraints
            print("\n🗑️ Deleting search data...")
            
            # Delete search results first (references searches)
            cur.execute("DELETE FROM search_results")
            deleted_results = cur.rowcount
            print(f"  - Deleted {deleted_results} search results")
            
            # Delete match scores (if any exist)
            cur.execute("DELETE FROM match_scores")
            deleted_scores = cur.rowcount
            print(f"  - Deleted {deleted_scores} match scores")
            
            # Delete validated overrides (if any exist)  
            cur.execute("DELETE FROM validated_overrides")
            deleted_overrides = cur.rowcount
            print(f"  - Deleted {deleted_overrides} validated overrides")
            
            # Delete images
            cur.execute("DELETE FROM images")
            deleted_images = cur.rowcount
            print(f"  - Deleted {deleted_images} image records")
            
            # Delete searches
            cur.execute("DELETE FROM searches")
            deleted_searches = cur.rowcount
            print(f"  - Deleted {deleted_searches} searches")
            
            # Delete state datasets (but preserve pharmacy datasets)
            cur.execute("DELETE FROM datasets WHERE kind = 'states'")
            deleted_datasets = cur.rowcount
            print(f"  - Deleted {deleted_datasets} state datasets")
            
            # Commit all changes
            conn.commit()
            
            print(f"\n✅ Database cleaned successfully!")
            print(f"   Pharmacy data preserved: {pharmacy_count} pharmacies remain")
            
    except Exception as e:
        print(f"❌ Error cleaning database: {e}")
        if 'conn' in locals():
            conn.rollback()
        return False
        
    finally:
        if 'conn' in locals():
            conn.close()
    
    return True

def main():
    """Main cleaning process"""
    print("PharmChecker Database Cleaner")
    print("=" * 40)
    
    # Confirm before cleaning
    response = input("This will delete ALL search data (searches, results, images). Continue? (y/N): ")
    if response.lower() != 'y':
        print("Cleaning cancelled.")
        return
    
    success = clean_search_data()
    
    if success:
        print("\n" + "=" * 40)
        print("🎯 Next steps:")
        print("1. Run: python -c \"from imports.states import StateImporter; StateImporter().import_directory('data/states_baseline', created_by='user')\"")
        print("2. Or use the command provided separately")
        print("\nDatabase is ready for fresh state data import!")

if __name__ == "__main__":
    main()