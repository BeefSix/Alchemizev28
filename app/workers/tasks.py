# app/workers/tasks.py
import subprocess
import os
import json
import logging
import glob
from datetime import datetime, timedelta

from app.celery_app import celery_app
from app.db import crud
from app.db.base import get_db_session
from app.services import video_engine, utils

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def run_videoclip_upload_job(self, job_id: str, user_id: int, video_path: str, add_captions: bool, aspect_ratio: str, platforms: list[str]):
    """Process uploaded video and create clips with live karaoke-style captions."""
    audio_path = None
    
    try:
        logger.info(f"🎬 Starting video job {job_id} for user {user_id}")
        logger.info(f"📋 Parameters: add_captions={add_captions}, aspect_ratio={aspect_ratio}")
        
        # Verify video file exists
        if not os.path.exists(video_path):
            raise ValueError(f"Video file not found: {video_path}")
        
        # Update initial status
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                progress_details={"description": "Processing video file...", "percentage": 10})

        # Get video info using ffprobe
        info_cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', video_path]
        result = subprocess.run(info_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise ValueError(f"Invalid video file: {result.stderr}")
        
        video_info = json.loads(result.stdout)
        duration = float(video_info['format']['duration'])
        logger.info(f"📹 Video duration: {duration:.1f} seconds")

        # Extract audio for transcription if captions are needed
        words_data = []
        captions_actually_added = False
        
        if add_captions:
            logger.info(f"🎤 Captions requested: {add_captions}")
            audio_path = os.path.join(os.path.dirname(video_path), f"{job_id}_audio.mp3")
            
            with get_db_session() as db:
                crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                    progress_details={"description": "Extracting audio for live captions...", "percentage": 20})
            
            extract_cmd = [
                'ffmpeg', '-i', video_path, 
                '-vn', '-acodec', 'mp3', '-ar', '16000', '-ac', '1',
                '-y', audio_path
            ]
            
            logger.info(f"🔧 Extracting audio: {' '.join(extract_cmd)}")
            result = subprocess.run(extract_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"❌ Audio extraction failed: {result.stderr}")
                add_captions = False
            else:
                logger.info(f"✅ Audio extracted successfully to: {audio_path}")
                
                # Transcribe for karaoke captions
                with get_db_session() as db:
                    crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                        progress_details={"description": "Creating live karaoke transcript...", "percentage": 35})
                
                logger.info(f"🎤 Starting transcription with OpenAI Whisper...")
                transcript_result = utils.transcribe_local_audio_file_sync(audio_path, user_id, job_id)
                
                if transcript_result and transcript_result.get('success'):
                    words_data = transcript_result['data'].get('words', [])
                    logger.info(f"🎉 Transcription complete: {len(words_data)} words for karaoke")
                    captions_actually_added = True
                else:
                    logger.error(f"❌ Transcription failed: {transcript_result.get('error', 'Unknown error') if transcript_result else 'No response'}")
                    add_captions = False
        else:
            logger.info(f"🚫 Captions disabled by user")

        # Generate clips from different parts of the video
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                progress_details={"description": "Creating clips with live karaoke captions...", "percentage": 50})

        # Calculate clip parameters
        clip_duration = min(60, duration * 0.6)  # Max 60 seconds or 60% of video
        num_clips = min(5, max(1, int(duration // 25)))  # 1 clip per 25 seconds, max 5
        
        logger.info(f"📊 Will create {num_clips} clips of {clip_duration:.1f}s each")
        
        clips_created = []
        
        for i in range(num_clips):
            # Distribute clips evenly across the video
            start_time = (duration / (num_clips + 1)) * (i + 1) - (clip_duration / 2)
            start_time = max(0, min(start_time, duration - clip_duration))
            
            moment = {
                'start': start_time,
                'duration': clip_duration
            }
            
            clip_id = f"{job_id}_clip_{i+1}"
            
            # Update progress
            progress = 50 + int((i / num_clips) * 45)
            with get_db_session() as db:
                crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                    progress_details={
                        "description": f"Creating clip {i+1}/{num_clips} with karaoke captions...", 
                        "percentage": progress
                    })

            # Process clip with karaoke captions
            logger.info(f"🎬 Processing clip {i+1}: {start_time:.1f}s - {start_time + clip_duration:.1f}s")
            logger.info(f"🎤 Captions for this clip: {add_captions}, Words available: {len(words_data)}")
            
            clip_result = video_engine.process_single_clip(
                video_path, 
                moment, 
                {"add_captions": add_captions, "aspect_ratio": aspect_ratio},
                user_id,
                clip_id, 
                words_data
            )
            
            if clip_result.get('success'):
                clips_created.append(clip_result['url'])
                logger.info(f"✅ Clip {i+1} created: {clip_result['url']}")
                logger.info(f"🎤 Clip {i+1} captions: {clip_result.get('captions_added', False)}")
            else:
                logger.warning(f"❌ Clip {i+1} failed: {clip_result.get('error', 'Unknown error')}")

        if not clips_created:
            raise ValueError("No clips were successfully generated")

        # Create results - FIXED structure for frontend
        results = {
            "clips_by_platform": {
                "all_platforms": clips_created  # Use the correct key name that frontend expects
            },
            "total_clips": len(clips_created),
            "video_duration": duration,
            "captions_added": captions_actually_added,  # Use the actual status
            "processing_details": {
                "aspect_ratio": aspect_ratio,
                "clip_duration": clip_duration,
                "karaoke_words": len(words_data),
                "caption_type": "live_karaoke" if captions_actually_added else "none"
            }
        }

        logger.info(f"📋 Final results: {json.dumps(results, indent=2)}")

        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "COMPLETED", 
                progress_details={
                    "description": f"🎉 Generated {len(clips_created)} clips with {'live karaoke captions' if captions_actually_added else 'no captions'}!", 
                    "percentage": 100
                },
                results=results)

        logger.info(f"🎉 Video job {job_id} completed: {len(clips_created)} clips generated, captions: {captions_actually_added}")

    except Exception as e:
        error_msg = f"Video processing failed: {str(e)}"
        logger.error(f"❌ Video job {job_id} failed: {error_msg}")
        
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "FAILED", error_message=error_msg)
        raise
        
    finally:
        # Clean up audio file
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                logger.info(f"🧹 Cleaned up: {audio_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup {audio_path}: {e}")

