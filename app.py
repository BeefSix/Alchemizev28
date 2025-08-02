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
        'connection_status': None
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# --- Enhanced Connection Test ---
def test_api_connection():
    if st.session_state.connection_tested:
        return st.session_state.connection_status
    
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
                
                if "web:8000" in test_url:
                    st.session_state.api_base_url = "http://web:8000/api/v1"
                elif "localhost:8000" in test_url:
                    st.session_state.api_base_url = "http://localhost:8000/api/v1"
                
                return True
        except Exception as e:
            continue
    
    st.session_state.connection_status = False
    st.session_state.connection_tested = True
    return False

# --- Helper Functions ---
def make_api_request(method, endpoint, **kwargs):
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
        try:
            error_data = response.json()
            error_detail = error_data.get("detail", "Signup failed")
        except:
            error_detail = f"HTTP {response.status_code}: {response.text}"
        return False, error_detail
    else:
        return False, "Could not connect to the API."

def get_job_status(job_id, job_type="video"):
    """Get job status from API"""
    if not job_id:
        return None
    
    response = make_api_request(
        "GET", f"/{job_type}/jobs/{job_id}",
        headers={"Authorization": f"Bearer {st.session_state.token}"}
    )
    return response.json() if response and response.status_code == 200 else None

def get_recent_jobs(job_type="video", limit=10):
    """Get recent jobs for the current user (this would require a new API endpoint)"""
    # For now, we'll use session state, but this should be stored in database
    return []

def display_video_results(job_data):
    """Display completed video job results properly"""
    if not job_data or job_data.get("status") != "COMPLETED":
        return False
    
    results = job_data.get("results", {})
    clips_by_platform = results.get("clips_by_platform", {})
    
    if not clips_by_platform:
        st.error("No clips were generated.")
        return False
    
    # Header with stats
    col1, col2 = st.columns([3, 1])
    with col1:
        total_clips = results.get("total_clips", 0)
        video_duration = results.get("video_duration", 0)
        captions_added = results.get("captions_added", False)
        
        st.success(f"✅ Generated {total_clips} clips successfully!")
        st.info(f"📹 Original video: {video_duration:.1f}s | 🎤 Live karaoke captions: {'Yes' if captions_added else 'No'}")
    
    with col2:
        # Download all button
        job_id = job_data.get("id")
        if job_id:
            response = make_api_request(
                "GET", f"/video/jobs/{job_id}/download-all",
                headers={"Authorization": f"Bearer {st.session_state.token}"},
                stream=True
            )
            if response and response.status_code == 200:
                st.download_button(
                    label="📥 Download All Clips",
                    data=response.content,
                    file_name=f"alchemize_clips_{job_id[:8]}.zip",
                    mime="application/zip",
                    use_container_width=True,
                    type="primary"
                )
    
    # Display clips in a grid
    all_clips = []
    for platform, urls in clips_by_platform.items():
        if isinstance(urls, list):
            all_clips.extend(urls)
    
    if all_clips:
        st.markdown("### 🎬 Your Generated Clips")
        
        # Display clips in rows of 3
        for i in range(0, len(all_clips), 3):
            cols = st.columns(3)
            for j, url in enumerate(all_clips[i:i+3]):
                with cols[j]:
                    # Build full URL
                    if url.startswith("/static/"):
                        full_url = f"http://localhost:8000{url}"
                    else:
                        full_url = url
                    
                    try:
                        st.video(full_url)
                        st.caption(f"🎥 Clip {i+j+1}")
                        
                        # Individual download button
                        response = requests.get(full_url, stream=True)
                        if response.status_code == 200:
                            filename = f"clip_{i+j+1}.mp4"
                            st.download_button(
                                label="⬇️ Download",
                                data=response.content,
                                file_name=filename,
                                mime="video/mp4",
                                key=f"download_{i+j+1}",
                                use_container_width=True
                            )
                    except Exception as e:
                        st.error(f"Could not load clip {i+j+1}")
                        st.text(f"URL: {full_url}")
    
    return True

def display_content_results(job_data):
    """Display completed content job results properly"""
    if not job_data or job_data.get("status") != "COMPLETED":
        return False
    
    results = job_data.get("results", {})
    
    st.success("✅ Content suite generated successfully!")
    
    # Display analysis
    if results.get("analysis"):
        with st.expander("📊 Content Analysis", expanded=False):
            st.markdown(results["analysis"])
    
    # Display generated posts
    if results.get("posts"):
        st.markdown("### 📝 Generated Social Media Posts")
        st.markdown(results["posts"])
        
        # Copy to clipboard button (JavaScript)
        st.markdown("""
        <script>
        function copyToClipboard() {
            navigator.clipboard.writeText(document.getElementById('posts-content').innerText);
            alert('Posts copied to clipboard!');
        }
        </script>
        <button onclick="copyToClipboard()" style="background-color: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer;">
            📋 Copy All Posts
        </button>
        <div id="posts-content" style="display: none;">""" + results["posts"] + """</div>
        """, unsafe_allow_html=True)
    
    return True

