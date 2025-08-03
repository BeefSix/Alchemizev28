import streamlit as st
import requests
from typing import Dict, Any, Optional
from .utils import APIClient, JobMonitor, validate_file_upload, format_file_size

class VideoProcessor:
    """Handles video upload and processing workflows"""
    
    def __init__(self, api_client: APIClient):
        self.api_client = api_client
        self.job_monitor = JobMonitor(api_client)
        
        # Supported video formats
        self.allowed_video_types = [
            'video/mp4', 'video/quicktime', 'video/x-msvideo', 
            'video/x-matroska', 'video/webm', 'video/avi',
            'video/x-ms-wmv', 'video/3gpp', 'video/x-flv'
        ]
        
        self.allowed_extensions = [
            'mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 
            'wmv', 'm4v', '3gp', 'ogv', 'ts', 'mts', 'm2ts'
        ]
    
    def render(self):
        """Render the video processing interface"""
        st.header("Create Viral Video Clips")
        st.markdown("Upload ANY video format and get professional clips with **live karaoke-style captions**!")
        
        # Check for active job in URL params
        active_video_job = st.query_params.get("video_job")
        
        if active_video_job:
            self._render_job_progress(active_video_job)
        else:
            self._render_upload_form()
    
    def _render_upload_form(self):
        """Render video upload form"""
        with st.form("video_upload_form"):
            uploaded_file = st.file_uploader(
                "Choose any video file", 
                type=self.allowed_extensions,
                help="✅ Supports ALL major video formats • Max size: 500MB",
                key="video_upload_file"
            )
            
            col1, col2 = st.columns(2)
            
            with col1:
                aspect_ratio = st.selectbox(
                    "Aspect Ratio", 
                    ["9:16 (Vertical/TikTok)", "1:1 (Square/Instagram)", "16:9 (Horizontal/YouTube)"],
                    index=0,
                    key="video_aspect_ratio"
                )
            
            with col2:
                add_captions = st.selectbox(
                    "🎤 Live Karaoke Captions",
                    ["Yes - Add live karaoke-style captions", "No - Video only"],
                    index=0,
                    key="video_add_captions"
                )
            
            # Advanced options (collapsed by default)
            with st.expander("⚙️ Advanced Options"):
                platforms = st.multiselect(
                    "Target Platforms",
                    ["TikTok", "Instagram Reels", "YouTube Shorts", "Facebook Stories"],
                    default=["TikTok", "Instagram Reels", "YouTube Shorts"]
                )
                
                clip_count = st.slider(
                    "Number of clips to generate",
                    min_value=1, max_value=5, value=3,
                    help="More clips = longer processing time"
                )
            
            submitted = st.form_submit_button(
                "🚀 Create Clips with Live Captions", 
                use_container_width=True, 
                type="primary"
            )
            
            if submitted:
                self._handle_form_submission(
                    uploaded_file, add_captions, aspect_ratio, 
                    platforms if 'platforms' in locals() else ["TikTok", "Instagram Reels", "YouTube Shorts"]
                )
    
    def _handle_form_submission(self, uploaded_file, add_captions_input: str, 
                               aspect_ratio_input: str, platforms: list):
        """Handle video upload form submission"""
        
        # Validate file upload
        is_valid, error_msg = validate_file_upload(
            uploaded_file, max_size_mb=500, allowed_types=self.allowed_video_types
        )
        
        if not is_valid:
            st.error(f"❌ {error_msg}")
            return
        
        # Parse form inputs
        add_captions_bool = add_captions_input.startswith("Yes")
        aspect_ratio_value = aspect_ratio_input.split(" ")[0]
        platforms_str = ",".join(platforms) if platforms else "TikTok,Instagram Reels,YouTube Shorts"
        
        # Show file info
        file_size = format_file_size(uploaded_file.size) if hasattr(uploaded_file, 'size') else "Unknown"
        st.info(f"📁 Uploading: {uploaded_file.name} ({file_size})")
        
        with st.spinner("🚀 Uploading and starting GPU processing..."):
            success, job_id = self._upload_video(
                uploaded_file, add_captions_bool, aspect_ratio_value, platforms_str
            )
            
            if success:
                st.success("✅ Upload successful! Processing started...")
                st.session_state.active_jobs['video'] = job_id
                st.query_params["video_job"] = job_id
                st.rerun()
            else:
                st.error(f"❌ Upload failed: {job_id}")  # job_id contains error message on failure
    
    def _upload_video(self, uploaded_file, add_captions: bool, aspect_ratio: str, 
                     platforms: str) -> tuple[bool, str]:
        """Upload video to backend API"""
        try:
            files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            data = {
                "add_captions": add_captions,
                "aspect_ratio": aspect_ratio,
                "platforms": platforms
            }
            
            response = self.api_client.make_authenticated_request(
                "POST", "/video/upload-and-clip",
                files=files,
                data=data
            )
            
            if response and response.status_code == 202:
                job_id = response.json().get('job_id')
                return True, job_id
            else:
                error_msg = response.text if response else "Unknown error"
                return False, error_msg
                
        except Exception as e:
            return False, str(e)
    
    def _render_job_progress(self, job_id: str):
        """Render job progress and results"""
        st.markdown("### 🔄 Processing Your Video...")
        
        # Monitor job status
        job_data = self.job_monitor.render_job_status(job_id, "video")
        
        if job_data and job_data.get("status") == "COMPLETED":
            self._render_video_results(job_data)
            
            # Process another button
            if st.button("🎬 Process Another Video", key=f"another_{job_id}", 
                        use_container_width=True, type="primary"):
                self.job_monitor.clear_job_from_url("video")
    
    def _render_video_results(self, job_data: Dict[str, Any]):
        """Display completed video job results"""
        results = job_data.get("results", {})
        clips_by_platform = results.get("clips_by_platform", {})
        
        if not clips_by_platform:
            st.error("❌ No clips were generated.")
            return
        
        # Header with stats
        col1, col2 = st.columns([3, 1])
        
        with col1:
            total_clips = results.get("total_clips", 0)
            video_duration = results.get("video_duration", 0)
            captions_added = results.get("captions_added", False)
            processing_details = results.get("processing_details", {})
            karaoke_words = processing_details.get("karaoke_words", 0)
            processing_method = processing_details.get("processing_method", "unknown")
            
            st.success(f"✅ Generated {total_clips} clips successfully!")
            
            # Processing info
            info_parts = [f"📹 Original: {video_duration:.1f}s"]
            
            if processing_method == "rtx_4080_optimized":
                info_parts.append("🚀 RTX 4080 GPU acceleration")
            elif "nvidia" in processing_method:
                info_parts.append("🎮 GPU acceleration")
            
            if captions_added:
                info_parts.append(f"🎤 Live karaoke captions: ✅ ({karaoke_words} words)")
            else:
                info_parts.append("🎤 Captions: ❌")
                
            st.info(" | ".join(info_parts))
        
        with col2:
            # Download all button
            job_id = job_data.get("id")
            if job_id and st.button("📥 Download All", type="primary", use_container_width=True):
                self._handle_download_all(job_id)
        
        # Display clips
        self._display_video_clips(clips_by_platform, captions_added, karaoke_words)
    
    def _handle_download_all(self, job_id: str):
        """Handle download all clips as ZIP"""
        try:
            response = self.api_client.make_authenticated_request(
                "GET", f"/video/jobs/{job_id}/download-all"
            )
            
            if response and response.status_code == 200:
                st.download_button(
                    label="📥 Download ZIP",
                    data=response.content,
                    file_name=f"alchemize_clips_{job_id[:8]}.zip",
                    mime="application/zip",
                    use_container_width=True,
                    key=f"download_zip_{job_id}"
                )
            else:
                st.error("Download failed - please try individual clip downloads")
        except Exception as e:
            st.error(f"Download error: {e}")
    
    def _display_video_clips(self, clips_by_platform: Dict, captions_added: bool, karaoke_words: int):
        """Display video clips in a grid"""
        # Collect all clips
        all_clips = []
        possible_keys = ["all", "all_platforms", "TikTok", "Instagram", "YouTube", "default"]
        
        for key in possible_keys:
            if key in clips_by_platform:
                urls = clips_by_platform[key]
                if isinstance(urls, list):
                    all_clips.extend(urls)
                    break
                elif isinstance(urls, str):
                    all_clips.append(urls)
                    break
        
        if not all_clips:
            for key, urls in clips_by_platform.items():
                if isinstance(urls, list):
                    all_clips.extend(urls)
                elif isinstance(urls, str):
                    all_clips.append(urls)
        
        # Remove duplicates
        seen = set()
        all_clips = [x for x in all_clips if not (x in seen or seen.add(x))]
        
        if not all_clips:
            st.error("❌ No valid clip URLs found")
            with st.expander("🔧 Debug Info", expanded=True):
                st.json({
                    "clips_by_platform": clips_by_platform,
                    "available_keys": list(clips_by_platform.keys()) if clips_by_platform else []
                })
            return
        
        st.markdown("### 🎬 Your Generated Clips")
        
        # Display clips in grid
        clips_per_row = 3
        for i in range(0, len(all_clips), clips_per_row):
            cols = st.columns(clips_per_row)
            
            for j, url in enumerate(all_clips[i:i+clips_per_row]):
                with cols[j]:
                    self._render_single_clip(url, i + j + 1, captions_added)
        
        # Success message
        if captions_added:
            st.success(f"🎉 All clips include live karaoke-style captions with {karaoke_words} words!")
        else:
            st.info("ℹ️ These clips were generated without captions.")
    
    def _render_single_clip(self, url: str, clip_num: int, captions_added: bool):
        """Render a single video clip with download option"""
        try:
            # Build correct URL for video display
            if url.startswith("/static/generated/"):
                full_url = f"{st.session_state.api_base_url.replace('/api/v1', '')}{url}"
            elif url.startswith("/static/"):
                full_url = f"{st.session_state.api_base_url.replace('/api/v1', '')}{url}"
            else:
                full_url = url
            
            st.video(full_url)
            
            caption_info = "🎤" if captions_added else "🔇"
            st.caption(f"🎥 Clip {clip_num} {caption_info}")
            
            # Individual download button
            if st.button(f"⬇️ Download", key=f"dl_{clip_num}", use_container_width=True):
                self._download_single_clip(full_url, clip_num)
                
        except Exception as e:
            st.error(f"❌ Could not load clip {clip_num}")
            st.code(f"URL: {url}")
            st.code(f"Error: {e}")
    
    def _download_single_clip(self, full_url: str, clip_num: int):
        """Handle individual clip download"""
        try:
            response = requests.get(full_url, timeout=10)
            if response.status_code == 200:
                st.download_button(
                    label=f"💾 Save Clip {clip_num}",
                    data=response.content,
                    file_name=f"alchemize_clip_{clip_num}.mp4",
                    mime="video/mp4",
                    key=f"save_{clip_num}",
                    use_container_width=True
                )
            else:
                st.error(f"Failed to fetch clip: {response.status_code}")
        except Exception as e:
            st.error(f"Download error: {e}")