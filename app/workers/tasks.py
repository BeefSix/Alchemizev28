# app/workers/tasks.py
from app.celery_app import celery_app
from app.db import crud
from app.db.base import get_db
from app.services import video_engine, utils
import json
import os
import time

# Example: Content Repurposing Task
@celery_app.task(bind=True)
async def run_content_repurpose_job(self, job_id: str, user_id: int, content_input: str, platforms: list[str]): # user_id is int
    db = next(get_db())
    try:
        crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Ingesting content...", "percentage": 5})

        # AWAIT THE ASYNC FUNCTION CALL
        ingestion_result = await utils._ingest_text_or_article_sync(content_input, user_id)
        if not ingestion_result['success']:
            raise ValueError(f"Content ingestion failed: {ingestion_result['error']}")
        content_to_process = ingestion_result['content']
        
        crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Analyzing content...", "percentage": 20})

        analysis_prompt = f"Analyze this content and extract key insights, tone, and audience.\n\nCONTENT:\n{content_to_process[:4000]}"
        content_analysis = utils.run_ai_generation(analysis_prompt, user_id, model="gpt-4o")
        if not content_analysis:
            raise Exception("AI content analysis failed.")

        crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Generating posts...", "percentage": 60})

        generation_prompt = f"""
        You are an expert content strategist. Transform the provided source content into a suite of high-quality social media posts for the specified platforms.
        - Base all posts on the SOURCE CONTENT.
        - For LinkedIn/Facebook, use bullet points or lists for depth.
        - For Twitter/Instagram, end with an engaging question.
        - Generate posts ONLY for the following platforms: {', '.join(platforms)}.

        SOURCE CONTENT:
        ```
        {content_to_process[:12000]}
        ```
        ---
        Generate the posts now. Use markdown headings for each platform (e.g., ### Twitter).
        """
        drafts = utils.run_ai_generation(generation_prompt, user_id, model="gpt-4o")
        if not drafts:
            raise Exception("AI content generation failed.")

        polished_drafts = utils.local_ai_polish(drafts)

        results_payload = {"analysis": content_analysis, "posts": polished_drafts}
        
        crud.update_job_full_status(db, job_id, "COMPLETED", progress_details={"description": "Content suite generated!", "percentage": 100}, results=results_payload)

    except Exception as e:
        error_message = f"Content repurposing failed: {str(e)}"
        crud.update_job_full_status(db, job_id, "FAILED", error_message=error_message)
        raise


# Video Clip Generation Task - MADE ASYNC
@celery_app.task(bind=True)
async def run_videoclip_job(self, job_id: str, user_id: int, video_url: str, add_captions: bool, aspect_ratio: str): # user_id is int now
    db = next(get_db())
    try:
        crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Validating video request...", "percentage": 5})

        can_validate, result = utils.validate_video_request(video_url)
        if not can_validate: raise ValueError(f"Video validation failed: {result}")
        
        can_process, limit_msg = utils.check_usage_limits(user_id, 'video')
        if not can_process: raise ValueError(f"Usage limit reached: {limit_msg}")
        
        crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Downloading video...", "percentage": 10})
        video_path_info = utils.download_media(video_url, is_video=True)
        if not video_path_info['success']: raise ValueError(f"Video download failed: {video_path_info['error']}")
        source_video_path = video_path_info['path']
        
        crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Extracting audio and transcribing...", "percentage": 20})
        transcript_result = await utils.get_or_create_transcript(video_url, user_id, job_id)
        if not transcript_result['success']: raise ValueError(f"Transcription failed: {transcript_result['error']}")
        
        full_transcript_text = transcript_result['data']['text']
        full_words_data = transcript_result['data']['words']
        audio_file_path = transcript_result['audio_file']

        crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Detecting viral moments...", "percentage": 40})
        
        speech_segments = utils.detect_silence_and_chunk(audio_file_path)
        if not speech_segments: raise ValueError("Could not detect any speech segments.")

        text_chunks_for_analysis = []
        for seg in speech_segments:
            chunk_words = [
                word_info['word'] for word_info in full_words_data
                if word_info['start'] >= seg['start'] and word_info['end'] <= seg['end']
            ]
            text_chunks_for_analysis.append(' '.join(chunk_words))

        viral_indices = analyze_content_chunks(text_chunks_for_analysis, user_id)
        if not viral_indices: raise ValueError("AI analysis found no high-scoring moments.")
        
        moments_to_clip = [{'start': speech_segments[i]['start'], 'duration': speech_segments[i]['end'] - speech_segments[i]['start']} for i in viral_indices]
        
        final_clips_urls = []
        total_clips = len(moments_to_clip)

        # Define flags once outside the loop, as they are constant for this task execution
        clip_processing_flags = {
            "add_captions": add_captions,
            "aspect_ratio": aspect_ratio,
            "add_music": True
        }

        for i, moment in enumerate(moments_to_clip):
            progress_desc = f"Rendering clip {i+1}/{total_clips}..."
            percentage = 40 + int(((i+1) / total_clips) * 50)
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": progress_desc, "percentage": percentage})

            # Pass full_words_data to process_single_clip so it can filter for the specific clip's words
            clip_result = video_engine.process_single_clip(source_video_path, moment, clip_processing_flags, user_id, i+1, full_words_data)
            
            if clip_result['success']:
                final_clips_urls.append(clip_result['url']) 
            else:
                print(f"Error processing clip {i+1}: {clip_result['error']}")
                raise Exception(f"Failed to process clip {i+1}: {clip_result['error']}")

        results_payload = {"clip_urls": final_clips_urls}
        crud.update_job_full_status(db, job_id, "COMPLETED", progress_details={"description": "Video clips generated!", "percentage": 100}, results=results_payload)

    except Exception as e:
        error_message = f"Video clipping job failed: {str(e)}"
        crud.update_job_full_status(db, job_id, "FAILED", error_message=error_message)
        raise
    finally:
        utils.cleanup_temp_files(patterns=[
            f"temp_*{job_id}*.*",
            f"final_clip_*{job_id}*.*",
            f"temp_transcription_chunk_{job_id}*.mp3"
        ])
        if 'source_video_path' in locals() and os.path.exists(source_video_path):
            try:
                os.remove(source_video_path)
            except OSError as e:
                print(f"Error removing source video {source_video_path}: {e}")

