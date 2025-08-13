"""
Authentication utilities for PharmChecker
Supports both local development and GitHub OAuth for production
"""

import os
import streamlit as st
from typing import Dict, Optional, Tuple
import logging
from .database import get_database_manager

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
                # Create or get default user from database
                db = get_database_manager()
                
                # Look for existing admin user or create one
                existing_user_sql = "SELECT id, github_login, email, role, is_active FROM app_users WHERE role = 'admin' OR github_login = 'admin' LIMIT 1"
                user_df = db.execute_query(existing_user_sql, [])
                
                if user_df.empty:
                    # No existing admin user found, create one
                    insert_sql = """
                    INSERT INTO app_users (github_login, email, role, is_active) 
                    VALUES (%s, %s, %s, %s)
                    """
                    db.execute_query(insert_sql, [
                        'local_admin', 
                        self.default_user_email, 
                        self.default_user_role, 
                        True
                    ])
                    
                    # Query back to get the created user
                    user_df = db.execute_query("SELECT id, github_login, email, role, is_active FROM app_users WHERE github_login = %s", ['local_admin'])
                    
                    if not user_df.empty:
                        user_data = user_df.iloc[0].to_dict()
                        logger.info(f"Created new local user: {self.default_user_email}")
                    else:
                        logger.error("Failed to create default local user")
                        return self._create_fallback_user()
                else:
                    # Found existing admin user, update it to match our config
                    existing_user = user_df.iloc[0].to_dict()
                    user_id = existing_user['id']
                    
                    update_sql = """
                    UPDATE app_users 
                    SET github_login = %s, email = %s, role = %s, is_active = %s
                    WHERE id = %s
                    """
                    db.execute_query(update_sql, [
                        'local_admin',
                        self.default_user_email,
                        self.default_user_role,
                        True,
                        user_id
                    ])
                    
                    # Query back to get the updated user
                    user_df = db.execute_query("SELECT id, github_login, email, role, is_active FROM app_users WHERE id = %s", [user_id])
                    user_data = user_df.iloc[0].to_dict()
                    logger.info(f"Updated existing user (ID {user_id}) to: {self.default_user_email}")
                
                # Store in session state
                st.session_state.user = user_data
                
            except Exception as e:
                if "Direct SQL" in str(e) or "not supported" in str(e):
                    logger.info("Direct SQL not supported - using fallback authentication")
                else:
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