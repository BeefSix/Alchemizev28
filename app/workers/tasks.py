# app/workers/tasks.py

import asyncio
import subprocess
import os
import json
import time
import logging

from app.celery_app import celery_app
from app.db import crud
from app.db.base import get_db
from app.services import video_engine, utils

# Configure logging to see print statements in Docker
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#================================================================================#
# == VIDEO UPLOAD TASK ==                                                        #
#================================================================================#

@celery_app.task(bind=True)
def run_videoclip_upload_job(self, job_id: str, user_id: int, video_path: str, add_captions: bool, aspect_ratio: str, platforms: list[str]):
    """
    Celery's synchronous entry point for the video clipping job.
    """
    asyncio.run(
        _async_videoclip_upload_job(job_id, user_id, video_path, add_captions, aspect_ratio, platforms)
    )

async def _async_videoclip_upload_job(job_id: str, user_id: int, video_path: str, add_captions: bool, aspect_ratio: str, platforms: list[str]):
    """The main asynchronous logic for processing an uploaded video."""
    db = next(get_db())
    audio_path = None
    
    try:
        # 1. Verify paths and update status
        if not os.path.isabs(video_path):
            video_path = os.path.abspath(video_path)
        
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        logger.info(f"Processing video: {video_path} (size: {os.path.getsize(video_path)} bytes)")
        crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
            progress_details={"description": "Extracting audio from video...", "percentage": 10})
        
        # 2. Extract audio using FFmpeg
        audio_path = video_path.rsplit('.', 1)[0] + '_audio.mp3'
        command = ['ffmpeg', '-i', video_path, '-vn', '-acodec', 'mp3', '-ab', '192k', '-ar', '44100', '-y', audio_path]
        logger.info(f"Running FFmpeg command: {' '.join(command)}")
        
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            error_details = f"FFmpeg failed with exit code {result.returncode}\nSTDERR: {result.stderr}"
            logger.error(error_details)
            raise ValueError(f"FFmpeg audio extraction failed.")
        
        logger.info(f"Audio extracted successfully: {audio_path}")

        # 3. Transcribe Audio
        crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
            progress_details={"description": "Transcribing audio (this may take a few minutes)...", "percentage": 25})
        
        transcript_result = await utils.transcribe_local_audio_file(audio_path, user_id, job_id)
        if not transcript_result or not transcript_result.get('success'):
            raise ValueError(f"Transcription failed: {transcript_result.get('error', 'Unknown error')}")
        
        full_words_data = transcript_result['data']['words']
        
        # 4. Find Viral Moments
        crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
            progress_details={"description": "Analyzing content for viral moments...", "percentage": 50})
        
        speech_segments = utils.detect_silence_and_chunk(audio_path)
        text_chunks = [' '.join(w['word'] for w in full_words_data if seg['start'] <= w.get('start', 0) <= seg['end']) for seg in speech_segments]
        logger.info(f"Found {len(speech_segments)} speech segments")
        
        # =================== FIX START ===================
        # We are already in an async function, so we must 'await' the async version directly.
        viral_indices = await utils.analyze_content_chunks(text_chunks, user_id)
        # =================== FIX END ===================

        if not viral_indices:
            viral_indices = list(range(min(3, len(speech_segments)))) # Fallback
            logger.info("No high-scoring segments found, using first segments as fallback")
        
        logger.info(f"Selected {len(viral_indices)} segments for clips: {viral_indices}")

        # 5. Generate Clips
        moments = [{'start': speech_segments[idx]['start'], 'duration': min(speech_segments[idx]['end'] - speech_segments[idx]['start'], 60)} for idx in viral_indices if idx < len(speech_segments)]
        
        clips_by_platform = {}
        total_clips_to_make = len(moments) * len(platforms)
        clips_made = 0
        
        for platform in platforms:
            platform_clips = []
            platform_aspect_ratio = "9:16" if platform in ["youtube_shorts", "tiktok", "instagram_reels"] else "1:1"
            
            for i, moment in enumerate(moments):
                clips_made += 1
                progress = 50 + int((clips_made / total_clips_to_make) * 45) if total_clips_to_make > 0 else 95
                crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                    progress_details={"description": f"Creating {platform} clip {i+1}/{len(moments)}...", "percentage": progress})
                
                clip_id = f"{job_id}_{platform}_{i+1}"
                try:
                    clip_result = video_engine.process_single_clip(
                        video_path, moment, 
                        {"add_captions": add_captions, "aspect_ratio": platform_aspect_ratio, "platform": platform},
                        user_id, clip_id, full_words_data
                    )
                    if clip_result.get('success'):
                        platform_clips.append(clip_result['url'])
                except Exception as e:
                    logger.error(f"Error creating clip for {platform}: {str(e)}")
            
            if platform_clips:
                clips_by_platform[platform] = platform_clips

        # 6. Complete the job
        if not clips_by_platform:
            raise ValueError("No clips were successfully generated")

        crud.update_job_full_status(db, job_id, "COMPLETED", 
            progress_details={"description": "All clips generated successfully!", "percentage": 100}, 
            results={"clips_by_platform": clips_by_platform})
        logger.info(f"Job completed successfully.")

    except Exception as e:
        import traceback
        error_message = f"Job failed: {str(e)}"
        logger.error(f"ERROR for job {job_id}: {error_message}\n{traceback.format_exc()}")
        crud.update_job_full_status(db, job_id, "FAILED", error_message=error_message)

    finally:
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                logger.info(f"Cleaned up audio file: {audio_path}")
            except Exception as e:
                logger.error(f"Error cleaning up audio file: {e}")

