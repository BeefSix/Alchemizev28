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
from pydub import AudioSegment
import uuid
import random

from app.db import crud
from app.db.base import get_db
from app.core.config import settings
from app.services.youtube_monitor import monitor

client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
STATIC_GENERATED_DIR = settings.STATIC_GENERATED_DIR
TEMP_DOWNLOAD_DIR = os.path.join(STATIC_GENERATED_DIR, "temp_downloads")
os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)


def _selenium_undetected_download(url, base_name, is_video):
    """Primary download method using undetected-chromedriver to bypass advanced bot detection."""
    try:
        import undetected_chromedriver as uc
    except ImportError:
        raise Exception("undetected-chromedriver is not installed.")

    options = uc.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = None
    try:
        driver = uc.Chrome(options=options)
        driver.get(url)
        time.sleep(random.uniform(4, 7)) # Allow page to fully load and run scripts
        
        cookies = driver.get_cookies()
        cookie_file = os.path.join(TEMP_DOWNLOAD_DIR, f"cookies_{base_name}.txt")
        with open(cookie_file, 'w') as f:
            for c in cookies:
                f.write(f"{c['domain']}\tTRUE\t{c['path']}\t{str(c['secure']).upper()}\t{int(c.get('expiry', 0)) or 0}\t{c['name']}\t{c['value']}\n")

        out_tmpl = os.path.join(TEMP_DOWNLOAD_DIR, f"{base_name}.%(ext)s")
        ydl_opts = {
            'outtmpl': out_tmpl, 'noplaylist': True, 'cookiefile': cookie_file,
            'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best' if is_video else 'bestaudio/best',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
        os.remove(cookie_file)
        return _find_downloaded_file(base_name, info, is_video)
    finally:
        if driver: driver.quit()

def _find_downloaded_file(base_name, info, is_video):
    expected_ext = '.mp4' if is_video else '.mp3'
    files = glob.glob(os.path.join(TEMP_DOWNLOAD_DIR, f"{base_name}.*"))
    if not files: raise FileNotFoundError(f"Download failed for {base_name}")
    actual_file = files[0]
    if not actual_file.endswith(expected_ext):
        new_path = os.path.splitext(actual_file)[0] + expected_ext
        os.rename(actual_file, new_path)
        actual_file = new_path
    return {'success': True, 'path': actual_file, 'duration': info.get('duration', 0)}

def download_media(url: str, is_video: bool):
    """Main download function that prioritizes the most robust method."""
    base_name = f"temp_{int(time.time())}_{uuid.uuid4().hex}"
    try:
        result = _selenium_undetected_download(url, base_name, is_video)
        if result.get('success'):
            monitor.log_attempt(url, "selenium_undetected", True)
            return result
    except Exception as e:
        monitor.log_attempt(url, "selenium_undetected", False, str(e))
        print(f"CRITICAL: Undetected Chromedriver failed: {e}")
    
    return {'success': False, 'error': 'All download methods failed.'}

# (The rest of the file is unchanged)
def is_valid_url(url: str): return url.startswith('http://') or url.startswith('https://')
def scrape_url(url: str):
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        for el in soup(["script", "style", "nav", "footer", "aside"]): el.decompose()
        return ' '.join(soup.stripped_strings)[:15000]
    except Exception: return "Error: Failed to scrape URL."
def cleanup_temp_files(patterns=None):
    if patterns is None: patterns = ['temp_*.*', 'cookies_*.txt']
    for pattern in patterns:
        for f_path in glob.glob(os.path.join(TEMP_DOWNLOAD_DIR, pattern)):
            try:
                if os.path.abspath(f_path).startswith(os.path.abspath(TEMP_DOWNLOAD_DIR)): os.remove(f_path)
            except OSError: pass
def validate_video_request(video_url: str):
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True, 'cookiefile': '/app/cookies.txt'}) as ydl:
            info = ydl.extract_info(video_url, download=False)
        if info.get('duration', 0) > 3600: return False, "Video is too long."
        return True, info
    except Exception as e: return False, f"Could not validate URL: {e}"
