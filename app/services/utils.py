# app/services/utils.py
import os
import glob
import time
import yt_dlp
import subprocess
import requests
from bs4 import BeautifulSoup
from openai import OpenAI, AsyncOpenAI
import re
import hashlib
import json
from pydub import AudioSegment, silence
import uuid
import random
import logging
import asyncio

from app.db import crud
from app.db.base import get_db
from app.core.config import settings

def _parse_score_from_response(response_text: str) -> int:
    """Extracts a score from the AI's response, handling digits and words."""
    if not response_text: return 0

    score_match = re.search(r'\d+', response_text)
    if score_match: return int(score_match.group())

    number_words = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}
    for word, value in number_words.items():
        if word in response_text.lower(): return value
    return 0 # Default score if nothing is found

# --- Initialization ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
async_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
STATIC_GENERATED_DIR = settings.STATIC_GENERATED_DIR
TEMP_DOWNLOAD_DIR = os.path.join(STATIC_GENERATED_DIR, "temp_downloads")
os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)

def ingest_content(content_input: str) -> str:
    """
    Ingests content from text or a URL.
    If it's a URL, it scrapes the content. Otherwise, it returns the text directly.
    """
    if is_valid_url(content_input):
        logger.info(f"Ingesting content from URL: {content_input}")
        return scrape_url(content_input)
    else:
        logger.info("Ingesting content from direct text input.")
        return content_input

# =================== FINAL FIX: THE MISSING FUNCTION ===================
# This is the new, top-level async function your Celery worker needs.
async def transcribe_local_audio_file(audio_path: str, user_id: int, job_id: str):
    """
    Transcribes an audio file from a local path using OpenAI Whisper API,
    handles chunking for large files, and tracks usage.
    """
    db = next(get_db())
    logger.info(f"Starting transcription for local audio file: {audio_path}")
    
    try:
        if not os.path.exists(audio_path):
            return {"success": False, "error": f"Audio file not found at path: {audio_path}"}

        audio = AudioSegment.from_file(audio_path)
        duration_seconds = len(audio) / 1000.0
        
        # Estimate cost before processing
        estimated_cost = (duration_seconds / 60) * settings.TOKEN_PRICES.get("whisper-1", {}).get("output", 0.006)
        crud.update_job_full_status(db, job_id, "IN_PROGRESS", progress_details={"description": f"Transcribing audio with OpenAI Whisper (est. cost: ${estimated_cost:.4f})...", "percentage": 30})
        
        # OpenAI's API has a 25MB file limit. We chunk to be safe.
        chunk_length_ms = 15 * 60 * 1000  # 15-minute chunks
        chunks = [audio[i:i + chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]
        
        all_words, full_text, total_cost = [], "", 0.0
        
        for i, chunk in enumerate(chunks):
            chunk_path = os.path.join(TEMP_DOWNLOAD_DIR, f"temp_chunk_{job_id}_{i}.mp3")
            chunk.export(chunk_path, format="mp3")
            
            transcription_result = await transcribe_audio_chunk(chunk_path)
            os.remove(chunk_path) # Clean up chunk immediately

            if transcription_result['success']:
                offset = i * (chunk_length_ms / 1000)
                words_data = transcription_result['data'].get('words', [])
                for word_dict in words_data:
                    word_dict['start'] += offset
                    word_dict['end'] += offset
                    all_words.append(word_dict)
                full_text += transcription_result['data'].get('text', '') + " "
        
        if not full_text.strip():
            return {'success': False, 'error': 'Transcription resulted in empty text.'}

        # Track the final accurate cost
        track_usage("whisper-1", user_id, 'transcription', custom_cost=estimated_cost)
        
        final_transcript_obj = {"text": full_text.strip(), "words": all_words}
        logger.info(f"Transcription successful for job {job_id}.")
        return {"success": True, "data": final_transcript_obj}

    except Exception as e:
        logger.error(f"An error occurred in transcribe_local_audio_file for job {job_id}: {e}")
        return {"success": False, "error": str(e)}
    
    def transcribe_local_audio_file_sync(audio_path: str, user_id: int, job_id: str):
         """Synchronous wrapper for the async transcription function."""
         return asyncio.run(transcribe_local_audio_file(audio_path, user_id, job_id))

async def transcribe_audio_chunk(audio_file_path: str):
    """Helper function to transcribe a single audio chunk."""
    if not client:
        return {"success": False, "error": "OpenAI client not initialized."}
    try:
        with open(audio_file_path, 'rb') as f:
            transcript_result = await async_client.audio.transcriptions.create(
                model="whisper-1", 
                file=f, 
                response_format="verbose_json", 
                timestamp_granularities=["word"]
            )
        return {"success": True, "data": transcript_result.model_dump()}
    except Exception as e:
        logger.error(f"Failed to transcribe chunk {audio_file_path}: {e}")
        return {"success": False, "error": f"Transcription failed for a chunk: {e}"}
# =================== END OF FIX ===================


# --- YOUR EXISTING FUNCTIONS (PRESERVED) ---

def download_media(url: str, is_video: bool):
    """SIMPLE YouTube download - like your alpha but for main project"""
    logger.info(f"🎯 Simple YouTube download: {url}")
    timestamp = int(time.time())
    base_name = f"temp_{timestamp}_{'video' if is_video else 'audio'}"
    
    ydl_opts = {
        'outtmpl': os.path.join(TEMP_DOWNLOAD_DIR, f"{base_name}.%(ext)s"),
        'cookiefile': '/app/cookies.txt',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'sleep_interval': random.uniform(1, 3),
        'noplaylist': True,
    }
    
    if is_video:
        ydl_opts['format'] = 'best[height<=720][ext=mp4]/best[ext=mp4]'
        final_filename = f"{base_name}.mp4"
    else:
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]
        final_filename = f"{base_name}.mp3"
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
        
        downloaded_files = glob.glob(os.path.join(TEMP_DOWNLOAD_DIR, f"{base_name}.*"))
        if not downloaded_files:
            raise FileNotFoundError(f"No files downloaded for: {base_name}")
        
        actual_file = downloaded_files[0]
        expected_path = os.path.join(TEMP_DOWNLOAD_DIR, final_filename)
        
        if actual_file != expected_path:
            try:
                os.rename(actual_file, expected_path)
                actual_file = expected_path
            except OSError:
                pass
        
        return {'success': True, 'title': info.get('title', 'N/A'), 'duration': info.get('duration', 0), 'path': actual_file}
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return {'success': False, 'error': str(e)}

