# app/services/video_engine.py
import os
import uuid
import subprocess
import json
import logging
from typing import Dict, List, Any
from app.core.config import settings
from app.services import firebase_utils
import tempfile

logger = logging.getLogger(__name__)

def detect_ffmpeg_capabilities():
    """Detect available FFmpeg encoders and hardware acceleration"""
    try:
        # Check for NVIDIA hardware acceleration
        result = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True)
        has_nvenc = 'h264_nvenc' in result.stdout
        has_cuda = 'cuda' in result.stdout
        
        if has_nvenc and has_cuda:
            return {
                'hwaccel': ['-hwaccel', 'cuda'],
                'video_codec': ['-c:v', 'h264_nvenc', '-preset', 'p5', '-cq', '24'],
                'type': 'nvidia'
            }
        else:
            return {
                'hwaccel': [],
                'video_codec': ['-c:v', 'libx264', '-preset', 'medium', '-crf', '23'],
                'type': 'software'
            }
    except:
        # Fallback to software encoding
        return {
            'hwaccel': [],
            'video_codec': ['-c:v', 'libx264', '-preset', 'medium', '-crf', '23'],
            'type': 'software'
        }

# Detect capabilities once at startup
FFMPEG_CONFIG = detect_ffmpeg_capabilities()
logger.info(f"Using FFmpeg config: {FFMPEG_CONFIG['type']}")

