# app/services/video_engine.py
import os
import subprocess
import shutil
import re
import uuid
from PIL import Image # For image saving
import time # For unique temp filenames (if needed outside uuid)

try:
    import torch
    from diffusers import DiffusionPipeline
    DIFFUSERS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Warning: Could not import diffusers: {e}")
    DIFFUSERS_AVAILABLE = False
except Exception as e:
    print(f"⚠️ Warning: CUDA/xFormers compatibility issue or other error with diffusers import: {e}")
    DIFFUSERS_AVAILABLE = False

# Use the correct import path for the new structure
from app.services import utils
from app.services import firebase_utils # <-- ADDED IMPORT
from app.core.config import settings # <-- ADDED IMPORT


# Define static directories (matching main.py and settings.py)
STATIC_FILES_ROOT_DIR = settings.STATIC_FILES_ROOT_DIR
STATIC_GENERATED_DIR = settings.STATIC_GENERATED_DIR # This is 'static/generated'
TEMP_DOWNLOAD_DIR = utils.TEMP_DOWNLOAD_DIR # Use the shared temp directory from utils
os.makedirs(STATIC_GENERATED_DIR, exist_ok=True) # Ensure the main generated directory exists


class LocalStableDiffusionGenerator:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(LocalStableDiffusionGenerator, cls).__new__(cls)
            cls._instance.pipeline = None
            cls._instance.is_model_loaded = False
        return cls._instance

    def load_model(self):
        if not DIFFUSERS_AVAILABLE:
            return False, "Diffusers library not available or CUDA/xFormers compatibility issue."
        if self._instance.is_model_loaded: return True, "Model already loaded."
        
        try:
            print("Loading Stable Diffusion model to GPU...");
            self._instance.pipeline = DiffusionPipeline.from_pretrained(
                "SG161222/RealVisXL_V4.0",
                torch_dtype=torch.float16,
                use_safetensors=True,
                variant="fp16"
            ).to("cuda")
            self._instance.pipeline.enable_model_cpu_offload()
            self._instance.is_model_loaded = True
            return True, "Model loaded successfully."
        except Exception as e:
            self._instance.pipeline = None
            self._instance.is_model_loaded = False
            return False, str(e)

    def generate_image(self, prompt: str, width: int = 1024, height: int = 1024) -> str | None:
        if not self.pipeline:
            print("❌ Stable Diffusion pipeline not loaded. Attempting to load now.")
            success, msg = self.load_model()
            if not success:
                print(f"❌ Failed to load model for generation: {msg}")
                return None

        temp_image_path = None
        try:
            p_prompt = f"cinematic shot, masterpiece, 4k, photorealistic, {prompt}"
            n_prompt = "deformed, ugly, blurry, low quality, cartoon, anime, disfigured, bad hands"
            
            image: Image.Image = self.pipeline(prompt=p_prompt, negative_prompt=n_prompt, width=width, height=height, num_inference_steps=25).images[0]
            
            # Save to a temporary location before uploading
            temp_image_filename = f"temp_thumbnail_{uuid.uuid4().hex}.png"
            temp_image_path = os.path.join(TEMP_DOWNLOAD_DIR, temp_image_filename) # Use TEMP_DOWNLOAD_DIR
            image.save(temp_image_path)
            
            # --- UPLOAD TO FIREBASE ---
            destination_blob_name = f"thumbnails/{temp_image_filename}" # Path in Firebase Storage
            public_url = firebase_utils.upload_to_storage(temp_image_path, destination_blob_name)
            
            return public_url
        except Exception as e:
            print(f"❌ Image generation or upload failed: {e}")
            return None
        finally:
            if temp_image_path and os.path.exists(temp_image_path):
                try:
                    os.remove(temp_image_path)
                    print(f"Cleaned up local temp image: {temp_image_path}")
                except OSError as e:
                    print(f"Error removing temp image file {temp_image_path}: {e}")

sd_generator = LocalStableDiffusionGenerator()

def _is_safe_path(path):
    # Only allow alphanumeric, dash, underscore, dot, and forward/backslash
    return bool(re.match(r'^[\w\-./:\\]+$', path))