def generate_hash(text: str): return hashlib.sha256(text.encode('utf-8')).hexdigest()
def is_youtube_url(url: str): return any(re.search(p, url) for p in [r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'])
def transcribe_audio_robust(audio_file_path: str):
    if not client: return {"success": False, "error": "OpenAI client not initialized."}
    try:
        with open(audio_file_path, 'rb') as f:
            transcript = client.audio.transcriptions.create(model="whisper-1", file=f, response_format="verbose_json", timestamp_granularities=["word"])
        return {"success": True, "data": {"text": transcript.text, "words": [w.model_dump() for w in transcript.words]}}
    except Exception as e: return {"success": False, "error": f"Transcription failed: {e}"}
async def get_or_create_transcript(source_url: str, user_id: int, job_id: str):
    db = next(get_db())
    if cached := crud.get_cached_transcript(db, source_url):
        audio_info = download_media(source_url, is_video=False)
        if not audio_info.get('success'): return audio_info
        return {'success': True, 'data': cached, 'audio_file': audio_info.get('path')}
    audio_info = download_media(source_url, is_video=False)
    if not audio_info['success']: return audio_info
    audio_path = audio_info['path']
    audio = AudioSegment.from_mp3(audio_path)
    chunks = [audio[i:i + 900000] for i in range(0, len(audio), 900000)]
    all_words, full_text, total_cost = [], "", 0.0
    for i, chunk in enumerate(chunks):
        chunk_path = os.path.join(TEMP_DOWNLOAD_DIR, f"temp_chunk_{job_id}_{i}.mp3")
        chunk.export(chunk_path, format="mp3")
        result = transcribe_audio_robust(chunk_path)
        if result['success']:
            offset = i * 900
            for w in result['data']['words']: w['start'] += offset; w['end'] += offset; all_words.append(w)
            full_text += result['data']['text'] + " "
        total_cost += (len(chunk)/60000) * 0.006
        os.remove(chunk_path)
    if not full_text.strip(): return {'success': False, 'error': 'Empty transcript.'}
    final_transcript = {"text": full_text.strip(), "words": all_words}
    crud.set_cached_transcript(db, source_url, final_transcript)
    crud.track_usage(db, user_id, "whisper-1", "transcription", custom_cost=total_cost)
    return {'success': True, 'data': final_transcript, 'audio_file': audio_path}
def cut_video_clip(video_file, start_time, duration, output_name):
    try:
        subprocess.run(['ffmpeg', '-ss', str(start_time), '-i', video_file, '-t', str(duration), '-c', 'copy', '-y', output_name], check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError: return False
def get_background_music():
    music_file = "music/background.mp3"
    return music_file if os.path.exists(music_file) else None
def detect_silence_and_chunk(audio_path: str):
    try:
        cmd = ['ffmpeg', '-i', audio_path, '-af', 'silencedetect=noise=-30dB:d=1.0', '-f', 'null', '-']
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        timestamps = [float(re.search(r'silence_end: (\d+\.?\d*)', line).group(1)) for line in result.stderr.split('\n') if 'silence_end' in line]
        if not timestamps:
            duration = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]).strip())
            return [{'start': 0, 'end': duration}]
        segments, start_time = [], 0.0
        for end_time in timestamps:
            if (end_time - start_time) > 5: segments.append({'start': start_time, 'end': end_time})
            start_time = end_time
        duration = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]).strip())
        if (duration - start_time) > 5: segments.append({'start': start_time, 'end': duration})
        return segments if segments else [{'start': 0, 'end': 30.0}]
    except Exception: return [{'start': 0, 'end': 30.0}]
def check_usage_limits(user_id: int):
    db = next(get_db())
    if crud.get_user_videos_today(db, user_id) >= 5: return False, "Daily video limit reached."
    return True, ""
def run_ai_generation(prompt: str, user_id: int, model: str = "gpt-4o-mini", max_tokens: int = 2000, temperature: float = 0.5, expect_json: bool = False):
    if not client: return None
    db = next(get_db())
    request_hash = generate_hash(f"{prompt}{model}{max_tokens}{temperature}{expect_json}")
    cached = crud.get_cached_response(db, request_hash)
    if cached: return cached
    try:
        response = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": prompt}], max_tokens=max_tokens, temperature=temperature,
            response_format={"type": "json_object"} if expect_json else {"type": "text"}
        )
        result = response.choices[0].message.content
        usage = response.usage
        crud.track_usage(db, user_id, "generation", usage.prompt_tokens, usage.completion_tokens, model=model)
        crud.set_cached_response(db, request_hash, result)
        return result
    except Exception as e:
        print(f"Error during AI generation: {e}"); return None
def _parse_score_from_response(response_text: str):
    if not response_text: return 0
    if match := re.search(r'\d+', response_text): return int(match.group())
    words = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}
    for word, value in words.items():
        if word in response_text.lower(): return value
    return 0
async def _ingest_text_or_article_sync(user_input: str, user_id: int):
    if is_youtube_url(user_input):
        transcript_result = await get_or_create_transcript(user_input, user_id, "ingestion_job")
        return {'success': True, 'content': transcript_result['data']['text']} if transcript_result['success'] else transcript_result
    elif is_valid_url(user_input):
        content = scrape_url(user_input)
        return {'success': False, 'error': content} if content.startswith("Error:") else {'success': True, 'content': content}
    else:
        return {'success': True, 'content': user_input}
def local_ai_polish(content: str):
    return content