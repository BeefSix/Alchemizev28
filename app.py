import streamlit as st
import requests
import time
import os
import json
from app.core.config import settings

# --- Page Configuration ---
st.set_page_config(
    page_title="Alchemize",
    page_icon="⚗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- State Management ---
if 'token' not in st.session_state:
    st.session_state.token = None
if 'job_id' not in st.session_state:
    st.session_state.job_id = None
if 'api_base_url' not in st.session_state:
    st.session_state.api_base_url = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")

# --- Helper Functions ---
def login(email, password):
    try:
        response = requests.post(
            f"{st.session_state.api_base_url}/auth/token",
            data={"username": email, "password": password}
        )
        if response.status_code == 200:
            st.session_state.token = response.json()['access_token']
            return True, "Login successful!"
        else:
            return False, response.json().get("detail", "Invalid credentials")
    except requests.exceptions.ConnectionError:
        return False, "Could not connect to the API. Is the backend running?"

def signup(email, password):
    try:
        response = requests.post(
            f"{st.session_state.api_base_url}/auth/users/",
            json={"email": email, "password": password}
        )
        if response.status_code == 200:
            return True, "Signup successful! Please log in."
        else:
            return False, response.json().get("detail", "Could not create user.")
    except requests.exceptions.ConnectionError:
        return False, "Could not connect to the API. Is the backend running?"

def poll_job_status(job_id):
    if not job_id:
        return None
    try:
        response = requests.get(
            f"{st.session_state.api_base_url}/video/jobs/{job_id}",
            headers={"Authorization": f"Bearer {st.session_state.token}"}
        )
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None

# --- UI Rendering ---

# --- Sidebar for Login/Signup/Logout ---
with st.sidebar:
    st.title("⚗️ Alchemize")
    st.markdown("---")
    if st.session_state.token:
        st.success("Logged in successfully.")
        if st.button("Logout"):
            st.session_state.token = None
            st.session_state.job_id = None
            st.rerun()
    else:
        st.markdown("### Member Access")
        login_tab, signup_tab = st.tabs(["Login", "Sign Up"])
        
        with login_tab:
            with st.form("login_form"):
                email = st.text_input("Email", key="login_email")
                password = st.text_input("Password", type="password", key="login_password")
                if st.form_submit_button("Login"):
                    success, message = login(email, password)
                    if success:
                        st.rerun()
                    else:
                        st.error(message)

        with signup_tab:
            with st.form("signup_form"):
                email = st.text_input("Email", key="signup_email")
                password = st.text_input("Password", type="password", key="signup_password")
                if st.form_submit_button("Sign Up"):
                    success, message = signup(email, password)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)

# --- Main Content Area ---
if not st.session_state.token:
    st.header("Welcome to Alchemize")
    st.markdown("The fastest way to turn long-form video into dozens of high-quality social media clips.")
    st.info("Please log in or sign up using the sidebar to begin.")
