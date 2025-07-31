# app/services/video_engine.py
import os
import uuid
import subprocess
import json
from typing import Dict, List, Any
from app.core.config import settings
from app.services import firebase_utils
import tempfile

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
            
            print("Loading Stable Diffusion model...")
            self.pipe = StableDiffusionPipeline.from_pretrained(
                "runwayml/stable-diffusion-v1-5",
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                cache_dir=settings.STATIC_GENERATED_DIR
            )
            
            if torch.cuda.is_available():
                self.pipe = self.pipe.to("cuda")
            
            self.model_loaded = True
            print("✅ Stable Diffusion model loaded successfully")
            
        except Exception as e:
            print(f"❌ Failed to load Stable Diffusion model: {e}")
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
            print(f"❌ Image generation failed: {e}")
            return None

# Global instance
sd_generator = StableDiffusionGenerator()

def process_single_clip(
    source_video_path: str,
    moment: Dict[str, float],
    flags: Dict[str, Any],
    user_id: int,
    clip_number: str,
    words_data: List[Dict]
) -> Dict[str, Any]:
    """Process a single video clip with better error handling"""
    
    temp_clip_path = None
    final_clip_path = None
    
    try:
        # Verify source video exists
        if not os.path.exists(source_video_path):
            return {'success': False, 'error': f'Source video not found: {source_video_path}'}
        
        start_time = moment['start']
        duration = min(moment['duration'], 60)  # Cap at 60 seconds
        aspect_ratio = flags.get('aspect_ratio', '9:16')
        add_captions = flags.get('add_captions', True)
        platform = flags.get('platform', 'unknown')
        
        print(f"Processing clip for {platform}: start={start_time}, duration={duration}, aspect={aspect_ratio}")
        
        # Generate unique filename
        clip_id = f"clip_{user_id}_{clip_number}_{uuid.uuid4().hex[:8]}"
        temp_clip_path = os.path.join(settings.STATIC_GENERATED_DIR, f"temp_{clip_id}.mp4")
        final_clip_path = os.path.join(settings.STATIC_GENERATED_DIR, f"final_{clip_id}.mp4")
        
        os.makedirs(settings.STATIC_GENERATED_DIR, exist_ok=True)
        
        # Step 1: Extract the base clip with more compatible settings
        extract_cmd = [
            'ffmpeg',
            '-ss', str(start_time),  # Seek to start time
            '-i', source_video_path, # Input file
            '-t', str(duration),     # Duration
            '-c:v', 'libx264',       # Video codec
            '-preset', 'fast',       # Encoding speed
            '-crf', '23',            # Quality (lower = better, 23 is default)
            '-c:a', 'aac',           # Audio codec
            '-b:a', '128k',          # Audio bitrate
            '-movflags', '+faststart', # Web optimization
            '-y',                    # Overwrite
            temp_clip_path
        ]
        
        print(f"Extracting clip: {' '.join(extract_cmd)}")
        result = subprocess.run(extract_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            error_msg = f"Video extraction failed (code {result.returncode}): {result.stderr[:500]}"
            print(error_msg)
            return {'success': False, 'error': error_msg}
        
        if not os.path.exists(temp_clip_path):
            return {'success': False, 'error': 'Temp clip was not created'}
        
        # Step 2: Apply aspect ratio (simplified for now, skip captions)
        filter_parts = []
        
        if aspect_ratio == '9:16':
            # Vertical (TikTok, Shorts, Reels)
            filter_parts.append("scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2")
        elif aspect_ratio == '1:1':
            # Square (Instagram Feed)
            filter_parts.append("scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2")
        else:
            # 16:9 (LinkedIn, Twitter) - just copy
            os.rename(temp_clip_path, final_clip_path)
            temp_clip_path = None
        
        # Apply filters if needed
        if filter_parts and temp_clip_path:
            process_cmd = [
                'ffmpeg',
                '-i', temp_clip_path,
                '-vf', ','.join(filter_parts),
                '-c:a', 'copy',
                '-y',
                final_clip_path
            ]
            
            print(f"Processing clip with filters: {' '.join(process_cmd[:6])}...")
            result = subprocess.run(process_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                error_msg = f"Video processing failed (code {result.returncode}): {result.stderr[:500]}"
                print(error_msg)
                return {'success': False, 'error': error_msg}
        
        # Verify final clip exists
        if not os.path.exists(final_clip_path):
            return {'success': False, 'error': 'Final clip was not created'}
        
        # Step 3: Return local URL (skip Firebase for now to isolate issue)
        local_url = f"/static/generated/{os.path.basename(final_clip_path)}"
        print(f"Clip created successfully: {local_url}")
        
        # Clean up temp file
        if temp_clip_path and os.path.exists(temp_clip_path):
            os.remove(temp_clip_path)
        
        return {'success': True, 'url': local_url}
            
    except Exception as e:
        error_msg = f"Unexpected error in process_single_clip: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        
        # Clean up any temp files
        for path in [temp_clip_path, final_clip_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass
        
        return {'success': False, 'error': error_msg}

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
        print(f"Thumbnail generation failed: {e}")
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