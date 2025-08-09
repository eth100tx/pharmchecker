"""
Configuration management for PharmChecker
"""
import os
import logging
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'pharmchecker'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '12')
}

# Logging configuration
LOGGING_LEVEL = os.getenv('LOGGING_LEVEL', 'INFO')
LOGGING_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

def setup_logging():
    """Configure logging for the application"""
    logging.basicConfig(
        level=getattr(logging, LOGGING_LEVEL.upper()),
        format=LOGGING_FORMAT,
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def get_db_config() -> Dict[str, Any]:
    """Get database configuration"""
    return DB_CONFIG.copy()

# Data directories
DATA_DIR = os.getenv('DATA_DIR', 'data')
SCREENSHOTS_DIR = os.path.join(DATA_DIR, 'screenshots')

# Storage configuration
STORAGE_TYPE = os.getenv('STORAGE_TYPE', 'local')  # 'local' or 'supabase'
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Streamlit configuration
STREAMLIT_PORT = int(os.getenv('STREAMLIT_PORT', 8501))
STREAMLIT_HOST = os.getenv('STREAMLIT_HOST', '0.0.0.0')