def create_ass_file(words_data, output_path):
    style_header = "[V4+ Styles]"
    style_format = "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"
    style_values = f"Style: Default,Impact,48,&H00FFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,1,2,10,10,20,1"
    event_header = "[Events]"
    event_format = "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("[Script Info]\nTitle: Generated by Alchemize AI\n\n")
        f.write(f"{style_header}\n{style_format}\n{style_values}\n\n")
        f.write(f"{event_header}\n{event_format}\n")

        for word_info in words_data:
            start_time = f"{int(word_info['start'] // 3600)}:{int((word_info['start'] % 3600) // 60):02}:{word_info['start'] % 60:05.2f}"
            end_time = f"{int(word_info['end'] // 3600)}:{int((word_info['end'] % 3600) // 60):02}:{word_info['end'] % 60:05.2f}"
            text = word_info['word'].upper().replace('"', '\\"').replace('{', '\\{').replace('}', '\\}')
            dialogue_line = f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,," + "{\\c&H00FFFF&}" + text
            f.write(dialogue_line + "\n")

# Modified: output_path is now a filename, full path is constructed inside
# This function still returns a local path, which will be uploaded by process_single_clip
def render_clip_with_ffmpeg(input_path, output_filename, aspect_ratio="9:16", add_captions=False, words_data=None, add_music=False):
    ass_path = None
    
    # Construct the full output path within the STATIC_GENERATED_DIR (which is a local temp staging dir now)
    full_output_path = os.path.join(STATIC_GENERATED_DIR, output_filename)

    # Basic safety check for paths
    for p in [input_path, full_output_path]:
        if not _is_safe_path(p):
            raise ValueError(f"Unsafe file path detected: {p}")
            
    try:
        video_input = ["-i", input_path]
        audio_input_path = utils.get_background_music()
        if add_music and audio_input_path:
             music_input = ["-i", audio_input_path]
             audio_map = "[1:a]volume=0.1[music];[0:a][music]amix=inputs=2[outa]"
             audio_output_map = ["-map", "[outa]"]
        else:
            music_input = []
            audio_map = ""
            audio_output_map = ["-map", "0:a?"]

        w, h = map(int, aspect_ratio.split(':'))
        crop_filter = f"crop=ih*{w}/{h}:ih"
        
        subtitle_filter = ""
        if add_captions and words_data:
            ass_path = os.path.join(TEMP_DOWNLOAD_DIR, f"temp_captions_{uuid.uuid4().hex}.ass") # Use TEMP_DOWNLOAD_DIR for subtitles
            if not _is_safe_path(ass_path):
                raise ValueError(f"Unsafe temp file path for subtitles: {ass_path}")
            create_ass_file(words_data, ass_path)
            subtitle_filter = f",subtitles={ass_path}:force_style='FontName=Impact,FontSize=48'"
            
        filter_complex = f"[0:v]{crop_filter},scale=1080:-2{subtitle_filter}[outv]"
        if audio_map:
            filter_complex = f"{audio_map};{filter_complex}"

        # Try CUDA first
        command_cuda = [
            "ffmpeg", "-hwaccel", "cuda", *video_input, *music_input,
            "-filter_complex", filter_complex, "-map", "[outv]", *audio_output_map,
            "-c:v", "h264_nvenc", "-preset", "p5", "-cq", "24", "-y", full_output_path
        ]
        
        print(f"🚀 Executing FFmpeg command with CUDA acceleration for {output_filename}...")
        try:
            result = subprocess.run(command_cuda, check=True, capture_output=True, text=True, timeout=300)
            print(f"✅ FFmpeg rendering complete with CUDA: {full_output_path}")
            print("FFmpeg stdout:", result.stdout)
            print("FFmpeg stderr:", result.stderr)
            return True, full_output_path # Return the full local path for success
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            error_output = e.stderr if hasattr(e, 'stderr') else str(e)
            print(f"⚠️ CUDA rendering failed for {output_filename}: {e}. Falling back to CPU. FFmpeg Error: {error_output}")
            
            # CPU Fallback
            command_cpu = [
                "ffmpeg", *video_input, *music_input,
                "-filter_complex", filter_complex, "-map", "[outv]", *audio_output_map,
                "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-y", full_output_path
            ]
            
            print(f"🚀 Executing FFmpeg command with CPU rendering for {output_filename}...")
            result = subprocess.run(command_cpu, check=True, capture_output=True, text=True, timeout=300)
            print(f"✅ FFmpeg rendering complete with CPU: {full_output_path}")
            print("FFmpeg stdout:", result.stdout)
            print("FFmpeg stderr:", result.stderr)
            return True, full_output_path # Return the full local path for success

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        error_output = e.stderr if hasattr(e, 'stderr') else str(e)
        print(f"❌ FFmpeg Error for {output_filename}: {error_output}")
        return False, f"FFmpeg failed: {error_output[:500]}"
    except Exception as e:
        # Catch any other unexpected errors during setup/execution
        return False, f"An unexpected error occurred during rendering: {e}"
    finally:
        if ass_path and os.path.exists(ass_path):
            try:
                os.remove(ass_path)
                print(f"Cleaned up local temp subtitle file: {ass_path}")
            except OSError as e:
                print(f"Error removing temp subtitle file {ass_path}: {e}")

