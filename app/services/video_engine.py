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
    clip_number: int,
    words_data: List[Dict]
) -> Dict[str, Any]:
    """Process a single video clip with the given parameters"""
    
    try:
        start_time = moment['start']
        duration = min(moment['duration'], 60)  # Cap at 60 seconds
        aspect_ratio = flags.get('aspect_ratio', '9:16')
        add_captions = flags.get('add_captions', True)
        
        # Generate unique filename
        clip_id = f"clip_{user_id}_{clip_number}_{uuid.uuid4().hex[:8]}"
        temp_clip_path = os.path.join(settings.STATIC_GENERATED_DIR, f"temp_{clip_id}.mp4")
        final_clip_path = os.path.join(settings.STATIC_GENERATED_DIR, f"final_{clip_id}.mp4")
        
        os.makedirs(settings.STATIC_GENERATED_DIR, exist_ok=True)
        
        # Step 1: Extract the base clip
        extract_cmd = [
            'ffmpeg', '-i', source_video_path,
            '-ss', str(start_time),
            '-t', str(duration),
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-y', temp_clip_path
        ]
        
        result = subprocess.run(extract_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Video extraction failed: {result.stderr}")
        
        # Step 2: Apply aspect ratio and captions if requested
        filter_complex = []
        
        # Aspect ratio filter
        if aspect_ratio == '9:16':
            filter_complex.append("scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280")
        elif aspect_ratio == '1:1':
            filter_complex.append("scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080")
        
        # Caption filter (simplified - you'd want to use the words_data for precise timing)
        if add_captions:
            # This is a placeholder - implement proper caption overlay based on words_data
            caption_text = _extract_text_for_timeframe(words_data, start_time, start_time + duration)
            if caption_text:
                # Simple text overlay (you might want to make this more sophisticated)
                caption_filter = f"drawtext=text='{caption_text[:50]}...':fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:fontsize=36:fontcolor=white:bordercolor=black:borderw=2:x=(w-text_w)/2:y=h-100"
                filter_complex.append(caption_filter)
        
        # Final processing command
        if filter_complex:
            process_cmd = [
                'ffmpeg', '-i', temp_clip_path,
                '-vf', ','.join(filter_complex),
                '-c:a', 'copy',
                '-y', final_clip_path
            ]
        else:
            # Just copy if no filters
            os.rename(temp_clip_path, final_clip_path)
            process_cmd = None
        
        if process_cmd:
            result = subprocess.run(process_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Video processing failed: {result.stderr}")
        
        # Step 3: Upload to Firebase or serve locally
        firebase_url = firebase_utils.upload_to_storage(
            final_clip_path,
            f"clips/{clip_id}.mp4"
        )
        
        if firebase_url:
            # Clean up local files
            for path in [temp_clip_path, final_clip_path]:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except:
                    pass
            return {'success': True, 'url': firebase_url}
        else:
            # Return local static URL
            # Clean up temp file
            try:
                if os.path.exists(temp_clip_path):
                    os.remove(temp_clip_path)
            except:
                pass
            return {'success': True, 'url': f"/static/generated/final_{clip_id}.mp4"}
            
    except Exception as e:
        # Clean up any temp files
        for path in [temp_clip_path, final_clip_path]:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except:
                pass
        return {'success': False, 'error': str(e)}

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