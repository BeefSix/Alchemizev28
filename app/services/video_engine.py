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
        return {
            'hwaccel': [],
            'video_codec': ['-c:v', 'libx264', '-preset', 'medium', '-crf', '23'],
            'type': 'software'
        }

FFMPEG_CONFIG = detect_ffmpeg_capabilities()
logger.info(f"Using FFmpeg config: {FFMPEG_CONFIG['type']}")

def get_duration(video_path: str) -> float:
    """Get video duration using ffprobe"""
    try:
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', video_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            info = json.loads(result.stdout)
            return float(info['format']['duration'])
        return 60.0  # fallback
    except:
        return 60.0

def create_karaoke_ass_file(words_data, output_path, start_offset, clip_duration):
    """Creates an ASS subtitle file with live karaoke-style highlighting."""
    if not words_data:
        logger.warning("No words data provided for ASS file creation")
        return False
        
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("""[Script Info]
Title: Alchemize Live Captions
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,44,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,10,10,45,1
Style: Karaoke,Arial Black,44,&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,10,10,45,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""")
            
            # Filter words for this clip
            clip_start = start_offset
            clip_end = start_offset + clip_duration
            clip_words = [word for word in words_data 
                         if clip_start <= word.get('start', 0) <= clip_end]
            
            if not clip_words:
                return False
            
            # Group words into phrases for karaoke effect
            phrase_length = 4
            
            for i in range(0, len(clip_words), phrase_length):
                phrase_words = clip_words[i:i + phrase_length]
                if not phrase_words:
                    continue
                
                phrase_start = phrase_words[0].get('start', 0) - start_offset
                phrase_end = phrase_words[-1].get('end', phrase_start + 1) - start_offset
                
                phrase_start = max(0, min(phrase_start, clip_duration))
                phrase_end = max(phrase_start + 0.5, min(phrase_end, clip_duration))
                
                # Create karaoke effect
                karaoke_text = ""
                for j, word in enumerate(phrase_words):
                    word_text = word.get('word', '').upper()
                    word_duration = max(0.3, word.get('end', 0) - word.get('start', 0))
                    timing_ms = int(word_duration * 100)
                    
                    if j > 0:
                        karaoke_text += " "
                    karaoke_text += f"{{\\k{timing_ms}}}{word_text}"
                
                # Format timing
                start_str = f"{int(phrase_start // 3600)}:{int((phrase_start % 3600) // 60):02}:{phrase_start % 60:05.2f}"
                end_str = f"{int(phrase_end // 3600)}:{int((phrase_end % 3600) // 60):02}:{phrase_end % 60:05.2f}"
                
                f.write(f"Dialogue: 0,{start_str},{end_str},Karaoke,,0,0,0,karaoke,{karaoke_text}\n")
        
        return True
    except Exception as e:
        logger.error(f"Failed to create karaoke ASS file: {e}")
        return False