# Modified: process_single_clip now uploads to Firebase and returns the public URL.
# It also receives full_words_data to filter for the relevant words.
def process_single_clip(source_video_path, moment, flags, user_id, index, full_words_data):
    # Temp path for the initial cut video
    base_clip_filename = f"temp_cut_clip_{user_id}_{index}_{uuid.uuid4().hex}.mp4"
    base_clip_path = os.path.join(TEMP_DOWNLOAD_DIR, base_clip_filename)
    
    # Final filename for the rendered clip (will be uploaded)
    final_clip_filename = f"clip_{user_id}_{index}_{uuid.uuid4().hex}.mp4" 
    
    local_rendered_clip_path = None
    try:
        if not utils.cut_video_clip(source_video_path, moment['start'], moment['duration'], base_clip_path):
            raise IOError("Failed to cut base clip.")
            
        clip_words_data = None
        if flags.get('add_captions', False):
            print(f"Transcribing clip {index} for captions...")
            # Filter the full words data to get only words relevant to this clip's time range
            clip_words_data = [
                word_info for word_info in full_words_data
                if word_info['start'] >= moment['start'] and word_info['end'] <= moment['start'] + moment['duration']
            ]
            if not clip_words_data:
                print(f"Warning: No word-level timestamps found for clip {index} within its time range.")

        # Call render_clip_with_ffmpeg which saves to STATIC_GENERATED_DIR locally
        success, local_rendered_clip_path = render_clip_with_ffmpeg(
            input_path=base_clip_path, 
            output_filename=final_clip_filename, # Pass just the filename
            aspect_ratio=flags.get('aspect_ratio', "9:16"), 
            add_captions=flags.get('add_captions', False),
            words_data=clip_words_data, # Pass filtered words data
            add_music=flags.get('add_music', False)
        )
        
        if success and local_rendered_clip_path:
            # --- UPLOAD TO FIREBASE ---
            destination_blob_name = f"videoclips/{final_clip_filename}" # Path in Firebase Storage
            public_url = firebase_utils.upload_to_storage(local_rendered_clip_path, destination_blob_name)
            
            if public_url:
                return {'success': True, 'url': public_url}
            else:
                raise Exception("Failed to upload clip to Firebase Storage.")
        else:
            raise RuntimeError(f"FFmpeg rendering failed for {final_clip_filename}: {local_rendered_clip_path}")

    except Exception as e:
        import traceback
        print(f"Error processing clip {index}: {e}")
        print(traceback.format_exc())
        return {'success': False, 'error': str(e)}
    finally:
        # Clean up temporary files
        if os.path.exists(base_clip_path):
            try:
                os.remove(base_clip_path)
                print(f"Cleaned up local temp base clip: {base_clip_path}")
            except OSError as e:
                print(f"Error removing temp base clip file {base_clip_path}: {e}")
        if local_rendered_clip_path and os.path.exists(local_rendered_clip_path):
            try:
                os.remove(local_rendered_clip_path)
                print(f"Cleaned up local rendered clip: {local_rendered_clip_path}")
            except OSError as e:
                print(f"Error removing local rendered clip file {local_rendered_clip_path}: {e}")