def validate_video_request(video_url: str):
    """Simple validation"""
    try:
        if not is_youtube_url(video_url):
            return False, "Not a valid YouTube URL."
        
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            duration = info.get('duration', 0)
            max_duration = settings.DAILY_LIMITS.get('max_video_duration', 3600)
            if duration > max_duration:
                return False, f"Video is too long ({duration//60} minutes)."
            return True, info
    except Exception as e:
        logger.warning(f"Validation warning: {e}")
        return True, {"duration": 1800, "title": "Video", "id": "unknown"}

def extract_video_id(url):
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)',
        r'youtube\.com\/v\/([^&\n?#]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def is_valid_url(url: str):
    return url.startswith('http://') or url.startswith('https://')

def is_youtube_url(url: str):
    patterns = [
        r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/',
        r'(https?://)?(www\.)?youtu\.be/'
    ]
    return any(re.search(p, url) for p in patterns)

def generate_hash(text: str):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def scrape_url(url: str):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        for el in soup(["script", "style", "nav", "footer", "aside", "form", "button", "header", "img", "svg"]):
            el.decompose()
        
        text_content = ' '.join(soup.stripped_strings)
        return text_content[:15000]
    except Exception as e:
        return f"Error: Failed to scrape URL: {e}"

def cleanup_temp_files(patterns=['temp_*.*', 'chunk_*.mp3', '*.pdf', '*.docx', 'thumbnail_*.png', 'final_clip_*.mp4']):
    logger.info("🧹 Cleaning up temporary files...")
    os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
    for p in patterns:
        search_pattern = os.path.join(TEMP_DOWNLOAD_DIR, p)
        for f_path in glob.glob(search_pattern):
            try:
                if os.path.abspath(f_path).startswith(os.path.abspath(TEMP_DOWNLOAD_DIR)):
                    os.remove(f_path)
                    logger.info(f"Removed: {f_path}")
            except OSError as e:
                logger.error(f"Error removing {f_path}: {e}")

