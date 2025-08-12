"""
Session state persistence utilities for PharmChecker
Simple database-based session storage for universal compatibility
"""

import streamlit as st
import json
import logging
from datetime import datetime
from typing import Dict, Optional
from .auth import get_auth_manager

logger = logging.getLogger(__name__)

class SessionManager:
    """Simple database-based session persistence"""
    
    def __init__(self):
        self.auth = get_auth_manager()
    
    def save_dataset_selection(self, datasets: Dict[str, Optional[str]]):
        """Save dataset selection to database"""
        try:
            from .database import get_database_manager
            
            user_id = self.auth.get_user_id()
            if not user_id:
                logger.warning("No user ID - session will not persist across restarts")
                return
            
            db = get_database_manager()
            
            # Create session data
            session_data = {
                'dataset_selection': datasets,
                'timestamp': datetime.now().isoformat()
            }
            
            # Save to database
            update_sql = """
            UPDATE app_users 
            SET session_data = %s, updated_at = now()
            WHERE id = %s
            """
            
            db.execute_query(update_sql, [json.dumps(session_data), user_id])
            logger.info(f"Saved dataset selection to database: {datasets}")
            
        except Exception as e:
            logger.error(f"Failed to save dataset selection: {e}")
    
    def get_available_datasets(self) -> Dict[str, list]:
        """Get all available dataset tags by kind"""
        try:
            from .database import get_database_manager
            db = get_database_manager()
            return db.get_datasets()
        except Exception as e:
            logger.error(f"Failed to get available datasets: {e}")
            return {'pharmacies': [], 'states': [], 'validated': []}
    
    def restore_valid_selections(self) -> Optional[Dict[str, Optional[str]]]:
        """Restore dataset selections, validating they still exist"""
        try:
            user_id = self.auth.get_user_id()
            if not user_id:
                logger.debug("No user ID - cannot restore session")
                return None
            
            from .database import get_database_manager
            db = get_database_manager()
            
            # Get saved session data
            select_sql = """
            SELECT session_data 
            FROM app_users 
            WHERE id = %s AND session_data IS NOT NULL
            """
            
            result_df = db.execute_query(select_sql, [user_id])
            
            if result_df.empty:
                logger.debug("No saved session data found")
                return None
            
            session_data_str = result_df.iloc[0]['session_data']
            if not session_data_str:
                return None
            
            session_data = json.loads(session_data_str) if isinstance(session_data_str, str) else session_data_str
            saved_datasets = session_data.get('dataset_selection', {})
            
            if not any(v for v in saved_datasets.values()):
                return None
            
            # Validate against currently available datasets
            available = self.get_available_datasets()
            validated_datasets = {}
            
            for kind, saved_tag in saved_datasets.items():
                if saved_tag and saved_tag in available.get(kind, []):
                    validated_datasets[kind] = saved_tag
                    logger.info(f"Restored {kind}: {saved_tag}")
                else:
                    validated_datasets[kind] = None
                    if saved_tag:
                        logger.warning(f"Saved {kind} dataset '{saved_tag}' no longer exists")
            
            # Only return if we have at least pharmacies and states
            if validated_datasets.get('pharmacies') and validated_datasets.get('states'):
                logger.info(f"Successfully restored valid dataset selection: {validated_datasets}")
                return validated_datasets
            else:
                logger.info("Saved session incomplete - missing required datasets")
                return None
            
        except Exception as e:
            logger.error(f"Failed to restore dataset selections: {e}")
            return None
    
    def clear_session_data(self):
        """Clear session data from database"""
        try:
            user_id = self.auth.get_user_id()
            if not user_id:
                return
            
            from .database import get_database_manager
            db = get_database_manager()
            
            clear_sql = """
            UPDATE app_users 
            SET session_data = NULL, updated_at = now()
            WHERE id = %s
            """
            
            db.execute_query(clear_sql, [user_id])
            logger.info("Cleared session data from database")
            
        except Exception as e:
            logger.error(f"Failed to clear session data: {e}")

# Global session manager instance
_session_manager = None

def get_session_manager() -> SessionManager:
    """Get singleton session manager instance"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager

def save_dataset_selection(datasets: Dict[str, Optional[str]]):
    """Save dataset selection to persistent storage"""
    try:
        session_manager = get_session_manager()
        session_manager.save_dataset_selection(datasets)
        
    except Exception as e:
        logger.error(f"Failed to save dataset selection: {e}")

def auto_restore_dataset_selection() -> Optional[Dict[str, Optional[str]]]:
    """Automatically restore and validate dataset selections"""
    try:
        session_manager = get_session_manager()
        return session_manager.restore_valid_selections()
        
    except Exception as e:
        logger.error(f"Failed to auto-restore dataset selection: {e}")
        return None

def clear_all_session_data():
    """Clear all session data"""
    try:
        session_manager = get_session_manager()
        session_manager.clear_session_data()
        
        logger.info("Cleared all session data")
        
    except Exception as e:
        logger.error(f"Failed to clear all session data: {e}")