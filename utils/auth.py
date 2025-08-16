"""
Authentication utilities for PharmChecker
Supports both local development and GitHub OAuth for production
"""

import os
import streamlit as st
from typing import Dict, Optional, Tuple
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

class AuthManager:
    """Handles authentication for both local and GitHub OAuth modes"""
    
    def __init__(self):
        self.auth_mode = os.getenv('AUTH_MODE', 'local').lower()
        self.default_user_email = os.getenv('DEFAULT_USER_EMAIL', 'admin@localhost')
        self.default_user_role = os.getenv('DEFAULT_USER_ROLE', 'admin')
        
    def get_current_user(self) -> Optional[Dict]:
        """Get current authenticated user"""
        if self.auth_mode == 'local':
            return self._get_local_user()
        elif self.auth_mode == 'github':
            return self._get_github_user()
        else:
            logger.error(f"Unknown auth mode: {self.auth_mode}")
            return None
    
    def _get_local_user(self) -> Dict:
        """Get default local user for development"""
        # Check if user exists in session state
        if 'user' not in st.session_state:
            try:
                # Create or get default user via Supabase API
                project_root = Path(__file__).parent.parent
                api_path = project_root / "api_poc" / "gui"
                sys.path.insert(0, str(api_path))
                
                from client import create_client
                import requests
                
                client = create_client()
                
                # Look for existing admin user
                url = f"{client.supabase_client.url}/rest/v1/app_users"
                params = {
                    'or': '(role.eq.admin,github_login.eq.admin)',
                    'limit': '1'
                }
                
                response = requests.get(url, headers=client.supabase_client.headers, params=params, timeout=10)
                
                if response.status_code == 200:
                    users = response.json()
                    
                    if not users:
                        # No existing admin user found, create one
                        user_data = {
                            'github_login': 'local_admin',
                            'email': self.default_user_email,
                            'role': self.default_user_role,
                            'is_active': True
                        }
                        
                        create_response = requests.post(url, 
                                                      headers=client.supabase_client.headers,
                                                      json=[user_data],
                                                      timeout=10)
                        
                        if create_response.status_code in [200, 201]:
                            # Get the created user
                            get_params = {'github_login': 'eq.local_admin'}
                            get_response = requests.get(url, headers=client.supabase_client.headers, params=get_params, timeout=10)
                            if get_response.status_code == 200:
                                created_users = get_response.json()
                                if created_users:
                                    user_data = created_users[0]
                                    logger.info(f"Created new local user: {self.default_user_email}")
                                else:
                                    logger.error("Failed to retrieve created user")
                                    return self._create_fallback_user()
                            else:
                                logger.error("Failed to retrieve created user")
                                return self._create_fallback_user()
                        else:
                            logger.error(f"Failed to create user: {create_response.status_code}")
                            return self._create_fallback_user()
                    else:
                        # Found existing admin user, update it to match our config
                        existing_user = users[0]
                        user_id = existing_user['id']
                        
                        update_data = {
                            'github_login': 'local_admin',
                            'email': self.default_user_email,
                            'role': self.default_user_role,
                            'is_active': True
                        }
                        
                        update_url = f"{client.supabase_client.url}/rest/v1/app_users"
                        update_headers = client.supabase_client.headers.copy()
                        update_headers['Prefer'] = 'return=representation'
                        update_params = {'id': f'eq.{user_id}'}
                        
                        update_response = requests.patch(update_url,
                                                       headers=update_headers,
                                                       params=update_params,
                                                       json=update_data,
                                                       timeout=10)
                        
                        if update_response.status_code == 200:
                            updated_users = update_response.json()
                            if updated_users:
                                user_data = updated_users[0]
                                logger.info(f"Updated existing user (ID {user_id}) to: {self.default_user_email}")
                            else:
                                user_data = existing_user
                                logger.warning("Update succeeded but no data returned, using existing user")
                        else:
                            logger.error(f"Failed to update user: {update_response.status_code}")
                            user_data = existing_user
                else:
                    logger.error(f"Failed to query users: {response.status_code}")
                    return self._create_fallback_user()
                
                # Store in session state
                st.session_state.user = user_data
                
            except Exception as e:
                logger.error(f"Database error during authentication: {e}")
                return self._create_fallback_user()
            
        return st.session_state.user
    
    def _create_fallback_user(self) -> Dict:
        """Create fallback user when database is not available"""
        fallback_user = {
            'id': 1,  # Use ID 1 to match existing database user
            'github_login': 'local_admin',
            'email': self.default_user_email,
            'role': self.default_user_role,
            'is_active': True
        }
        st.session_state.user = fallback_user
        logger.info(f"Created fallback user: {self.default_user_email}")
        return fallback_user
    
    def _get_github_user(self) -> Optional[Dict]:
        """Get GitHub authenticated user (placeholder for future implementation)"""
        # This would integrate with streamlit-authenticator or similar
        # For now, return None to indicate GitHub auth not implemented
        st.error("GitHub authentication not yet implemented. Please use AUTH_MODE=local")
        return None
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        user = self.get_current_user()
        return user is not None and user.get('is_active', False)
    
    def get_user_id(self) -> Optional[int]:
        """Get current user ID"""
        user = self.get_current_user()
        return user.get('id') if user else None
    
    def get_user_email(self) -> Optional[str]:
        """Get current user email"""
        user = self.get_current_user()
        return user.get('email') if user else None
    
    def get_user_role(self) -> Optional[str]:
        """Get current user role"""
        user = self.get_current_user()
        return user.get('role') if user else None
    
    def is_admin(self) -> bool:
        """Check if current user is admin"""
        return self.get_user_role() == 'admin'
    
    def logout(self):
        """Clear user session"""
        if 'user' in st.session_state:
            del st.session_state.user
        logger.info("User logged out")

# Global auth manager instance
_auth_manager = None

def get_auth_manager() -> AuthManager:
    """Get singleton auth manager instance"""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager

def require_auth() -> bool:
    """Require authentication, show login if not authenticated"""
    try:
        auth = get_auth_manager()
        
        if not auth.is_authenticated():
            st.error("Authentication required")
            st.info(f"Current auth mode: {auth.auth_mode}")
            
            if auth.auth_mode == 'local':
                st.info("Local development mode - check your .env configuration or database connection")
                # In local mode, try to continue anyway with fallback user
                user = auth.get_current_user()
                if user:
                    st.success(f"Continuing with fallback user: {user['email']}")
                    return True
            elif auth.auth_mode == 'github':
                st.info("GitHub authentication not yet implemented")
                
            st.stop()
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        st.error(f"Authentication system error: {e}")
        st.info("Continuing with limited functionality...")
        return True

def get_current_user() -> Optional[Dict]:
    """Convenience function to get current user"""
    return get_auth_manager().get_current_user()

def get_user_context() -> Dict:
    """Get user context for display"""
    auth = get_auth_manager()
    user = auth.get_current_user()
    
    if user:
        return {
            'authenticated': True,
            'email': user.get('email'),
            'role': user.get('role'),
            'auth_mode': auth.auth_mode,
            'is_admin': auth.is_admin()
        }
    else:
        return {
            'authenticated': False,
            'auth_mode': auth.auth_mode
        }