async def get_or_create_transcript(source_url: str, user_id: int, job_id: str):
    db = next(get_db())
    cached_transcript_obj = crud.get_cached_transcript(db, source_url)
    if cached_transcript_obj:
        logger.info("✅ Transcript found in cache.")
        audio_info = download_media(source_url, is_video=False)
        return {'success': True, 'data': cached_transcript_obj, 'audio_file': audio_info.get('path')}

    logger.info("❌ Transcript not in cache. Starting new transcription...")
    audio_info = download_media(source_url, is_video=False)
    if not audio_info.get('success'):
        return {'success': False, 'error': f"Audio download failed: {audio_info.get('error')}"}
    
    # Re-use the new local file transcription logic
    return await transcribe_local_audio_file(audio_info['path'], user_id, job_id)

def track_usage(model: str, user_id: int, operation: str, input_tokens: int = 0, output_tokens: int = 0, custom_cost: float = None):
    """Track usage with proper database connection handling"""
    db = None
    try:
        # Get a fresh database session
        db = next(get_db())
        
        cost = 0.0
        if custom_cost is not None:
            cost = custom_cost
        elif model in settings.TOKEN_PRICES:
            cost = ((input_tokens / 1_000_000) * settings.TOKEN_PRICES[model].get("input", 0)) + \
                   ((output_tokens / 1_000_000) * settings.TOKEN_PRICES[model].get("output", 0))
        
        crud.track_usage(db, user_id, model, operation, cost)
        db.commit()  # Explicitly commit
        
    except Exception as e:
        print(f"Error in track_usage: {e}")
        if db:
            db.rollback()
    finally:
        # CRITICAL: Always close the database connection
        if db:
            db.close()

# Also fix the check_usage_limits function

def check_usage_limits(user_id: int, operation_type: str = 'video'):
    """Check usage limits with proper database connection handling"""
    db = None
    try:
        db = next(get_db())
        
        videos_today = crud.get_user_videos_today(db, user_id)
        daily_limit = settings.DAILY_LIMITS.get('videos_per_user', 10)
        
        if videos_today >= daily_limit:
            return False, f"Daily video limit reached ({videos_today}/{daily_limit})."
        
        usage_summary = crud.get_usage_summary(db, user_id)
        daily_cost = usage_summary.get('daily_cost', 0)
        cost_limit = settings.DAILY_LIMITS.get('total_daily_cost', 15.00)
        
        if daily_cost >= cost_limit:
            return False, f"Daily cost limit reached (${daily_cost:.2f}/${cost_limit:.2f})."
        
        return True, ""
        
    except Exception as e:
        print(f"Error checking usage limits: {e}")
        return True, ""
    finally:
        if db:
            db.close()

def cut_video_clip(video_file: str, start_time: float, duration: float, output_name: str):
    try:
        command = ['ffmpeg', '-ss', str(start_time), '-i', video_file, '-t', str(duration), '-c', 'copy', '-y', output_name]
        subprocess.run(command, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error cutting video clip: {e.stderr}")
        return False

def detect_silence_and_chunk(audio_path: str):
    try:
        # Using pydub's silence detection is often more reliable
        audio = AudioSegment.from_file(audio_path)
        not_silences = silence.detect_nonsilent(audio, min_silence_len=700, silence_thresh=-35)

        if not not_silences:
            return [{'start': 0, 'end': len(audio) / 1000.0}]
        
        # Merge chunks that are close together
        merged_chunks = []
        if not_silences:
            start_i, end_i = not_silences[0]
            for next_start, next_end in not_silences[1:]:
                if next_start < end_i + 500: # Merge if gap is less than 500ms
                    end_i = next_end
                else:
                    merged_chunks.append({'start': start_i / 1000.0, 'end': end_i / 1000.0})
                    start_i, end_i = next_start, next_end
            merged_chunks.append({'start': start_i / 1000.0, 'end': end_i / 1000.0})

        final_segments = [seg for seg in merged_chunks if (seg['end'] - seg['start']) > 5]
        if not final_segments:
            final_segments.append({'start': 0, 'end': min(30.0, len(audio) / 1000.0)})
        
        return final_segments
    except Exception as e:
        logger.error(f"Error during silence detection: {e}")
        return [{'start': 0, 'end': 15.0}]

async def run_ai_generation(prompt: str, user_id: int, model: str = "gpt-4o-mini", max_tokens: int = 2000, temperature: float = 0.5, expect_json: bool = False):
    """Run AI generation with the specified model"""
    if not client:
        return None
    
    try:
        response_format = {"type": "json_object"} if expect_json else {"type": "text"}
        response = await async_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
            response_format=response_format
        )
        result = response.choices[0].message.content
        
        if expect_json:
            try: json.loads(result)
            except json.JSONDecodeError: return None
        
        track_usage(model, user_id, "generation", input_tokens=len(prompt.split()), output_tokens=len(result.split()))
        return result
    except Exception as e:
        logger.error(f"AI generation error: {e}")
        return None