else:
    # Main application interface after login
    st.title("AI Video Repurposing Engine")

    # =================== THIS IS THE MODIFIED SECTION ===================
    st.header("1. Create Your Clips")
    with st.form("video_upload_form"):
        uploaded_file = st.file_uploader(
            "Choose a video file to process (MP4, MOV, etc.)", 
            type=['mp4', 'mov', 'avi', 'mkv', 'webm']
        )

        st.write("**Select Platforms to Export To:**")
        col1, col2, col3 = st.columns(3)
        with col1:
            yt_selected = st.checkbox("YouTube Shorts", value=True)
            tk_selected = st.checkbox("TikTok", value=True)
        with col2:
            ig_selected = st.checkbox("Instagram Reels", value=True)
            li_selected = st.checkbox("LinkedIn", value=True)
        with col3:
            tw_selected = st.checkbox("Twitter / X", value=True)
        
        submitted = st.form_submit_button("Start Clipping")

    if submitted and uploaded_file is not None:
        platforms_to_export = []
        if yt_selected: platforms_to_export.append("youtube_shorts")
        if tk_selected: platforms_to_export.append("tiktok")
        if ig_selected: platforms_to_export.append("instagram_reels")
        if li_selected: platforms_to_export.append("linkedin")
        if tw_selected: platforms_to_export.append("twitter")

        if not platforms_to_export:
            st.error("Please select at least one platform.")
        else:
            platform_string = ",".join(platforms_to_export)
            with st.spinner("Uploading video and starting job... This may take a moment."):
                files = {'file': (uploaded_file.name, uploaded_file, uploaded_file.type)}
                api_url = f"{st.session_state.api_base_url}/video/upload-and-clip"
                params = {"platforms": platform_string, "add_captions": True}
                
                try:
                    response = requests.post(
                        api_url, 
                        files=files, 
                        params=params, 
                        headers={"Authorization": f"Bearer {st.session_state.token}"}
                    )
                    if response.status_code == 202:
                        job_info = response.json()
                        st.session_state.job_id = job_info.get('job_id')
                        st.success(f"✅ {job_info.get('message', 'Job started!')}")
                        st.info(f"Your Job ID is: {st.session_state.job_id}. Track its progress below.")
                    else:
                        st.error(f"Failed to start job: {response.status_code} - {response.text}")
                except requests.exceptions.RequestException as e:
                    st.error(f"Could not connect to the backend: {e}")
    # =================== END OF MODIFIED SECTION ===================
    
    st.markdown("---")

    # --- Job Status & Results Viewer ---
    st.header("2. Job Status & Results")
    if st.session_state.job_id:
        st.info(f"Tracking Job ID: **{st.session_state.job_id}**")
        
        status_placeholder = st.empty()
        
        # Polling logic
        while True:
            job_data = poll_job_status(st.session_state.job_id)
            if not job_data:
                st.warning("Could not retrieve job status. Retrying in 5 seconds...")
                time.sleep(5)
                continue

            status = job_data.get("status", "UNKNOWN")
            progress = job_data.get("progress_details", {})
            
            with status_placeholder.container():
                st.write(f"**Status:** `{status}`")
                if progress:
                    desc = progress.get("description", "Processing...")
                    percent = progress.get("percentage", 0)
                    st.progress(percent, text=desc)
            
            if status == "COMPLETED":
                st.balloons()
                st.success("🎉 Job completed! Your clips are ready below.")
                results = job_data.get("results", {})
                clips_by_platform = results.get("clips_by_platform", {})
                
                # Check for download content before showing the button
                try:
                    download_response = requests.get(
                        f"{st.session_state.api_base_url}/video/jobs/{st.session_state.job_id}/download-all",
                        headers={"Authorization": f"Bearer {st.session_state.token}"},
                        stream=True
                    )
                    if download_response.status_code == 200:
                        st.download_button(
                            label="📥 Download All Clips (.zip)",
                            data=download_response.content,
                            file_name=f"alchemize_clips_{st.session_state.job_id[:8]}.zip",
                            mime="application/zip",
                        )
                    else:
                        st.warning("Could not prepare download file.")
                except Exception as e:
                    st.error(f"Download failed: {e}")
                
                st.markdown("---")

                for platform, urls in clips_by_platform.items():
                    st.subheader(f"Clips for {platform.replace('_', ' ').title()}")
                    for i, url in enumerate(urls):
                        # Construct full URL for local static files
                        full_url = f"http://localhost:8000{url}" if url.startswith("/static") else url
                        st.video(full_url)
                break
            elif status == "FAILED":
                st.error(f"Job Failed: {job_data.get('error_message', 'An unknown error occurred.')}")
                break
            elif status in ["PENDING", "IN_PROGRESS"]:
                time.sleep(5)
            else: # Stop polling if status is unknown or unexpected
                break
    else:
        st.info("Submit a video above to see its status and results here.")