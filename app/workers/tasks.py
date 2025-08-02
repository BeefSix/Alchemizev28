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
    """Process uploaded video and create clips for multiple platforms."""
    audio_path = None
    
    try:
        logger.info(f"Starting video job {job_id} for user {user_id}")
        
        # Update initial status
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                progress_details={"description": "Preparing video...", "percentage": 5})

        # Extract audio from video
        audio_path = video_path.rsplit('.', 1)[0] + '_audio.mp3'
        extract_cmd = ['ffmpeg', '-i', video_path, '-vn', '-acodec', 'mp3', '-y', audio_path]
        result = subprocess.run(extract_cmd, check=True, capture_output=True, text=True)
        
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                progress_details={"description": "Transcribing audio...", "percentage": 15})

        # Transcribe audio
        transcript_result = utils.transcribe_local_audio_file_sync(audio_path, user_id, job_id)
        if not transcript_result or not transcript_result.get('success'):
            raise ValueError(f"Transcription failed: {transcript_result.get('error', 'Unknown error')}")

        full_words_data = transcript_result['data']['words']
        
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                progress_details={"description": "Analyzing content for best moments...", "percentage": 30})

        # Find speech segments and analyze content
        speech_segments = utils.detect_silence_and_chunk(audio_path)
        text_chunks = [
            ' '.join(w['word'] for w in full_words_data 
                    if seg['start'] <= w.get('start', 0) <= seg['end']) 
            for seg in speech_segments
        ]
        
        viral_indices = utils.analyze_content_chunks_sync(text_chunks, user_id)
        if not viral_indices: 
            viral_indices = list(range(min(3, len(speech_segments))))

        # Create moments for clipping
        moments = []
        for idx in viral_indices:
            if idx < len(speech_segments):
                seg = speech_segments[idx]
                moment = {
                    'start': max(0, seg['start'] - 2),
                    'duration': min(seg['end'] - seg['start'] + 4, 60)
                }
                moments.append(moment)

        if not moments:
            raise ValueError("No suitable moments found for clipping")

        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                progress_details={"description": "Creating video clips...", "percentage": 40})

        # Generate clips for each platform
        clips_by_platform = {p: [] for p in platforms}
        total_clips_to_make = len(moments) * len(platforms)
        clips_made = 0

        for i, moment in enumerate(moments):
            for platform in platforms:
                clips_made += 1
                
                # Update progress
                with get_db_session() as db:
                    progress = 40 + int((clips_made / total_clips_to_make) * 55)
                    crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                        progress_details={
                            "description": f"Creating clip {clips_made}/{total_clips_to_make} for {platform}...", 
                            "percentage": progress
                        })

                # Set aspect ratio based on platform
                clip_aspect_ratio = aspect_ratio  # Default to user choice
                if platform in ["instagram_feed", "linkedin", "twitter"]:
                    clip_aspect_ratio = "1:1"
                elif platform in ["youtube_shorts", "tiktok", "instagram_reels"]:
                    clip_aspect_ratio = "9:16"

                # Generate clip
                clip_id = f"{job_id}_moment{i}_{platform}"
                clip_result = video_engine.process_single_clip(
                    video_path, 
                    moment, 
                    {"add_captions": add_captions, "aspect_ratio": clip_aspect_ratio},
                    user_id, 
                    clip_id, 
                    full_words_data
                )
                
                if clip_result.get('success'):
                    clips_by_platform[platform].append(clip_result['url'])
                else:
                    logger.warning(f"Failed to create clip {clip_id}: {clip_result.get('error', 'Unknown error')}")

        # Check if any clips were created
        total_clips_created = sum(len(urls) for urls in clips_by_platform.values())
        if total_clips_created == 0:
            raise ValueError("No clips were successfully generated")

        # Mark as completed
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "COMPLETED", 
                progress_details={"description": f"Generated {total_clips_created} clips!", "percentage": 100},
                results={"clips_by_platform": clips_by_platform})

        logger.info(f"Video job {job_id} completed successfully with {total_clips_created} clips")

    except Exception as e:
        logger.error(f"Video job {job_id} failed: {str(e)}")
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "FAILED", error_message=str(e))
        raise  # Re-raise for Celery error handling
        
    finally:
        # Clean up audio file
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                logger.info(f"Cleaned up audio file: {audio_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up audio file {audio_path}: {e}")

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