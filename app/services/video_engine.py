import os
import uuid
import subprocess
import json
import logging
from typing import Dict, List, Any
from concurrent.futures import ThreadPoolExecutor
import tempfile
from app.core.config import settings
from app.services import firebase_utils
from app.services.gpu_manager import get_gpu_manager

logger = logging.getLogger(__name__)

def detect_gpu_capabilities():
    """Get GPU capabilities from the GPU manager"""
    try:
        gpu_manager = get_gpu_manager()
        config = gpu_manager.get_processing_config()
        
        if gpu_manager.is_gpu_available():
            gpu_info = gpu_manager.gpu_info
            logger.info(f"🎮 GPU Available: {gpu_info.name}")
            logger.info(f"💾 VRAM: {gpu_info.memory_total}MB total, {gpu_info.memory_free}MB free")
            
            # Get optimized FFmpeg arguments
            hwaccel_args = gpu_manager.get_ffmpeg_gpu_args()
            encoder_args = gpu_manager.get_ffmpeg_encoder_args()
            
            return {
                'hwaccel': hwaccel_args,
                'video_codec': encoder_args,
                'scale_filter': 'scale_npp' if 'nvenc' in str(encoder_args) else 'scale',
                'type': config.get('processing_method', 'gpu_optimized'),
                'parallel_encode': config.get('parallel_encode', False),
                'max_concurrent_clips': config.get('max_concurrent_clips', 2),
                'gpu_memory_fraction': config.get('gpu_memory_fraction', 0.7)
            }
        
        # Fallback to CPU
        logger.info("💻 Using CPU encoding (no GPU detected)")
        return {
                'hwaccel': [],
                'video_codec': ['-c:v', 'libx264', '-preset', 'medium', '-crf', '23'],
                'scale_filter': 'scale',
                'type': 'cpu_fallback',
                'parallel_encode': False
            }
    except Exception as e:
        logger.error(f"GPU detection failed: {e}")
        return {
            'hwaccel': [],
            'video_codec': ['-c:v', 'libx264', '-preset', 'fast', '-crf', '25'],
            'scale_filter': 'scale',
            'type': 'cpu_emergency',
            'parallel_encode': False
        }

# Initialize GPU configuration
FFMPEG_CONFIG = detect_gpu_capabilities()
logger.info(f"🔧 Video engine initialized: {FFMPEG_CONFIG['type']}")

def get_duration(video_path: str) -> float:
    """Get video duration using ffprobe with better error handling"""
    try:
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', video_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            info = json.loads(result.stdout)
            duration = float(info['format']['duration'])
            logger.info(f"📹 Video duration: {duration:.1f}s")
            return duration
        else:
            logger.error(f"ffprobe failed: {result.stderr}")
            return 60.0  # fallback
    except Exception as e:
        logger.error(f"Duration detection failed: {e}")
        return 60.0

