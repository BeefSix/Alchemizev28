import streamlit as st
from typing import Dict, Any, List
from .utils import APIClient, JobMonitor

class ContentGenerator:
    """Handles content generation workflows"""
    
    def __init__(self, api_client: APIClient):
        self.api_client = api_client
        self.job_monitor = JobMonitor(api_client)
        
        # Available platforms
        self.available_platforms = [
            "LinkedIn", "Twitter", "Instagram", "TikTok", "Facebook", "YouTube"
        ]
        
        # Tone options
        self.tone_options = [
            "Professional", "Casual", "Enthusiastic", "Friendly", "Authoritative",
            "Humorous", "Inspirational", "Educational", "Conversational"
        ]
        
        # Style options
        self.style_options = [
            "Concise", "Detailed", "Storytelling", "Listicle", "Question-based",
            "How-to", "Behind-the-scenes", "Opinion piece", "Case study"
        ]
    
    def render(self):
        """Render the content generation interface"""
        st.header("Generate Social Media Content Suite")
        st.markdown("Transform any content into engaging social media posts across platforms!")
        
        # Check for active job in URL params
        active_content_job = st.query_params.get("content_job")
        
        if active_content_job:
            self._render_job_progress(active_content_job)
        else:
            self._render_content_form()
    
    def _render_content_form(self):
        """Render content generation form"""
        with st.form("content_form"):
            # Content input
            content_input = st.text_area(
                "Enter content or URL", 
                height=200,
                placeholder="Paste text, article URL, or YouTube URL here...",
                help="💡 Tip: You can paste article URLs, YouTube links, or raw text"
            )
            
            # Configuration options
            col1, col2 = st.columns(2)
            
            with col1:
                tone = st.selectbox(
                    "Tone", 
                    self.tone_options,
                    help="The overall voice and feeling of your posts"
                )
                
                platforms = st.multiselect(
                    "Target Platforms",
                    self.available_platforms,
                    default=["LinkedIn", "Twitter", "Instagram"],
                    help="Select which social media platforms to optimize for"
                )
            
            with col2:
                style = st.selectbox(
                    "Writing Style", 
                    self.style_options,
                    help="The structure and approach for your content"
                )
                
                content_length = st.selectbox(
                    "Content Length",
                    ["Short & Punchy", "Medium Detail", "Long Form"],
                    index=1,
                    help="How detailed should the generated posts be"
                )
            
            # Advanced options
            with st.expander("⚙️ Advanced Options"):
                additional_instructions = st.text_area(
                    "Additional Instructions",
                    placeholder="e.g., 'Include call-to-action buttons', 'Focus on benefits not features', 'Use emojis sparingly'",
                    help="Any specific requirements or preferences for the generated content"
                )
                
                include_hashtags = st.checkbox(
                    "Include relevant hashtags", 
                    value=True,
                    help="Automatically generate platform-appropriate hashtags"
                )
                
                cta_style = st.selectbox(
                    "Call-to-Action Style",
                    ["Question-based", "Direct action", "Soft engagement", "Educational", "None"],
                    index=0,
                    help="How should posts encourage engagement"
                )
            
            submitted = st.form_submit_button(
                "✨ Generate Content Suite", 
                use_container_width=True, 
                type="primary"
            )
            
            if submitted:
                self._handle_form_submission(
                    content_input, platforms, tone, style, 
                    additional_instructions if 'additional_instructions' in locals() else "",
                    content_length if 'content_length' in locals() else "Medium Detail",
                    include_hashtags if 'include_hashtags' in locals() else True,
                    cta_style if 'cta_style' in locals() else "Question-based"
                )
    
    def _handle_form_submission(self, content_input: str, platforms: List[str], 
                               tone: str, style: str, additional_instructions: str,
                               content_length: str, include_hashtags: bool, cta_style: str):
        """Handle content generation form submission"""
        
        # Validate inputs
        if not content_input.strip():
            st.error("Please enter some content to repurpose.")
            return
        
        if not platforms:
            st.error("Please select at least one platform.")
            return
        
        # Build enhanced instructions
        enhanced_instructions = self._build_enhanced_instructions(
            additional_instructions, content_length, include_hashtags, cta_style
        )
        
        # Show processing info
        st.info(f"🤖 Generating content for {len(platforms)} platforms with {tone.lower()} tone...")
        
        with st.spinner("🔄 Analyzing content and generating posts..."):
            success, job_id = self._start_content_generation(
                content_input, platforms, tone, style, enhanced_instructions
            )
            
            if success:
                st.success("✅ Content generation started!")
                st.query_params["content_job"] = job_id
                st.rerun()
            else:
                st.error(f"❌ Failed to start content generation: {job_id}")
    
    def _build_enhanced_instructions(self, additional_instructions: str, content_length: str,
                                   include_hashtags: bool, cta_style: str) -> str:
        """Build enhanced instructions from form options"""
        instructions = []
        
        if additional_instructions.strip():
            instructions.append(additional_instructions.strip())
        
        # Content length instructions
        length_map = {
            "Short & Punchy": "Keep posts concise and impactful, under 100 words each",
            "Medium Detail": "Provide good detail while staying engaging, 100-200 words each", 
            "Long Form": "Create detailed, comprehensive posts with full explanations"
        }
        if content_length in length_map:
            instructions.append(length_map[content_length])
        
        # Hashtag instructions
        if include_hashtags:
            instructions.append("Include 3-5 relevant hashtags for each platform")
        else:
            instructions.append("Do not include hashtags")
        
        # CTA instructions
        cta_map = {
            "Question-based": "End posts with engaging questions to encourage comments",
            "Direct action": "Include clear call-to-action buttons or direct requests",
            "Soft engagement": "Use subtle engagement prompts and conversation starters",
            "Educational": "Focus on teaching and providing value",
            "None": "Do not include explicit calls-to-action"
        }
        if cta_style in cta_map:
            instructions.append(cta_map[cta_style])
        
        return " | ".join(instructions)
    
    def _start_content_generation(self, content_input: str, platforms: List[str],
                                 tone: str, style: str, additional_instructions: str) -> tuple[bool, str]:
        """Start content generation job"""
        try:
            payload = {
                "content": content_input.strip(), 
                "platforms": platforms,
                "tone": tone, 
                "style": style, 
                "additional_instructions": additional_instructions
            }
            
            response = self.api_client.make_authenticated_request(
                "POST", "/content/repurpose",
                json=payload
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
        st.markdown("### 🔄 Generating Your Content...")
        
        # Monitor job status
        job_data = self.job_monitor.render_job_status(job_id, "content")
        
        if job_data and job_data.get("status") == "COMPLETED":
            self._render_content_results(job_data)
            
            # Process another button
            if st.button("✨ Generate More Content", key=f"another_{job_id}", 
                        use_container_width=True, type="primary"):
                self.job_monitor.clear_job_from_url("content")
    
    def _render_content_results(self, job_data: Dict[str, Any]):
        """Display completed content generation results"""
        results = job_data.get("results", {})
        
        if not results:
            st.error("❌ No content was generated.")
            return
        
        st.success("✅ Content suite generated successfully!")
        
        # Display settings used
        settings = results.get("settings", {})
        if settings:
            with st.expander("⚙️ Generation Settings", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Tone:** {settings.get('tone', 'N/A')}")
                    st.write(f"**Style:** {settings.get('style', 'N/A')}")
                with col2:
                    platforms = results.get("platforms", [])
                    st.write(f"**Platforms:** {', '.join(platforms) if platforms else 'N/A'}")
                    
                additional = settings.get("additional_instructions", "")
                if additional:
                    st.write(f"**Instructions:** {additional}")
        
        # Display content analysis
        if results.get("analysis"):
            with st.expander("📊 Content Analysis", expanded=False):
                st.markdown(results["analysis"])
        
        # Display generated posts
        if results.get("posts"):
            st.markdown("### 📝 Generated Social Media Posts")
            
            # Add copy-all button
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button("📋 Copy All Posts", use_container_width=True):
                    # Note: Streamlit doesn't have built-in clipboard, but we can show the content
                    st.text_area(
                        "All Generated Content (Copy this):",
                        value=results["posts"],
                        height=200,
                        key="copy_all_content"
                    )
            
            # Display the posts with syntax highlighting
            st.markdown(results["posts"])
            
            # Individual platform extraction (if possible)
            self._extract_platform_posts(results["posts"])
        
        # Export options
        self._render_export_options(job_data)
    
    def _extract_platform_posts(self, posts_content: str):
        """Try to extract individual platform posts"""
        # Look for markdown headers that indicate platform sections
        platform_indicators = ["##", "###", "**"]
        
        for platform in self.available_platforms:
            # Simple extraction - look for platform name in headers
            if any(f"{indicator} {platform}" in posts_content or 
                   f"{indicator}{platform}" in posts_content 
                   for indicator in platform_indicators):
                
                with st.expander(f"📱 {platform} Posts", expanded=False):
                    # This is a simplified extraction - you could make it more sophisticated
                    lines = posts_content.split('\n')
                    platform_lines = []
                    capturing = False
                    
                    for line in lines:
                        if platform.lower() in line.lower() and any(ind in line for ind in platform_indicators):
                            capturing = True
                            continue
                        elif capturing and any(ind in line for ind in platform_indicators):
                            # Hit another platform section
                            if not any(platform.lower() in line.lower() for platform in self.available_platforms):
                                platform_lines.append(line)
                            else:
                                break
                        elif capturing:
                            platform_lines.append(line)
                    
                    if platform_lines:
                        platform_content = '\n'.join(platform_lines).strip()
                        st.markdown(platform_content)
                        
                        # Individual copy button
                        st.text_area(
                            f"Copy {platform} content:",
                            value=platform_content,
                            height=150,
                            key=f"copy_{platform.lower()}"
                        )
    
    def _render_export_options(self, job_data: Dict[str, Any]):
        """Render export and download options"""
        st.markdown("### 📤 Export Options")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📄 Export as Text", use_container_width=True):
                results = job_data.get("results", {})
                content = f"""# Alchemize Content Suite
Generated on: {job_data.get('created_at', 'Unknown')}

## Settings
{results.get('settings', {})}

## Analysis
{results.get('analysis', 'No analysis available')}

## Generated Posts
{results.get('posts', 'No posts generated')}
"""
                st.download_button(
                    label="💾 Download Text File",
                    data=content,
                    file_name=f"alchemize_content_{job_data.get('id', 'unknown')[:8]}.txt",
                    mime="text/plain"
                )
        
        with col2:
            if st.button("📊 Export as JSON", use_container_width=True):
                import json
                json_data = json.dumps(job_data.get("results", {}), indent=2)
                st.download_button(
                    label="💾 Download JSON",
                    data=json_data,
                    file_name=f"alchemize_content_{job_data.get('id', 'unknown')[:8]}.json",
                    mime="application/json"
                )
        
        with col3:
            if st.button("🔄 Generate Variations", use_container_width=True):
                st.info("💡 Tip: Use 'Generate More Content' to create new variations with different settings!")