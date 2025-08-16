"""
Session state persistence utilities for PharmChecker
Uses Supabase REST API endpoints exclusively
"""

import streamlit as st
import json
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from .auth import get_auth_manager

logger = logging.getLogger(__name__)

class SessionManager:
    """API-based session persistence using Supabase REST endpoints"""
    
    def __init__(self):
        self.auth = get_auth_manager()
        self._client = None
        
    def _get_client(self):
        """Get or create Supabase API client"""
        if self._client is None:
            try:
                import sys
                import os
                sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'api_poc', 'gui'))
                from client import create_client
                
                # Always use Supabase
                self._client = create_client()
            except Exception as e:
                logger.error(f"Failed to create API client: {e}")
                raise
        return self._client
    
    def save_dataset_selection(self, datasets: Dict[str, Optional[str]]):
        """Save dataset selection via Supabase REST API"""
        try:
            user_id = self.auth.get_user_id()
            if not user_id:
                logger.warning("No user ID - session will not persist across restarts")
                return
            
            client = self._get_client()
            
            # Create session data
            session_data = {
                'dataset_selection': datasets,
                'timestamp': datetime.now().isoformat()
            }
            
            # Update app_users table via Supabase REST API
            import requests
            url = f"{client.supabase_client.url}/rest/v1/app_users"
            
            headers = client.supabase_client.headers.copy()
            headers['Prefer'] = 'return=minimal'
            
            params = {'id': f'eq.{user_id}'}
            data = {
                'session_data': session_data,
                'updated_at': datetime.now().isoformat()
            }
            
            response = requests.patch(url, 
                                     headers=headers,
                                     params=params,
                                     json=data,
                                     timeout=10)
            
            if response.status_code in [200, 204]:
                logger.info(f"Saved dataset selection to Supabase: {datasets}")
            else:
                logger.error(f"Failed to save session: {response.status_code} {response.text}")
            
        except Exception as e:
            logger.error(f"Failed to save dataset selection: {e}")
    
    def get_available_datasets(self) -> Dict[str, list]:
        """Get all available dataset tags by kind via API"""
        try:
            client = self._get_client()
            datasets = client.get_datasets()
            
            # Group by kind
            result = {'pharmacies': [], 'states': [], 'validated': []}
            for dataset in datasets:
                kind = dataset.get('kind')
                tag = dataset.get('tag')
                if kind in result and tag:
                    result[kind].append(tag)
            
            return result
        except Exception as e:
            logger.error(f"Failed to get available datasets: {e}")
            return {'pharmacies': [], 'states': [], 'validated': []}
    
    def restore_valid_selections(self) -> Optional[Dict[str, Optional[str]]]:
        """Restore dataset selections from Supabase, validating they still exist"""
        try:
            user_id = self.auth.get_user_id()
            if not user_id:
                logger.debug("No user ID - cannot restore session")
                return None
            
            client = self._get_client()
            
            # Get saved session data via Supabase REST API
            import requests
            url = f"{client.supabase_client.url}/rest/v1/app_users"
            
            params = {
                'id': f'eq.{user_id}',
                'select': 'session_data'
            }
            
            response = requests.get(url,
                                   headers=client.supabase_client.headers,
                                   params=params,
                                   timeout=10)
            
            if response.status_code != 200:
                logger.debug(f"Failed to get session data: {response.status_code}")
                return None
            
            result = response.json()
            if not result or len(result) == 0:
                logger.debug("No saved session data found")
                return None
            
            session_data = result[0].get('session_data')
            if not session_data:
                return None
            
            # Handle both string and dict formats
            if isinstance(session_data, str):
                session_data = json.loads(session_data)
            
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
        """Clear session data from Supabase"""
        try:
            user_id = self.auth.get_user_id()
            if not user_id:
                return
            
            client = self._get_client()
            
            # Clear session data via Supabase REST API
            import requests
            url = f"{client.supabase_client.url}/rest/v1/app_users"
            
            headers = client.supabase_client.headers.copy()
            headers['Prefer'] = 'return=minimal'
            
            params = {'id': f'eq.{user_id}'}
            data = {
                'session_data': None,
                'updated_at': datetime.now().isoformat()
            }
            
            response = requests.patch(url,
                                     headers=headers,
                                     params=params,
                                     json=data,
                                     timeout=10)
            
            if response.status_code in [200, 204]:
                logger.info("Cleared session data from Supabase")
            else:
                logger.error(f"Failed to clear session: {response.status_code}")
            
        except Exception as e:
            logger.error(f"Failed to clear session data: {e}")
    
    def save_work_state(self, state_data: Dict[str, Any]):
        """Save generic work state to Supabase (filters, selections, etc.)"""
        try:
            user_id = self.auth.get_user_id()
            if not user_id:
                return
            
            client = self._get_client()
            
            # Get existing session data first
            existing_session = self._get_session_data(user_id)
            if existing_session is None:
                existing_session = {}
            
            # Merge with new work state
            existing_session['work_state'] = state_data
            existing_session['work_state_timestamp'] = datetime.now().isoformat()
            
            # Save back to Supabase
            import requests
            url = f"{client.supabase_client.url}/rest/v1/app_users"
            
            headers = client.supabase_client.headers.copy()
            headers['Prefer'] = 'return=minimal'
            
            params = {'id': f'eq.{user_id}'}
            data = {
                'session_data': existing_session,
                'updated_at': datetime.now().isoformat()
            }
            
            response = requests.patch(url,
                                     headers=headers,
                                     params=params,
                                     json=data,
                                     timeout=10)
            
            if response.status_code in [200, 204]:
                logger.debug(f"Saved work state to Supabase")
            else:
                logger.error(f"Failed to save work state: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Failed to save work state: {e}")
    
    def get_work_state(self) -> Optional[Dict[str, Any]]:
        """Get saved work state from Supabase"""
        try:
            user_id = self.auth.get_user_id()
            if not user_id:
                return None
            
            session_data = self._get_session_data(user_id)
            if session_data:
                return session_data.get('work_state')
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get work state: {e}")
            return None
    
    def _get_session_data(self, user_id: int) -> Optional[Dict]:
        """Internal method to get session data for a user"""
        try:
            client = self._get_client()
            
            import requests
            url = f"{client.supabase_client.url}/rest/v1/app_users"
            
            params = {
                'id': f'eq.{user_id}',
                'select': 'session_data'
            }
            
            response = requests.get(url,
                                   headers=client.supabase_client.headers,
                                   params=params,
                                   timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result and len(result) > 0:
                    session_data = result[0].get('session_data')
                    if isinstance(session_data, str):
                        return json.loads(session_data)
                    return session_data
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get session data: {e}")
            return None

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

def save_work_state(state_data: Dict[str, Any]):
    """Save generic work state (filters, selections, etc.)"""
    try:
        session_manager = get_session_manager()
        session_manager.save_work_state(state_data)
        
    except Exception as e:
        logger.error(f"Failed to save work state: {e}")

def get_work_state() -> Optional[Dict[str, Any]]:
    """Get saved work state"""
    try:
        session_manager = get_session_manager()
        return session_manager.get_work_state()
        
    except Exception as e:
        logger.error(f"Failed to get work state: {e}")
        return None