def render_job_status_with_auto_refresh(job_id, job_type):
    """Render job status with proper auto-refresh and results display"""
    if not job_id:
        return None
    
    # Get current job status
    job_data = get_job_status(job_id, job_type)
    
    if not job_data:
        st.warning("⚠️ Could not retrieve job status")
        if st.button("🔄 Retry", key=f"retry_{job_id}"):
            st.rerun()
        return None
    
    status = job_data.get("status", "UNKNOWN")
    progress = job_data.get("progress_details") or {}
    percentage = progress.get("percentage", 0) if progress else 0
    description = progress.get("description", "Processing...") if progress else "Processing..."
    
    # Status display
    if status == "PENDING":
        st.info("⏳ Job is queued and waiting to start...")
        time.sleep(2)
        st.rerun()
        
    elif status == "IN_PROGRESS":
        st.info(f"🔄 {description}")
        if percentage > 0:
            st.progress(percentage / 100, text=f"{percentage}% complete")
        
        # Auto-refresh every 3 seconds for active jobs
        time.sleep(3)
        st.rerun()
        
    elif status == "COMPLETED":
        # Display results based on job type
        if job_type == "video":
            display_video_results(job_data)
        elif job_type == "content":
            display_content_results(job_data)
        
        return job_data
        
    elif status == "FAILED":
        error_message = job_data.get('error_message', 'Unknown error')
        st.error(f"❌ Job failed: {error_message}")
        
        if st.button("🔄 Try Again", key=f"retry_failed_{job_id}"):
            # Clear this job and allow new submission
            return "retry"
    
    return None

# --- Main UI ---
st.title("🧪 Alchemize - Video to Viral Content")

# Connection status
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
    st.markdown("⚗️", help="Your AI video wizard!")
    st.title("The Alchemist's Lab")
    
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
            st.rerun()

        st.markdown("### 📊 Your Stats")
        st.metric("Videos Processed", "Coming Soon")
        st.metric("Clips Generated", "Coming Soon")
    else:
        st.error("⚠️ Cannot connect to API")

# --- Main Content ---
if not st.session_state.connection_status:
    st.error("🔌 **Connection Issue Detected**")
    st.markdown("The frontend cannot connect to the backend API.")

elif not st.session_state.token:
    st.markdown("### Turn your videos into viral social media content")
    st.info("👈 Please log in or sign up to begin")
    
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
    tab1, tab2 = st.tabs(["🎬 Video Clips", "✍️ Content Suite"])
    
    # --- VIDEO CLIPS TAB ---
    with tab1:
        st.header("Create Viral Video Clips")
        st.markdown("Upload ANY video format and get professional clips with **live karaoke-style captions**!")
        
        # Check for active job in URL params
        active_video_job = st.query_params.get("video_job")
        
        if active_video_job:
            st.markdown("### 🔄 Processing Your Video...")
            result = render_job_status_with_auto_refresh(active_video_job, "video")
            
            if result == "retry":
                # Clear the job and start over
                st.query_params.clear()
                st.rerun()
            elif result:
                # Job completed successfully 
                if st.button("🎬 Process Another Video", use_container_width=True, type="primary"):
                    st.query_params.clear()
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
                
                submitted = st.form_submit_button("🚀 Create Clips with Live Captions", use_container_width=True, type="primary")

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
                            job_id = response.json().get('job_id')
                            st.success("✅ Upload successful! Processing started...")
                            # Store job ID in URL params to persist across refreshes
                            st.query_params["video_job"] = job_id
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
        
        # Check for active job in URL params
        active_content_job = st.query_params.get("content_job")
        
        if active_content_job:
            st.markdown("### 🔄 Generating Your Content...")
            result = render_job_status_with_auto_refresh(active_content_job, "content")
            
            if result == "retry":
                # Clear the job and start over
                st.query_params.clear()
                st.rerun()
            elif result:
                # Job completed successfully
                if st.button("✍️ Create New Content", use_container_width=True, type="primary"):
                    st.query_params.clear()
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
                
                submitted = st.form_submit_button("✨ Generate Content Suite", use_container_width=True, type="primary")

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
                            job_id = response.json().get('job_id')
                            st.success("Content generation started!")
                            # Store job ID in URL params to persist across refreshes
                            st.query_params["content_job"] = job_id
                            st.rerun()
                        else:
                            error_msg = response.text if response else "Unknown error"
                            st.error(f"Failed to start content generation: {error_msg}")
                elif submitted and not content_input.strip():
                    st.error("Please enter some content to repurpose.")
                elif submitted and not platforms:
                    st.error("Please select at least one platform.")

# --- Footer ---
st.markdown("---")
st.markdown(f"**Status:** {'🟢 Connected' if st.session_state.connection_status else '🔴 Disconnected'} | API: {st.session_state.api_base_url}")