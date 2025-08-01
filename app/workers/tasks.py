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

# (Your existing run_videoclip_upload_job and run_content_repurpose_job functions go here, unchanged)

@celery_app.task(bind=True)
def run_videoclip_upload_job(self, job_id: str, user_id: int, video_path: str, add_captions: bool, aspect_ratio: str, platforms: list[str]):
    """The main synchronous logic for processing an uploaded video."""
    audio_path = None
    try:
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Preparing video...", "percentage": 5})

        audio_path = video_path.rsplit('.', 1)[0] + '_audio.mp3'
        extract_cmd = ['ffmpeg', '-i', video_path, '-vn', '-acodec', 'mp3', '-y', audio_path]
        subprocess.run(extract_cmd, check=True, capture_output=True, text=True)

        transcript_result = utils.transcribe_local_audio_file_sync(audio_path, user_id, job_id)
        if not transcript_result or not transcript_result.get('success'):
            raise ValueError("Transcription failed")

        full_words_data = transcript_result['data']['words']
        speech_segments = utils.detect_silence_and_chunk(audio_path)
        text_chunks = [' '.join(w['word'] for w in full_words_data if seg['start'] <= w.get('start', 0) <= seg['end']) for seg in speech_segments]
        
        viral_indices = utils.analyze_content_chunks_sync(text_chunks, user_id)
        if not viral_indices: viral_indices = list(range(min(3, len(speech_segments))))

        moments = [
            {'start': max(0, speech_segments[idx]['start'] - 2), 'duration': min(speech_segments[idx]['end'] - speech_segments[idx]['start'] + 4, 60)}
            for idx in viral_indices if idx < len(speech_segments)
        ]

        clips_by_platform = {p: [] for p in platforms}
        total_clips_to_make = len(moments) * len(platforms)
        clips_made = 0

        for i, moment in enumerate(moments):
            for platform in platforms:
                clips_made += 1
                with get_db_session() as db:
                    progress = 50 + int((clips_made / total_clips_to_make) * 45)
                    crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": f"Creating clip {clips_made}/{total_clips_to_make} for {platform}...", "percentage": progress})

                if platform in ["instagram_feed", "linkedin", "twitter"]:
                    aspect_ratio = "1:1"
                elif platform in ["youtube_shorts", "tiktok", "instagram_reels"]:
                    aspect_ratio = "9:16"
                else:
                    # This line is no longer needed, you can delete it or comment it out.
                    # aspect_ratio = aspect_ratio_default 
                    # A better approach is to just use the new variable name directly.

                    clip_id = f"{job_id}_moment{i}_{platform}"
                    clip_result = video_engine.process_single_clip(
                    video_path, moment, {"add_captions": add_captions, "aspect_ratio": aspect_ratio},
                    user_id, clip_id, full_words_data
                )
                if clip_result.get('success'):
                    clips_by_platform[platform].append(clip_result['url'])

        if not any(clips_by_platform.values()):
            raise ValueError("No clips were successfully generated")

        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "COMPLETED", results={"clips_by_platform": clips_by_platform})

    except Exception as e:
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "FAILED", error_message=str(e))
    finally:
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)

@celery_app.task(bind=True)
def run_content_repurpose_job(self, job_id: str, user_id: int, content_input: str, platforms: list[str], tone: str, style: str, additional_instructions: str):
    """Celery task for content repurposing, now fully synchronous."""
    try:
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Ingesting content...", "percentage": 5})
        
        content_to_process = utils.ingest_content(content_input)

        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Analyzing content...", "percentage": 20})
        
        analysis_prompt = f"Analyze this content...\n\nCONTENT:\n{content_to_process[:4000]}"
        content_analysis = utils.run_ai_generation_sync(analysis_prompt, user_id, model="gpt-4o")
        if not content_analysis: raise Exception("AI content analysis failed.")
        
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Generating posts...", "percentage": 60})
        
        generation_prompt = f"""You are an expert content strategist...""" # (Your full prompt here)
        drafts = utils.run_ai_generation_sync(generation_prompt, user_id, model="gpt-4o")
        if not drafts: raise Exception("AI content generation failed.")
        
        results = {"analysis": content_analysis, "posts": drafts}
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "COMPLETED", progress_details={"description": "Content suite generated!", "percentage": 100}, results=results)

    except Exception as e:
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "FAILED", error_message=f"Content repurposing failed: {str(e)}")

@celery_app.task(bind=True)
def generate_thumbnail_job(self, job_id: str, user_id: int, prompt_text: str):
    """Celery task for generating thumbnails, now fully synchronous."""
    try:
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Generating thumbnail prompts...", "percentage": 10})

        prompt_gen_prompt = f'Based on the content, generate 3 striking prompts...\nCONTENT: {prompt_text}'
        image_prompts = []
        for attempt in range(3):
            response_str = utils.run_ai_generation_sync(prompt_gen_prompt, user_id, "gpt-4o-mini", 500, expect_json=True)
            if response_str:
                try:
                    prompts = json.loads(response_str)
                    if isinstance(prompts, list) and prompts:
                        image_prompts = prompts
                        break
                except (json.JSONDecodeError, TypeError):
                    pass
        
        if not image_prompts: raise Exception("Failed to generate valid image prompts.")
        
        urls = []
        for i, prompt in enumerate(image_prompts):
            with get_db_session() as db:
                progress = 20 + int(((i + 1) / len(image_prompts)) * 75)
                crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": f"Generating thumbnail {i+1}/{len(image_prompts)}...", "percentage": progress})

            url = video_engine.sd_generator.generate_image(prompt, 1280, 720)
            if url:
                urls.append(url)
                utils.track_usage("stable-diffusion-local", user_id, 'thumbnail', custom_cost=0.0)

        if not urls: raise Exception("No thumbnails were successfully generated.")
        
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "COMPLETED", progress_details={"description": "Thumbnails ready!", "percentage": 100}, results={"thumbnail_urls": urls})
            
    except Exception as e:
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "FAILED", error_message=f"Thumbnail generation failed: {str(e)}")


@celery_app.task
def cleanup_old_files():
    """
    A daily task to clean up old files from uploads and temporary directories
    to prevent the server from running out of space.
    """
    logger.info("🧹 Starting daily cleanup of old files...")
    from app.core.config import settings
    
    cleanup_age_days = 1 
    cutoff = datetime.now() - timedelta(days=cleanup_age_days)
    
    upload_dir = os.path.join(settings.STATIC_GENERATED_DIR, "uploads")
    temp_clips_dir = settings.STATIC_GENERATED_DIR
    
    patterns = [
        os.path.join(upload_dir, '*'),
        os.path.join(temp_clips_dir, 'temp_*.mp4'),
        os.path.join(temp_clips_dir, 'final_*.mp4'), # Also clean up final clips
        os.path.join(temp_clips_dir, 'captions_*.srt'),
        os.path.join(temp_clips_dir, 'captions_*.ass')
    ]
    
    files_removed = 0
    for pattern in patterns:
        for file_path in glob.glob(pattern):
            try:
                file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                if file_mod_time < cutoff:
                    os.remove(file_path)
                    logger.info(f"Removed old file: {file_path}")
                    files_removed += 1
            except Exception as e:
                logger.error(f"Error removing file {file_path}: {e}")
    
    logger.info(f"✅ Daily cleanup finished. Removed {files_removed} old files.")