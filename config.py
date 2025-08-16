"""
Configuration management for PharmChecker
Handles environment variables and Supabase configuration
"""
import os
import logging
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Configuration
API_CACHE_TTL = int(os.getenv('API_CACHE_TTL', '300'))  # Cache timeout in seconds
API_RETRY_COUNT = int(os.getenv('API_RETRY_COUNT', '3'))  # Number of retry attempts

# Supabase Configuration (primary backend)
SUPABASE_CONFIG = {
    'url': os.getenv('SUPABASE_URL', ''),
    'anon_key': os.getenv('SUPABASE_ANON_KEY', ''),
    'service_key': os.getenv('SUPABASE_SERVICE_KEY', '')
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

def get_supabase_config() -> Dict[str, Any]:
    """Get Supabase configuration dictionary"""
    return SUPABASE_CONFIG.copy()

def get_db_config() -> Dict[str, Any]:
    """Get database configuration (legacy - for migration scripts only)"""
    # Return minimal config for legacy compatibility
    return {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', 5432)),
        'database': os.getenv('DB_NAME', 'pharmchecker'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'password')
    }

def validate_config() -> Dict[str, str]:
    """Validate configuration and return any issues"""
    issues = {}
    
    # Validate Supabase configuration
    if not SUPABASE_CONFIG['url']:
        issues['supabase_url'] = 'SUPABASE_URL is required'
    if not SUPABASE_CONFIG['anon_key']:
        issues['supabase_key'] = 'SUPABASE_ANON_KEY is required'
    
    return issues

def get_config_summary() -> Dict[str, Any]:
    """Get a summary of current configuration for debugging"""
    return {
        'backend': 'supabase',
        'supabase_configured': bool(SUPABASE_CONFIG['url'] and SUPABASE_CONFIG['anon_key']),
        'auth_mode': AUTH_MODE,
        'logging_level': LOGGING_LEVEL
    }

# Data directories
DATA_DIR = os.getenv('DATA_DIR', 'data')
SCREENSHOTS_DIR = os.path.join(DATA_DIR, 'screenshots')

# Storage configuration
STORAGE_TYPE = os.getenv('STORAGE_TYPE', 'local')  # 'local' or 'supabase'
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Authentication Configuration
AUTH_MODE = os.getenv('AUTH_MODE', 'local')
DEFAULT_USER_EMAIL = os.getenv('DEFAULT_USER_EMAIL', 'admin@localhost')
DEFAULT_USER_ROLE = os.getenv('DEFAULT_USER_ROLE', 'admin')

# Streamlit configuration
STREAMLIT_PORT = int(os.getenv('STREAMLIT_PORT', 8501))
STREAMLIT_HOST = os.getenv('STREAMLIT_HOST', '0.0.0.0')