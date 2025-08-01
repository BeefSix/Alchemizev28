# app/workers/tasks.py

import asyncio
import subprocess
import os
import json
import time
import logging

from app.celery_app import celery_app
from app.db import crud
from app.db.base import get_db_session
from app.services import video_engine, utils

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    audio_path = None # Define audio_path here to ensure it's available in the finally block
    
    try:
        # --- DB Write 1: Set initial status ---
        with get_db_session() as db:
            if not os.path.isabs(video_path):
                video_path = os.path.abspath(video_path)
            if not os.path.exists(video_path):
                raise FileNotFoundError(f"Video file not found: {video_path}")
            
            logger.info(f"Processing video: {video_path} (size: {os.path.getsize(video_path)} bytes)")
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                progress_details={"description": "Extracting audio from video...", "percentage": 10})

        # --- Long-running task: Audio Extraction ---
        audio_path = video_path.rsplit('.', 1)[0] + '_audio.mp3'
        command = ['ffmpeg', '-i', video_path, '-vn', '-acodec', 'mp3', '-ab', '192k', '-ar', '44100', '-y', audio_path]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        logger.info(f"Audio extracted successfully: {audio_path}")

        # --- DB Write 2: Update status ---
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                progress_details={"description": "Transcribing audio (this may take a few minutes)...", "percentage": 25})
        
        # --- Long-running task: Transcription ---
        transcript_result = await utils.transcribe_local_audio_file(audio_path, user_id, job_id)
        if not transcript_result or not transcript_result.get('success'):
            raise ValueError(f"Transcription failed: {transcript_result.get('error', 'Unknown error')}")
        
        full_words_data = transcript_result['data']['words']
        
        # --- DB Write 3: Update status ---
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                progress_details={"description": "Analyzing content for viral moments...", "percentage": 50})
        
        # --- Long-running task: AI Analysis ---
        speech_segments = utils.detect_silence_and_chunk(audio_path)
        text_chunks = [' '.join(w['word'] for w in full_words_data if seg['start'] <= w.get('start', 0) <= seg['end']) for seg in speech_segments]
        viral_indices = await utils.analyze_content_chunks(text_chunks, user_id)
        if not viral_indices:
            viral_indices = list(range(min(3, len(speech_segments))))
        
        moments = [{'start': speech_segments[idx]['start'], 'duration': min(speech_segments[idx]['end'] - speech_segments[idx]['start'], 60)} for idx in viral_indices if idx < len(speech_segments)]
        clips_by_platform = {p: [] for p in platforms}

        # --- Loop for Clip Creation ---
        for i, moment in enumerate(moments):
            with get_db_session() as db:
                progress = 50 + int(((i + 1) / len(moments)) * 45) if len(moments) > 0 else 95
                crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                    progress_details={"description": f"Creating clip {i+1}/{len(moments)}...", "percentage": progress})
            
            clip_id = f"{job_id}_clip_{i+1}"
            clip_result = video_engine.process_single_clip(
                video_path, moment, {"add_captions": add_captions, "aspect_ratio": aspect_ratio, "platform": "multi-platform"},
                user_id, clip_id, full_words_data
            )
            if clip_result.get('success'):
                for platform in platforms:
                    clips_by_platform[platform].append(clip_result['url'])
        
        if not any(clips_by_platform.values()):
            raise ValueError("No clips were successfully generated")

        # --- DB Write 4: Final Success Status ---
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "COMPLETED", 
                progress_details={"description": "All clips generated successfully!", "percentage": 100}, 
                results={"clips_by_platform": clips_by_platform})
        logger.info(f"Job completed successfully.")

    except Exception as e:
        import traceback
        error_message = f"Job failed: {str(e)}"
        logger.error(f"ERROR for job {job_id}: {error_message}\n{traceback.format_exc()}")
        # --- DB Write 5: Final Failure Status ---
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "FAILED", error_message=error_message)

    finally:
        # --- THIS BLOCK ALWAYS RUNS ---
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                logger.info(f"Cleaned up audio file: {audio_path}")
            except Exception as e:
                logger.error(f"Error cleaning up audio file: {e}")