@celery_app.task(bind=True)
def run_content_repurpose_job(self, job_id: str, user_id: int, content_input: str, platforms: list[str], tone: str, style: str, additional_instructions: str):
    """Generate repurposed content for multiple social media platforms."""
    try:
        logger.info(f"Starting content job {job_id} for user {user_id}")
        
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                progress_details={"description": "Ingesting content...", "percentage": 5})
        
        # Ingest content (handles URLs or raw text)
        content_to_process = utils.ingest_content(content_input)
        if not content_to_process or content_to_process.startswith("Error:"):
            raise ValueError(f"Failed to ingest content: {content_to_process}")

        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                progress_details={"description": "Analyzing content...", "percentage": 20})
        
        # Analyze content
        analysis_prompt = f"""Analyze this content and extract key insights, tone, audience, and main themes.
        Focus on what makes it engaging and how it could be adapted for social media.
        
        CONTENT:
        {content_to_process[:4000]}"""
        
        content_analysis = utils.run_ai_generation_sync(analysis_prompt, user_id, model="gpt-4o")
        if not content_analysis: 
            raise Exception("AI content analysis failed - check your OpenAI API key and credits.")
        
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                progress_details={"description": "Generating social media posts...", "percentage": 60})
        
        # Generate content for platforms
        platform_str = ", ".join(platforms)
        generation_prompt = f"""You are an expert social media content strategist. Transform the provided content into engaging posts for {platform_str}.

TONE: {tone}
STYLE: {style}
ADDITIONAL INSTRUCTIONS: {additional_instructions}

GUIDELINES:
- Create platform-specific content that fits each platform's style
- For LinkedIn: Professional, thought-provoking, use bullet points
- For Twitter: Concise, engaging, thread-worthy
- For Instagram: Visual storytelling, hashtag-friendly
- For TikTok: Trend-aware, hook-focused
- Each post should be complete and ready to publish
- Include relevant hashtags where appropriate
- End with engaging questions or calls-to-action

SOURCE CONTENT:
{content_to_process[:8000]}

Generate compelling posts for each platform. Use markdown headings to separate platforms (e.g., ## LinkedIn, ## Twitter)."""
        
        drafts = utils.run_ai_generation_sync(generation_prompt, user_id, model="gpt-4o", max_tokens=3000)
        if not drafts: 
            raise Exception("AI content generation failed - check your OpenAI API key and credits.")
        
        results = {
            "analysis": content_analysis, 
            "posts": drafts,
            "platforms": platforms,
            "settings": {
                "tone": tone,
                "style": style,
                "additional_instructions": additional_instructions
            }
        }
        
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "COMPLETED", 
                progress_details={"description": "Content suite generated!", "percentage": 100}, 
                results=results)

        logger.info(f"Content job {job_id} completed successfully")

    except Exception as e:
        logger.error(f"Content job {job_id} failed: {str(e)}")
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "FAILED", 
                error_message=f"Content repurposing failed: {str(e)}")
        raise

