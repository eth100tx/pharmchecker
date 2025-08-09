#!/usr/bin/env python3
"""
Update database functions for optimized schema
"""

from config import get_db_config
import psycopg2

def update_functions():
    """Drop and recreate functions with optimized schema"""
    
    # First, drop existing functions
    drop_sql = """
    DROP FUNCTION IF EXISTS get_results_matrix(text,text,text);
    DROP FUNCTION IF EXISTS find_missing_scores(text,text);
    """
    
    # Read optimized functions
    with open('functions_optimized.sql', 'r') as f:
        create_sql = f.read()
    
    with psycopg2.connect(**get_db_config()) as conn:
        with conn.cursor() as cur:
            print("Dropping existing functions...")
            cur.execute(drop_sql)
            
            print("Creating optimized functions...")
            cur.execute(create_sql)
        
        conn.commit()
    
    print("✅ Database functions updated successfully")

if __name__ == "__main__":
    update_functions()