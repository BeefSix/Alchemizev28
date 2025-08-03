import streamlit as st
from typing import Tuple
from .utils import APIClient

class AuthManager:
    """Handles user authentication"""
    
    def __init__(self, api_client: APIClient):
        self.api_client = api_client
    
    def login(self, email: str, password: str) -> Tuple[bool, str]:
        """Authenticate user and store token"""
        response = self.api_client.make_request(
            "POST", "/auth/token",
            data={"username": email, "password": password}
        )
        
        if response and response.status_code == 200:
            token_data = response.json()
            st.session_state.token = token_data['access_token']
            st.session_state.user_email = email
            return True, "Login successful!"
        elif response:
            try:
                error_data = response.json()
                error_detail = error_data.get("detail", "Login failed")
            except:
                error_detail = f"HTTP {response.status_code}: {response.text}"
            return False, error_detail
        else:
            return False, "Could not connect to the API."
    
    def signup(self, email: str, password: str, full_name: str) -> Tuple[bool, str]:
        """Register new user account"""
        response = self.api_client.make_request(
            "POST", "/auth/register",
            json={"email": email, "password": password, "full_name": full_name}
        )
        
        if response and response.status_code == 200:
            return True, "Signup successful! Please log in."
        elif response:
            try:
                error_data = response.json()
                error_detail = error_data.get("detail", "Signup failed")
            except:
                error_detail = f"HTTP {response.status_code}: {response.text}"
            return False, error_detail
        else:
            return False, "Could not connect to the API."
    
    def logout(self):
        """Clear authentication state"""
        st.session_state.token = None
        st.session_state.user_email = None
        st.query_params.clear()
        st.rerun()
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        return bool(st.session_state.token)
    
    def render_auth_section(self):
        """Render authentication UI in sidebar"""
        if st.session_state.connection_status and not st.session_state.token:
            self._render_login_signup()
        elif st.session_state.token:
            self._render_user_info()
        else:
            st.error("⚠️ Cannot connect to API")
    
    def _render_login_signup(self):
        """Render login and signup forms"""
        st.markdown("### 🔐 Login / Sign Up")
        
        tab1, tab2 = st.tabs(["Login", "Sign Up"])
        
        with tab1:
            with st.form("login_form"):
                email = st.text_input("Email", key="login_email")
                password = st.text_input("Password", type="password", key="login_pass")
                
                if st.form_submit_button("Login", use_container_width=True):
                    if email and password:
                        success, message = self.login(email, password)
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                    else:
                        st.error("Please enter both email and password")
        
        with tab2:
            with st.form("signup_form"):
                full_name = st.text_input("Full Name", key="signup_name")
                email = st.text_input("Email", key="signup_email")
                password = st.text_input("Password", type="password", key="signup_pass")
                
                if st.form_submit_button("Sign Up", use_container_width=True):
                    if full_name and email and password:
                        success, message = self.signup(email, password, full_name)
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
                    else:
                        st.error("Please fill in all fields")
    
    def _render_user_info(self):
        """Render authenticated user information"""
        st.success(f"✅ Logged in as: {st.session_state.user_email}")
        
        if st.button("Logout", use_container_width=True):
            self.logout()
        
        st.markdown("### 📊 Your Stats")
        # TODO: Implement actual statistics
        st.metric("Videos Processed", "Coming Soon")
        st.metric("Clips Generated", "Coming Soon")