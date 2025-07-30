# app/workers/tasks.py

import asyncio
import subprocess
import os
import json
import time

from app.celery_app import celery_app
from app.db import crud
from app.db.base import get_db
from app.services import video_engine, utils
from pydub import AudioSegment

#================================================================================#
# == NEW & CORRECTED VIDEO UPLOAD TASK ==                                        #
# This replaces the old YouTube URL logic and fixes your core feature.           #
#================================================================================#

@celery_app.task(bind=True)
def run_videoclip_upload_job(self, job_id: str, user_id: int, video_path: str, add_captions: bool, aspect_ratio: str, platforms: list[str]):
    """
    Celery task to process an uploaded video file. This is the new core of your application.
    """
    # This runs the main async function and waits for it to complete.
    asyncio.run(
        _async_videoclip_upload_job(job_id, user_id, video_path, add_captions, aspect_ratio, platforms)
    )

async def _async_videoclip_upload_job(job_id: str, user_id: int, video_path: str, add_captions: bool, aspect_ratio: str, platforms: list[str]):
    """
    The main asynchronous logic for processing an uploaded video.
    """
    db = next(get_db())
    audio_path = None
    
    try:
        # 1. Update Status & Extract Audio using FFmpeg
        crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Extracting audio from video...", "percentage": 10})
        
        audio_path = video_path.rsplit('.', 1)[0] + '.mp3'
        command = ['ffmpeg', '-i', video_path, '-q:a', '0', '-map', 'a', '-y', audio_path]
        subprocess.run(command, check=True, capture_output=True, text=True) # Use capture_output to hide ffmpeg logs
        
        if not os.path.exists(audio_path):
            raise FileNotFoundError("FFmpeg failed to create the audio file. Check FFmpeg installation and file paths.")

        # 2. Transcribe Audio (Requires your new utility function)
        crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Transcribing audio (this can take a moment)...", "percentage": 25})
        
        # This will call your Whisper logic on the extracted local audio file.
        # You need to ensure utils.transcribe_local_audio_file is implemented.
        transcript_result = await utils.transcribe_local_audio_file(audio_path, user_id, job_id)
        if not transcript_result or not transcript_result.get('success'):
            raise ValueError(f"Transcription failed: {transcript_result.get('error', 'Unknown error')}")
        full_words_data = transcript_result['data']['words']

        # 3. Find Viral Moments (Your secret sauce)
        crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Analyzing content for viral moments...", "percentage": 60})
        speech_segments = utils.detect_silence_and_chunk(audio_path)
        text_chunks = [' '.join(w['word'] for w in full_words_data if w['start'] >= s['start'] and w['end'] <= s['end']) for s in speech_segments]
        
        viral_indices = utils.analyze_content_chunks(text_chunks, user_id)
        if not viral_indices:
            raise ValueError("AI analysis did not find any high-potential video clips.")

        # 4. Generate Clips for Each Platform
        moments = [{'start': speech_segments[i]['start'], 'duration': speech_segments[i]['end'] - speech_segments[i]['start']} for i in viral_indices]
        clips_by_platform = {p: [] for p in platforms}
        flags = {"add_captions": add_captions, "add_music": True}

        for i, moment in enumerate(moments):
            progress = 60 + int(((i + 1) / len(moments)) * 35)
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": f"Rendering clip {i+1} of {len(moments)}...", "percentage": progress})
            
            for platform in platforms:
                platform_aspect_ratio = "9:16" # Default for TikTok/Shorts/Reels
                if platform in ["linkedin", "twitter"]:
                    platform_aspect_ratio = "1:1"
                
                flags["aspect_ratio"] = platform_aspect_ratio
                unique_clip_id = f"{job_id}_{i+1}_{platform}"
                
                clip_result = video_engine.process_single_clip(video_path, moment, flags, user_id, unique_clip_id, full_words_data)
                if clip_result.get('success'):
                    clips_by_platform[platform].append(clip_result['url'])

        # 5. Finalize Job
        crud.update_job_full_status(db, job_id, "COMPLETED", progress_details={"description": "All clips generated!", "percentage": 100}, results={"clips_by_platform": clips_by_platform})

    except Exception as e:
        # Detailed error logging for you to debug
        import traceback
        error_message = f"Job failed: {str(e)}"
        print(f"ERROR for job {job_id}: {error_message}\n{traceback.format_exc()}")
        crud.update_job_full_status(db, job_id, "FAILED", error_message=error_message)

    finally:
        # Clean up the temp audio file
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
        # To save space, you can also delete the original large video upload.
        # Be sure this is what you want before enabling it.
        # if video_path and os.path.exists(video_path):
        #     os.remove(video_path)


#================================================================================#
# == YOUR OTHER EXISTING TASKS ==                                                #
# These are preserved to ensure other app features continue to work.             #
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
        content_analysis = utils.run_ai_generation(analysis_prompt, user_id, model="gpt-4o")
        if not content_analysis: raise Exception("AI content analysis failed.")
        crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Generating posts...", "percentage": 60})
        generation_prompt = f"""
        You are an expert content strategist. Transform the source content into social media posts for: {', '.join(platforms)}.
        SOURCE CONTENT:\n{content_to_process[:12000]}
        """
        drafts = utils.run_ai_generation(generation_prompt, user_id, model="gpt-4o")
        if not drafts: raise Exception("AI content generation failed.")
        polished_drafts = utils.local_ai_polish(drafts)
        results = {"analysis": content_analysis, "posts": polished_drafts}
        crud.update_job_full_status(db, job_id, "COMPLETED", progress_details={"description": "Content suite generated!", "percentage": 100}, results=results)
    except Exception as e:
        crud.update_job_full_status(db, job_id, "FAILED", error_message=f"Content repurposing failed: {str(e)}")


@celery_app.task(bind=True)
def generate_thumbnail_job(self, job_id: str, user_id: int, prompt_text: str):
    db = next(get_db())
    try:
        crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Generating prompts...", "percentage": 10})
        prompt_gen_prompt = f'Based on the content, generate 3 striking prompts for an AI image generator to create a thumbnail. Respond with ONLY a valid JSON list of strings.\nCONTENT: {prompt_text}'
        image_prompts = []
        for _ in range(3):
            response_str = utils.run_ai_generation(prompt_gen_prompt, user_id, "gpt-4o-mini", 500, expect_json=True)
            if response_str:
                try:
                    prompts = json.loads(response_str)
                    if isinstance(prompts, list) and prompts: image_prompts = prompts; break
                except (json.JSONDecodeError, TypeError): pass
            time.sleep(1)
        if not image_prompts: raise Exception("Failed to generate valid image prompts.")
        urls = []
        for i, prompt in enumerate(image_prompts):
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": f"Generating thumbnail {i+1}/{len(image_prompts)}...", "percentage": 20+int(((i+1)/len(image_prompts))*75)})
            url = video_engine.sd_generator.generate_image(prompt, 1280, 720)
            if url:
                urls.append(url)
                utils.track_usage("stable-diffusion-local", user_id, 'thumbnail', custom_cost=0.0)
        if not urls: raise Exception("No thumbnails were successfully generated.")
        crud.update_job_full_status(db, job_id, "COMPLETED", progress_details={"description": "Thumbnails ready!", "percentage": 100}, results={"thumbnail_urls": urls})
    except Exception as e:
        crud.update_job_full_status(db, job_id, "FAILED", error_message=f"Thumbnail generation failed: {str(e)}")