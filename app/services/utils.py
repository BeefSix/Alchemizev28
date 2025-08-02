# app/services/utils.py
import os
import glob
import time
import yt_dlp
import subprocess
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import re
import hashlib
import json
from pydub import AudioSegment, silence
import uuid
import random
import logging
import asyncio

from app.db import crud
from app.db.base import get_db_session
from app.core.config import settings

# --- Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
STATIC_GENERATED_DIR = settings.STATIC_GENERATED_DIR
TEMP_DOWNLOAD_DIR = os.path.join(STATIC_GENERATED_DIR, "temp_downloads")
os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)

def _parse_score_from_response(response_text: str) -> int:
    """Extracts a score from the AI's response, handling digits and words."""
    if not response_text: return 0
    score_match = re.search(r'\d+', response_text)
    if score_match: return int(score_match.group())
    number_words = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}
    for word, value in number_words.items():
        if word in response_text.lower(): return value
    return 0

# --- Content Processing ---
def ingest_content(content_input: str) -> str:
    """Ingests content from text or a URL."""
    if is_valid_url(content_input):
        logger.info(f"Ingesting content from URL: {content_input}")
        return scrape_url(content_input)
    else:
        logger.info("Ingesting content from direct text input.")
        return content_input

def scrape_url(url: str):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        for el in soup(["script", "style", "nav", "footer", "aside", "form", "button", "header", "img", "svg"]):
            el.decompose()
        
        text_content = ' '.join(soup.stripped_strings)
        return text_content[:15000]
    except Exception as e:
        return f"Error: Failed to scrape URL: {e}"

# --- YouTube/Media Download ---
def download_media(url: str, is_video: bool):
    """Download YouTube media"""
    logger.info(f"🎯 Downloading: {url}")
    timestamp = int(time.time())
    base_name = f"temp_{timestamp}_{'video' if is_video else 'audio'}"
    
    ydl_opts = {
        'outtmpl': os.path.join(TEMP_DOWNLOAD_DIR, f"{base_name}.%(ext)s"),
        'cookiefile': '/app/cookies.txt',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
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

# --- Audio Processing ---
def transcribe_local_audio_file_sync(audio_path: str, user_id: int, job_id: str):
    """Transcribe audio file using OpenAI Whisper"""
    logger.info(f"Starting transcription for: {audio_path}")
    
    try:
        if not os.path.exists(audio_path):
            return {"success": False, "error": f"Audio file not found: {audio_path}"}

        # Update job status
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                progress_details={"description": "Transcribing audio...", "percentage": 30})

        # Transcribe with OpenAI
        with open(audio_path, 'rb') as f:
            transcript_result = client.audio.transcriptions.create(
                model="whisper-1", 
                file=f, 
                response_format="verbose_json", 
                timestamp_granularities=["word"]
            )
        
        # Track usage
        duration_seconds = AudioSegment.from_file(audio_path).duration_seconds
        estimated_cost = (duration_seconds / 60) * 0.006
        track_usage("whisper-1", user_id, 'transcription', custom_cost=estimated_cost)
        
        return {"success": True, "data": transcript_result.model_dump()}
        
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return {"success": False, "error": str(e)}

def detect_silence_and_chunk(audio_path: str):
    """Detect speech segments in audio"""
    try:
        audio = AudioSegment.from_file(audio_path)
        not_silences = silence.detect_nonsilent(audio, min_silence_len=700, silence_thresh=-35)

        if not not_silences:
            return [{'start': 0, 'end': len(audio) / 1000.0}]
        
        # Convert to seconds and merge close segments
        merged_chunks = []
        if not_silences:
            start_i, end_i = not_silences[0]
            for next_start, next_end in not_silences[1:]:
                if next_start < end_i + 500:  # Merge if gap < 500ms
                    end_i = next_end
                else:
                    merged_chunks.append({'start': start_i / 1000.0, 'end': end_i / 1000.0})
                    start_i, end_i = next_start, next_end
            merged_chunks.append({'start': start_i / 1000.0, 'end': end_i / 1000.0})

        # Filter out short segments
        final_segments = [seg for seg in merged_chunks if (seg['end'] - seg['start']) > 5]
        if not final_segments:
            final_segments.append({'start': 0, 'end': min(30.0, len(audio) / 1000.0)})
        
        return final_segments
    except Exception as e:
        logger.error(f"Error during silence detection: {e}")
        return [{'start': 0, 'end': 15.0}]