#================================================================================#
# == YOUR OTHER EXISTING TASKS (PRESERVED) ==                                    #
#================================================================================#

@celery_app.task(bind=True)
def run_content_repurpose_job(self, job_id: str, user_id: int, content_input: str, platforms: list[str]):
    asyncio.run(_async_content_repurpose_job(job_id, user_id, content_input, platforms))

async def _async_content_repurpose_job(job_id: str, user_id: int, content_input: str, platforms: list[str]):
    db = next(get_db())
    try:
        crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Ingesting content...", "percentage": 5})
        ingestion_result = await utils._ingest_text_or_article_sync(content_input, user_id)
        if not ingestion_result['success']: raise ValueError(f"Content ingestion failed: {ingestion_result['error']}")
        content_to_process = ingestion_result['content']
        crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Analyzing content...", "percentage": 20})
        analysis_prompt = f"Analyze this content and extract key insights, tone, and audience.\n\nCONTENT:\n{content_to_process[:4000]}"
        content_analysis = await utils.run_ai_generation(analysis_prompt, user_id, model="gpt-4o")
        if not content_analysis: raise Exception("AI content analysis failed.")
        crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Generating posts...", "percentage": 60})
        generation_prompt = f"""
        You are an expert content strategist. Transform the source content into social media posts for: {', '.join(platforms)}.
        SOURCE CONTENT:\n{content_to_process[:12000]}
        """
        drafts = await utils.run_ai_generation(generation_prompt, user_id, model="gpt-4o")
        if not drafts: raise Exception("AI content generation failed.")
        polished_drafts = utils.local_ai_polish(drafts)
        results = {"analysis": content_analysis, "posts": polished_drafts}
        crud.update_job_full_status(db, job_id, "COMPLETED", progress_details={"description": "Content suite generated!", "percentage": 100}, results=results)
    except Exception as e:
        crud.update_job_full_status(db, job_id, "FAILED", error_message=f"Content repurposing failed: {str(e)}")

@celery_app.task(bind=True)
def generate_thumbnail_job(self, job_id: str, user_id: int, prompt_text: str):
    asyncio.run(_async_generate_thumbnail_job(job_id, user_id, prompt_text))

async def _async_generate_thumbnail_job(job_id: str, user_id: int, prompt_text: str):
    db = next(get_db())
    try:
        crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Generating prompts...", "percentage": 10})
        prompt_gen_prompt = f'Based on the content, generate 3 striking prompts for an AI image generator to create a thumbnail. Respond with ONLY a valid JSON list of strings.\nCONTENT: {prompt_text}'
        image_prompts = []
        for _ in range(3):
            response_str = await utils.run_ai_generation(prompt_gen_prompt, user_id, "gpt-4o-mini", 500, expect_json=True)
            if response_str:
                try:
                    prompts = json.loads(response_str)
                    if isinstance(prompts, list) and prompts:
                        image_prompts = prompts
                        break
                except (json.JSONDecodeError, TypeError):
                    pass
            await asyncio.sleep(1)
        if not image_prompts: raise Exception("Failed to generate valid image prompts.")
        urls = []
        for i, prompt in enumerate(image_prompts):
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": f"Generating thumbnail {i+1}/{len(image_prompts)}...", "percentage": 20+int(((i+1)/len(image_prompts))*75)})
            url = video_engine.sd_generator.generate_image(prompt, 1280, 720) # Assuming this is synchronous
            if url:
                urls.append(url)
                utils.track_usage("stable-diffusion-local", user_id, 'thumbnail', custom_cost=0.0)
        if not urls: raise Exception("No thumbnails were successfully generated.")
        crud.update_job_full_status(db, job_id, "COMPLETED", progress_details={"description": "Thumbnails ready!", "percentage": 100}, results={"thumbnail_urls": urls})
    except Exception as e:
        crud.update_job_full_status(db, job_id, "FAILED", error_message=f"Thumbnail generation failed: {str(e)}")