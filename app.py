import streamlit as st
import requests
import time
import os
import json
from datetime import datetime
# Emergency fix - clear problematic session state
import streamlit as st
st.session_state.clear()  # This will reset everything

# --- Page Configuration ---
st.set_page_config(
    page_title="Alchemize",
    page_icon="⚗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Initialize Session State ---
def init_session_state():
    defaults = {
        'token': None,
        'user_email': None,
        'content_job_id': None,
        'clip_job_id': None,
        'api_base_url': os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1"),
        'last_poll_time': 0
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# --- Helper Functions ---
def make_api_request(method, endpoint, **kwargs):
    """Make API request with error handling"""
    try:
        url = f"{st.session_state.api_base_url}{endpoint}"
        response = requests.request(method, url, timeout=10, **kwargs)
        return response
    except requests.exceptions.RequestException as e:
        st.error(f"API connection error: {e}")
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
        return False, response.json().get("detail", "Invalid credentials")
    else:
        return False, "Could not connect to the API. Is the backend running?"

def signup(email, password, full_name):
    response = make_api_request(
        "POST", "/auth/register",
        json={"email": email, "password": password, "full_name": full_name}
    )
    if response and response.status_code == 200:
        return True, "Signup successful! Please log in."
    elif response:
        return False, response.json().get("detail", "Could not create user.")
    else:
        return False, "Could not connect to the API."

def poll_job_status(job_id, job_type="video"):
    """Non-blocking job status check with proper error handling"""
    if not job_id:
        return None
    
    # Rate limit polling to every 3 seconds
    current_time = time.time()
    if current_time - st.session_state.last_poll_time < 3:
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
    """Render job status with proper error handling"""
    if not job_id:
        return None
        
    job_data = poll_job_status(job_id, job_type)
    
    if not job_data:
        st.warning("Checking job status...")
        time.sleep(1)
        st.rerun()
        return None
    
    status = job_data.get("status", "UNKNOWN")
    progress = job_data.get("progress_details") or {}  # Handle None case
    percentage = progress.get("percentage", 0) if progress else 0
    description = progress.get("description", "Working...") if progress else "Working..."
    
    # Status display
    if status == "PENDING":
        st.info("⏳ Job is queued and waiting to start...")
    elif status == "IN_PROGRESS":
        st.info(f"🔄 {description}")
        st.progress(percentage / 100)
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
    
    # Auto-refresh for active jobs
    if status in ["PENDING", "IN_PROGRESS"]:
        time.sleep(2)
        st.rerun()
    
    return None

# --- UI Rendering ---

# --- Sidebar ---
with st.sidebar:
    st.markdown("⚗️", help="Your wizard mascot here!")
    st.title("The Alchemist's Lab")
    st.markdown("---")

    if st.session_state.token:
        st.success(f"Logged in as: {st.session_state.user_email}")
        if st.button("Logout", use_container_width=True):
            # Clear only auth-related state
            st.session_state.token = None
            st.session_state.user_email = None
            st.session_state.clip_job_id = None
            st.session_state.content_job_id = None
            st.rerun()

        st.markdown("### 📊 Your Stats")
        st.metric("Videos Processed", "Coming Soon")
        st.metric("Clips Generated", "Coming Soon")
    else:
        st.markdown("### Access Your Account")
        login_tab, signup_tab = st.tabs(["Login", "Sign Up"])
        
        with login_tab:
            with st.form("login_form"):
                email = st.text_input("Email", key="login_email")
                password = st.text_input("Password", type="password", key="login_pass")
                if st.form_submit_button("Login", use_container_width=True):
                    success, message = login(email, password)
                    if success:
                        st.rerun()
                    else:
                        st.error(message)
        
        with signup_tab:
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

# --- Main Content ---
if not st.session_state.token:
    st.title("🧪 Welcome to Alchemize")
    st.markdown("### Turn your videos into viral social media content")
    st.info("👈 Please log in or sign up to begin")
else:
    st.title("Alchemist's Dashboard")
    
    tab1, tab2, tab3 = st.tabs(["🎬 Video Clips", "✍️ Content Suite", "⚙️ Settings"])
    
    # --- VIDEO CLIPS TAB ---
    with tab1:
        st.header("Create Viral Video Clips")
        
        if st.session_state.clip_job_id:
            job_data = render_job_status(st.session_state.clip_job_id, "video")
            
            if job_data and job_data.get("status") == "COMPLETED":
                results = job_data.get("results", {})
                clips_by_platform = results.get("clips_by_platform", {})
                
                if clips_by_platform:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        total_clips = sum(len(urls) for urls in clips_by_platform.values())
                        st.markdown(f"### Generated {total_clips} clips")
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
                    
                    # Display clips by platform
                    for platform, urls in clips_by_platform.items():
                        if urls:
                            st.markdown(f"#### {platform.replace('_', ' ').title()}")
                            cols = st.columns(min(len(urls), 5))
                            for i, url in enumerate(urls):
                                with cols[i % 5]:
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
                    "Choose a video file", 
                    type=['mp4', 'mov', 'avi', 'mkv', 'webm'],
                    help="Max file size: 500MB"
                )
                
                aspect_ratio = st.radio(
                    "Select aspect ratio", 
                    ["9:16 (Vertical)", "1:1 (Square)", "16:9 (Horizontal)"],
                    index=0, horizontal=True
                )
                aspect_ratio_value = aspect_ratio.split(" ")[0]
                
                st.markdown("**Select Platforms:**")
                col1, col2, col3 = st.columns(3)
                with col1:
                    yt_shorts = st.checkbox("YouTube Shorts", value=True)
                    tiktok = st.checkbox("TikTok", value=True)
                with col2:
                    ig_reels = st.checkbox("Instagram Reels", value=True)
                    ig_feed = st.checkbox("Instagram Feed")
                with col3:
                    linkedin = st.checkbox("LinkedIn")
                    twitter = st.checkbox("Twitter/X")
                
                add_captions = st.checkbox("✨ Add Captions", value=True)
                submitted = st.form_submit_button("🚀 Generate Clips", use_container_width=True)

                if submitted and uploaded_file:
                    platforms = [p for p, checked in {
                        "youtube_shorts": yt_shorts, "tiktok": tiktok, "instagram_reels": ig_reels,
                        "instagram_feed": ig_feed, "linkedin": linkedin, "twitter": twitter
                    }.items() if checked]

                    if not platforms:
                        st.error("Please select at least one platform.")
                    else:
                        with st.spinner("Uploading and starting job..."):
                            files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                            params = {
                                "platforms": ",".join(platforms), 
                                "add_captions": add_captions,
                                "aspect_ratio": aspect_ratio_value
                            }
                            response = make_api_request(
                                "POST", "/video/upload-and-clip",
                                files=files, params=params,
                                headers={"Authorization": f"Bearer {st.session_state.token}"}
                            )
                            if response and response.status_code == 202:
                                st.session_state.clip_job_id = response.json().get('job_id')
                                st.success("Upload successful! Processing started...")
                                st.rerun()
                            else:
                                error_msg = response.text if response else "Unknown error"
                                st.error(f"Failed to start job: {error_msg}")
    
    # --- CONTENT SUITE TAB ---
    with tab2:
        st.header("Generate Social Media Content Suite")
        
        if st.session_state.content_job_id:
            job_data = render_job_status(st.session_state.content_job_id, "content")
            
            if job_data and job_data.get("status") == "COMPLETED":
                results = job_data.get("results", {})
                
                if results.get("analysis"):
                    with st.expander("📊 Content Analysis", expanded=True):
                        st.write(results["analysis"])
                
                if results.get("posts"):
                    st.markdown("### Generated Content")
                    st.text_area("Social Media Posts", results["posts"], height=400)
                
                if st.button("✍️ Create New Content", use_container_width=True, key="new_content_job"):
                    clear_job_state("content")
                    st.rerun()

        else:
            # Content generation form
            with st.form("content_form"):
                content_input = st.text_area(
                    "Enter content or URL", 
                    height=200,
                    help="Paste text, article URL, or YouTube URL"
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    tone = st.selectbox("Tone", ["Professional", "Casual", "Enthusiastic"])
                with col2:
                    style = st.selectbox("Writing Style", ["Concise", "Detailed", "Storytelling"])
                
                additional_instructions = st.text_area("Additional Instructions (optional)")
                submitted = st.form_submit_button("✨ Generate Content", use_container_width=True)

                if submitted and content_input.strip():
                    with st.spinner("Starting content generation..."):
                        payload = {
                            "content": content_input.strip(), 
                            "platforms": ["LinkedIn", "Twitter", "Instagram"],
                            "tone": tone, 
                            "style": style, 
                            "additional_instructions": additional_instructions
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
                elif submitted:
                    st.error("Please enter some content to repurpose.")

    # --- SETTINGS TAB ---
    with tab3:
        st.header("Settings")
        st.info("Brand voice customization and preferences coming soon!")
        
        # Add some placeholder settings
        with st.expander("🔧 System Info"):
            st.write(f"API URL: {st.session_state.api_base_url}")
            st.write(f"Logged in as: {st.session_state.user_email}")
        
        if st.button("Clear All Jobs", type="secondary"):
            st.session_state.clip_job_id = None
            st.session_state.content_job_id = None
            st.success("All jobs cleared!")