def analyze_content_chunks(text_chunks: list[str], user_id: int) -> list[int]:
    """Analyze text chunks and return indices of the most viral/engaging ones"""
    # This is now a synchronous wrapper around the async implementation
    return asyncio.run(analyze_content_chunks(text_chunks, user_id))

async def analyze_content_chunks(text_chunks: list[str], user_id: int) -> list[int]:
    """Asynchronously analyze text chunks and return indices of the most viral ones"""
    tasks = []
    for i, chunk in enumerate(text_chunks):
        if len(chunk.strip().split()) < 10:
            continue
        prompt = f"""Rate this content from 1-10 for viral potential. Consider hook, emotion, and shareability. Reply with ONLY a number. Content: "{chunk[:500]}..." """
        tasks.append(_get_chunk_score(prompt, user_id, i))
    
    scores = await asyncio.gather(*tasks)
    
    high_scoring_indices = [s['index'] for s in scores if s['score'] >= 7]
    if not high_scoring_indices:
        sorted_scores = sorted(scores, key=lambda x: x['score'], reverse=True)
        high_scoring_indices = [s['index'] for s in sorted_scores[:3]]
    
    return high_scoring_indices[:5]

def analyze_content_chunks_sync(text_chunks: list[str], user_id: int) -> list[int]:
    """Synchronous wrapper for the async content analysis function."""
    return asyncio.run(analyze_content_chunks(text_chunks, user_id))

def run_ai_generation_sync(prompt: str, user_id: int, model: str = "gpt-4o-mini", max_tokens: int = 2000, temperature: float = 0.5, expect_json: bool = False):
    """Synchronous wrapper for the async AI generation function."""
    return asyncio.run(run_ai_generation(prompt, user_id, model, max_tokens, temperature, expect_json))

async def _get_chunk_score(prompt, user_id, index):
    """Gets a score for a content chunk using the robust parsing logic."""
    response_str = await run_ai_generation(prompt, user_id, model="gpt-4o-mini", max_tokens=10, temperature=0.1)
    # --- START UPGRADE (from video_processor.py) ---
    score = _parse_score_from_response(response_str)
    # --- END UPGRADE ---
    return {"index": index, "score": score}
# =================== FIX END ===================

def local_ai_polish(content: str) -> str:
    """Placeholder for local AI polishing"""
    return content

async def _ingest_text_or_article_sync(content_input: str, user_id: int) -> dict:
    """Ingest text or article content"""
    try:
        if is_valid_url(content_input):
            content = scrape_url(content_input)
            if content.startswith("Error:"):
                return {"success": False, "error": content}
            return {"success": True, "content": content}
        else:
            return {"success": True, "content": content_input}
    except Exception as e:
        return {"success": False, "error": str(e)}
# --- SYNCHRONOUS WRAPPERS FOR CELERY TASKS ---

def run_ai_generation_sync(prompt: str, user_id: int, model: str = "gpt-4o-mini", max_tokens: int = 2000, temperature: float = 0.5, expect_json: bool = False):
    """Synchronous version of the AI generation function for Celery."""
    if not client:
        return None
    try:
        response_format = {"type": "json_object"} if expect_json else {"type": "text"}
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
            response_format=response_format
        )
        result = response.choices[0].message.content
        # (Usage tracking and validation logic can be added here if needed)
        return result
    except Exception as e:
        logger.error(f"Synchronous AI generation error: {e}")
        return None

def transcribe_local_audio_file_sync(audio_path: str, user_id: int, job_id: str):
    """Synchronous wrapper for the async transcription function."""
    return asyncio.run(transcribe_local_audio_file(audio_path, user_id, job_id))

def analyze_content_chunks_sync(text_chunks: list[str], user_id: int) -> list[int]:
    """Synchronous wrapper for the async content analysis function."""
    return asyncio.run(analyze_content_chunks(text_chunks, user_id))