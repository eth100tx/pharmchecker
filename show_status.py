#!/usr/bin/env python3
"""
Show database status - datasets and data counts
"""
import os
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

def show_status():
    """Show database status"""
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Show datasets
        print("Datasets:")
        cur.execute('SELECT tag, kind, description, created_at FROM datasets ORDER BY created_at DESC')
        datasets = cur.fetchall()
        
        if not datasets:
            print("  (no datasets)")
        else:
            for row in datasets:
                tag, kind, description, created_at = row
                desc_short = description[:50] + "..." if description and len(description) > 50 else description or ""
                print(f"  {tag} ({kind}) - {desc_short}")
        
        # Show data counts
        print("\nData Counts:")
        
        cur.execute('SELECT COUNT(*) FROM pharmacies')
        pharmacy_count = cur.fetchone()[0]
        print(f"  Pharmacies: {pharmacy_count}")
        
        cur.execute('SELECT COUNT(*) FROM search_results')
        result_count = cur.fetchone()[0]
        print(f"  Search Results: {result_count}")
        
        # Count unique searches in merged table
        cur.execute('SELECT COUNT(DISTINCT (search_name, search_state)) FROM search_results')
        search_count = cur.fetchone()[0]
        print(f"  Unique Searches: {search_count}")
        
        cur.execute('SELECT COUNT(*) FROM images')
        image_count = cur.fetchone()[0]
        print(f"  Screenshots: {image_count}")
        
        # Show search breakdown if we have searches
        if search_count > 0:
            print("\nSearch Breakdown:")
            cur.execute("""
                SELECT search_name, search_state, COUNT(*) as result_count
                FROM search_results
                GROUP BY search_name, search_state
                ORDER BY search_name, search_state
            """)
            
            for row in cur.fetchall():
                name, state, count = row
                print(f"  {name} in {state}: {count} results")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error checking status: {e}")

if __name__ == "__main__":
    show_status()