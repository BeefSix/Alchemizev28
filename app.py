import streamlit as st
import requests
import time
import os
import json
from datetime import datetime

# --- Page Configuration ---
st.set_page_config(
    page_title="Alchemize",
    page_icon="⚗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Initialize Session State ---
if 'token' not in st.session_state:
    st.session_state.token = None
if 'user_email' not in st.session_state:
    st.session_state.user_email = None
if 'content_job_id' not in st.session_state:
    st.session_state.content_job_id = None
if 'clip_job_id' not in st.session_state:
    st.session_state.clip_job_id = None
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
            st.session_state.user_email = email
            return True, "Login successful!"
        else:
            return False, response.json().get("detail", "Invalid credentials")
    except requests.exceptions.ConnectionError:
        return False, "Could not connect to the API. Is the backend running?"

def signup(email, password, full_name):
    try:
        response = requests.post(
            f"{st.session_state.api_base_url}/auth/register",
            json={"email": email, "password": password, "full_name": full_name}
        )
        if response.status_code == 200:
            return True, "Signup successful! Please log in."
        else:
            return False, response.json().get("detail", "Could not create user.")
    except requests.exceptions.ConnectionError:
        return False, "Could not connect to the API."

def poll_job_status(job_id, job_type="video"):
    """Polls the API for the status of a given job ID."""
    if not job_id:
        return None
    try:
        endpoint = f"{st.session_state.api_base_url}/{job_type}/jobs/{job_id}"
        response = requests.get(
            endpoint,
            headers={"Authorization": f"Bearer {st.session_state.token}"}
        )
        return response.json() if response.status_code == 200 else None
    except requests.exceptions.RequestException:
        return None

# --- UI Rendering ---

# --- Sidebar ---
with st.sidebar:
    wizard_image_path = "app/static/img/your_wizard_image.png" # Make sure to create this path
    if os.path.exists(wizard_image_path):
        st.sidebar.image(wizard_image_path, width=150)
    else:
        st.sidebar.markdown("⚗️", help="Your wizard mascot here!")
        
    st.sidebar.title("The Alchemist's Lab")
    st.markdown("---")

    if st.session_state.token:
        st.success(f"Logged in as: {st.session_state.user_email}")
        if st.button("Logout", use_container_width=True):
            for key in st.session_state.keys():
                del st.session_state[key]
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
            # Create placeholders for the progress bar and status text
            status_placeholder = st.empty()
            progress_bar = st.empty()

            while True:
                job_data = poll_job_status(st.session_state.clip_job_id, job_type="video")
                if not job_data:
                    status_placeholder.error("Could not retrieve job status.")
                    break

                status = job_data.get("status", "UNKNOWN")
                progress = job_data.get("progress_details", {})
                percentage = progress.get("percentage", 0)
                description = progress.get("description", "Working...")
                
                # Update placeholders
                with status_placeholder.container():
                    st.info(f"Status: {status}")
                with progress_bar.container():
                    st.progress(percentage / 100, text=description)

                if status == "COMPLETED":
                    st.success("✅ Clips generated successfully!")
                    # Display results logic from your original code
                    results = job_data.get("results", {})
                    clips_by_platform = results.get("clips_by_platform", {})
                    
                    if clips_by_platform:
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"### Generated {sum(len(urls) for urls in clips_by_platform.values())} clips")
                        with col2:
                            download_response = requests.get(
                                f"{st.session_state.api_base_url}/video/jobs/{st.session_state.clip_job_id}/download-all",
                                headers={"Authorization": f"Bearer {st.session_state.token}"},
                                stream=True
                            )
                            if download_response.status_code == 200:
                                st.download_button(
                                    label="📥 Download All",
                                    data=download_response.content,
                                    file_name=f"alchemize_clips_{st.session_state.clip_job_id[:8]}.zip",
                                    mime="application/zip",
                                    use_container_width=True
                                )
                        
                        for platform, urls in clips_by_platform.items():
                            if urls:
                                st.markdown(f"#### {platform.replace('_', ' ').title()}")
                                num_columns = 5
                                for row_start in range(0, len(urls), num_columns):
                                    cols = st.columns(num_columns)
                                    for i, url in enumerate(urls[row_start:row_start+num_columns]):
                                        with cols[i]:
                                            full_url = url if url.startswith("http") else f"http://localhost:8000{url}"
                                            st.video(full_url)
                                            st.caption(f"Clip {row_start + i + 1}")
                    
                    if st.button("🎬 Process Another Video", use_container_width=True, key="new_video_job"):
                        st.session_state.clip_job_id = None
                        st.rerun()
                    break # Exit the loop

                elif status == "FAILED":
                    st.error(f"Job failed: {job_data.get('error_message', 'Unknown error')}")
                    if st.button("Try Again", key="failed_video_job"):
                        st.session_state.clip_job_id = None
                        st.rerun()
                    break # Exit the loop
                
                time.sleep(3) # Wait before polling again

        else: # If no job is active, show the form
            with st.form("video_upload_form"):
                uploaded_file = st.file_uploader(
                    "Choose a video file", type=['mp4', 'mov', 'avi', 'mkv', 'webm']
                )
                aspect_ratio = st.radio(
                    "Select aspect ratio", ["9:16 (Vertical)", "1:1 (Square)", "16:9 (Horizontal)"],
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
                                "platforms": ",".join(platforms), "add_captions": add_captions,
                                "aspect_ratio": aspect_ratio_value
                            }
                            response = requests.post(
                                f"{st.session_state.api_base_url}/video/upload-and-clip", 
                                files=files, params=params,
                                headers={"Authorization": f"Bearer {st.session_state.token}"}
                            )
                            if response.status_code == 202:
                                st.session_state.clip_job_id = response.json().get('job_id')
                                st.rerun()
                            else:
                                st.error(f"Failed to start job: {response.text}")
    
    # --- CONTENT SUITE TAB ---
    with tab2:
        st.header("Generate Social Media Content Suite")
        
        if st.session_state.content_job_id:
            # Polling logic for content job
            status_placeholder = st.empty()
            progress_bar = st.empty()
            while True:
                job_data = poll_job_status(st.session_state.content_job_id, job_type="content")
                if not job_data:
                    status_placeholder.error("Could not retrieve job status.")
                    break
                status = job_data.get("status", "UNKNOWN")
                progress = job_data.get("progress_details", {})
                percentage = progress.get("percentage", 0)
                description = progress.get("description", "Working...")
                with status_placeholder.container():
                    st.info(f"Status: {status}")
                with progress_bar.container():
                    st.progress(percentage / 100, text=description)
                if status == "COMPLETED":
                    st.success("✅ Content generated successfully!")
                    results = job_data.get("results", {})
                    # Display results from your original code
                    if results.get("analysis"):
                        with st.expander("📊 Content Analysis", expanded=True):
                            st.write(results["analysis"])
                    if results.get("posts"):
                        st.text_area("Generated Posts", results["posts"], height=400)
                    if st.button("✍️ Create New Content", use_container_width=True, key="new_content_job"):
                        st.session_state.content_job_id = None
                        st.rerun()
                    break
                elif status == "FAILED":
                    st.error(f"Job failed: {job_data.get('error_message', 'Unknown error')}")
                    if st.button("Try Again", key="failed_content_job"):
                        st.session_state.content_job_id = None
                        st.rerun()
                    break
                time.sleep(3)

        else: # Show content form
            with st.form("content_form"):
                content_input = st.text_area("Enter content", height=200)
                col1, col2 = st.columns(2)
                with col1:
                    tone = st.selectbox("Tone", ["Professional", "Casual", "Enthusiastic"])
                with col2:
                    style = st.selectbox("Writing Style", ["Concise", "Detailed", "Storytelling"])
                additional_instructions = st.text_area("Additional Instructions (optional)")
                submitted = st.form_submit_button("✨ Generate Content", use_container_width=True)

                if submitted and content_input:
                    with st.spinner("Starting content job..."):
                        payload = {
                            "content": content_input, "platforms": ["LinkedIn", "Twitter"],
                            "tone": tone, "style": style, "additional_instructions": additional_instructions
                        }
                        response = requests.post(
                            f"{st.session_state.api_base_url}/content/repurpose", json=payload,
                            headers={"Authorization": f"Bearer {st.session_state.token}"}
                        )
                        if response.status_code == 202:
                            st.session_state.content_job_id = response.json().get('job_id')
                            st.rerun()
                        else:
                            st.error(f"Failed: {response.text}")

    # --- SETTINGS TAB ---
    with tab3:
        st.header("Settings")
        st.info("Brand voice customization and preferences coming soon!")