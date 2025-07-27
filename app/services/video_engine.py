# app/workers/tasks.py
import asyncio
from app.celery_app import celery_app
from app.db import crud
from app.db.base import get_db
from app.services import video_engine, utils
import json
import os
import time
from pydub import AudioSegment

async def run_with_progress_updates(db, job_id, start_percent, end_percent, total_duration, task_coroutine, description):
    update_interval = 5
    estimated_task_duration = max(total_duration / 10, update_interval) # Ensure at least one update cycle
    num_updates = int(estimated_task_duration / update_interval)
    percent_per_update = (end_percent - start_percent) / num_updates if num_updates > 0 else (end_percent - start_percent)

    async def update_progress():
        for i in range(1, num_updates + 1):
            await asyncio.sleep(update_interval)
            current_percent = start_percent + int(percent_per_update * i)
            time_remaining = int(estimated_task_duration - (i * update_interval))
            eta_description = f"{description} (est. {time_remaining}s left)"
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": eta_description, "percentage": current_percent})

    progress_task = asyncio.create_task(update_progress())
    result = await task_coroutine
    progress_task.cancel()
    crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": f"{description.replace('...','')} complete!", "percentage": end_percent})
    return result

@celery_app.task(bind=True)
def run_videoclip_job(self, job_id: str, user_id: int, video_url: str, add_captions: bool, aspect_ratio: str):
    asyncio.run(_async_videoclip_job(job_id, user_id, video_url, add_captions, aspect_ratio))

async def _async_videoclip_job(job_id: str, user_id: int, video_url: str, add_captions: bool, aspect_ratio: str):
    db = next(get_db())
    source_video_path, audio_path = None, None
    try:
        crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Validating video...", "percentage": 5})
        can_validate, _ = utils.validate_video_request(video_url)
        if not can_validate: raise ValueError("Video validation failed.")
        
        crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Downloading...", "percentage": 10})
        video_path_info = utils.download_media(video_url, is_video=True)
        if not video_path_info['success']: raise ValueError(f"Video download failed: {video_path_info['error']}")
        source_video_path = video_path_info['path']
        
        audio_info = utils.download_media(video_url, is_video=False)
        if not audio_info['success']: raise ValueError("Failed to extract audio.")
        audio_path = audio_info['path']
        audio_duration = AudioSegment.from_mp3(audio_path).duration_seconds
        
        transcript_coro = utils.get_or_create_transcript(video_url, user_id, job_id)
        transcript_result = await run_with_progress_updates(db, job_id, 20, 50, audio_duration, transcript_coro, "Transcribing...")
        if not transcript_result['success']: raise ValueError(f"Transcription failed: {transcript_result['error']}")
        
        full_words_data = transcript_result['data']['words']
        
        crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Finding viral moments...", "percentage": 55})
        speech_segments = utils.detect_silence_and_chunk(audio_path)
        if not speech_segments: raise ValueError("Could not detect any speech segments.")
        
        text_chunks = [' '.join(w['word'] for w in full_words_data if w['start'] >= s['start'] and w['end'] <= s['end']) for s in speech_segments]
        viral_indices = analyze_content_chunks(text_chunks, user_id)
        if not viral_indices: raise ValueError("AI analysis found no high-scoring moments.")
        
        moments = [{'start': speech_segments[i]['start'], 'duration': speech_segments[i]['end'] - speech_segments[i]['start']} for i in viral_indices]
        urls = []
        flags = {"add_captions": add_captions, "aspect_ratio": aspect_ratio, "add_music": True}
        
        for i, moment in enumerate(moments):
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": f"Rendering clip {i+1}/{len(moments)}...", "percentage": 60+int(((i+1)/len(moments))*35)})
            clip_result = video_engine.process_single_clip(source_video_path, moment, flags, user_id, i+1, full_words_data)
            if not clip_result['success']: raise Exception(f"Failed to process clip {i+1}: {clip_result['error']}")
            urls.append(clip_result['url'])
            
        crud.update_job_full_status(db, job_id, "COMPLETED", progress_details={"description": "Clips generated!", "percentage": 100}, results={"clip_urls": urls})
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        crud.update_job_full_status(db, job_id, "FAILED", error_message=f"Video clipping job failed: {str(e)}")
    finally:
        utils.cleanup_temp_files(patterns=[f"temp_*{job_id}*.*", f"final_clip_*{job_id}*.*", os.path.basename(source_video_path or ''), os.path.basename(audio_path or '')])


# --- Other Functions (No Change) ---
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

def analyze_content_chunks(text_chunks, user_id):
    scores = []
    for i, chunk in enumerate(text_chunks):
        if len(chunk.strip()) < 80: scores.append({'index': i, 'score': 0}); continue
        prompt = f'On a scale of 1-10, how engaging is this text for a short video clip? Answer with a single integer.\nTEXT: "{chunk}"'
        score = 0
        for _ in range(2):
            response = utils.run_ai_generation(prompt, user_id, "gpt-4o-mini", 10, 0.2)
            score = utils._parse_score_from_response(response)
            if score > 0: break
        scores.append({'index': i, 'score': score})
    sorted_chunks = sorted(scores, key=lambda x: x['score'], reverse=True)
    indices = [c['index'] for c in sorted_chunks if c['score'] >= 5]
    if not indices and sorted_chunks: indices = [c['index'] for c in sorted_chunks[:2]]
    return indices[:3]