@celery_app.task(bind=True)
def generate_thumbnail_job(self, job_id: str, user_id: int, prompt_text: str):
    """Generate thumbnail images based on content."""
    try:
        logger.info(f"Starting thumbnail job {job_id} for user {user_id}")
        
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                progress_details={"description": "Generating thumbnail prompts...", "percentage": 10})

        # Generate image prompts
        prompt_gen_prompt = f'''Based on the following content, generate 3 striking visual prompts for thumbnail images.
        Return them as a JSON array of strings. Each prompt should be vivid, specific, and thumbnail-worthy.
        
        CONTENT: {prompt_text[:2000]}
        
        Return format: ["prompt1", "prompt2", "prompt3"]'''
        
        image_prompts = []
        for attempt in range(3):
            response_str = utils.run_ai_generation_sync(prompt_gen_prompt, user_id, "gpt-4o-mini", 500, expect_json=True)
            if response_str:
                try:
                    prompts = json.loads(response_str)
                    if isinstance(prompts, list) and prompts:
                        image_prompts = prompts
                        break
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Failed to parse prompts on attempt {attempt + 1}: {e}")
        
        if not image_prompts: 
            raise Exception("Failed to generate valid image prompts after 3 attempts.")
        
        # Generate images
        urls = []
        for i, prompt in enumerate(image_prompts):
            with get_db_session() as db:
                progress = 20 + int(((i + 1) / len(image_prompts)) * 75)
                crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                    progress_details={"description": f"Generating thumbnail {i+1}/{len(image_prompts)}...", "percentage": progress})

            url = video_engine.sd_generator.generate_image(prompt, 1280, 720)
            if url:
                urls.append(url)
                utils.track_usage("stable-diffusion-local", user_id, 'thumbnail', custom_cost=0.0)
            else:
                logger.warning(f"Failed to generate image for prompt: {prompt}")

        if not urls: 
            raise Exception("No thumbnails were successfully generated.")
        
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "COMPLETED", 
                progress_details={"description": f"Generated {len(urls)} thumbnails!", "percentage": 100}, 
                results={"thumbnail_urls": urls, "prompts_used": image_prompts})
        
        logger.info(f"Thumbnail job {job_id} completed with {len(urls)} images")
            
    except Exception as e:
        logger.error(f"Thumbnail job {job_id} failed: {str(e)}")
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "FAILED", 
                error_message=f"Thumbnail generation failed: {str(e)}")
        raise

@celery_app.task
def cleanup_old_files():
    """Clean up old files to prevent disk space issues."""
    logger.info("🧹 Starting daily cleanup of old files...")
    
    try:
        from app.core.config import settings
        
        cleanup_age_days = 1 
        cutoff = datetime.now() - timedelta(days=cleanup_age_days)
        
        upload_dir = os.path.join(settings.STATIC_GENERATED_DIR, "uploads")
        temp_clips_dir = settings.STATIC_GENERATED_DIR
        
        patterns = [
            os.path.join(upload_dir, '*'),
            os.path.join(temp_clips_dir, 'temp_*.mp4'),
            os.path.join(temp_clips_dir, 'final_*.mp4'),
            os.path.join(temp_clips_dir, 'captions_*.srt'),
            os.path.join(temp_clips_dir, 'captions_*.ass'),
            os.path.join(temp_clips_dir, '*_audio.mp3')
        ]
        
        files_removed = 0
        total_size_freed = 0
        
        for pattern in patterns:
            for file_path in glob.glob(pattern):
                try:
                    file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if file_mod_time < cutoff:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        files_removed += 1
                        total_size_freed += file_size
                        logger.info(f"Removed old file: {file_path}")
                except Exception as e:
                    logger.error(f"Error removing file {file_path}: {e}")
        
        # Convert bytes to MB for logging
        size_mb = total_size_freed / (1024 * 1024)
        logger.info(f"✅ Daily cleanup finished. Removed {files_removed} files, freed {size_mb:.1f}MB")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")