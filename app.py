import streamlit as st
import requests
import time
import os
import json
import sys
from datetime import datetime

# --- Page Configuration ---
st.set_page_config(
    page_title="Alchemize",
    page_icon="⚗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Initialize Session State ---
def init_session_state():
    # Multiple fallback options for API URL
    api_url_options = [
        os.environ.get("API_BASE_URL"),
        "http://web:8000/api/v1",
        "http://localhost:8000/api/v1"
    ]
    
    # Use the first non-None option
    api_base_url = next((url for url in api_url_options if url), "http://localhost:8000/api/v1")
    
    defaults = {
        'token': None,
        'user_email': None,
        'content_job_id': None,
        'clip_job_id': None,
        'api_base_url': api_base_url,
        'last_poll_time': 0,
        'connection_tested': False,
        'connection_status': None
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# --- Enhanced Connection Test ---
def test_api_connection():
    """Test API connection with multiple fallback URLs"""
    if st.session_state.connection_tested:
        return st.session_state.connection_status
    
    # Test multiple possible URLs
    test_urls = [
        st.session_state.api_base_url.replace("/api/v1", "/health"),
        "http://web:8000/health",
        "http://localhost:8000/health"
    ]
    
    for test_url in test_urls:
        try:
            response = requests.get(test_url, timeout=5)
            if response.status_code == 200:
                st.session_state.connection_status = True
                st.session_state.connection_tested = True
                
                # Update API base URL based on successful connection
                if "web:8000" in test_url:
                    st.session_state.api_base_url = "http://web:8000/api/v1"
                elif "localhost:8000" in test_url:
                    st.session_state.api_base_url = "http://localhost:8000/api/v1"
                
                return True
        except Exception as e:
            continue
    
    # If all URLs fail
    st.session_state.connection_status = False
    st.session_state.connection_tested = True
    return False

# --- Helper Functions ---
def make_api_request(method, endpoint, **kwargs):
    """Make API request with clean error handling (no debug spam)"""
    try:
        url = f"{st.session_state.api_base_url}{endpoint}"
        kwargs.setdefault('timeout', 30)
        response = requests.request(method, url, **kwargs)
        return response
    except requests.exceptions.RequestException as e:
        st.error(f"API connection error: {e}")
        st.session_state.connection_tested = False
        return None

def login(email, password):
    response = make_api_request(
        "POST", "/auth/token",
        data={"username": email, "password": password}
    )
    
    if response and response.status_code == 200:
        st.session_state.token = response.json()['access_token']
        st.session_state.user_email = email
        return True, "Login successful!"
    elif response:
        # Fix: Parse JSON once and store it
        try:
            error_data = response.json()
            error_detail = error_data.get("detail", "Login failed")
        except:
            error_detail = f"HTTP {response.status_code}: {response.text}"
        return False, error_detail
    else:
        return False, "Could not connect to the API."

def signup(email, password, full_name):
    response = make_api_request(
        "POST", "/auth/register",
        json={"email": email, "password": password, "full_name": full_name}
    )
    if response and response.status_code == 200:
        return True, "Signup successful! Please log in."
    elif response:
        # Fix: Parse JSON once and store it
        try:
            error_data = response.json()
            error_detail = error_data.get("detail", "Signup failed")
        except:
            error_detail = f"HTTP {response.status_code}: {response.text}"
        return False, error_detail
    else:
        return False, "Could not connect to the API."

def poll_job_status(job_id, job_type="video"):
    """Non-blocking job status check with proper error handling"""
    if not job_id:
        return None
    
    # Rate limit polling to every 5 seconds (reduced flashing)
    current_time = time.time()
    if current_time - st.session_state.last_poll_time < 5:
        return None
    
    st.session_state.last_poll_time = current_time
    
    response = make_api_request(
        "GET", f"/{job_type}/jobs/{job_id}",
        headers={"Authorization": f"Bearer {st.session_state.token}"}
    )
    return response.json() if response and response.status_code == 200 else None

def clear_job_state(job_type):
    """Clear specific job state"""
    if job_type == "video":
        st.session_state.clip_job_id = None
    elif job_type == "content":
        st.session_state.content_job_id = None

def render_job_status(job_id, job_type):
    """Render job status with manual refresh (no auto-refresh spam)"""
    if not job_id:
        return None
        
    job_data = poll_job_status(job_id, job_type)
    
    if not job_data:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.warning("Checking job status...")
        with col2:
            if st.button("🔄 Refresh", key=f"refresh_{job_id}"):
                st.rerun()
        return None
    
    status = job_data.get("status", "UNKNOWN")
    progress = job_data.get("progress_details") or {}
    percentage = progress.get("percentage", 0) if progress else 0
    description = progress.get("description", "Working...") if progress else "Working..."
    
    # Status display
    if status == "PENDING":
        st.info("⏳ Job is queued and waiting to start...")
    elif status == "IN_PROGRESS":
        st.info(f"🔄 {description}")
        if percentage > 0:
            st.progress(percentage / 100)
        # Manual refresh button for active jobs
        if st.button("🔄 Refresh Status", key=f"refresh_active_{job_id}"):
            st.rerun()
    elif status == "COMPLETED":
        st.success("✅ Job completed successfully!")
        return job_data
    elif status == "FAILED":
        error_message = job_data.get('error_message', 'Unknown error')
        st.error(f"❌ Job failed: {error_message}")
        if st.button(f"Try Again", key=f"retry_{job_type}_{job_id}"):
            clear_job_state(job_type)
            st.rerun()
        return None
    
    return None

# --- Main UI ---
st.title("🧪 Alchemize - Video to Viral Content")

# Connection status at the top
col1, col2 = st.columns([4, 1])
with col1:
    if test_api_connection():
        st.success(f"🟢 Connected to API (Using: {st.session_state.api_base_url})")
    else:
        st.error("🔴 Cannot connect to API - Check debug info in sidebar")

with col2:
    if st.button("🔄 Retry Connection"):
        st.session_state.connection_tested = False
        st.rerun()

# --- Sidebar ---
with st.sidebar:
    st.markdown("⚗️", help="Your wizard mascot here!")
    st.title("The Alchemist's Lab")
    
    # Minimal debug info (no spam)
    with st.expander("🔧 Debug Info", expanded=False):
        st.write(f"**API URL:** {st.session_state.api_base_url}")
        st.write(f"**Connection Status:** {st.session_state.connection_status}")
    
    if st.session_state.connection_status and not st.session_state.token:
        st.markdown("### 🔐 Login / Sign Up")
        
        tab1, tab2 = st.tabs(["Login", "Sign Up"])
        
        with tab1:
            with st.form("login_form"):
                email = st.text_input("Email", key="login_email")
                password = st.text_input("Password", type="password", key="login_pass")
                if st.form_submit_button("Login", use_container_width=True):
                    success, message = login(email, password)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
        
        with tab2:
            with st.form("signup_form"):
                full_name = st.text_input("Full Name", key="signup_name")
                email = st.text_input("Email", key="signup_email")
                password = st.text_input("Password", type="password", key="signup_pass")
                if st.form_submit_button("Sign Up", use_container_width=True):
                    success, message = signup(email, password, full_name)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
    
    elif st.session_state.token:
        st.success(f"✅ Logged in as: {st.session_state.user_email}")
        if st.button("Logout", use_container_width=True):
            st.session_state.token = None
            st.session_state.user_email = None
            st.session_state.clip_job_id = None
            st.session_state.content_job_id = None
            st.rerun()

        st.markdown("### 📊 Your Stats")
        st.metric("Videos Processed", "Coming Soon")
        st.metric("Clips Generated", "Coming Soon")
    else:
        st.error("⚠️ Cannot connect to API")
        st.info("Please check that the backend is running and try refreshing the page.")

# --- Main Content ---
if not st.session_state.connection_status:
    st.error("🔌 **Connection Issue Detected**")
    st.markdown("The frontend cannot connect to the backend API. Check the debug info in the sidebar.")

elif not st.session_state.token:
    st.markdown("### Turn your videos into viral social media content")
    st.info("👈 Please log in or sign up to begin")
    
    # Show features while not logged in
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        **🎤 Live Karaoke Captions**
        - Words highlight as spoken
        - Perfect timing sync
        - Professional quality
        """)
    with col2:
        st.markdown("""
        **📱 Multi-Platform Ready**
        - 9:16 (TikTok/Instagram)
        - 1:1 (Instagram Square)
        - 16:9 (YouTube/Facebook)
        """)
    with col3:
        st.markdown("""
        **⚡ AI-Powered Processing**
        - Auto clip generation
        - Content optimization
        - Hardware acceleration
        """)

else:
    st.title("Alchemist's Dashboard")
    
    tab1, tab2, tab3 = st.tabs(["🎬 Video Clips", "✍️ Content Suite", "⚙️ Settings"])
    
    # --- VIDEO CLIPS TAB ---
    with tab1:
        st.header("Create Viral Video Clips")
        st.markdown("Upload ANY video format and get professional clips with **live karaoke-style captions**!")
        
        if st.session_state.clip_job_id:
            job_data = render_job_status(st.session_state.clip_job_id, "video")
            
            if job_data and job_data.get("status") == "COMPLETED":
                results = job_data.get("results", {})
                clips_by_platform = results.get("clips_by_platform", {})
                
                if clips_by_platform:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        total_clips = results.get("total_clips", 0)
                        video_duration = results.get("video_duration", 0)
                        captions_added = results.get("captions_added", False)
                        
                        st.markdown(f"### ✅ Generated {total_clips} clips")
                        st.info(f"📹 Original video: {video_duration:.1f}s | 🎤 Live karaoke captions: {'Yes' if captions_added else 'No'}")
                    
                    with col2:
                        response = make_api_request(
                            "GET", f"/video/jobs/{st.session_state.clip_job_id}/download-all",
                            headers={"Authorization": f"Bearer {st.session_state.token}"},
                            stream=True
                        )
                        if response and response.status_code == 200:
                            st.download_button(
                                label="📥 Download All",
                                data=response.content,
                                file_name=f"alchemize_clips_{st.session_state.clip_job_id[:8]}.zip",
                                mime="application/zip",
                                use_container_width=True
                            )
                    
                    # Display clips
                    all_clips = []
                    for platform, urls in clips_by_platform.items():
                        if isinstance(urls, list):
                            all_clips.extend(urls)
                    
                    if all_clips:
                        st.markdown("#### Your Clips")
                        cols = st.columns(min(len(all_clips), 4))
                        for i, url in enumerate(all_clips):
                            with cols[i % 4]:
                                full_url = url if url.startswith("http") else f"http://localhost:8000{url}"
                                try:
                                    st.video(full_url)
                                    st.caption(f"Clip {i + 1}")
                                except:
                                    st.error(f"Could not load clip {i + 1}")
                
                if st.button("🎬 Process Another Video", use_container_width=True, key="new_video_job"):
                    clear_job_state("video")
                    st.rerun()

        else:
            # Video upload form
            with st.form("video_upload_form"):
                uploaded_file = st.file_uploader(
                    "Choose any video file", 
                    type=['mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'wmv', 'm4v', '3gp', 'ogv', 'ts', 'mts', 'm2ts'],
                    help="✅ Supports ALL major video formats • Max size: 500MB"
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    aspect_ratio = st.selectbox(
                        "Aspect Ratio", 
                        ["9:16 (Vertical/TikTok)", "1:1 (Square/Instagram)", "16:9 (Horizontal/YouTube)"],
                        index=0
                    )
                    aspect_ratio_value = aspect_ratio.split(" ")[0]
                
                with col2:
                    add_captions = st.selectbox(
                        "🎤 Live Karaoke Captions",
                        ["Yes - Add live karaoke-style captions", "No - Video only"],
                        index=0
                    )
                    add_captions_bool = add_captions.startswith("Yes")
                
                submitted = st.form_submit_button("🚀 Create Clips with Live Captions", use_container_width=True)

                if submitted and uploaded_file:
                    with st.spinner("Uploading and starting processing..."):
                        files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                        data = {
                            "add_captions": add_captions_bool,
                            "aspect_ratio": aspect_ratio_value
                        }
                        response = make_api_request(
                            "POST", "/video/upload-and-clip",
                            files=files, 
                            data=data,
                            headers={"Authorization": f"Bearer {st.session_state.token}"}
                        )
                        if response and response.status_code == 202:
                            st.session_state.clip_job_id = response.json().get('job_id')
                            st.success("✅ Upload successful! Processing started...")
                            st.rerun()
                        else:
                            error_msg = response.text if response else "Unknown error"
                            st.error(f"❌ Failed to start processing: {error_msg}")
                elif submitted:
                    st.error("Please upload a video file first.")
    
    # --- CONTENT SUITE TAB ---
    with tab2:
        st.header("Generate Social Media Content Suite")
        st.markdown("Transform any content into engaging social media posts across platforms!")
        
        if st.session_state.content_job_id:
            job_data = render_job_status(st.session_state.content_job_id, "content")
            
            if job_data and job_data.get("status") == "COMPLETED":
                results = job_data.get("results", {})
                
                if results.get("analysis"):
                    with st.expander("📊 Content Analysis", expanded=True):
                        st.write(results["analysis"])
                
                if results.get("posts"):
                    st.markdown("### Generated Content")
                    st.text_area("Social Media Posts", results["posts"], height=500)
                
                if st.button("✍️ Create New Content", use_container_width=True, key="new_content_job"):
                    clear_job_state("content")
                    st.rerun()

        else:
            # Content generation form
            with st.form("content_form"):
                content_input = st.text_area(
                    "Enter content or URL", 
                    height=200,
                    placeholder="Paste text, article URL, or YouTube URL here..."
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    tone = st.selectbox("Tone", ["Professional", "Casual", "Enthusiastic", "Friendly", "Authoritative"])
                with col2:
                    style = st.selectbox("Writing Style", ["Concise", "Detailed", "Storytelling", "Listicle", "Question-based"])
                
                platforms = st.multiselect(
                    "Target Platforms",
                    ["LinkedIn", "Twitter", "Instagram", "TikTok", "Facebook", "YouTube"],
                    default=["LinkedIn", "Twitter", "Instagram"]
                )
                
                submitted = st.form_submit_button("✨ Generate Content Suite", use_container_width=True)

                if submitted and content_input.strip() and platforms:
                    with st.spinner("Analyzing content and generating posts..."):
                        payload = {
                            "content": content_input.strip(), 
                            "platforms": platforms,
                            "tone": tone, 
                            "style": style, 
                            "additional_instructions": ""
                        }
                        response = make_api_request(
                            "POST", "/content/repurpose",
                            json=payload,
                            headers={"Authorization": f"Bearer {st.session_state.token}"}
                        )
                        if response and response.status_code == 202:
                            st.session_state.content_job_id = response.json().get('job_id')
                            st.success("Content generation started!")
                            st.rerun()
                        else:
                            error_msg = response.text if response else "Unknown error"
                            st.error(f"Failed to start content generation: {error_msg}")
                elif submitted and not content_input.strip():
                    st.error("Please enter some content to repurpose.")
                elif submitted and not platforms:
                    st.error("Please select at least one platform.")

    # --- SETTINGS TAB ---
    with tab3:
        st.header("Settings & Information")
        
        with st.expander("🔧 System Information", expanded=True):
            st.write(f"**API URL:** {st.session_state.api_base_url}")
            st.write(f"**Logged in as:** {st.session_state.user_email}")
            st.write(f"**Connection Status:** {'🟢 Connected' if st.session_state.connection_status else '🔴 Disconnected'}")
        
        if st.button("🗑️ Clear All Job History", type="secondary"):
            st.session_state.clip_job_id = None
            st.session_state.content_job_id = None
            st.success("All job history cleared!")
            st.rerun()

# --- Footer ---
st.markdown("---")
st.markdown(f"**Status:** {'🟢 Connected' if st.session_state.connection_status else '🔴 Disconnected'} | API: {st.session_state.api_base_url}")