# --- AI Processing ---
def run_ai_generation_sync(prompt: str, user_id: int, model: str = "gpt-4o-mini", max_tokens: int = 2000, temperature: float = 0.5, expect_json: bool = False):
    """Generate AI response synchronously"""
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
        
        if expect_json:
            try: 
                json.loads(result)
            except json.JSONDecodeError: 
                return None
        
        # Track usage
        track_usage(model, user_id, "generation", 
                   input_tokens=len(prompt.split()), 
                   output_tokens=len(result.split()))
        return result
    except Exception as e:
        logger.error(f"AI generation error: {e}")
        return None

def analyze_content_chunks_sync(text_chunks: list[str], user_id: int) -> list[int]:
    """Analyze text chunks for viral potential"""
    scores = []
    
    for i, chunk in enumerate(text_chunks):
        if len(chunk.strip().split()) < 10:
            continue
            
        prompt = f"Rate this content from 1-10 for viral potential. Reply with ONLY a number. Content: {chunk[:500]}"
        response_str = run_ai_generation_sync(prompt, user_id, model="gpt-4o-mini", max_tokens=10, temperature=0.1)
        score = _parse_score_from_response(response_str)
        scores.append({"index": i, "score": score})
    
    # Return indices of high-scoring chunks
    high_scoring_indices = [s['index'] for s in scores if s['score'] >= 7]
    if not high_scoring_indices:
        sorted_scores = sorted(scores, key=lambda x: x['score'], reverse=True)
        high_scoring_indices = [s['index'] for s in sorted_scores[:3]]
    
    return high_scoring_indices[:5]

# --- Video Processing ---
def get_video_moments(transcript_data, duration_limit=60):
    """Extract interesting moments from transcript data"""
    moments = []

    if not transcript_data or not transcript_data.get('words'):
        return [{'start': 0, 'duration': min(30, duration_limit)}]

    words = transcript_data['words']
    chunk_size = 20

    for i in range(0, len(words), chunk_size):
        chunk_words = words[i:i + chunk_size]
        if chunk_words:
            start_time = chunk_words[0].get('start', 0)
            end_time = chunk_words[-1].get('end', start_time + 15)
            duration = min(end_time - start_time, duration_limit)

            moments.append({
                'start': start_time,
                'duration': duration
            })

    return moments[:5]

def cut_video_clip(video_file: str, start_time: float, duration: float, output_name: str):
    """Cut a video clip using FFmpeg"""
    try:
        command = ['ffmpeg', '-ss', str(start_time), '-i', video_file, '-t', str(duration), '-c', 'copy', '-y', output_name]
        subprocess.run(command, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error cutting video clip: {e.stderr}")
        return False

# --- Usage Tracking ---
def track_usage(model: str, user_id: int, operation: str, input_tokens: int = 0, output_tokens: int = 0, custom_cost: float = None):
    """Track API usage with proper database handling"""
    try:
        with get_db_session() as db:
            cost = 0.0
            if custom_cost is not None:
                cost = custom_cost
            elif model in settings.TOKEN_PRICES:
                cost = ((input_tokens / 1_000_000) * settings.TOKEN_PRICES[model].get("input", 0)) + \
                       ((output_tokens / 1_000_000) * settings.TOKEN_PRICES[model].get("output", 0))
            
            crud.track_usage(db, user_id, model, operation, cost)
    except Exception as e:
        logger.error(f"Error in track_usage: {e}")

def check_usage_limits(user_id: int, operation_type: str = 'video'):
    """Check if user has exceeded usage limits"""
    try:
        with get_db_session() as db:
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
        logger.error(f"Error checking usage limits: {e}")
        return True, ""

# --- Utility Functions ---
def is_valid_url(url: str):
    return url.startswith('http://') or url.startswith('https://')

def is_youtube_url(url: str):
    patterns = [
        r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/',
        r'(https?://)?(www\.)?youtu\.be/'
    ]
    return any(re.search(p, url) for p in patterns)

def validate_video_request(video_url: str):
    """Validate video URL and duration"""
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

def generate_hash(text: str):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def cleanup_temp_files(patterns=['temp_*.*', 'chunk_*.mp3', '*.pdf', '*.docx', 'thumbnail_*.png', 'final_clip_*.mp4']):
    """Clean up temporary files"""
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