def create_improved_karaoke_ass(words_data, output_path, start_offset, clip_duration):
    """Creates karaoke-style ASS subtitles optimized for your content"""
    if not words_data:
        logger.warning("No words data provided for captions")
        return False
        
    try:
        # Filter words for this specific clip
        clip_start = start_offset
        clip_end = start_offset + clip_duration
        clip_words = [
            word for word in words_data 
            if clip_start <= word.get('start', -1) <= clip_end
        ]
        
        if not clip_words:
            logger.warning(f"No words found in clip timeframe {clip_start:.1f}s - {clip_end:.1f}s")
            return False

        with open(output_path, 'w', encoding='utf-8') as f:
            # High-quality ASS styling optimized for social media
            f.write("""[Script Info]
Title: Zuexis Pro Karaoke Captions
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,Arial Black,44,&H00FFFF00,&H00FF6600,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,10,10,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""")
            
            # Optimized phrase grouping for better readability
            phrase_length = 3 if len(clip_words) > 20 else 4
            
            for i in range(0, len(clip_words), phrase_length):
                phrase_words = clip_words[i:i + phrase_length]
                if not phrase_words:
                    continue
                
                # Calculate timing relative to clip start
                phrase_start = phrase_words[0].get('start', 0) - start_offset
                phrase_end = phrase_words[-1].get('end', phrase_start + 2) - start_offset
                
                # Ensure times are within clip bounds
                phrase_start = max(0, min(phrase_start, clip_duration))
                phrase_end = max(phrase_start + 0.5, min(phrase_end, clip_duration))
                
                # Build karaoke text with improved timing
                karaoke_text = ""
                for j, word in enumerate(phrase_words):
                    word_text = word.get('word', '').strip().upper()
                    if not word_text:
                        continue
                        
                    word_duration = max(0.4, word.get('end', 0) - word.get('start', 0))
                    timing_centiseconds = int(word_duration * 100)
                    
                    if j > 0:
                        karaoke_text += " "
                    karaoke_text += f"{{\\k{timing_centiseconds}}}{word_text}"
                
                if karaoke_text:
                    start_str = format_ass_time(phrase_start)
                    end_str = format_ass_time(phrase_end)
                    f.write(f"Dialogue: 0,{start_str},{end_str},Karaoke,,0,0,0,karaoke,{karaoke_text}\n")
        
        logger.info(f"🎤 Created karaoke ASS file: {len(clip_words)} words")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create karaoke ASS file: {e}")
        return False

