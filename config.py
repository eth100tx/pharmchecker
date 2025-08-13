"""
Configuration management for PharmChecker
Handles environment variables and database configuration
"""
import os
import logging
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Backend Configuration - API-First Architecture
USE_CLOUD_DB = os.getenv('USE_CLOUD_DB', 'true').lower() == 'true'

# API Configuration
API_CACHE_TTL = int(os.getenv('API_CACHE_TTL', '300'))  # Cache timeout in seconds
API_RETRY_COUNT = int(os.getenv('API_RETRY_COUNT', '3'))  # Number of retry attempts
POSTGREST_URL = os.getenv('POSTGREST_URL', 'http://localhost:3000')

# Database configuration (for direct database mode)
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'pharmchecker'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '12')
}

# Supabase Configuration (for API mode)
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

def get_db_config() -> Dict[str, Any]:
    """Get database configuration (legacy - for migration scripts only)"""
    return DB_CONFIG.copy()

def get_supabase_config() -> Dict[str, Any]:
    """Get Supabase configuration dictionary"""
    return SUPABASE_CONFIG.copy()

def is_api_mode() -> bool:
    """Check if running in API mode (always True in API-first architecture)"""
    return True

def use_cloud_database() -> bool:
    """Check if cloud database (Supabase) should be used"""
    return USE_CLOUD_DB

def get_backend_type() -> str:
    """Get the backend type based on configuration"""
    if USE_CLOUD_DB and SUPABASE_CONFIG['url'] and SUPABASE_CONFIG['anon_key']:
        return 'supabase'
    else:
        return 'postgrest'

def validate_config() -> Dict[str, str]:
    """Validate configuration and return any issues"""
    issues = {}
    
    # Validate API configuration (always in API mode)
    if USE_CLOUD_DB:
        if not SUPABASE_CONFIG['url']:
            issues['supabase_url'] = 'SUPABASE_URL is required when USE_CLOUD_DB=true'
        if not SUPABASE_CONFIG['anon_key']:
            issues['supabase_key'] = 'SUPABASE_ANON_KEY is required when USE_CLOUD_DB=true'
    else:
        if not POSTGREST_URL:
            issues['postgrest_url'] = 'POSTGREST_URL is required for PostgREST API mode'
        # Also validate PostgreSQL config for PostgREST backend
        if not DB_CONFIG['password']:
            issues['db_password'] = 'DB_PASSWORD is required for PostgREST backend'
        if not DB_CONFIG['host']:
            issues['db_host'] = 'DB_HOST is required for PostgREST backend'
    
    return issues

def get_config_summary() -> Dict[str, Any]:
    """Get a summary of current configuration for debugging"""
    return {
        'mode': get_backend_type(),
        'api_mode': True,  # Always True in API-first architecture
        'use_cloud_db': USE_CLOUD_DB,
        'postgrest_url': POSTGREST_URL,
        'supabase_configured': bool(SUPABASE_CONFIG['url'] and SUPABASE_CONFIG['anon_key']),
        'database_configured': bool(DB_CONFIG['host'] and DB_CONFIG['password']),
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