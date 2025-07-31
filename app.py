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
    if not job_id:
        return None
    try:
        # Use the appropriate endpoint based on job type
        if job_type == "content":
            endpoint = f"{st.session_state.api_base_url}/content/jobs/{job_id}"
        else:
            endpoint = f"{st.session_state.api_base_url}/video/jobs/{job_id}"
            
        response = requests.get(
            endpoint,
            headers={"Authorization": f"Bearer {st.session_state.token}"}
        )
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None

# --- Main UI ---
with st.sidebar:
    st.title("⚗️ Alchemize")
    st.markdown("---")
    
    if st.session_state.token:
        st.success(f"Logged in as: {st.session_state.user_email}")
        if st.button("Logout", use_container_width=True):
            st.session_state.token = None
            st.session_state.user_email = None
            st.session_state.content_job_id = None
            st.session_state.clip_job_id = None
            st.rerun()
            
        # Stats section
        st.markdown("### 📊 Your Stats")
        st.metric("Videos Processed", "Coming Soon")
        st.metric("Clips Generated", "Coming Soon")
        
    else:
        st.markdown("### Access Your Account")
        login_tab, signup_tab = st.tabs(["Login", "Sign Up"])
        
        with login_tab:
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                if st.form_submit_button("Login", use_container_width=True):
                    success, message = login(email, password)
                    if success:
                        st.rerun()
                    else:
                        st.error(message)

        with signup_tab:
            with st.form("signup_form"):
                full_name = st.text_input("Full Name")
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
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
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### 🎬 Upload Video")
        st.markdown("Support for MP4, MOV, MKV and more")
    with col2:
        st.markdown("#### 🤖 AI Analysis")
        st.markdown("Find the most engaging moments")
    with col3:
        st.markdown("#### 📱 Multi-Platform")
        st.markdown("Export for every social network")
    
    st.info("👈 Please log in or sign up to begin")
    
