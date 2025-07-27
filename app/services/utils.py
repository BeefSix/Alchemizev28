# app/services/utils.py
import os
import glob
import time
import yt_dlp
import subprocess
import requests
from bs4 import BeautifulSoup
from openai import OpenAI, APIError, APITimeoutError
from dotenv import load_dotenv
import re
import hashlib
import json
from datetime import datetime, date
from pydub import AudioSegment
import uuid

# Changed to import from the new crud and base for SQLAlchemy
from app.db import crud
from app.db.base import get_db

# Assuming app.core.config contains these settings now
from app.core.config import settings

# --- API Clients & Configuration ---
OPENAI_API_KEY = settings.OPENAI_API_KEY
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

OWNER_DISCORD_ID = os.getenv('OWNER_DISCORD_ID', '')

try:
    import ollama as ollama_pkg
    OLLAMA_AVAILABLE = True
except ImportError:
    ollama_pkg = None
    OLLAMA_AVAILABLE = False


# Define static directories (matching main.py and settings.py)
STATIC_FILES_ROOT_DIR = settings.STATIC_FILES_ROOT_DIR
STATIC_GENERATED_DIR = settings.STATIC_GENERATED_DIR
TEMP_DOWNLOAD_DIR = os.path.join(STATIC_GENERATED_DIR, "temp_downloads")
os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)


# --- Core Helper Functions (Ordered for correct dependency) ---

def generate_hash(text: str):
    """Generates a SHA256 hash for caching."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def is_youtube_url(url: str):
    """Checks if a URL is a YouTube URL."""
    patterns = [r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/', r'(https?://)?(www\.)?youtu\.be/']
    return any(re.search(p, url) for p in patterns)

def is_valid_url(url: str):
    """Checks if a string is a valid HTTP/HTTPS URL."""
    return url.startswith('http://') or url.startswith('https://')

def scrape_url(url: str):
    """Scrapes text content from a given URL."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        for el in soup(["script", "style", "nav", "footer", "aside", "form", "button", "header", "img", "svg"]):
            el.decompose()
        text_content = ' '.join(soup.stripped_strings)
        return text_content[:15000] # Truncate to a reasonable size for LLM input
    except requests.RequestException as e:
        return f"Error: Failed to scrape URL: {e}"
    except Exception as e:
        return f"Error during scraping: {e}"

def track_usage(model: str, user_id: int, operation: str, input_tokens: int = 0, output_tokens: int = 0, custom_cost: float = None):
    """Tracks API usage costs."""
    db = next(get_db())
    try:
        cost = 0.0
        if custom_cost is not None:
            cost = custom_cost
        elif model in settings.TOKEN_PRICES and isinstance(settings.TOKEN_PRICES[model], dict):
             if model == "whisper-1" and operation == "full-transcription":
                 pass
             else:
                 cost = ((input_tokens / 1_000_000) * settings.TOKEN_PRICES[model].get("input", 0)) + \
                        ((output_tokens / 1_000_000) * settings.TOKEN_PRICES[model].get("output", 0))
        
        if cost < 0:
            cost = 0.0
            
        crud.track_usage(db, user_id, model, operation, cost)
    except Exception as e:
        print(f"Error in track_usage: {e}")

# ADDED: Ingestion function (from old content_processor.py)
async def _ingest_text_or_article_sync(user_input: str, user_id: int):
    """Handles ingestion of text, YouTube URLs, or other article URLs."""
    if is_youtube_url(user_input):
        print("YouTube URL detected. Getting transcript...")
        # get_or_create_transcript is async, so await it
        transcript_result = await get_or_create_transcript(user_input, user_id, "ingestion_job_id") # Pass a dummy job_id or generate one
        if transcript_result['success']:
            return {'success': True, 'content': transcript_result['data']['text']}
        else:
            return {'success': False, 'error': f"Failed to get transcript: {transcript_result['error']}"}
    elif is_valid_url(user_input):
        print("Article URL detected. Scraping content...")
        content = scrape_url(user_input)
        if content.startswith("Error:"):
            return {'success': False, 'error': content}
        return {'success': True, 'content': content}
    else:
        # It's raw text
        return {'success': True, 'content': user_input}