def create_ass_file(words_data, output_path, start_offset):
    """Creates an ASS subtitle file with improved error handling."""
    if not words_data:
        logger.warning("No words data provided for ASS file creation")
        return False
        
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("""[Script Info]
Title: Alchemize Captions
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,36,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,2,2,10,10,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""")
            
            # Group words into phrases (3-4 words each for better readability)
            phrase_length = 3
            for i in range(0, len(words_data), phrase_length):
                phrase_words = words_data[i:i + phrase_length]
                if not phrase_words:
                    continue
                
                phrase_text = " ".join([word.get('word', '') for word in phrase_words])
                start_time = phrase_words[0].get('start', 0) - start_offset
                end_time = phrase_words[-1].get('end', start_time + 1) - start_offset
                
                # Ensure positive timing
                start_time = max(0, start_time)
                end_time = max(start_time + 0.5, end_time)
                
                # Format timing (H:MM:SS.CC)
                start_str = f"{int(start_time // 3600)}:{int((start_time % 3600) // 60):02}:{start_time % 60:05.2f}"
                end_str = f"{int(end_time // 3600)}:{int((end_time % 3600) // 60):02}:{end_time % 60:05.2f}"
                
                f.write(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{phrase_text.upper()}\n")
        
        return True
    except Exception as e:
        logger.error(f"Failed to create ASS file: {e}")
        return False

def _generate_srt_file(words_data: List[Dict], start_time: float, duration: float, clip_id: str) -> str:
    """Generates a temporary SRT subtitle file from Whisper's word data."""
    srt_path = os.path.join(settings.STATIC_GENERATED_DIR, f"captions_{clip_id}.srt")
    clip_start = start_time
    clip_end = start_time + duration
    clip_words = [word for word in words_data if clip_start <= word.get('start', -1) <= clip_end]

    with open(srt_path, 'w', encoding='utf-8') as f:
        for i, word in enumerate(clip_words):
            start_ts = max(0, word['start'] - clip_start)
            end_ts = max(0, word['end'] - clip_start)

            start_h, rem = divmod(start_ts, 3600)
            start_m, rem = divmod(rem, 60)
            start_s, start_ms = divmod(rem, 1)

            end_h, rem = divmod(end_ts, 3600)
            end_m, rem = divmod(rem, 60)
            end_s, end_ms = divmod(rem, 1)

            f.write(f"{i + 1}\n")
            f.write(f"{int(start_h):02}:{int(start_m):02}:{int(start_s):02},{int(start_ms*1000):03} --> "
                    f"{int(end_h):02}:{int(end_m):02}:{int(end_s):02},{int(end_ms*1000):03}\n")
            f.write(f"{word['word'].upper()}\n\n")

    return srt_path

class StableDiffusionGenerator:
    """Local Stable Diffusion image generator"""
    
    def __init__(self):
        self.model_loaded = False
        self.pipe = None
    
    def _load_model(self):
        """Load the Stable Diffusion model on first use"""
        if self.model_loaded:
            return
        
        try:
            from diffusers import StableDiffusionPipeline
            import torch
            
            logger.info("Loading Stable Diffusion model...")
            self.pipe = StableDiffusionPipeline.from_pretrained(
                "runwayml/stable-diffusion-v1-5",
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                cache_dir=settings.STATIC_GENERATED_DIR
            )
            
            if torch.cuda.is_available():
                self.pipe = self.pipe.to("cuda")
            
            self.model_loaded = True
            logger.info("✅ Stable Diffusion model loaded successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to load Stable Diffusion model: {e}")
            self.model_loaded = False
    
    def generate_image(self, prompt: str, width: int = 1280, height: int = 720) -> str | None:
        """Generate an image and return its URL"""
        try:
            self._load_model()
            if not self.model_loaded:
                return None
            
            # Generate image
            image = self.pipe(
                prompt=f"high quality, professional, {prompt}",
                negative_prompt="blurry, low quality, distorted, text, watermark",
                width=width,
                height=height,
                num_inference_steps=20,
                guidance_scale=7.5
            ).images[0]
            
            # Save locally first
            filename = f"thumbnail_{uuid.uuid4().hex}.png"
            local_path = os.path.join(settings.STATIC_GENERATED_DIR, filename)
            os.makedirs(settings.STATIC_GENERATED_DIR, exist_ok=True)
            image.save(local_path)
            
            # Upload to Firebase if available
            firebase_url = firebase_utils.upload_to_storage(
                local_path, 
                f"thumbnails/{filename}"
            )
            
            if firebase_url:
                # Clean up local file if upload successful
                try:
                    os.remove(local_path)
                except:
                    pass
                return firebase_url
            else:
                # Return local static URL
                return f"/static/generated/{filename}"
                
        except Exception as e:
            logger.error(f"❌ Image generation failed: {e}")
            return None

# Global instance
sd_generator = StableDiffusionGenerator()

def process_single_clip(
    source_video_path: str,
    moment: Dict[str, float],
    flags: Dict[str, Any],
    user_id: int,
    clip_id: str,
    words_data: List[Dict]
) -> Dict[str, Any]:
    """Processes a single video clip with adaptive hardware acceleration."""

    temp_clip_path, final_clip_path, ass_path = None, None, None

    try:
        start_time = moment['start']
        duration = min(moment['duration'], 60)
        aspect_ratio = flags.get('aspect_ratio', '9:16')
        add_captions = flags.get('add_captions', True)

        temp_clip_path = os.path.join(settings.STATIC_GENERATED_DIR, f"temp_{clip_id}.mp4")
        final_clip_path = os.path.join(settings.STATIC_GENERATED_DIR, f"final_{clip_id}.mp4")

        # Step 1: Extract the base clip with adaptive hardware acceleration
        extract_cmd = ['ffmpeg'] + FFMPEG_CONFIG['hwaccel'] + [
            '-ss', str(start_time), '-i', source_video_path,
            '-t', str(duration)
        ] + FFMPEG_CONFIG['video_codec'] + [
            '-c:a', 'aac', '-b:a', '128k', '-y', temp_clip_path
        ]
        
        result = subprocess.run(extract_cmd, check=True, capture_output=True, text=True)
        logger.debug(f"Extract command completed for {clip_id}")

        # Step 2: Prepare filters
        filter_parts = []
        if aspect_ratio == '9:16':
            filter_parts.append("scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2")
        elif aspect_ratio == '1:1':
            filter_parts.append("scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2")

        if add_captions and words_data:
            # Filter words to only include those in this specific clip
            clip_start_time = start_time
            clip_end_time = start_time + duration
            clip_words = [word for word in words_data if clip_start_time <= word.get('start', -1) <= clip_end_time]

            if clip_words:
                ass_path = os.path.join(settings.STATIC_GENERATED_DIR, f"captions_{clip_id}.ass")
                if create_ass_file(clip_words, ass_path, start_offset=clip_start_time):
                    filter_parts.append(f"ass={ass_path}")
                else:
                    logger.warning(f"Failed to create ASS file for {clip_id}")

        # Step 3: Apply filters
        if filter_parts:
            process_cmd = ['ffmpeg'] + FFMPEG_CONFIG['hwaccel'] + [
                '-i', temp_clip_path, '-vf', ",".join(filter_parts)
            ] + FFMPEG_CONFIG['video_codec'] + [
                '-c:a', 'copy', '-y', final_clip_path
            ]
            subprocess.run(process_cmd, check=True, capture_output=True, text=True)
        else: 
            os.rename(temp_clip_path, final_clip_path)
            temp_clip_path = None

        local_url = f"/static/generated/{os.path.basename(final_clip_path)}"
        logger.info(f"Successfully processed clip {clip_id}")
        return {'success': True, 'url': local_url}

    except subprocess.CalledProcessError as e:
        error_msg = f"FFmpeg failed for {clip_id}: {e.stderr[:500] if e.stderr else 'Unknown FFmpeg error'}"
        logger.error(error_msg)
        return {'success': False, 'error': error_msg}
    except Exception as e:
        error_msg = f"Unexpected error processing {clip_id}: {str(e)}"
        logger.error(error_msg)
        return {'success': False, 'error': error_msg}
    finally:
        # Guaranteed cleanup
        for path in [temp_clip_path, ass_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    logger.warning(f"Failed to cleanup {path}: {e}")

def _extract_text_for_timeframe(words_data: List[Dict], start_time: float, end_time: float) -> str:
    """Extract text from words data for a specific timeframe"""
    relevant_words = [
        word['word'] for word in words_data 
        if start_time <= word.get('start', 0) <= end_time
    ]
    return ' '.join(relevant_words).strip()

def generate_clip_thumbnail(video_path: str, timestamp: float, output_path: str) -> bool:
    """Generate a thumbnail from video at specific timestamp"""
    try:
        cmd = [
            'ffmpeg', '-i', video_path,
            '-ss', str(timestamp),
            '-vframes', '1',
            '-q:v', '2',
            '-y', output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Thumbnail generation failed: {e}")
        return False

def process_single_clip_with_preview(
    source_video_path: str,
    moment: Dict[str, float],
    flags: Dict[str, Any],
    user_id: int,
    clip_number: str,
    words_data: List[Dict]
) -> Dict[str, Any]:
    """Enhanced clip processor that also generates preview thumbnail"""
    
    # First, generate thumbnail
    thumbnail_path = os.path.join(settings.STATIC_GENERATED_DIR, f"thumb_{user_id}_{clip_number}.jpg")
    thumbnail_generated = generate_clip_thumbnail(
        source_video_path, 
        moment['start'] + 2,  # 2 seconds into the clip for better thumbnail
        thumbnail_path
    )
    
    # Process the video clip
    result = process_single_clip(source_video_path, moment, flags, user_id, clip_number, words_data)
    
    if result['success'] and thumbnail_generated:
        # Upload thumbnail
        thumbnail_url = firebase_utils.upload_to_storage(
            thumbnail_path,
            f"thumbnails/clips/thumb_{user_id}_{clip_number}.jpg"
        )
        if thumbnail_url:
            result['thumbnail_url'] = thumbnail_url
            # Clean up local thumbnail
            try:
                os.remove(thumbnail_path)
            except:
                pass
        else:
            result['thumbnail_url'] = f"/static/generated/thumb_{user_id}_{clip_number}.jpg"
    
    return result