def format_ass_time(seconds):
    """Format seconds as ASS timestamp (H:MM:SS.CC)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"

def process_single_clip_gpu(
    source_video_path: str,
    moment: Dict[str, float],
    flags: Dict[str, Any],
    user_id: int,
    clip_id: str,
    words_data: List[Dict]
) -> Dict[str, Any]:
    """GPU-optimized single clip processing for your 4080 Super"""

    temp_clip_path, final_clip_path, ass_path = None, None, None

    try:
        start_time = moment['start']
        duration = min(moment['duration'], settings.VIDEO_PROCESSING['max_clip_duration'])
        aspect_ratio = flags.get('aspect_ratio', '9:16')
        add_captions = flags.get('add_captions', True)

        # GPU-optimized file paths
        temp_clip_path = os.path.join(settings.STATIC_GENERATED_DIR, f"temp_{clip_id}.mp4")
        final_clip_path = os.path.join(settings.STATIC_GENERATED_DIR, f"final_{clip_id}.mp4")

        logger.info(f"🚀 GPU processing clip {clip_id}: {start_time:.1f}s, duration={duration:.1f}s")

        # Build GPU-optimized FFmpeg command
        cmd = ['ffmpeg', '-y']
        
        # Add GPU acceleration if available
        if FFMPEG_CONFIG['hwaccel']:
            cmd.extend(FFMPEG_CONFIG['hwaccel'])
        
        # Input with precise seeking
        cmd.extend(['-ss', str(start_time), '-i', source_video_path, '-t', str(duration)])
        
        # Build filter chain
        filters = []
        
        # GPU-accelerated scaling based on aspect ratio
        scale_filter = FFMPEG_CONFIG['scale_filter']
        if aspect_ratio == '9:16':
            filters.append(f"{scale_filter}=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2:black")
        elif aspect_ratio == '1:1':
            filters.append(f"{scale_filter}=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2:black")
        elif aspect_ratio == '16:9':
            filters.append(f"{scale_filter}=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black")

        # Add captions if requested
        caption_added = False
        if add_captions and words_data:
            ass_path = os.path.join(settings.STATIC_GENERATED_DIR, f"captions_{clip_id}.ass")
            
            if create_improved_karaoke_ass(words_data, ass_path, start_time, duration):
                escaped_ass_path = ass_path.replace('\\', '\\\\').replace(':', '\\:')
                filters.append(f"ass='{escaped_ass_path}'")
                caption_added = True
                logger.info(f"🎤 Added GPU-accelerated captions to {clip_id}")

        # Apply filters
        if filters:
            cmd.extend(['-vf', ','.join(filters)])

        # GPU-optimized encoding settings
        cmd.extend(FFMPEG_CONFIG['video_codec'])
        
        # Audio settings
        cmd.extend(['-c:a', 'aac', '-b:a', '128k'])
        
        # Optimization flags
        cmd.extend([
            '-movflags', '+faststart',
            '-avoid_negative_ts', 'make_zero'
        ])
        
        cmd.append(final_clip_path)
        
        # Execute with timeout
        logger.info(f"🔧 GPU command: {' '.join(cmd[:10])}...")  # Log first 10 elements
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=settings.VIDEO_PROCESSING['ffmpeg_timeout']
        )
        
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, cmd, result.stderr)

        # Verify output
        if not os.path.exists(final_clip_path):
            raise FileNotFoundError(f"GPU processing failed - output not created: {final_clip_path}")
        
        file_size = os.path.getsize(final_clip_path)
        if file_size < 1024:
            raise ValueError(f"Output too small ({file_size} bytes) - GPU processing may have failed")

        # Return success with local URL
        filename = os.path.basename(final_clip_path)
        local_url = f"/static/generated/{filename}"
        
        logger.info(f"✅ GPU clip success {clip_id}: {file_size:,}B, captions: {caption_added}")
        
        return {
            'success': True, 
            'url': local_url, 
            'file_size': file_size,
            'captions_added': caption_added,
            'duration': duration,
            'processing_method': FFMPEG_CONFIG['type']
        }

    except subprocess.CalledProcessError as e:
        error_msg = f"GPU FFmpeg failed for {clip_id}: {e.stderr[-500:] if e.stderr else 'Unknown error'}"
        logger.error(f"❌ {error_msg}")
        return {'success': False, 'error': error_msg}
        
    except Exception as e:
        error_msg = f"GPU processing error {clip_id}: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return {'success': False, 'error': error_msg}
        
    finally:
        # Cleanup
        for path in [temp_clip_path, ass_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

def process_clips_parallel(
    source_video_path: str,
    moments: List[Dict],
    flags: Dict[str, Any],
    user_id: int,
    job_id: str,
    words_data: List[Dict]
) -> List[Dict[str, Any]]:
    """Process multiple clips in parallel using your GPU efficiently"""
    
    if not FFMPEG_CONFIG.get('parallel_encode', False):
        # Fallback to sequential for CPU
        logger.info("🔄 Using sequential processing (CPU mode)")
        results = []
        for i, moment in enumerate(moments):
            clip_id = f"{job_id}_clip_{i+1}"
            result = process_single_clip_gpu(source_video_path, moment, flags, user_id, clip_id, words_data)
            results.append(result)
        return results
    
    # Parallel GPU processing for RTX 4080
    logger.info(f"🚀 Using parallel GPU processing for {len(moments)} clips")
    
    def process_clip_wrapper(args):
        source_path, moment, flags, user_id, clip_id, words_data = args
        return process_single_clip_gpu(source_path, moment, flags, user_id, clip_id, words_data)
    
    # Use 2-3 parallel workers max to avoid overwhelming GPU memory
    max_workers = min(3, len(moments))
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        clip_args = [
            (source_video_path, moment, flags, user_id, f"{job_id}_clip_{i+1}", words_data)
            for i, moment in enumerate(moments)
        ]
        
        results = list(executor.map(process_clip_wrapper, clip_args))
    
    logger.info(f"🎉 Parallel processing complete: {sum(1 for r in results if r.get('success'))} successful clips")
    return results

# Legacy function name for compatibility
def process_single_clip(*args, **kwargs):
    """Wrapper for backward compatibility"""
    return process_single_clip_gpu(*args, **kwargs)

class StableDiffusionGenerator:
    """GPU-accelerated Stable Diffusion for your RTX 4080"""
    
    def __init__(self):
        self.model_loaded = False
        self.pipe = None
    
    def _load_model(self):
        if self.model_loaded:
            return
        
        try:
            from diffusers import StableDiffusionPipeline
            import torch
            
            logger.info("🎨 Loading Stable Diffusion on RTX 4080...")
            
            # Optimized for RTX 4080
            self.pipe = StableDiffusionPipeline.from_pretrained(
                "runwayml/stable-diffusion-v1-5",
                torch_dtype=torch.float16,
                cache_dir=settings.STATIC_GENERATED_DIR,
                safety_checker=None,  # Disable for speed
                requires_safety_checker=False
            )
            
            if torch.cuda.is_available():
                self.pipe = self.pipe.to("cuda")
                # RTX 4080 optimizations
                self.pipe.enable_attention_slicing()
                self.pipe.enable_memory_efficient_attention()
                logger.info("🚀 RTX 4080 optimizations enabled!")
            
            self.model_loaded = True
            logger.info("✅ Stable Diffusion loaded on GPU")
            
        except Exception as e:
            logger.error(f"❌ Failed to load Stable Diffusion: {e}")
            self.model_loaded = False
    
    def generate_image(self, prompt: str, width: int = 1280, height: int = 720) -> str | None:
        try:
            self._load_model()
            if not self.model_loaded:
                return None
            
            import torch
            
            # RTX 4080 optimized generation
            image = self.pipe(
                prompt=f"high quality, professional, {prompt}",
                negative_prompt="blurry, low quality, distorted, text, watermark, ugly",
                width=width,
                height=height,
                num_inference_steps=25,  # Good balance for RTX 4080
                guidance_scale=7.5,
                generator=torch.Generator(device="cuda").manual_seed(42)  # Consistent results
            ).images[0]
            
            filename = f"thumbnail_{uuid.uuid4().hex}.png"
            local_path = os.path.join(settings.STATIC_GENERATED_DIR, filename)
            image.save(local_path, optimize=True, quality=85)
            
            # Try Firebase upload, fallback to local
            firebase_url = firebase_utils.upload_to_storage(local_path, f"thumbnails/{filename}")
            
            if firebase_url:
                try:
                    os.remove(local_path)
                except:
                    pass
                return firebase_url
            else:
                return f"/static/generated/{filename}"
                
        except Exception as e:
            logger.error(f"❌ GPU image generation failed: {e}")
            return None

sd_generator = StableDiffusionGenerator()

def process_video_sync(
    video_path: str,
    job_id: str,
    user_id: int,
    add_captions: bool,
    aspect_ratio: str,
    platforms: list[str],
    words_data: list[dict]
) -> list[dict]:
    """Synchronous video processing for when Redis/Celery is not available."""
    try:
        logger.info(f"🎬 Starting synchronous video processing for job {job_id}")
        
        # Generate moments for clips (simplified version)
        import random
        
        # For sync mode, create 3 clips with random moments
        # In a real implementation, you'd use proper moment detection
        video_info_cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', video_path]
        result = subprocess.run(video_info_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise ValueError("Could not get video duration")
            
        video_info = json.loads(result.stdout)
        duration = float(video_info['format']['duration'])
        
        # Create 3 clips with 60-second duration each
        clip_duration = 60
        moments = []
        
        for i in range(min(3, int(duration // clip_duration))):
            start_time = i * clip_duration
            if start_time + clip_duration <= duration:
                moments.append({
                    'start': start_time,
                    'duration': clip_duration,
                    'score': 0.0  # Removed fake confidence scores
                })
        
        if not moments:
            # If video is too short, create one clip from the beginning
            moments = [{
                'start': 0,
                'duration': min(duration, clip_duration),
                'score': 0.9
            }]
        
        logger.info(f"📋 Generated {len(moments)} moments for processing")
        
        # Process clips using existing parallel processing
        flags = {
            'add_captions': add_captions,
            'aspect_ratio': aspect_ratio,
            'platforms': platforms
        }
        
        clip_results = process_clips_parallel(
            source_video_path=video_path,
            moments=moments,
            flags=flags,
            user_id=user_id,
            job_id=job_id,
            words_data=words_data
        )
        
        # Filter successful clips and format output
        successful_clips = [result for result in clip_results if result.get('success')]
        
        logger.info(f"✅ Synchronous processing complete: {len(successful_clips)} clips created")
        
        return successful_clips
        
    except Exception as e:
        logger.error(f"❌ Synchronous video processing failed: {e}")
        raise e