# This is a helper for analyze_content_chunks, used internally by tasks.py
def analyze_content_chunks(text_chunks, user_id):
    """
    Analyzes transcribed text chunks to find engaging moments using a scoring system.
    """
    print("🤖 Analyzing content chunks for viral potential...")
    chunk_scores = []
    
    for i, chunk in enumerate(text_chunks):
        if len(chunk.strip()) < 80:
            chunk_scores.append({'index': i, 'score': 0})
            continue
        
        prompt = f"""
        You are a viral video producer. On a scale of 1-10, how likely is the following text segment to be an engaging, self-contained short video clip?
        Your answer MUST be a single integer or word (e.g., 8 or 'eight').

        TEXT SEGMENT:
        "{chunk}"
        """
        score = 0
        for attempt in range(2):
            response = utils.run_ai_generation(prompt, user_id, model="gpt-4o-mini", max_tokens=10, temperature=0.2)
            score = utils._parse_score_from_response(response)
            if score > 0:
                break
            else:
                print(f"⚠️ Could not parse score for chunk {i} on attempt {attempt+1}. Retrying in 2 seconds...")
                time.sleep(2)

        chunk_scores.append({'index': i, 'score': score})
        print(f"Chunk {i} scored: {score}/10")

    sorted_chunks = sorted(chunk_scores, key=lambda x: x['score'], reverse=True)
    
    viral_indices = [chunk['index'] for chunk in sorted_chunks if chunk['score'] >= 5]
    
    if not viral_indices and sorted_chunks:
        print("⚠️ No high-scoring chunks found. Falling back to the top 2 chunks regardless of score.")
        viral_indices = [chunk['index'] for chunk in sorted_chunks[:2]]
    elif len(viral_indices) > 3:
        viral_indices = viral_indices[:3]
    
    return viral_indices


# Thumbnail Generation Task
@celery_app.task(bind=True)
def generate_thumbnail_job(self, job_id: str, user_id: int, prompt_text: str):
    db = next(get_db())
    try:
        crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": "Initializing thumbnail generation...", "percentage": 10})

        prompt_generation_prompt = f"""
        Based on the following content analysis, generate 3 distinct, visually striking, and compelling prompts for an AI image generator to create a YouTube thumbnail.
        IMPORTANT: You must respond with ONLY a valid JSON list of strings and nothing else. Do not include conversational text or markdown formatting.
        Example response: ["a photorealistic image of a rising sun", "a dramatic closeup of a lion"]

        CONTENT ANALYSIS:
        {prompt_text}
        """
        image_prompts = []
        for attempt in range(3):
            print(f"Attempting to generate image prompts (Attempt {attempt + 1}/3)...")
            response_str = utils.run_ai_generation(prompt_generation_prompt, user_id, "gpt-4o-mini", 500, expect_json=True)
            if response_str:
                try:
                    parsed_prompts = json.loads(response_str)
                    if isinstance(parsed_prompts, list) and len(parsed_prompts) > 0:
                        image_prompts = parsed_prompts
                        print("✅ Successfully generated and parsed image prompts.")
                        break
                except (json.JSONDecodeError, TypeError):
                    print(f"⚠️ Failed to parse AI response on attempt {attempt + 1}. Response: {response_str[:100]}... Retrying in 2 seconds...")
            time.sleep(2)
        
        if not image_prompts:
            raise Exception("Failed to generate valid image prompts after multiple attempts.")

        thumbnail_urls = []
        for i, prompt in enumerate(image_prompts):
            progress_desc = f"Generating thumbnail {i+1}/{len(image_prompts)}..."
            percentage = 10 + int(((i+1) / len(image_prompts)) * 80)
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": progress_desc, "percentage": percentage})

            generated_url = video_engine.sd_generator.generate_image(prompt, width=1280, height=720)
            
            if generated_url:
                thumbnail_urls.append(generated_url)
                utils.track_usage("stable-diffusion-local", user_id, 'thumbnail', custom_cost=0.0)
            else:
                print(f"⚠️ Warning: Thumbnail generation failed for prompt: '{prompt}'")

        if not thumbnail_urls:
            raise Exception("No thumbnails were successfully generated.")

        results_payload = {"thumbnail_urls": thumbnail_urls}
        crud.update_job_full_status(db, job_id, "COMPLETED", progress_details={"description": "Thumbnails generated!", "percentage": 100}, results=results_payload)

    except Exception as e:
        error_message = f"Thumbnail generation failed: {str(e)}"
        crud.update_job_full_status(db, job_id, "FAILED", error_message=error_message)
        raise
    finally:
        utils.cleanup_temp_files(patterns=[f"thumbnail_{job_id}*.png"])