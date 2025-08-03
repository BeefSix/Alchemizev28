import streamlit as st
import requests
import time
import os
from typing import Optional, Dict, Any

def init_session_state():
    """Initialize Streamlit session state with default values"""
    api_url_options = [
        os.environ.get("API_BASE_URL"),
        "http://web:8000/api/v1",
        "http://localhost:8000/api/v1"
    ]
    
    api_base_url = next((url for url in api_url_options if url), "http://localhost:8000/api/v1")
    
    defaults = {
        'token': None,
        'user_email': None,
        'api_base_url': api_base_url,
        'connection_tested': False,
        'connection_status': None,
        'active_jobs': {},
        'last_job_check': {}
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

class APIClient:
    """Handles all API communication"""
    
    def __init__(self):
        self.base_url = st.session_state.api_base_url
        self.timeout = 30
    
    def make_request(self, method: str, endpoint: str, **kwargs) -> Optional[requests.Response]:
        """Make HTTP request to API with error handling"""
        try:
            url = f"{self.base_url}{endpoint}"
            kwargs.setdefault('timeout', self.timeout)
            response = requests.request(method, url, **kwargs)
            return response
        except requests.exceptions.RequestException as e:
            st.error(f"API connection error: {e}")
            st.session_state.connection_tested = False
            return None
    
    def make_authenticated_request(self, method: str, endpoint: str, **kwargs) -> Optional[requests.Response]:
        """Make authenticated request with Bearer token"""
        if not st.session_state.token:
            st.error("Not authenticated")
            return None
        
        headers = kwargs.get('headers', {})
        headers['Authorization'] = f"Bearer {st.session_state.token}"
        kwargs['headers'] = headers
        
        return self.make_request(method, endpoint, **kwargs)
    
    def test_connection(self) -> bool:
        """Test API connection and update session state"""
        if st.session_state.connection_tested:
            return st.session_state.connection_status
        
        test_urls = [
            self.base_url.replace("/api/v1", "/health"),
            "http://web:8000/health",
            "http://localhost:8000/health"
        ]
        
        for test_url in test_urls:
            try:
                response = requests.get(test_url, timeout=5)
                if response.status_code == 200:
                    st.session_state.connection_status = True
                    st.session_state.connection_tested = True
                    
                    # Update base URL if needed
                    if "web:8000" in test_url:
                        st.session_state.api_base_url = "http://web:8000/api/v1"
                        self.base_url = st.session_state.api_base_url
                    elif "localhost:8000" in test_url:
                        st.session_state.api_base_url = "http://localhost:8000/api/v1"
                        self.base_url = st.session_state.api_base_url
                    
                    return True
            except Exception:
                continue
        
        st.session_state.connection_status = False
        st.session_state.connection_tested = True
        return False
    
    def is_connected(self) -> bool:
        """Check if API is connected"""
        return st.session_state.connection_status

class JobMonitor:
    """Handles job status monitoring and display"""
    
    def __init__(self, api_client: APIClient):
        self.api_client = api_client
    
    def get_job_status(self, job_id: str, job_type: str = "video") -> Optional[Dict[str, Any]]:
        """Get job status with auto-cleanup of non-existent jobs"""
        if not job_id:
            return None
        
        try:
            response = self.api_client.make_authenticated_request(
                "GET", f"/{job_type}/jobs/{job_id}"
            )
            
            if response and response.status_code == 200:
                return response.json()
            elif response and response.status_code == 404:
                st.warning("⚠️ Job not found. Clearing...")
                self.clear_job_from_url(job_type)
                return None
            elif response:
                st.error(f"Failed to get job status: {response.status_code}")
            return None
        except Exception as e:
            st.error(f"Error checking job status: {e}")
            return None
    
    def clear_job_from_url(self, job_type: str):
        """Clear job parameter from URL and reset state"""
        param_name = f"{job_type}_job"
        if param_name in st.query_params:
            st.query_params.clear()
            st.rerun()
    
    def render_job_status(self, job_id: str, job_type: str):
        """Render job status with automatic refresh and cleanup"""
        if not job_id:
            return None
        
        # Throttle API calls
        current_time = time.time()
        last_check_key = f"{job_type}_{job_id}"
        last_check = st.session_state.last_job_check.get(last_check_key, 0)
        
        if current_time - last_check < 2:
            time.sleep(1)
            st.rerun()
            return None
        
        st.session_state.last_job_check[last_check_key] = current_time
        
        # Get current job status
        job_data = self.get_job_status(job_id, job_type)
        
        if not job_data:
            st.warning("⚠️ Could not retrieve job status")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Retry", key=f"retry_{job_id}"):
                    st.rerun()
            with col2:
                if st.button("❌ Cancel", key=f"cancel_{job_id}"):
                    self.clear_job_from_url(job_type)
            return None
        
        status = job_data.get("status", "UNKNOWN")
        progress = job_data.get("progress_details") or {}
        percentage = progress.get("percentage", 0) if progress else 0
        description = progress.get("description", "Processing...") if progress else "Processing..."
        
        # Handle different job statuses
        if status == "PENDING":
            st.info("⏳ Job is queued and waiting to start...")
            if st.button("❌ Cancel Job", key=f"cancel_pending_{job_id}"):
                self.clear_job_from_url(job_type)
                return None
            time.sleep(3)
            st.rerun()
            
        elif status == "IN_PROGRESS":
            st.info(f"🔄 {description}")
            if percentage > 0:
                st.progress(percentage / 100, text=f"{percentage}% complete")
            
            if st.button("❌ Cancel Job", key=f"cancel_progress_{job_id}"):
                self.clear_job_from_url(job_type)
                return None
            
            time.sleep(3)
            st.rerun()
            
        elif status == "COMPLETED":
            return job_data  # Let caller handle results display
            
        elif status == "FAILED":
            error_message = job_data.get('error_message', 'Unknown error')
            st.error(f"❌ Job failed: {error_message}")
            
            with st.expander("🔧 Debug Info"):
                st.json(job_data)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Try Again", key=f"retry_failed_{job_id}"):
                    self.clear_job_from_url(job_type)
            with col2:
                if st.button("❌ Clear", key=f"clear_failed_{job_id}"):
                    self.clear_job_from_url(job_type)
        
        return None

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"

def validate_file_upload(uploaded_file, max_size_mb: int = 500, allowed_types: list = None) -> tuple[bool, str]:
    """Validate uploaded file"""
    if not uploaded_file:
        return False, "No file uploaded"
    
    if allowed_types and uploaded_file.type not in allowed_types:
        return False, f"Invalid file type. Allowed: {', '.join(allowed_types)}"
    
    if hasattr(uploaded_file, 'size') and uploaded_file.size:
        max_size_bytes = max_size_mb * 1024 * 1024
        if uploaded_file.size > max_size_bytes:
            return False, f"File too large. Maximum size: {max_size_mb}MB"
    
    return True, "File valid"