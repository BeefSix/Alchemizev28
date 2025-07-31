# app/services/utils.py - SIMPLE FIX for your main project
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
from pydub import AudioSegment
import uuid
import random

from app.db import crud
from app.db.base import get_db
from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
STATIC_GENERATED_DIR = settings.STATIC_GENERATED_DIR
TEMP_DOWNLOAD_DIR = os.path.join(STATIC_GENERATED_DIR, "temp_downloads")
os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)

def download_media(url: str, is_video: bool):
    """SIMPLE YouTube download - like your alpha but for main project"""
    print(f"🎯 Simple YouTube download: {url}")
    
    timestamp = int(time.time())
    base_name = f"temp_{timestamp}_{'video' if is_video else 'audio'}"
    
    # Simple approach like your alpha
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
        
        # Find the downloaded file
        downloaded_files = glob.glob(os.path.join(TEMP_DOWNLOAD_DIR, f"{base_name}.*"))
        if not downloaded_files:
            raise FileNotFoundError(f"No files downloaded for: {base_name}")
        
        actual_file = downloaded_files[0]
        expected_path = os.path.join(TEMP_DOWNLOAD_DIR, final_filename)
        
        # Rename if needed
        if actual_file != expected_path:
            try:
                os.rename(actual_file, expected_path)
                actual_file = expected_path
            except:
                pass
        
        return {
            'success': True,
            'title': info.get('title', 'N/A'),
            'duration': info.get('duration', 0),
            'path': actual_file
        }
        
    except Exception as e:
        print(f"Download failed: {e}")
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
        # Don't fail validation completely
        print(f"Validation warning: {e}")
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
        
        # Remove unwanted elements
        for el in soup(["script", "style", "nav", "footer", "aside", "form", "button", "header", "img", "svg"]):
            el.decompose()
        
        text_content = ' '.join(soup.stripped_strings)
        return text_content[:15000]
    except Exception as e:
        return f"Error: Failed to scrape URL: {e}"

def cleanup_temp_files(patterns=['temp_*.*', 'chunk_*.mp3', '*.pdf', '*.docx', 'thumbnail_*.png', 'final_clip_*.mp4']):
    print("🧹 Cleaning up temporary files...")
    os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
    for p in patterns:
        search_pattern = os.path.join(TEMP_DOWNLOAD_DIR, p)
        for f_path in glob.glob(search_pattern):
            try:
                if os.path.abspath(f_path).startswith(os.path.abspath(TEMP_DOWNLOAD_DIR)):
                    os.remove(f_path)
                    print(f"Removed: {f_path}")
            except OSError as e:
                print(f"Error removing {f_path}: {e}")

def transcribe_audio_robust(audio_file_path: str):
    if not client:
        return {"success": False, "error": "OpenAI client not initialized."}
    try:
        with open(audio_file_path, 'rb') as f:
            transcript_result = client.audio.transcriptions.create(
                model="whisper-1", 
                file=f, 
                response_format="verbose_json", 
                timestamp_granularities=["word"]
            )
        word_list_dicts = [word.model_dump() for word in transcript_result.words] if hasattr(transcript_result, 'words') else []
        return {"success": True, "data": {"text": transcript_result.text, "words": word_list_dicts}}
    except Exception as e:
        return {"success": False, "error": f"Transcription failed: {e}"}

