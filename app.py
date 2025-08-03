import streamlit as st
import os
import sys

# Add the current directory to Python path so it can find the frontend module
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Now import the frontend modules
from frontend.auth import AuthManager
from frontend.video_processor import VideoProcessor
from frontend.content_generator import ContentGenerator
from frontend.utils import APIClient, init_session_state

# --- Page Configuration ---
st.set_page_config(
    page_title="Alchemize",
    page_icon="⚗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Initialize App ---
def main():
    """Main application entry point"""
    
    # Initialize session state and API client
    init_session_state()
    api_client = APIClient()
    
    # Initialize managers
    auth_manager = AuthManager(api_client)
    video_processor = VideoProcessor(api_client)
    content_generator = ContentGenerator(api_client)
    
    # --- Header ---
    st.title("🧪 Alchemize - Video to Viral Content")
    
    # --- Connection Status ---
    render_connection_status(api_client)
    
    # --- Sidebar ---
    render_sidebar(auth_manager)
    
    # --- Main Content ---
    if not api_client.is_connected():
        st.error("🔌 **Connection Issue Detected**")
        st.markdown("The frontend cannot connect to the backend API.")
        
    elif not st.session_state.token:
        render_landing_page()
        
    else:
        render_main_app(video_processor, content_generator)

def render_connection_status(api_client):
    """Render API connection status"""
    col1, col2 = st.columns([4, 1])
    
    with col1:
        if api_client.test_connection():
            st.success(f"🟢 Connected to API (Using: {st.session_state.api_base_url})")
        else:
            st.error("🔴 Cannot connect to API")
    
    with col2:
        if st.button("🔄 Retry Connection"):
            st.session_state.connection_tested = False
            st.rerun()

def render_sidebar(auth_manager):
    """Render sidebar with auth and debug info"""
    with st.sidebar:
        st.markdown("⚗️", help="Your AI video wizard!")
        st.title("The Alchemist's Lab")
        
        # Debug controls
        if st.button("🔄 Reset App State"):
            st.query_params.clear()
            for key in ['active_jobs', 'last_job_check']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        
        with st.expander("🔧 Debug Info", expanded=False):
            st.write(f"**API URL:** {st.session_state.api_base_url}")
            st.write(f"**Connection Status:** {st.session_state.connection_status}")
            st.write(f"**URL Params:** {dict(st.query_params)}")
            st.write(f"**Python Path:** {current_dir}")  # Debug info
        
        # Authentication section
        auth_manager.render_auth_section()

def render_landing_page():
    """Render landing page for non-authenticated users"""
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

def render_main_app(video_processor, content_generator):
    """Render main application tabs"""
    tab1, tab2 = st.tabs(["🎬 Video Clips", "✍️ Content Suite"])
    
    with tab1:
        video_processor.render()
    
    with tab2:
        content_generator.render()
    
    # Footer
    st.markdown("---")
    status_text = "🟢 Connected" if st.session_state.connection_status else "🔴 Disconnected"
    st.markdown(f"**Status:** {status_text} | API: {st.session_state.api_base_url}")

if __name__ == "__main__":
    main()