else:
    st.title("🧪 Alchemize Dashboard")
    
    # Create tabs for different features
    tab1, tab2, tab3 = st.tabs(["🎬 Video Clips", "✍️ Content Suite", "⚙️ Settings"])
    
    # --- VIDEO CLIPS TAB ---
    with tab1:
        st.header("Create Viral Video Clips")
        
        if 'clip_job_id' not in st.session_state or st.session_state.clip_job_id is None:
            with st.form("video_upload_form"):
                uploaded_file = st.file_uploader(
                    "Choose a video file", 
                    type=['mp4', 'mov', 'avi', 'mkv', 'webm'],
                    help="Maximum file size: 500MB"
                )

                # Aspect Ratio Selection
                st.markdown("**Choose Clip Format:**")
                aspect_ratio = st.radio(
                    "Select aspect ratio for your clips",
                    options=["9:16 (Vertical - Shorts/Reels)", "1:1 (Square - Instagram)", "16:9 (Horizontal - YouTube)"],
                    index=0,
                    horizontal=True
                )
                aspect_ratio_value = aspect_ratio.split(" ")[0]  # Extract just the ratio

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
                
                add_captions = st.checkbox("✨ Add Captions", value=True, help="Add animated captions to your clips")
                
                submitted = st.form_submit_button("🚀 Generate Clips", use_container_width=True)

            if submitted and uploaded_file:
                platforms = []
                if yt_shorts: platforms.append("youtube_shorts")
                if tiktok: platforms.append("tiktok")
                if ig_reels: platforms.append("instagram_reels")
                if ig_feed: platforms.append("instagram_feed")
                if linkedin: platforms.append("linkedin")
                if twitter: platforms.append("twitter")

                if not platforms:
                    st.error("Please select at least one platform.")
                else:
                    with st.spinner("Uploading and processing video..."):
                        files = {'file': (uploaded_file.name, uploaded_file, uploaded_file.type)}
                        params = {
                            "platforms": ",".join(platforms), 
                            "add_captions": add_captions,
                            "aspect_ratio": aspect_ratio_value
                        }
                        
                        try:
                            response = requests.post(
                                f"{st.session_state.api_base_url}/video/upload-and-clip", 
                                files=files, 
                                params=params, 
                                headers={"Authorization": f"Bearer {st.session_state.token}"}
                            )
                            if response.status_code == 202:
                                job_info = response.json()
                                st.session_state.clip_job_id = job_info.get('job_id')
                                st.rerun()
                            else:
                                st.error(f"Failed to start job: {response.text}")
                        except Exception as e:
                            st.error(f"Error: {e}")
        
        # Show job status and results
        if st.session_state.clip_job_id:
            job_data = poll_job_status(st.session_state.clip_job_id)
            
            if job_data:
                status = job_data.get("status", "UNKNOWN")
                
                if status in ["PENDING", "IN_PROGRESS"]:
                    progress = job_data.get("progress_details", {})
                    st.info(f"Status: {status}")
                    if progress:
                        st.progress(
                            progress.get("percentage", 0) / 100,
                            text=progress.get("description", "Processing...")
                        )
                    time.sleep(2)
                    st.rerun()
                    
                elif status == "COMPLETED":
                    st.success("✅ Clips generated successfully!")
                    
                    results = job_data.get("results", {})
                    clips_by_platform = results.get("clips_by_platform", {})
                    
                    if clips_by_platform:
                        # Download button
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
                        
                        # Display clips by platform with 5-column grid
                        for platform, urls in clips_by_platform.items():
                            if urls:  # Only show platforms with clips
                                st.markdown(f"#### {platform.replace('_', ' ').title()}")
                                
                                # Create rows of 5 videos
                                for row_start in range(0, len(urls), 5):
                                    cols = st.columns(5)
                                    for i, url in enumerate(urls[row_start:row_start+5]):
                                        with cols[i]:
                                            full_url = url if url.startswith("http") else f"http://localhost:8000{url}"
                                            st.video(full_url)
                                            st.caption(f"Clip {row_start + i + 1}")
                        
                        # New job button
                        if st.button("🎬 Process Another Video", use_container_width=True):
                            st.session_state.clip_job_id = None
                            st.rerun()
                    else:
                        st.warning("No clips were generated. Please try again.")
                        if st.button("Try Again"):
                            st.session_state.clip_job_id = None
                            st.rerun()
                            
                elif status == "FAILED":
                    st.error(f"Job failed: {job_data.get('error_message', 'Unknown error')}")
                    if st.button("Try Again"):
                        st.session_state.clip_job_id = None
                        st.rerun()
    
    # --- CONTENT SUITE TAB ---
    with tab2:
        st.header("Generate Social Media Content Suite")
        
        if 'content_job_id' not in st.session_state or st.session_state.content_job_id is None:
            with st.form("content_form"):
                content_input = st.text_area(
                    "Enter your content", 
                    placeholder="Paste text, article URL, or video transcript...",
                    height=200
                )
                
                # Tone and style options
                col1, col2 = st.columns(2)
                with col1:
                    tone = st.selectbox(
                        "Tone",
                        ["Professional", "Casual", "Enthusiastic", "Educational", "Humorous"],
                        index=0
                    )
                with col2:
                    style = st.selectbox(
                        "Writing Style",
                        ["Concise", "Detailed", "Storytelling", "Data-driven", "Conversational"],
                        index=0
                    )
                
                st.markdown("**Select Platforms:**")
                col1, col2 = st.columns(2)
                with col1:
                    linkedin_post = st.checkbox("LinkedIn", value=True)
                    facebook_post = st.checkbox("Facebook", value=True)
                    twitter_post = st.checkbox("Twitter/X", value=True)
                with col2:
                    instagram_post = st.checkbox("Instagram", value=True)
                    tiktok_post = st.checkbox("TikTok Caption", value=True)
                    blog_post = st.checkbox("Blog Post")
                
                # Additional instructions
                additional_instructions = st.text_area(
                    "Additional Instructions (optional)",
                    placeholder="Any specific requirements, hashtags to include, CTAs, etc.",
                    height=100
                )
                
                submitted = st.form_submit_button("✨ Generate Content", use_container_width=True)
            
            if submitted and content_input:
                platforms = []
                if linkedin_post: platforms.append("LinkedIn")
                if facebook_post: platforms.append("Facebook")
                if twitter_post: platforms.append("Twitter")
                if instagram_post: platforms.append("Instagram")
                if tiktok_post: platforms.append("TikTok")
                if blog_post: platforms.append("Blog")
                
                with st.spinner("Generating content..."):
                    try:
                        # Include tone and style in the request
                        payload = {
                            "content": content_input,
                            "platforms": platforms,
                            "tone": tone,
                            "style": style,
                            "additional_instructions": additional_instructions
                        }
                        
                        response = requests.post(
                            f"{st.session_state.api_base_url}/content/repurpose",
                            json=payload,
                            headers={"Authorization": f"Bearer {st.session_state.token}"}
                        )
                        if response.status_code == 202:
                            job_info = response.json()
                            st.session_state.content_job_id = job_info.get('job_id')
                            st.rerun()
                        else:
                            st.error(f"Failed: {response.text}")
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        # Show content job status
        if st.session_state.content_job_id:
            job_data = poll_job_status(st.session_state.content_job_id, job_type="content")
            
            if job_data:
                status = job_data.get("status", "UNKNOWN")
                
                if status in ["PENDING", "IN_PROGRESS"]:
                    progress = job_data.get("progress_details", {})
                    st.info(f"Status: {status}")
                    if progress:
                        st.progress(
                            progress.get("percentage", 0) / 100,
                            text=progress.get("description", "Processing...")
                        )
                    time.sleep(2)
                    st.rerun()
                    
                elif status == "COMPLETED":
                    st.success("✅ Content generated successfully!")
                    
                    results = job_data.get("results", {})
                    if results:
                        # Show analysis
                        if results.get("analysis"):
                            with st.expander("📊 Content Analysis", expanded=True):
                                st.write(results["analysis"])
                        
                        # Show generated posts with reroll functionality
                        if results.get("posts"):
                            st.markdown("### Generated Posts")
                            
                            # Control buttons
                            col1, col2, col3 = st.columns([2, 1, 1])
                            with col1:
                                st.markdown("**Your content is ready!**")
                            with col2:
                                if st.button("🔄 Regenerate", use_container_width=True):
                                    # Reuse the same content but trigger new generation
                                    st.session_state.content_job_id = None
                                    st.rerun()
                            with col3:
                                st.download_button(
                                    "📋 Download",
                                    data=results["posts"],
                                    file_name=f"social_posts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                                    mime="text/plain",
                                    use_container_width=True
                                )
                            
                            # Display posts
                            st.text_area("", results["posts"], height=400)
                        
                        # New content button
                        if st.button("✍️ Create New Content", use_container_width=True):
                            st.session_state.content_job_id = None
                            st.rerun()
                            
                elif status == "FAILED":
                    st.error(f"Job failed: {job_data.get('error_message', 'Unknown error')}")
                    if st.button("Try Again"):
                        st.session_state.content_job_id = None
                        st.rerun()
    
    # --- SETTINGS TAB ---
    with tab3:
        st.header("Settings")
        st.info("Brand voice customization and preferences coming soon!")
        
        # Placeholder for future settings
        with st.expander("🎨 Brand Voice"):
            st.text_input("Brand Tone", placeholder="Professional, Casual, Friendly...")
            st.text_area("Sample Posts", placeholder="Paste examples of your brand's writing style...")
            st.button("Save Brand Voice", disabled=True)
        
        with st.expander("🔧 Preferences"):
            st.slider("Default Clip Length", 15, 60, 30, help="Default length for video clips in seconds")
            st.multiselect("Default Platforms", ["YouTube Shorts", "TikTok", "Instagram Reels"])
            st.button("Save Preferences", disabled=True)