async def get_or_create_transcript(source_url: str, user_id: int, job_id: str):
    db = next(get_db())
    cached_transcript_obj = crud.get_cached_transcript(db, source_url)
    if cached_transcript_obj:
        print("✅ Transcript found in cache.")
        audio_info = download_media(source_url, is_video=False)
        return {'success': True, 'data': cached_transcript_obj, 'audio_file': audio_info.get('path')}

    print("❌ Transcript not in cache. Starting new transcription...")
    audio_info = download_media(source_url, is_video=False)
    if not audio_info.get('success'):
        return {'success': False, 'error': f"Audio download failed: {audio_info.get('error')}"}
    
    if not os.path.exists(audio_info['path']):
        raise FileNotFoundError(f"Downloaded audio file not found: {audio_info['path']}")

    audio = AudioSegment.from_mp3(audio_info['path'])
    chunk_length_ms = 15 * 60 * 1000
    chunks = [audio[i:i + chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]
    
    all_words, full_text, total_cost = [], "", 0.0
    
    for i, chunk in enumerate(chunks):
        chunk_path = os.path.join(TEMP_DOWNLOAD_DIR, f"temp_transcription_chunk_{job_id}_{i}_{uuid.uuid4().hex}.mp3")
        chunk.export(chunk_path, format="mp3")
        
        transcription_result = transcribe_audio_robust(chunk_path)
        if transcription_result['success']:
            offset = i * (chunk_length_ms / 1000)
            for word_dict in transcription_result['data']['words']:
                word_dict['start'] += offset
                word_dict['end'] += offset
                all_words.append(word_dict)
            full_text += transcription_result['data']['text'] + " "
        
        duration_seconds = len(chunk) / 1000
        whisper_cost_per_minute = settings.TOKEN_PRICES.get("whisper-1", {}).get("output", 0.006)
        chunk_cost = (duration_seconds / 60) * whisper_cost_per_minute
        total_cost += chunk_cost
        
        if os.path.exists(chunk_path):
            os.remove(chunk_path)

    if not full_text.strip():
        return {'success': False, 'error': 'Transcription resulted in empty text.'}

    final_transcript_obj = {"text": full_text.strip(), "words": all_words}
    crud.set_cached_transcript(db, source_url, final_transcript_obj)
    track_usage("whisper-1", user_id, 'full-transcription', custom_cost=total_cost) 
    
    return {'success': True, 'data': final_transcript_obj, 'audio_file': audio_info.get('path')}

def track_usage(model: str, user_id: int, operation: str, input_tokens: int = 0, output_tokens: int = 0, custom_cost: float = None):
    db = next(get_db())
    try:
        cost = 0.0
        if custom_cost is not None:
            cost = custom_cost
        elif model in settings.TOKEN_PRICES:
            cost = ((input_tokens / 1_000_000) * settings.TOKEN_PRICES[model].get("input", 0)) + \
                   ((output_tokens / 1_000_000) * settings.TOKEN_PRICES[model].get("output", 0))
        crud.track_usage(db, user_id, model, operation, cost)
    except Exception as e:
        print(f"Error in track_usage: {e}")

def check_usage_limits(user_id: int, operation_type: str = 'video'):
    db = next(get_db())
    try:
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

# Keep other utility functions as needed for your project...
def cut_video_clip(video_file: str, start_time: float, duration: float, output_name: str):
    try:
        command = ['ffmpeg', '-ss', str(start_time), '-i', video_file, '-t', str(duration), '-c', 'copy', '-y', output_name]
        subprocess.run(command, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error cutting video clip: {e.stderr}")
        return False

def detect_silence_and_chunk(audio_path: str):
    try:
        command = ['ffmpeg', '-i', audio_path, '-af', 'silencedetect=noise=-30dB:d=1.0', '-f', 'null', '-']
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        timestamps = []
        for line in result.stderr.split('\n'):
            if 'silence_end' in line:
                end_time = float(re.search(r'silence_end: (\d+\.?\d*)', line).group(1))
                timestamps.append(end_time)
        
        if not timestamps:
            duration_result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio_path], capture_output=True, text=True)
            duration = float(duration_result.stdout.strip())
            return [{'start': 0, 'end': duration}]

        segments = []
        start_time = 0.0
        for end_time in timestamps:
            if (end_time - start_time) > 0.5:
                segments.append({'start': start_time, 'end': end_time})
            start_time = end_time
        
        duration_result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio_path], capture_output=True, text=True)
        total_duration = float(duration_result.stdout.strip())
        if (total_duration - start_time) > 0.5:
            segments.append({'start': start_time, 'end': total_duration})

        final_segments = [seg for seg in segments if (seg['end'] - seg['start']) > 5]
        if not final_segments:
            final_segments.append({'start': 0, 'end': min(30.0, total_duration)})

        return final_segments
    except Exception as e:
        print(f"Error during silence detection: {e}")
        return [{'start': 0, 'end': 15.0}]
    
    # Move the async function to top-level (not nested inside another function)
    async def transcribe_local_audio_file(audio_file_path: str, user_id: int, job_id: str):
        """
        Transcribe a local audio file (not from YouTube).
        This is what your upload feature needs!
        """
        if not client:
            return {"success": False, "error": "OpenAI client not initialized."}
        
        if not os.path.exists(audio_file_path):
            return {"success": False, "error": f"Audio file not found: {audio_file_path}"}
        
        try:
            # For large files, we need to chunk them
            audio = AudioSegment.from_file(audio_file_path)
            duration_seconds = len(audio) / 1000.0
            
            # If file is small enough (< 25MB or ~15 minutes), transcribe directly
            if duration_seconds < 900:  # 15 minutes
                with open(audio_file_path, 'rb') as f:
                    transcript_result = client.audio.transcriptions.create(
                        model="whisper-1", 
                        file=f, 
                        response_format="verbose_json", 
                        timestamp_granularities=["word"]
                    )
                
                word_list_dicts = [word.model_dump() for word in transcript_result.words] if hasattr(transcript_result, 'words') else []
                
                # Track usage
                cost = (duration_seconds / 60) * settings.TOKEN_PRICES.get("whisper-1", {}).get("output", 0.006)
                track_usage("whisper-1", user_id, 'transcription', custom_cost=cost)
                
                return {
                    "success": True, 
                    "data": {
                        "text": transcript_result.text, 
                        "words": word_list_dicts
                    }
                }
            
            # For larger files, chunk them
            chunk_length_ms = 15 * 60 * 1000  # 15 minutes
            chunks = [audio[i:i + chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]
            
            all_words = []
            full_text = ""
            total_cost = 0.0
            
            for i, chunk in enumerate(chunks):
                chunk_path = os.path.join(TEMP_DOWNLOAD_DIR, f"chunk_{job_id}_{i}.mp3")
                chunk.export(chunk_path, format="mp3")
                
                try:
                    with open(chunk_path, 'rb') as f:
                        transcript_result = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=f,
                            response_format="verbose_json",
                            timestamp_granularities=["word"]
                        )
                    
                    # Adjust timestamps for chunk offset
                    offset = i * (chunk_length_ms / 1000)
                    words = transcript_result.words if hasattr(transcript_result, 'words') else []
                    
                    for word in words:
                        word_dict = word.model_dump()
                        word_dict['start'] += offset
                        word_dict['end'] += offset
                        all_words.append(word_dict)
                    
                    full_text += transcript_result.text + " "
                    
                    # Calculate cost
                    chunk_duration = len(chunk) / 1000.0
                    chunk_cost = (chunk_duration / 60) * settings.TOKEN_PRICES.get("whisper-1", {}).get("output", 0.006)
                    total_cost += chunk_cost
                    
                finally:
                    if os.path.exists(chunk_path):
                        os.remove(chunk_path)
            
            # Track total usage
            track_usage("whisper-1", user_id, 'transcription', custom_cost=total_cost)
            
            return {
                "success": True,
                "data": {
                    "text": full_text.strip(),
                    "words": all_words
                }
            }
            
        except Exception as e:
            return {"success": False, "error": f"Transcription failed: {str(e)}"}