@celery_app.task(bind=True)
def run_content_repurpose_job(self, job_id: str, user_id: int, content_input: str, platforms: list[str], tone: str, style: str, additional_instructions: str):
    """
    Celery task for content repurposing, now with tone, style, and instructions.
    """
    asyncio.run(_async_content_repurpose_job(job_id, user_id, content_input, platforms, tone, style, additional_instructions))

async def _async_content_repurpose_job(job_id: str, user_id: int, content_input: str, platforms: list[str], tone: str, style: str, additional_instructions: str):
    try:
        # --- DB Write 1: Set initial status ---
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Ingesting content...", "percentage": 5})
        
        # --- Long-running task (no DB connection held) ---
        content_to_process = utils.ingest_content(content_input)

        # --- DB Write 2: Update status ---
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Analyzing content...", "percentage": 20})
        
        # --- Long-running AI task (no DB connection held) ---
        analysis_prompt = f"Analyze this content and extract key insights, tone, and audience.\n\nCONTENT:\n{content_to_process[:4000]}"
        content_analysis = await utils.run_ai_generation(analysis_prompt, user_id, model="gpt-4o")
        if not content_analysis: raise Exception("AI content analysis failed.")
        
        # --- DB Write 3: Update status ---
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Generating posts...", "percentage": 60})
        
        # --- Long-running AI task (no DB connection held) ---
        generation_prompt = f"""
You are an expert content strategist. Transform the provided source content into a suite of high-quality social media posts for these platforms: {', '.join(platforms)}.

Adhere to these specific instructions:
- Tone: {tone}
- Writing Style: {style}
- Additional Instructions: {additional_instructions if additional_instructions else "None"}

- Base all posts on the SOURCE CONTENT.
- For LinkedIn/Facebook, use bullet points or lists for depth.
- For Twitter/Instagram, end with an engaging question.

SOURCE CONTENT:
{content_to_process[:12000]}

---
Generate the posts now. Use markdown headings for each platform (e.g., ### Twitter).
"""
        drafts = await utils.run_ai_generation(generation_prompt, user_id, model="gpt-4o")
        if not drafts: raise Exception("AI content generation failed.")
        
        # --- DB Write 4: Final update ---
        results = {"analysis": content_analysis, "posts": drafts}
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "COMPLETED", progress_details={"description": "Content suite generated!", "percentage": 100}, results=results)

    except Exception as e:
        # --- DB Write (on failure): Final update ---
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "FAILED", error_message=f"Content repurposing failed: {str(e)}")

# (Keep your existing thumbnail job task as is)
@celery_app.task(bind=True)
def generate_thumbnail_job(self, job_id: str, user_id: int, prompt_text: str):
    asyncio.run(_async_generate_thumbnail_job(job_id, user_id, prompt_text))

async def _async_generate_thumbnail_job(job_id: str, user_id: int, prompt_text: str):
    try:
        # --- DB Write 1: Set initial status ---
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Generating prompts...", "percentage": 10})

        # --- Long-running AI Task (no DB connection held) ---
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
            await asyncio.sleep(1) # Wait before retrying
        
        if not image_prompts: raise Exception("Failed to generate valid image prompts.")
        
        urls = []
        for i, prompt in enumerate(image_prompts):
            # --- DB Write (for each loop iteration) ---
            with get_db_session() as db:
                progress = 20 + int(((i + 1) / len(image_prompts)) * 75)
                crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": f"Generating thumbnail {i+1}/{len(image_prompts)}...", "percentage": progress})
            
            # --- Long-running Image Generation Task (no DB connection held) ---
            url = video_engine.sd_generator.generate_image(prompt, 1280, 720)
            if url:
                urls.append(url)
                # This call to track_usage now safely manages its own DB session inside utils.py
                utils.track_usage("stable-diffusion-local", user_id, 'thumbnail', custom_cost=0.0)

        if not urls: raise Exception("No thumbnails were successfully generated.")
        
        # --- DB Write: Final Success Status ---
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "COMPLETED", progress_details={"description": "Thumbnails ready!", "percentage": 100}, results={"thumbnail_urls": urls})
            
    except Exception as e:
        # --- DB Write: Final Failure Status ---
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "FAILED", error_message=f"Thumbnail generation failed: {str(e)}")