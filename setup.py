#!/usr/bin/env python3
"""
PharmChecker Setup Script
This script sets up the database infrastructure and verifies the installation.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import Optional, List, Tuple
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class PharmCheckerSetup:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.env_file = self.project_root / '.env'
        self.env_example = self.project_root / '.env.example'
        self.requirements_file = self.project_root / 'requirements.txt'
        self.schema_file = self.project_root / 'schema.sql'
        self.functions_file = self.project_root / 'functions_comprehensive.sql'
        self.data_dir = self.project_root / 'data'
        
        self.db_config = None
        
    def run_setup(self) -> bool:
        """Run the complete setup process"""
        logger.info("🏥 PharmChecker Setup Starting...")
        
        steps = [
            ("Checking environment file", self.check_env_file),
            ("Installing Python dependencies", self.install_dependencies),
            ("Loading configuration", self.load_configuration),
            ("Testing database connection", self.test_db_connection),
            ("Creating database schema", self.create_schema),
            ("Creating database functions", self.create_functions),
            ("Setting up data directories", self.setup_data_directories),
            ("Creating initial admin user", self.create_admin_user),
            ("Running verification tests", self.run_verification),
        ]
        
        for step_name, step_func in steps:
            logger.info(f"📋 {step_name}...")
            try:
                if not step_func():
                    logger.error(f"❌ Failed: {step_name}")
                    return False
                logger.info(f"✅ Completed: {step_name}")
            except Exception as e:
                logger.error(f"❌ Error in {step_name}: {str(e)}")
                return False
        
        logger.info("🎉 PharmChecker setup completed successfully!")
        self.print_next_steps()
        return True
    
    def check_env_file(self) -> bool:
        """Check if .env file exists, create from example if not"""
        if not self.env_file.exists():
            if not self.env_example.exists():
                logger.error("Neither .env nor .env.example found!")
                return False
            
            logger.info("Creating .env from .env.example...")
            with open(self.env_example) as src, open(self.env_file, 'w') as dst:
                content = src.read()
                dst.write(content)
            
            logger.warning("⚠️  IMPORTANT: Please edit .env file with your database credentials!")
            logger.warning("   The default password is set to 'your_password_here' - you MUST change this.")
            
            response = input("Have you updated the .env file with correct database credentials? (y/N): ")
            if response.lower() != 'y':
                logger.error("Please update .env file first, then run setup again.")
                return False
        
        # Load and validate .env
        load_dotenv(self.env_file)
        
        required_vars = ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            logger.error(f"Missing required environment variables: {missing_vars}")
            return False
        
        # Check for placeholder password
        if os.getenv('DB_PASSWORD') == 'your_password_here':
            logger.error("Please update DB_PASSWORD in .env file with your actual password!")
            return False
        
        return True
    
    def install_dependencies(self) -> bool:
        """Install Python dependencies"""
        if not self.requirements_file.exists():
            logger.error("requirements.txt not found!")
            return False
        
        try:
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', '-r', str(self.requirements_file)
            ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install dependencies: {e.stderr.decode()}")
            return False
    
    def load_configuration(self) -> bool:
        """Load database configuration from environment"""
        try:
            self.db_config = {
                'host': os.getenv('DB_HOST'),
                'port': int(os.getenv('DB_PORT')),
                'database': os.getenv('DB_NAME'),
                'user': os.getenv('DB_USER'),
                'password': os.getenv('DB_PASSWORD')
            }
            return True
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid configuration: {e}")
            return False
    
    def test_db_connection(self) -> bool:
        """Test database connection and create database if it doesn't exist"""
        # First try to connect to the target database
        try:
            conn = psycopg2.connect(**self.db_config)
            conn.close()
            return True
        except psycopg2.OperationalError as e:
            if "does not exist" in str(e):
                # Try to create the database
                logger.info(f"Database {self.db_config['database']} doesn't exist, creating it...")
                return self.create_database()
            else:
                logger.error(f"Database connection failed: {e}")
                return False
    
    def create_database(self) -> bool:
        """Create the database if it doesn't exist"""
        try:
            # Connect to postgres database to create the target database
            temp_config = self.db_config.copy()
            temp_config['database'] = 'postgres'
            
            conn = psycopg2.connect(**temp_config)
            conn.autocommit = True
            
            with conn.cursor() as cur:
                # Check if database exists
                cur.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s",
                    (self.db_config['database'],)
                )
                
                if not cur.fetchone():
                    # Create database
                    cur.execute(
                        sql.SQL("CREATE DATABASE {}").format(
                            sql.Identifier(self.db_config['database'])
                        )
                    )
                    logger.info(f"Created database {self.db_config['database']}")
            
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Failed to create database: {e}")
            return False
    
    def create_schema(self) -> bool:
        """Create database schema from schema.sql"""
        if not self.schema_file.exists():
            logger.error("schema.sql not found!")
            return False
        
        try:
            with open(self.schema_file) as f:
                schema_sql = f.read()
            
            conn = psycopg2.connect(**self.db_config)
            with conn.cursor() as cur:
                cur.execute(schema_sql)
            conn.commit()
            conn.close()
            
            return True
        except Exception as e:
            logger.error(f"Failed to create schema: {e}")
            return False
    
    def create_functions(self) -> bool:
        """Create database functions from functions_comprehensive.sql"""
        if not self.functions_file.exists():
            logger.error("functions_comprehensive.sql not found!")
            return False
        
        try:
            with open(self.functions_file) as f:
                functions_sql = f.read()
            
            conn = psycopg2.connect(**self.db_config)
            with conn.cursor() as cur:
                # Drop existing functions first to avoid conflicts
                cur.execute("DROP FUNCTION IF EXISTS get_results_matrix(text,text,text);")
                cur.execute("DROP FUNCTION IF EXISTS find_missing_scores(text,text);")
                
                # Create the new functions
                cur.execute(functions_sql)
            conn.commit()
            conn.close()
            
            return True
        except Exception as e:
            logger.error(f"Failed to create functions: {e}")
            return False
    
    def setup_data_directories(self) -> bool:
        """Create necessary data directories"""
        try:
            self.data_dir.mkdir(exist_ok=True)
            (self.data_dir / 'screenshots').mkdir(exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Failed to create data directories: {e}")
            return False
    
    def create_admin_user(self) -> bool:
        """Create an initial admin user"""
        try:
            conn = psycopg2.connect(**self.db_config)
            with conn.cursor() as cur:
                # Check if any users exist
                cur.execute("SELECT COUNT(*) FROM app_users")
                user_count = cur.fetchone()[0]
                
                if user_count == 0:
                    # Create admin user
                    admin_login = input("Enter admin GitHub username (or press Enter to skip): ").strip()
                    if admin_login:
                        cur.execute("""
                            INSERT INTO app_users (github_login, role, is_active)
                            VALUES (%s, 'admin', true)
                            ON CONFLICT (github_login) DO NOTHING
                        """, (admin_login,))
                        conn.commit()
                        logger.info(f"Created admin user: {admin_login}")
                    else:
                        logger.info("Skipped admin user creation - you can add users later")
            
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to create admin user: {e}")
            return False
    
    def run_verification(self) -> bool:
        """Run verification tests to ensure everything is working"""
        try:
            conn = psycopg2.connect(**self.db_config)
            with conn.cursor() as cur:
                # Test 1: Check all tables exist
                expected_tables = [
                    'datasets', 'pharmacies', 'search_results', 
                    'match_scores', 'validated_overrides', 'images', 'app_users'
                ]
                
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                actual_tables = {row[0] for row in cur.fetchall()}
                
                missing_tables = set(expected_tables) - actual_tables
                if missing_tables:
                    logger.error(f"Missing tables: {missing_tables}")
                    return False
                
                # Test 2: Check functions exist
                cur.execute("""
                    SELECT routine_name 
                    FROM information_schema.routines 
                    WHERE routine_schema = 'public'
                    AND routine_name IN ('get_results_matrix', 'find_missing_scores')
                """)
                functions = {row[0] for row in cur.fetchall()}
                
                expected_functions = {'get_results_matrix', 'find_missing_scores'}
                missing_functions = expected_functions - functions
                if missing_functions:
                    logger.error(f"Missing functions: {missing_functions}")
                    return False
                
                # Test 3: Check trigram extension
                cur.execute("""
                    SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'
                """)
                if not cur.fetchone():
                    logger.error("pg_trgm extension not installed!")
                    return False
                
                logger.info("✅ All verification tests passed!")
            
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False
    
    def print_next_steps(self) -> None:
        """Print next steps for the user"""
        logger.info("\n" + "="*60)
        logger.info("🎉 SETUP COMPLETE! Next steps:")
        logger.info("="*60)
        logger.info("1. Install sample data (optional):")
        logger.info("   python -c \"from imports.pharmacies import PharmacyImporter; print('Ready for data import')\"")
        logger.info("")
        logger.info("2. Run the Streamlit UI:")
        logger.info("   streamlit run app.py")
        logger.info("")
        logger.info("3. Or import data programmatically:")
        logger.info("   python -c \"from imports import *; print('Import modules ready')\"")
        logger.info("="*60)

def main():
    """Main entry point"""
    setup = PharmCheckerSetup()
    success = setup.run_setup()
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()