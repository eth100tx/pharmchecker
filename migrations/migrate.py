#!/usr/bin/env python3
"""
PharmChecker Database Migration Runner

This script applies database migrations to either local PostgreSQL or Supabase.
It tracks applied migrations to avoid duplicate applications.
"""

import os
import sys
import psycopg2
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MigrationRunner:
    def __init__(self, target: str = 'local'):
        self.target = target
        self.migrations_dir = Path(__file__).parent / 'migrations'
        self.connection = None
        
    def get_connection(self):
        """Get database connection based on target"""
        if self.target == 'supabase':
            return self._get_supabase_connection()
        else:
            return self._get_local_connection()
    
    def _get_supabase_connection(self):
        """Connect to Supabase - manual setup required"""
        raise NotImplementedError(
            "Supabase migrations require manual setup. Please:\n\n"
            "1. Go to https://supabase.com/dashboard\n"
            "2. Select your project\n" 
            "3. Open SQL Editor\n"
            "4. Run these migration files in order:\n\n"
            "   MIGRATION 1 - Initial Schema:\n"
            "   Copy/paste: migrations/migrations/20240101000000_initial_schema.sql\n\n"
            "   MIGRATION 2 - Functions:\n"
            "   Copy/paste: migrations/migrations/20240101000001_comprehensive_functions.sql\n\n"
            "   MIGRATION 3 - Indexes:\n"
            "   Copy/paste: migrations/migrations/20240101000002_indexes_and_performance.sql\n\n"
            "After manual setup, both databases will have identical schemas."
        )
    
    def _get_local_connection(self):
        """Connect to local PostgreSQL"""
        from dotenv import load_dotenv
        load_dotenv()
        
        return psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 5432)),
            database=os.getenv('DB_NAME', 'pharmchecker'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', '')
        )
    
    def ensure_migration_table(self):
        """Create migration tracking table if it doesn't exist"""
        with self.connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pharmchecker_migrations (
                    version VARCHAR(255) PRIMARY KEY,
                    name VARCHAR(255),
                    applied_at TIMESTAMP DEFAULT NOW()
                );
            """)
            self.connection.commit()
    
    def get_applied_migrations(self) -> List[str]:
        """Get list of already applied migrations"""
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT version FROM pharmchecker_migrations ORDER BY version")
            return [row[0] for row in cursor.fetchall()]
    
    def get_available_migrations(self) -> List[Tuple[str, str, Path]]:
        """Get list of available migration files"""
        migrations = []
        for file_path in sorted(self.migrations_dir.glob('*.sql')):
            version = file_path.stem
            name = version.replace('_', ' ').title()
            migrations.append((version, name, file_path))
        return migrations
    
    def apply_migration(self, version: str, name: str, file_path: Path):
        """Apply a single migration"""
        logger.info(f"Applying migration {version}: {name}")
        
        # Read migration file
        with open(file_path, 'r') as f:
            sql_content = f.read()
        
        # Execute migration
        with self.connection.cursor() as cursor:
            cursor.execute(sql_content)
            
            # Record migration as applied
            cursor.execute(
                "INSERT INTO pharmchecker_migrations (version, name) VALUES (%s, %s)",
                (version, name)
            )
            
            self.connection.commit()
        
        logger.info(f"✅ Applied migration {version}")
    
    def run_migrations(self):
        """Run all pending migrations"""
        self.connection = self.get_connection()
        
        try:
            self.ensure_migration_table()
            
            applied = set(self.get_applied_migrations())
            available = self.get_available_migrations()
            
            pending = [(v, n, p) for v, n, p in available if v not in applied]
            
            if not pending:
                logger.info("✅ No pending migrations")
                return
            
            logger.info(f"Found {len(pending)} pending migrations")
            
            for version, name, file_path in pending:
                self.apply_migration(version, name, file_path)
            
            logger.info(f"✅ Successfully applied {len(pending)} migrations to {self.target}")
            
        finally:
            if self.connection:
                self.connection.close()
    
    def show_status(self):
        """Show migration status"""
        self.connection = self.get_connection()
        
        try:
            self.ensure_migration_table()
            
            applied = set(self.get_applied_migrations())
            available = self.get_available_migrations()
            
            print(f"\n📊 Migration Status ({self.target})")
            print("=" * 50)
            
            for version, name, file_path in available:
                status = "✅ Applied" if version in applied else "⏳ Pending"
                print(f"{status} | {version} | {name}")
            
            print(f"\nTotal: {len(available)} migrations, {len(applied)} applied")
            
        finally:
            if self.connection:
                self.connection.close()

def main():
    parser = argparse.ArgumentParser(description='PharmChecker Migration Runner')
    parser.add_argument('--target', choices=['local', 'supabase'], default='local',
                       help='Target database (default: local)')
    parser.add_argument('--status', action='store_true',
                       help='Show migration status instead of running migrations')
    
    args = parser.parse_args()
    
    runner = MigrationRunner(target=args.target)
    
    try:
        if args.status:
            runner.show_status()
        else:
            runner.run_migrations()
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()