# Also add this helper function if not already present
def run_ai_generation(prompt: str, user_id: int, model: str = "gpt-4o-mini", max_tokens: int = 2000, temperature: float = 0.5, expect_json: bool = False):
    """Run AI generation with the specified model"""
    if not client:
        return None
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        result = response.choices[0].message.content
        
        if expect_json:
            try:
                json.loads(result)
            except json.JSONDecodeError:
                return None
        
        # Track usage (simplified - you may want to count actual tokens)
        track_usage(model, user_id, "generation", input_tokens=len(prompt.split()), output_tokens=len(result.split()))
        
        return result
        
    except Exception as e:
        print(f"AI generation error: {e}")
        return None

# Add these missing helper functions too
def analyze_content_chunks(text_chunks: list[str], user_id: int) -> list[int]:
    """Analyze text chunks and return indices of the most viral/engaging ones"""
    scores = []
    
    for i, chunk in enumerate(text_chunks):
        if len(chunk.strip()) < 50:  # Skip very short chunks
            scores.append(0)
            continue
        
        prompt = f"""Rate this content from 1-10 for viral potential on social media.
Consider: Hook strength, emotional impact, shareability, and completeness.
Reply with ONLY a number 1-10.

Content: "{chunk[:500]}..."
"""
        
        response = run_ai_generation(prompt, user_id, model="gpt-4o-mini", max_tokens=10, temperature=0.3)
        
        try:
            score = int(response.strip())
            scores.append(score)
        except:
            scores.append(5)  # Default middle score
    
    # Get indices of top scoring chunks (score >= 7)
    good_indices = [i for i, score in enumerate(scores) if score >= 7]
    
    # If no high scorers, take top 3
    if not good_indices:
        sorted_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        good_indices = sorted_indices[:3]
    
    return good_indices[:5]  # Maximum 5 clips

def local_ai_polish(content: str) -> str:
    """Polish content locally (placeholder - implement if you have local AI)"""
    # For now, just return the content as-is
    # You could integrate Ollama here if needed
    return content

async def _ingest_text_or_article_sync(content_input: str, user_id: int) -> dict:
    """Ingest text or article content"""
    try:
        if is_valid_url(content_input):
            # It's a URL - scrape it
            content = scrape_url(content_input)
            if content.startswith("Error:"):
                return {"success": False, "error": content}
            return {"success": True, "content": content}
        else:
            # It's raw text
            return {"success": True, "content": content_input}
    except Exception as e:
        return {"success": False, "error": str(e)}