# app.py
import streamlit as st
import requests
import time
import os

# --- Page Configuration ---
st.set_page_config(
    page_title="Alchemize",
    page_icon="🧪",
    layout="wide"
)

# --- API Configuration ---
API_URL = os.getenv("API_URL", "http://localhost:8000")

# --- Session State Initialization ---
# This ensures all necessary keys exist in the session state
def initialize_session_state():
    defaults = {
        'user_token': None,
        'user_info': None,
        'content_job_id': None,
        'content_status': 'idle',
        'content_results': None,
        'clip_job_id': None,
        'clip_status': 'idle',
        'clip_results': None,
        'thumbnail_job_id': None,   # ADDED FOR THUMBNAIL
        'thumbnail_status': 'idle', # ADDED FOR THUMBNAIL
        'thumbnail_results': None,  # ADDED FOR THUMBNAIL
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

initialize_session_state()

# --- Authentication Functions ---
def get_auth_headers():
    if not st.session_state.user_token:
        return {}
    return {"Authorization": f"Bearer {st.session_state.user_token}"}

def login(email, password):
    try:
        response = requests.post(f"{API_URL}/api/v1/auth/token", data={"username": email, "password": password})
        if response.status_code == 200:
            token_data = response.json()
            st.session_state.user_token = token_data["access_token"]
            user_response = requests.get(f"{API_URL}/api/v1/auth/me", headers=get_auth_headers())
            if user_response.status_code == 200:
                st.session_state.user_info = user_response.json()
            st.rerun()
        else:
            st.error(response.json().get("detail", "Login failed."))
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to connect to the API: {e}")

def signup(email, password, full_name):
    try:
        payload = {"email": email, "password": password, "full_name": full_name}
        response = requests.post(f"{API_URL}/api/v1/auth/register", json=payload)
        if response.status_code == 200:
            st.success("Signup successful! Please log in.")
        else:
            st.error(response.json().get("detail", "Signup failed."))
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to connect to the API: {e}")

def logout():
    # Reset all session state keys to their defaults
    initialize_session_state()
    st.rerun()

# --- Job Polling and Display ---
def poll_job_status(job_id):
    try:
        api_url = f"{API_URL}/api/v1/video/jobs/{job_id}" # Using a single endpoint for all jobs
        resp = requests.get(api_url, headers=get_auth_headers(), timeout=15)
        return resp.json() if resp.status_code == 200 else None
    except requests.exceptions.RequestException:
        return None

def display_job_interface(job_type):
    job_id_key = f'{job_type}_job_id'
    status_key = f'{job_type}_status'
    results_key = f'{job_type}_results'

    # Check if a job is in progress or pending
    if st.session_state[status_key] not in ['idle', 'COMPLETED', 'FAILED']:
        job_id = st.session_state[job_id_key]
        status_data = poll_job_status(job_id)
        
        if status_data:
            # Update session state with the latest status and details
            status = status_data.get("status", "UNKNOWN")
            st.session_state[status_key] = status
            st.session_state[results_key] = status_data # Store full status_data for later retrieval of results/error

            progress_details = status_data.get("progress_details")
            if progress_details and isinstance(progress_details, dict):
                desc = progress_details.get("description", "Processing...")
                percentage = progress_details.get("percentage", 0)
                st.progress(percentage / 100, text=desc)
            
            # If job is completed or failed, force a rerun to render final state
            if status in ["COMPLETED", "FAILED"]:
                 st.rerun() # Rerun to display final results/error without delay
            else:
                time.sleep(3) # Wait before polling again for ongoing jobs
                st.rerun()
        else:
            st.warning("Could not retrieve job status. Retrying...")
            time.sleep(3)
            st.rerun()

    # Display results or error once job is in a final state
    if st.session_state[status_key] == "COMPLETED":
        results_data = st.session_state.get(results_key, {})
        st.success(f"✅ {job_type.replace('_', ' ').title()} job completed!")
        
        # Display specific results based on job type
        if job_type == 'clip':
            clip_urls = results_data.get("results", {}).get("clip_urls", [])
            if clip_urls:
                st.subheader("Generated Video Clips:")
                for url in clip_urls:
                    st.video(f"{API_URL}{url}") # Prepend API_URL for full path
            else:
                st.info("No video clips generated.")
        elif job_type == 'content':
            posts = results_data.get("results", {}).get("posts", "No content generated.")
            st.text_area("Generated Content", posts, height=300)

            # --- NEW: Thumbnail Generation Button (for 'content' job type) ---
            st.subheader("Generate Thumbnail")
            # Only show button if no thumbnail job is pending/running/completed for this content
            # or if the previous thumbnail job failed
            if st.session_state.thumbnail_status == 'idle' or st.session_state.thumbnail_status == 'FAILED': 
                if st.button("Generate Thumbnail from Content", key="generate_thumbnail_button"):
                    content_job_id = st.session_state[job_id_key] # Get the ID of the *completed* content job
                    if content_job_id:
                        payload = {"content_job_id": content_job_id}
                        try:
                            # IMPORTANT: This POSTs to the /content/generate-thumbnail endpoint
                            response = requests.post(f"{API_URL}/api/v1/content/generate-thumbnail", json=payload, headers=get_auth_headers())
                            if response.status_code == 202:
                                st.session_state.thumbnail_job_id = response.json().get("job_id")
                                st.session_state.thumbnail_status = "PENDING"
                                # Store the content job ID with the thumbnail job ID to link them
                                st.session_state.thumbnail_parent_content_job_id = content_job_id
                                st.rerun()
                            else:
                                st.error(f"Error submitting thumbnail job: {response.text}")
                        except requests.exceptions.RequestException as e:
                            st.error(f"Could not connect to the API for thumbnail generation: {e}")
                    else:
                        st.warning("Please generate content first to enable thumbnail generation.")
            
            # Display thumbnail job status (if a thumbnail job was initiated for this content job)
            if st.session_state.thumbnail_job_id and st.session_state.get('thumbnail_parent_content_job_id') == st.session_state.content_job_id:
                with st.expander("Thumbnail Generation Progress"):
                    # This recursively calls display_job_interface for the thumbnail job
                    display_job_interface('thumbnail')

            # Display the generated thumbnail if completed for this content job
            if st.session_state.thumbnail_status == "COMPLETED" and \
               st.session_state.get('thumbnail_parent_content_job_id') == st.session_state.content_job_id and \
               st.session_state.thumbnail_results:
                thumbnail_url = st.session_state.thumbnail_results.get("results", {}).get("thumbnail_url")
                if thumbnail_url:
                    st.subheader("Generated Thumbnail:")
                    st.image(f"{API_URL}{thumbnail_url}", caption="Generated Thumbnail") # Prepend API_URL
                else:
                    st.info("Thumbnail generation completed, but no URL found in results.")
            elif st.session_state.thumbnail_status == "FAILED" and \
                 st.session_state.get('thumbnail_parent_content_job_id') == st.session_state.content_job_id:
                thumbnail_error = st.session_state.thumbnail_results.get("error_message", "Thumbnail generation failed with an unknown error.")
                st.error(f"Thumbnail Generation Failed: {thumbnail_error}")


        # Button to start a new job of this type
        if st.button(f"Start New {job_type.replace('_', ' ').title()} Job", key=f"new_{job_type}_job_button"):
            st.session_state[job_id_key] = None
            st.session_state[status_key] = 'idle'
            st.session_state[results_key] = None
            # Reset thumbnail state if starting a new content job
            if job_type == 'content':
                st.session_state.thumbnail_job_id = None
                st.session_state.thumbnail_status = 'idle'
                st.session_state.thumbnail_results = None
                st.session_state.thumbnail_parent_content_job_id = None # Clear parent link
            st.rerun()

    elif st.session_state[status_key] == "FAILED":
        results_data = st.session_state.get(results_key, {})
        error_msg = results_data.get("error_message", "An unknown error occurred.")
        st.error(f"❌ Job failed: {error_msg}")
        if st.button(f"Try {job_type.replace('_', ' ').title()} Job Again", key=f"retry_{job_type}_job_button"):
            st.session_state[job_id_key] = None
            st.session_state[status_key] = 'idle'
            st.session_state[results_key] = None
            # Reset thumbnail state if retrying content job
            if job_type == 'content':
                st.session_state.thumbnail_job_id = None
                st.session_state.thumbnail_status = 'idle'
                st.session_state.thumbnail_results = None
                st.session_state.thumbnail_parent_content_job_id = None # Clear parent link
            st.rerun()

# --- Main App Rendering ---
def render_page():
    if not st.session_state.user_token:
        # --- LOGIN / SIGNUP PAGE ---
        st.title("Welcome to Alchemize 🧪")
        signup_tab, login_tab = st.tabs(["Create Account", "Login"])
        with signup_tab:
            st.header("Create an Account")
            with st.form("signup_form"):
                signup_name = st.text_input("Full Name", key="signup_name")
                signup_email = st.text_input("Email", key="signup_email")
                signup_password = st.text_input("Password", type="password", key="signup_password")
                if st.form_submit_button("Sign Up"):
                    if all([signup_name, signup_email, signup_password]):
                        signup(signup_email, signup_password, signup_name)
                    else:
                        st.warning("Please fill out all fields.")
        with login_tab:
            st.header("Login")
            with st.form("login_form"):
                login_email = st.text_input("Email", key="login_email")
                login_password = st.text_input("Password", type="password", key="login_password")
                if st.form_submit_button("Login"):
                    if login_email and login_password:
                        login(login_email, login_password)
                    else:
                        st.warning("Please enter both email and password.")
    else:
        # --- MAIN APPLICATION DASHBOARD ---
        st.sidebar.header(f"Welcome, {st.session_state.user_info.get('full_name', 'User')}")
        st.sidebar.button("Logout", on_click=logout)
        st.title("Alchemize Dashboard")
        
        tab1, tab2 = st.tabs(["✍️ Content Suite", "🎬 Video Clips"])
        
        with tab1:
            st.header("Generate a Full Social Media Suite")
            if st.session_state.content_status == 'idle':
                content_input = st.text_area("Paste a URL or type text:", height=150, key="content_input")
                if st.button("Generate Content Suite", key="content_button"):
                    if content_input:
                        payload = {"content": content_input}
                        try:
                            # IMPORTANT: This POSTs to the /content/repurpose endpoint
                            response = requests.post(f"{API_URL}/api/v1/content/repurpose", json=payload, headers=get_auth_headers())
                            if response.status_code == 202:
                                st.session_state.content_job_id = response.json().get("job_id")
                                st.session_state.content_status = "PENDING"
                                st.rerun()
                            else:
                                st.error(f"Error submitting job: {response.text}")
                        except requests.exceptions.RequestException as e:
                            st.error(f"Could not connect to the API: {e}")
            display_job_interface('content') # This will now handle thumbnail display logic too

        with tab2:
            st.header("Find & Create Viral Video Clips")
            if st.session_state.clip_status == 'idle':
                clip_url = st.text_input("Paste a YouTube URL:", key="clip_url")
                col1, col2 = st.columns(2)
                with col1:
                    add_captions_toggle = st.checkbox("Add Animated Captions", value=True)
                with col2:
                    aspect_ratio_choice = st.radio("Select Aspect Ratio:", ("9:16 (Vertical)", "1:1 (Square)"), horizontal=True)
                
                if st.button("Generate Clips", key="clip_button"):
                    if clip_url:
                        payload = {
                            "video_url": clip_url, 
                            "add_captions": add_captions_toggle, 
                            "aspect_ratio": aspect_ratio_choice.split(" ")[0]
                        }
                        try:
                            # IMPORTANT: This POSTs to the /video/videoclips endpoint
                            response = requests.post(f"{API_URL}/api/v1/video/videoclips", json=payload, headers=get_auth_headers())
                            if response.status_code == 202:
                                st.session_state.clip_job_id = response.json().get("job_id")
                                st.session_state.clip_status = "PENDING"
                                st.rerun()
                            else:
                                st.error(f"Error submitting job: {response.text}")
                        except requests.exceptions.RequestException as e:
                            st.error(f"Could not connect to the API: {e}")
            display_job_interface('clip')

if __name__ == "__main__":
    render_page()