def create_simple_ass_file(words_data, output_path, start_offset, clip_duration):
    """Creates a simple ASS subtitle file without karaoke effects as fallback."""
    if not words_data:
        return False
        
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("""[Script Info]
Title: Alchemize Captions
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,38,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,2,2,10,10,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""")
            
            clip_start = start_offset
            clip_end = start_offset + clip_duration
            clip_words = [word for word in words_data 
                         if clip_start <= word.get('start', 0) <= clip_end]
            
            phrase_length = 3
            for i in range(0, len(clip_words), phrase_length):
                phrase_words = clip_words[i:i + phrase_length]
                if not phrase_words:
                    continue
                
                phrase_text = " ".join([word.get('word', '') for word in phrase_words]).upper()
                start_time = phrase_words[0].get('start', 0) - start_offset
                end_time = phrase_words[-1].get('end', start_time + 1) - start_offset
                
                start_time = max(0, start_time)
                end_time = max(start_time + 0.5, end_time)
                
                start_str = f"{int(start_time // 3600)}:{int((start_time % 3600) // 60):02}:{start_time % 60:05.2f}"
                end_str = f"{int(end_time // 3600)}:{int((end_time % 3600) // 60):02}:{end_time % 60:05.2f}"
                
                f.write(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{phrase_text}\n")
        
        return True
    except Exception as e:
        logger.error(f"Failed to create simple ASS file: {e}")
        return False

class StableDiffusionGenerator:
    """Local Stable Diffusion image generator"""
    
    def __init__(self):
        self.model_loaded = False
        self.pipe = None
    
    def _load_model(self):
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
        try:
            self._load_model()
            if not self.model_loaded:
                return None
            
            image = self.pipe(
                prompt=f"high quality, professional, {prompt}",
                negative_prompt="blurry, low quality, distorted, text, watermark",
                width=width,
                height=height,
                num_inference_steps=20,
                guidance_scale=7.5
            ).images[0]
            
            filename = f"thumbnail_{uuid.uuid4().hex}.png"
            local_path = os.path.join(settings.STATIC_GENERATED_DIR, filename)
            os.makedirs(settings.STATIC_GENERATED_DIR, exist_ok=True)
            image.save(local_path)
            
            firebase_url = firebase_utils.upload_to_storage(
                local_path, 
                f"thumbnails/{filename}"
            )
            
            if firebase_url:
                try:
                    os.remove(local_path)
                except:
                    pass
                return firebase_url
            else:
                return f"/static/generated/{filename}"
                
        except Exception as e:
            logger.error(f"❌ Image generation failed: {e}")
            return None

sd_generator = StableDiffusionGenerator()

def process_single_clip(
    source_video_path: str,
    moment: Dict[str, float],
    flags: Dict[str, Any],
    user_id: int,  # ADD THIS PARAMETER
    clip_id: str,
    words_data: List[Dict]
) -> Dict[str, Any]:
    """Process a single video clip with karaoke-style captions."""

    temp_clip_path, final_clip_path, ass_path = None, None, None

    try:
        start_time = moment['start']
        duration = min(moment['duration'], 60)
        aspect_ratio = flags.get('aspect_ratio', '9:16')
        add_captions = flags.get('add_captions', True)

        # Use job-specific filenames to avoid conflicts
        temp_clip_path = os.path.join(settings.STATIC_GENERATED_DIR, f"temp_{clip_id}.mp4")
        final_clip_path = os.path.join(settings.STATIC_GENERATED_DIR, f"final_{clip_id}.mp4")

        logger.info(f"🎬 Processing clip {clip_id}: start={start_time:.1f}s, duration={duration:.1f}s, captions={add_captions}")

        # Step 1: Extract base clip with better seeking
        extract_cmd = [
            'ffmpeg', '-y',
            '-ss', str(start_time),  # Seek before input for better accuracy
            '-i', source_video_path,
            '-t', str(duration),
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k',
            '-avoid_negative_ts', 'make_zero',
            '-movflags', '+faststart',
            temp_clip_path
        ]
        
        logger.info(f"🔧 Extracting clip: {' '.join(extract_cmd)}")
        result = subprocess.run(extract_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, extract_cmd, result.stderr)

        # Step 2: Apply scaling and captions
        filter_parts = []
        
        # Add scaling based on aspect ratio
        if aspect_ratio == '9:16':
            filter_parts.append("scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2:black")
        elif aspect_ratio == '1:1':
            filter_parts.append("scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2:black")
        elif aspect_ratio == '16:9':
            filter_parts.append("scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black")

        # Add karaoke captions if available
        caption_added = False
        if add_captions and words_data:
            ass_path = os.path.join(settings.STATIC_GENERATED_DIR, f"captions_{clip_id}.ass")
            
            # Create improved ASS subtitle file
            caption_success = create_improved_karaoke_ass(words_data, ass_path, start_time, duration)
            if caption_success:
                # Escape the path for FFmpeg
                escaped_ass_path = ass_path.replace('\\', '\\\\').replace(':', '\\:')
                filter_parts.append(f"ass='{escaped_ass_path}'")
                caption_added = True
                logger.info(f"🎤 Added karaoke captions to {clip_id}")
            else:
                logger.warning(f"⚠️ Failed to create captions for {clip_id}")

        # Step 3: Apply all filters
        if filter_parts:
            process_cmd = [
                'ffmpeg', '-y',
                '-i', temp_clip_path, 
                '-vf', ','.join(filter_parts),
                '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
                '-c:a', 'copy',
                '-movflags', '+faststart',
                final_clip_path
            ]
            
            logger.info(f"🎨 Applying filters: {' '.join(process_cmd)}")
            result = subprocess.run(process_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, process_cmd, result.stderr)
        else: 
            # No filters needed, just rename
            os.rename(temp_clip_path, final_clip_path)
            temp_clip_path = None

        # Verify output file was created successfully
        if not os.path.exists(final_clip_path):
            raise FileNotFoundError(f"Output clip was not created: {final_clip_path}")
        
        file_size = os.path.getsize(final_clip_path)
        if file_size < 1024:  # Less than 1KB is suspicious
            raise ValueError(f"Output clip is too small ({file_size} bytes)")

        # Return the correct URL format that matches your static file serving
        filename = os.path.basename(final_clip_path)
        local_url = f"/static/generated/{filename}"
        
        logger.info(f"✅ Successfully created {clip_id}: {file_size:,} bytes, captions: {caption_added}")
        
        return {
            'success': True, 
            'url': local_url, 
            'file_size': file_size,
            'captions_added': caption_added,
            'duration': duration
        }

    except subprocess.CalledProcessError as e:
        error_msg = f"FFmpeg failed for {clip_id}: {e.stderr[:500] if e.stderr else 'Unknown FFmpeg error'}"
        logger.error(f"❌ {error_msg}")
        return {'success': False, 'error': error_msg}
        
    except Exception as e:
        error_msg = f"Unexpected error processing {clip_id}: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return {'success': False, 'error': error_msg}
        
    finally:
        # Cleanup temporary files
        for path in [temp_clip_path, ass_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                    logger.debug(f"🧹 Cleaned up: {path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup {path}: {e}")


def create_improved_karaoke_ass(words_data, output_path, start_offset, clip_duration):
    """Creates an improved ASS subtitle file with karaoke highlighting."""
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
            # Write ASS header with improved styling
            f.write("""[Script Info]
Title: Alchemize Live Karaoke Captions
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,Arial Black,42,&H00FFFF00,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,10,10,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""")
            
            # Group words into phrases for better readability
            phrase_length = 4  # 4 words per phrase
            
            for i in range(0, len(clip_words), phrase_length):
                phrase_words = clip_words[i:i + phrase_length]
                if not phrase_words:
                    continue
                
                # Calculate phrase timing relative to clip start
                phrase_start = phrase_words[0].get('start', 0) - start_offset
                phrase_end = phrase_words[-1].get('end', phrase_start + 2) - start_offset
                
                # Ensure times are within clip bounds
                phrase_start = max(0, min(phrase_start, clip_duration))
                phrase_end = max(phrase_start + 0.5, min(phrase_end, clip_duration))
                
                # Build karaoke text with timing
                karaoke_text = ""
                for j, word in enumerate(phrase_words):
                    word_text = word.get('word', '').strip().upper()
                    if not word_text:
                        continue
                        
                    word_duration = max(0.3, word.get('end', 0) - word.get('start', 0))
                    timing_centiseconds = int(word_duration * 100)
                    
                    if j > 0:
                        karaoke_text += " "
                    karaoke_text += f"{{\\k{timing_centiseconds}}}{word_text}"
                
                if karaoke_text:  # Only add if we have actual text
                    # Format ASS timestamps (H:MM:SS.CC)
                    start_str = format_ass_time(phrase_start)
                    end_str = format_ass_time(phrase_end)
                    
                    f.write(f"Dialogue: 0,{start_str},{end_str},Karaoke,,0,0,0,karaoke,{karaoke_text}\n")
        
        logger.info(f"🎤 Created karaoke ASS file: {len(clip_words)} words in {output_path}")
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