# --- AI Generation Function (Moved from content_processor.py) ---
def run_ai_generation(prompt: str, user_id: int, model: str = "gpt-4o-mini", max_tokens: int = 2000, temperature: float = 0.5, expect_json: bool = False):
    """
    Handles calling OpenAI API (or other LLMs) for content generation.
    Includes caching and usage tracking.
    """
    if not client: 
        print("Error: OpenAI client not initialized. OPENAI_API_KEY may be missing.")
        return None
    
    db = next(get_db())
    request_hash = generate_hash(f"{prompt}{model}{max_tokens}{temperature}{expect_json}")
    cached_response = crud.get_cached_response(db, request_hash)
    if cached_response:
        print(f"✅ Cache hit for model {model}.")
        return cached_response
    
    print(f"❌ Cache miss. Calling OpenAI API for model {model}...")
    try:
        response = client.chat.completions.create(
            model=model, 
            messages=[{"role": "user", "content": prompt}], 
            max_tokens=max_tokens, 
            temperature=temperature,
            response_format={"type": "json_object"} if expect_json else {"type": "text"}
        )
        result_text = response.choices[0].message.content
        usage = response.usage
        
        track_usage(model, user_id, 'generation', usage.prompt_tokens, usage.completion_tokens)

        if expect_json:
            try:
                json.loads(result_text)
                crud.set_cached_response(db, request_hash, result_text)
            except json.JSONDecodeError:
                print("⚠️ AI returned invalid JSON. Will not cache this response.")
        else:
            crud.set_cached_response(db, request_hash, result_text)
        
        return result_text
    except (APIError, APITimeoutError) as e:
        print(f"Error: AI generation failed (OpenAI API error): {e}")
        return None
    except Exception as e:
        print(f"Error: AI generation failed (General error): {e}")
        return None

def _parse_score_from_response(response_text: str) -> int:
    """
    A robust function to extract a score from the AI's response for viral moment detection.
    It can handle both digits ('7') and words ('seven').
    """
    if not response_text:
        return 0
    
    score_match = re.search(r'\d+', response_text)
    if score_match:
        return int(score_match.group())

    number_words = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
    }
    for word, value in number_words.items():
        if word in response_text.lower():
            return value
            
    return 0


# --- Local AI Polish Function ---
def local_ai_polish(content: str):
    if not OLLAMA_AVAILABLE: 
        print("Ollama not available for local AI polish.")
        return content
    prompt = f"Polish the following social media posts.\n\n{content}"
    try:
        response = ollama_pkg.generate(model='llama3:latest', prompt=prompt, stream=False)
        return response['response']
    except Exception as e:
        print(f"Local AI polish failed: {e}")
        return content


# --- Media Processing & Transcription Helpers ---
def cleanup_temp_files(patterns=['temp_*.*', 'chunk_*.mp3', '*.pdf', '*.docx', 'thumbnail_*.png', 'final_clip_*.mp4']):
    """Cleans up temporary files from the static/generated/temp_downloads directory."""
    print("🧹 Cleaning up temporary files...")
    
    os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
    
    for p in patterns:
        search_pattern = os.path.join(TEMP_DOWNLOAD_DIR, p)
        for f_path in glob.glob(search_pattern):
            try:
                if os.path.abspath(f_path).startswith(os.path.abspath(TEMP_DOWNLOAD_DIR)):
                    os.remove(f_path)
                    print(f"Removed temp file: {f_path}")
                else:
                    print(f"Skipping potentially unsafe file deletion: {f_path}")
            except OSError as e:
                print(f"Error removing file {f_path}: {e}")
    
    if os.path.exists(TEMP_DOWNLOAD_DIR) and not os.listdir(TEMP_DOWNLOAD_DIR):
        try:
            os.rmdir(TEMP_DOWNLOAD_DIR)
            print(f"Removed empty temp directory: {TEMP_DOWNLOAD_DIR}")
        except OSError as e:
            print(f"Error removing empty directory {TEMP_DOWNLOAD_DIR}: {e}")


def download_media(url: str, is_video: bool):
    timestamp = int(time.time())
    
    os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)

    base_name = f"temp_{timestamp}_{uuid.uuid4().hex}_{'video' if is_video else 'audio'}"
    out_tmpl = os.path.join(TEMP_DOWNLOAD_DIR, f"{base_name}.%(ext)s")
    
    if is_video:
        ydl_opts = {
            'format': 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]',
            'outtmpl': out_tmpl,
            'noplaylist': True,
            'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}]
        }
    else:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': out_tmpl,
            'noplaylist': True,
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]
        }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
        
        downloaded_files = glob.glob(os.path.join(TEMP_DOWNLOAD_DIR, f"{base_name}.*"))
        
        if not downloaded_files:
            raise FileNotFoundError(f"yt-dlp download failed, no file found for base name: {base_name}")
        
        actual_file_path = downloaded_files[0]
        
        expected_ext = '.mp4' if is_video else '.mp3'
        if not actual_file_path.endswith(expected_ext):
            renamed_path = os.path.splitext(actual_file_path)[0] + expected_ext
            try:
                os.rename(actual_file_path, renamed_path)
                actual_file_path = renamed_path
            except OSError as e:
                print(f"Warning: Could not rename {actual_file_path} to {renamed_path}: {e}")
        
        return {'success': True, 'title': info.get('title', 'N/A'), 'duration': info.get('duration', 0), 'path': actual_file_path}
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return {'success': False, 'error': str(e)}


