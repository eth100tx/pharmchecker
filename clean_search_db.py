#!/usr/bin/env python3
"""
Clean search database - removes all search-related data while preserving pharmacies
"""
import os
import shutil
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
            # Check what we have before cleaning (using optimized schema)
            cur.execute("SELECT COUNT(*) FROM search_results")
            results_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM images")
            images_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM datasets WHERE kind = 'states'")
            state_datasets_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM pharmacies")
            pharmacy_count = cur.fetchone()[0]
            
            print(f"Before cleaning:")
            print(f"  - Search results: {results_count} (merged table)")
            print(f"  - Images: {images_count}")
            print(f"  - State datasets: {state_datasets_count}")
            print(f"  - Pharmacies: {pharmacy_count} (will be preserved)")
            
            if results_count == 0 and images_count == 0:
                print("✅ Database is already clean!")
                return
            
            # Delete in proper order to respect foreign key constraints (optimized schema)
            print("\n🗑️ Deleting search data...")
            
            # Delete match scores first (references search_results)
            cur.execute("DELETE FROM match_scores")
            deleted_scores = cur.rowcount
            print(f"  - Deleted {deleted_scores} match scores")
            
            # Delete validated overrides (if any exist)  
            cur.execute("DELETE FROM validated_overrides")
            deleted_overrides = cur.rowcount
            print(f"  - Deleted {deleted_overrides} validated overrides")
            
            # Delete images (may reference search_results)
            cur.execute("DELETE FROM images")
            deleted_images = cur.rowcount
            print(f"  - Deleted {deleted_images} image records")
            
            # Delete search results from merged table
            cur.execute("DELETE FROM search_results")
            deleted_results = cur.rowcount
            print(f"  - Deleted {deleted_results} search results")
            
            # Delete state datasets (but preserve pharmacy datasets)
            cur.execute("DELETE FROM datasets WHERE kind = 'states'")
            deleted_datasets = cur.rowcount
            print(f"  - Deleted {deleted_datasets} state datasets")
            
            # Commit all changes
            conn.commit()
            
            # Clean image cache directory
            print("\n🗑️ Cleaning image cache...")
            cache_dir = Path('image_cache')
            if cache_dir.exists():
                # Count files before deletion
                cache_files = list(cache_dir.rglob('*'))
                cache_file_count = len([f for f in cache_files if f.is_file()])
                
                # Remove entire cache directory
                shutil.rmtree(cache_dir)
                print(f"  - Deleted {cache_file_count} cached image files")
                print(f"  - Removed image_cache directory")
            else:
                print("  - No image cache directory found")

            print(f"\n✅ Database and image cache cleaned successfully!")
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
    response = input("This will delete ALL search data (search results, images, image cache). Continue? (y/N): ")
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