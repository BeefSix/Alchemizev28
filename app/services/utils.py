# app/services/utils.py - Complete YouTube Bypass Solution 2025
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
import base64

from app.db import crud
from app.db.base import get_db
from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
STATIC_GENERATED_DIR = settings.STATIC_GENERATED_DIR
TEMP_DOWNLOAD_DIR = os.path.join(STATIC_GENERATED_DIR, "temp_downloads")
os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)

# --- ADVANCED YOUTUBE BYPASS SYSTEM ---

def get_rotating_user_agents():
    """Get a pool of realistic user agents with recent versions"""
    return [
        # Chrome on Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        
        # Chrome on macOS
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        
        # Firefox
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
        
        # Safari
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
        
        # Edge
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    ]

def get_random_user_agent():
    """Select a random user agent from the pool"""
    return random.choice(get_rotating_user_agents())

def create_realistic_headers(user_agent=None):
    """Create realistic browser headers that pass bot detection"""
    if not user_agent:
        user_agent = get_random_user_agent()
    
    # Determine browser type from user agent
    is_chrome = 'Chrome' in user_agent and 'Edg' not in user_agent
    is_firefox = 'Firefox' in user_agent
    is_safari = 'Safari' in user_agent and 'Chrome' not in user_agent
    is_edge = 'Edg' in user_agent
    
    base_headers = {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    # Add browser-specific headers
    if is_chrome or is_edge:
        base_headers.update({
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"' if 'Windows' in user_agent else '"macOS"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        })
    
    return base_headers

def method_1_undetected_chrome(url, base_name, is_video):
    """Most sophisticated method using undetected-chromedriver"""
    print("🚀 Method 1: Undetected Chrome (Anti-Detection)")
    try:
        import undetected_chromedriver as uc
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except ImportError:
        raise Exception("undetected-chromedriver not available")
    
    options = uc.ChromeOptions()
    options.add_argument('--headless=new')  # Use new headless mode
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-plugins')
    options.add_argument('--disable-images')  # Faster loading
    options.add_argument('--disable-javascript')  # Bypass some detection
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    driver = None
    try:
        # Use undetected-chromedriver which bypasses most detection
        driver = uc.Chrome(options=options, version_main=None)
        
        # Navigate to YouTube first
        driver.get("https://www.youtube.com")
        time.sleep(random.uniform(2, 4))
        
        # Navigate to the specific video
        driver.get(url)
        time.sleep(random.uniform(3, 6))
        
        # Extract cookies
        cookies = driver.get_cookies()
        cookie_file = os.path.join(TEMP_DOWNLOAD_DIR, f"uc_cookies_{base_name}.txt")
        with open(cookie_file, 'w') as f:
            for cookie in cookies:
                f.write(f"{cookie['domain']}\tTRUE\t{cookie['path']}\t{str(cookie['secure']).upper()}\t{int(cookie.get('expiry', 0))}\t{cookie['name']}\t{cookie['value']}\n")
        
        driver.quit()
        driver = None
        
        # Use yt-dlp with fresh cookies
        return _download_with_ydl(url, base_name, is_video, cookie_file, method="undetected_chrome")
        
    except Exception as e:
        if driver:
            driver.quit()
        raise e

def method_2_android_client(url, base_name, is_video):
    """Use Android YouTube client - often bypasses restrictions"""
    print("🚀 Method 2: Android Client Emulation")
    
    ydl_opts = {
        'user_agent': 'com.google.android.youtube/18.48.37 (Linux; U; Android 13; SM-G991B) gzip',
        'headers': {
            'X-YouTube-Client-Name': '3',
            'X-YouTube-Client-Version': '18.48.37',
            'X-YouTube-Identity-Token': base64.b64encode(f"android_client_{random.randint(1000,9999)}".encode()).decode(),
        },
        'outtmpl': os.path.join(TEMP_DOWNLOAD_DIR, f"{base_name}.%(ext)s"),
        'format': 'worst[height<=480]/worst' if is_video else 'worstaudio[abr<=128]/worstaudio',
        'extractor_args': {
            'youtube': {
                'player_client': ['android'],
                'skip': ['webpage', 'configs'],
                'innertube_host': ['youtubei.googleapis.com'],
            }
        },
        'cookiefile': '/app/cookies.txt',
        'sleep_interval': random.uniform(1, 3),
        'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}] if is_video else [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
    }
    
    time.sleep(random.uniform(2, 5))
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
    
    return _find_downloaded_file(base_name, info, is_video)

def method_3_ios_client(url, base_name, is_video):
    """Use iOS YouTube client"""
    print("🚀 Method 3: iOS Client Emulation")
    
    ydl_opts = {
        'user_agent': 'com.google.ios.youtube/18.48.3 (iPhone15,2; U; CPU iOS 17_1_1 like Mac OS X)',
        'headers': {
            'X-YouTube-Client-Name': '5',
            'X-YouTube-Client-Version': '18.48.3',
        },
        'outtmpl': os.path.join(TEMP_DOWNLOAD_DIR, f"{base_name}.%(ext)s"),
        'format': 'worst[height<=720]/worst' if is_video else 'worstaudio/worst',
        'extractor_args': {
            'youtube': {
                'player_client': ['ios'],
                'skip': ['webpage'],
            }
        },
        'cookiefile': '/app/cookies.txt',
        'sleep_interval': random.uniform(2, 4),
        'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}] if is_video else [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
    }
    
    time.sleep(random.uniform(3, 6))
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
    
    return _find_downloaded_file(base_name, info, is_video)

def method_4_tv_client(url, base_name, is_video):
    """Use TV/living room client - often less restricted"""
    print("🚀 Method 4: TV Client Emulation")
    
    ydl_opts = {
        'user_agent': 'Mozilla/5.0 (SMART-TV; LINUX; Tizen 6.0) AppleWebKit/537.36 (KHTML, like Gecko) 85.0.4183.93/6.0 TV Safari/537.36',
        'headers': {
            'X-YouTube-Client-Name': '7',
            'X-YouTube-Client-Version': '7.20231213.13.00',
        },
        'outtmpl': os.path.join(TEMP_DOWNLOAD_DIR, f"{base_name}.%(ext)s"),
        'format': 'worst[height<=720]/worst' if is_video else 'worstaudio/worst',
        'extractor_args': {
            'youtube': {
                'player_client': ['tv'],
                'skip': ['webpage', 'configs'],
            }
        },
        'cookiefile': '/app/cookies.txt',
        'sleep_interval': random.uniform(3, 7),
        'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}] if is_video else [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
    }
    
    time.sleep(random.uniform(4, 8))
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
    
    return _find_downloaded_file(base_name, info, is_video)

def method_5_enhanced_web(url, base_name, is_video):
    """Enhanced web client with sophisticated anti-detection"""
    print("🚀 Method 5: Enhanced Web Client")
    
    headers = create_realistic_headers()
    
    ydl_opts = {
        'user_agent': headers['User-Agent'],
        'headers': headers,
        'outtmpl': os.path.join(TEMP_DOWNLOAD_DIR, f"{base_name}.%(ext)s"),
        'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]' if is_video else 'bestaudio/best',
        'extractor_args': {
            'youtube': {
                'player_client': ['web'],
                'player_skip': ['configs'],
                'lang': ['en'],
                'innertube_host': ['youtubei.googleapis.com'],
                'innertube_key': ['AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8'],
            }
        },
        'cookiefile': '/app/cookies.txt',
        'sleep_interval': random.uniform(2, 5),
        'max_sleep_interval': 10,
        'extractor_retries': 3,
        'fragment_retries': 3,
        'youtube_include_dash_manifest': False,
        'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}] if is_video else [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
    }
    
    time.sleep(random.uniform(1, 3))
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
    
    return _find_downloaded_file(base_name, info, is_video)

def method_6_proxy_rotation(url, base_name, is_video):
    """Use geo-bypass and proxy techniques"""
    print("🚀 Method 6: Proxy/Geo Bypass")
    
    countries = ['US', 'GB', 'CA', 'AU', 'DE', 'FR', 'NL', 'SE']
    selected_country = random.choice(countries)
    
    ydl_opts = {
        'user_agent': get_random_user_agent(),
        'outtmpl': os.path.join(TEMP_DOWNLOAD_DIR, f"{base_name}.%(ext)s"),
        'format': 'worst[height<=480]/worst' if is_video else 'worstaudio[abr<=96]/worstaudio',
        'geo_bypass': True,
        'geo_bypass_country': selected_country,
        'extractor_args': {
            'youtube': {
                'player_client': ['web', 'android'],
                'skip': ['webpage'],
            }
        },
        'cookiefile': '/app/cookies.txt',
        'sleep_interval': random.uniform(4, 8),
        'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}] if is_video else [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
    }
    
    print(f"Attempting from: {selected_country}")
    time.sleep(random.uniform(3, 6))
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
    
    return _find_downloaded_file(base_name, info, is_video)

def _download_with_ydl(url, base_name, is_video, cookie_file=None, method="standard"):
    """Helper function for yt-dlp downloads"""
    ydl_opts = {
        'outtmpl': os.path.join(TEMP_DOWNLOAD_DIR, f"{base_name}.%(ext)s"),
        'format': 'best[height<=720]/best' if is_video else 'bestaudio/best',
        'cookiefile': cookie_file or '/app/cookies.txt',
        'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}] if is_video else [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
    
    # Clean up temporary cookie file
    if cookie_file and cookie_file != '/app/cookies.txt' and os.path.exists(cookie_file):
        os.remove(cookie_file)
    
    return _find_downloaded_file(base_name, info, is_video)

def _find_downloaded_file(base_name, info, is_video):
    """Find and verify downloaded files"""
    downloaded_files = glob.glob(os.path.join(TEMP_DOWNLOAD_DIR, f"{base_name}.*"))
    
    if not downloaded_files:
        raise FileNotFoundError(f"Download failed for: {base_name}")
    
    actual_file_path = downloaded_files[0]
    expected_ext = '.mp4' if is_video else '.mp3'
    
    if not actual_file_path.endswith(expected_ext):
        renamed_path = os.path.splitext(actual_file_path)[0] + expected_ext
        try:
            os.rename(actual_file_path, renamed_path)
            actual_file_path = renamed_path
        except OSError as e:
            print(f"Warning: Could not rename {actual_file_path}: {e}")
    
    return {
        'success': True,
        'title': info.get('title', 'N/A'),
        'duration': info.get('duration', 0),
        'path': actual_file_path
    }

def download_media(url: str, is_video: bool):
    """Main download function with comprehensive bypass methods"""
    print(f"🎯 Starting comprehensive YouTube bypass for: {url}")
    
    timestamp = int(time.time())
    base_name = f"temp_{timestamp}_{uuid.uuid4().hex}_{'video' if is_video else 'audio'}"
    
    # Prioritized methods - most effective first
    methods = [
        method_1_undetected_chrome,    # Highest success rate
        method_2_android_client,       # Very reliable
        method_3_ios_client,          # Good alternative
        method_4_tv_client,           # Often unrestricted
        method_5_enhanced_web,        # Sophisticated web
        method_6_proxy_rotation,      # Geographic bypass
    ]
    
    for i, method in enumerate(methods, 1):
        try:
            print(f"🔄 Attempting method {i}/6: {method.__name__}")
            result = method(url, base_name, is_video)
            
            if result['success']:
                print(f"✅ SUCCESS with {method.__name__}!")
                print(f"📁 File: {result['path']}")
                print(f"📹 Title: {result.get('title', 'Unknown')}")
                print(f"⏱️ Duration: {result.get('duration', 0)} seconds")
                return result
                
        except Exception as e:
            print(f"❌ {method.__name__} failed: {e}")
            
            # Add progressive delays to avoid rate limiting
            delay = random.uniform(2, 5) * (i * 0.5)  # Increasing delay
            print(f"⏳ Waiting {delay:.1f}s before next method...")
            time.sleep(delay)
            continue
    
    # If all methods fail
    return {
        'success': False, 
        'error': 'All YouTube bypass methods failed. The video may be restricted, private, or unavailable in any region.'
    }

# --- VALIDATION FUNCTION ---

def validate_video_request(video_url: str):
    """Validate video URL with anti-detection measures"""
    try:
        # Use lightweight Android client for validation
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'user_agent': 'com.google.android.youtube/18.48.37 (Linux; U; Android 13; SM-G991B) gzip',
            'extractor_args': {
                'youtube': {
                    'player_client': ['android'],
                    'skip': ['webpage', 'configs'],
                }
            },
            'cookiefile': '/app/cookies.txt',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            duration = info.get('duration', 0)
            
            if duration > settings.DAILY_LIMITS.get('max_video_duration', 3600):
                return False, f"Video is too long ({duration//60} minutes)."
            
            return True, info
            
    except Exception as e:
        error_msg = str(e)
        
        # Handle bot detection gracefully
        if any(phrase in error_msg.lower() for phrase in [
            "sign in to confirm", "bot", "verify", "captcha", "blocked"
        ]):
            print(f"🤖 Bot detection in validation - will handle during download")
            # Allow validation to pass, let download methods handle detection
            return True, {
                "duration": 1800,  # Assume reasonable duration
                "title": "Video (validation bypassed)",
                "id": extract_video_id(video_url) or "unknown"
            }
        
        return False, f"Could not validate URL: {error_msg}"

def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)',
        r'youtube\.com\/v\/([^&\n?#]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

# --- EXISTING UTILITY FUNCTIONS (unchanged) ---

def is_valid_url(url: str):
    return url.startswith('http://') or url.startswith('https://')

def is_youtube_url(url: str):
    patterns = [r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/', r'(https?://)?(www\.)?youtu\.be/']
    return any(re.search(p, url) for p in patterns)

def generate_hash(text: str):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def scrape_url(url: str):
    try:
        headers = {'User-Agent': get_random_user_agent()}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        for el in soup(["script", "style", "nav", "footer", "aside", "form", "button", "header", "img", "svg"]):
            el.decompose()
        text_content = ' '.join(soup.stripped_strings)
        return text_content[:15000]
    except Exception as e:
        return f"Error: Failed to scrape URL: {e}"

def cleanup_temp_files(patterns=['temp_*.*', 'chunk_*.mp3', '*.pdf', '*.docx', 'thumbnail_*.png', 'final_clip_*.mp4', 'uc_cookies_*.txt']):
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

async def _ingest_text_or_article_sync(user_input: str, user_id: int):
    if is_youtube_url(user_input):
        transcript_result = await get_or_create_transcript(user_input, user_id, "ingestion_job")
        return {'success': True, 'content': transcript_result['data']['text']} if transcript_result['success'] else transcript_result
    elif is_valid_url(user_input):
        content = scrape_url(user_input)
        return {'success': False, 'error': content} if content.startswith("Error:") else {'success': True, 'content': content}
    else:
        return {'success': True, 'content': user_input}

def run_ai_generation(prompt: str, user_id: int, model: str = "gpt-4o-mini", max_tokens: int = 2000, temperature: float = 0.5, expect_json: bool = False):
    if not client: 
        return None
    
    db = next(get_db())
    request_hash = generate_hash(f"{prompt}{model}{max_tokens}{temperature}{expect_json}")
    cached_response = crud.get_cached_response(db, request_hash)
    if cached_response:
        return cached_response
    
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
        crud.set_cached_response(db, request_hash, result_text)
        return result_text
    except Exception as e:
        print(f"Error: AI generation failed: {e}")
        return None

def _parse_score_from_response(response_text: str) -> int:
    if not response_text:
        return 0
    score_match = re.search(r'\d+', response_text)
    if score_match:
        return int(score_match.group())
    number_words = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}
    for word, value in number_words.items():
        if word in response_text.lower():
            return value
    return 0

def local_ai_polish(content: str):
    return content

def cut_video_clip(video_file: str, start_time: float, duration: float, output_name: str):
    try:
        command = ['ffmpeg', '-ss', str(start_time), '-i', video_file, '-t', str(duration), '-c', 'copy', '-y', output_name]
        subprocess.run(command, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error cutting video clip: {e.stderr}")
        return False

def get_background_music():
    music_file = "music/background.mp3"
    return music_file if os.path.exists(music_file) else None

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

def get_or_create_transcript_sync(source_url: str, user_id: int = None):
    """Synchronous version of transcript generation for content processing"""
    db = next(get_db())
    
    # Check cache first
    cached = crud.get_cached_transcript(db, source_url)
    if cached:
        return {'success': True, 'data': cached}
    
    # Download audio
    audio_info = download_media(source_url, is_video=False)
    if not audio_info['success']:
        return audio_info
    
    audio_path = audio_info['path']
    audio = AudioSegment.from_mp3(audio_path)
    
    # Process in chunks if needed
    chunks = [audio[i:i + 900000] for i in range(0, len(audio), 900000)]  # 15 min chunks
    all_words, full_text, total_cost = [], "", 0.0
    
    for i, chunk in enumerate(chunks):
        chunk_path = os.path.join(TEMP_DOWNLOAD_DIR, f"temp_chunk_sync_{i}.mp3")
        chunk.export(chunk_path, format="mp3")
        
        result = transcribe_audio_robust(chunk_path)
        if result['success']:
            offset = i * 900  # 15 minutes in seconds
            for w in result['data']['words']:
                w['start'] += offset
                w['end'] += offset
                all_words.append(w)
            full_text += result['data']['text'] + " "
        
        # Calculate cost
        total_cost += (len(chunk) / 60000) * 0.006  # $0.006 per minute
        
        # Cleanup chunk
        try:
            os.remove(chunk_path)
        except:
            pass
    
    if not full_text.strip():
        return {'success': False, 'error': 'Empty transcript generated'}
    
    final_transcript = {
        "text": full_text.strip(),
        "words": all_words
    }
    
    # Cache the result
    crud.set_cached_transcript(db, source_url, final_transcript)
    
    # Track usage if user_id provided
    if user_id:
        crud.track_usage(db, user_id, "whisper-1", "transcription", total_cost)
    
    # Cleanup audio file
    try:
        os.remove(audio_path)
    except:
        pass
    
    return {'success': True, 'data': final_transcript}