def transcribe_audio_robust(audio_file_path: str):
    if not client: return {"success": False, "error": "OpenAI client not initialized."}
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
    except (APIError, APITimeoutError) as e:
        print(f"Transcription failed (OpenAI API error): {e}")
        return {"success": False, "error": f"Transcription failed (OpenAI API error): {e}"}
    except Exception as e:
        print(f"Transcription failed (general error): {e}")
        return {"success": False, "error": f"Transcription failed (general error): {e}"}


async def get_or_create_transcript(source_url: str, user_id: int, job_id: str):
    db = next(get_db())
    
    cached_transcript_obj = crud.get_cached_transcript(db, source_url)
    if cached_transcript_obj:
        print("✅ Transcript found in cache.")
        audio_info = download_media(source_url, is_video=False)
        return {'success': True, 'data': cached_transcript_obj, 'audio_file': audio_info.get('path')}

    print("❌ Transcript not in cache. Starting new transcription job...")
    audio_info = download_media(source_url, is_video=False)
    if not audio_info.get('success'):
        return {'success': False, 'error': f"Audio download failed: {audio_info.get('error')}"}
    
    if not os.path.exists(audio_info['path']):
        raise FileNotFoundError(f"Downloaded audio file not found: {audio_info['path']}")

    audio = AudioSegment.from_mp3(audio_info['path'])
    chunk_length_ms = 15 * 60 * 1000 # 15 minutes in milliseconds
    chunks = [audio[i:i + chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]
    
    all_words = []
    full_text = ""
    total_cost = 0.0
    
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
        else:
            print(f"Warning: Transcription of chunk {i} failed: {transcription_result['error']}")
        
        duration_seconds = len(chunk) / 1000
        whisper_cost_per_minute = settings.TOKEN_PRICES.get("whisper-1", {}).get("output", 0.006)
        chunk_cost = (duration_seconds / 60) * whisper_cost_per_minute
        total_cost += chunk_cost
        
        if os.path.exists(chunk_path):
            os.remove(chunk_path)

    if not full_text.strip():
        if os.path.exists(audio_info['path']):
            os.remove(audio_info['path'])
        return {'success': False, 'error': 'Transcription resulted in empty text.'}

    final_transcript_obj = {"text": full_text.strip(), "words": all_words}

    crud.set_cached_transcript(db, source_url, final_transcript_obj)
    track_usage("whisper-1", user_id, 'full-transcription', custom_cost=total_cost) 
    print("✅ New transcript generated and saved to cache.")
    
    return {'success': True, 'data': final_transcript_obj, 'audio_file': audio_info.get('path')}


def cut_video_clip(video_file: str, start_time: float, duration: float, output_name: str):
    try:
        command = [
            'ffmpeg', '-ss', str(start_time), '-i', video_file, 
            '-t', str(duration), '-c', 'copy', '-y', output_name
        ]
        print(f"Executing cut command: {' '.join(command)}")
        subprocess.run(command, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error cutting video clip: {e.stderr}")
        return False

def validate_video_request(video_url: str):
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            duration = info.get('duration', 0)
            if duration > settings.DAILY_LIMITS.get('max_video_duration', 3600):
                return False, f"Video is too long ({duration//60} min)."
            return True, info
    except Exception as e:
        return False, f"Could not validate URL. Error: {e}"

def get_background_music():
    music_file = "music/background.mp3"
    if os.path.exists(music_file):
        return music_file
    else:
        print(f"Warning: Background music file not found at '{music_file}'. Music will not be added.")
        return None

def detect_silence_and_chunk(audio_path: str):
    print("🤫 Detecting silence to create smart chunks...")
    try:
        command = ['ffmpeg', '-i', audio_path, '-af', 'silencedetect=noise=-30dB:d=1.0', '-f', 'null', '-']
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        lines = result.stderr.split('\n')
        timestamps = []
        for line in lines:
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
            print("Warning: No viable speech segments found. Falling back to first 30 seconds.")
            final_segments.append({'start': 0, 'end': min(30.0, total_duration)})


        print(f"✅ Found {len(final_segments)} speech segments.")
        return final_segments
    except Exception as e:
        print(f"Error during silence detection: {e}")
        try:
            duration_result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio_path], capture_output=True, text=True)
            total_duration = float(duration_result.stdout.strip())
            return [{'start': 0, 'end': min(30.0, total_duration)}]
        except:
            return [{'start': 0, 'end': 15.0}]