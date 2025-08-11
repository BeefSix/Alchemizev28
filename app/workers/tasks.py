import subprocess
import os
import json
import logging
import glob
import gc
import psutil
import tempfile
from datetime import datetime, timedelta
from contextlib import contextmanager

from app.celery_app import celery_app
from app.db import crud
from app.db.base import get_db_session
from app.services import video_engine, utils
from app.core.config import settings
from celery.exceptions import Retry
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Memory management utilities
@contextmanager
def memory_monitor(job_id: str, max_memory_mb: int = 2048):
    """Monitor memory usage during video processing"""
    process = psutil.Process()
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    logger.info(f"Job {job_id}: Initial memory usage: {initial_memory:.1f}MB")
    
    try:
        yield
    finally:
        # Force garbage collection
        gc.collect()
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_diff = final_memory - initial_memory
        
        logger.info(f"Job {job_id}: Final memory usage: {final_memory:.1f}MB (diff: {memory_diff:+.1f}MB)")
        
        if final_memory > max_memory_mb:
            logger.warning(f"Job {job_id}: High memory usage detected: {final_memory:.1f}MB")

def cleanup_temp_files(*file_paths):
    """Safely clean up temporary files"""
    for file_path in file_paths:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Cleaned up temp file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up {file_path}: {e}")

def check_disk_space(path: str, required_mb: int = 1024) -> bool:
    """Check if there's enough disk space for processing"""
    try:
        free_space = psutil.disk_usage(path).free / 1024 / 1024  # MB
        return free_space > required_mb
    except Exception:
        return True  # Assume OK if check fails

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60}, retry_backoff=True)
def run_videoclip_upload_job(self, job_id: str, user_id: int, video_path: str, add_captions: bool, aspect_ratio: str, platforms: list[str]):
    """Process uploaded video and create clips with live karaoke-style captions."""
    audio_path = None
    temp_files = []  # Track temporary files for cleanup
    
    with memory_monitor(job_id, max_memory_mb=4096):  # 4GB limit
        try:
            logger.info(f"🎬 Starting video job {job_id} for user {user_id}")
            logger.info(f"📋 Parameters: add_captions={add_captions}, aspect_ratio={aspect_ratio}")
            
            # STEP 1: Enhanced file validation and disk space check
            if not os.path.exists(video_path):
                raise ValueError(f"Video file not found: {video_path}")
            
            file_size = os.path.getsize(video_path)
            if file_size < 1024:  # Less than 1KB
                raise ValueError(f"Video file too small: {file_size} bytes")
            
            # Check disk space (require 3x file size for processing)
            required_space_mb = (file_size * 3) / (1024 * 1024)
            if not check_disk_space(os.path.dirname(video_path), required_space_mb):
                raise ValueError(f"Insufficient disk space. Required: {required_space_mb:.1f}MB")
            
            logger.info(f"📹 Video file: {video_path} ({file_size:,} bytes)")
            
            # Update initial status
            with get_db_session() as db:
                crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                    progress_details={"description": "Validating video file...", "percentage": 5})

            # STEP 2: Enhanced video info extraction with better error handling
            info_cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', video_path]
            logger.info(f"🔍 Running: {' '.join(info_cmd)}")
            
            result = subprocess.run(info_cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                logger.error(f"❌ ffprobe failed: {result.stderr}")
                raise ValueError(f"Invalid video file - ffprobe error: {result.stderr}")
        
            video_info = json.loads(result.stdout)
            duration = float(video_info['format']['duration'])
            logger.info(f"📹 Video duration: {duration:.1f} seconds")

            # STEP 3: Enhanced audio extraction and transcription
            words_data = []
            captions_actually_added = False
        
            if add_captions:
                logger.info(f"🎤 Starting caption processing...")
                
                # Verify OpenAI client is available
                if not utils.client:
                    logger.error("❌ OpenAI client not configured - check OPENAI_API_KEY")
                    add_captions = False
                else:
                    with get_db_session() as db:
                        crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                            progress_details={"description": "Extracting audio for captions...", "percentage": 15})
                    
                    # Create audio file path
                    audio_path = os.path.join(os.path.dirname(video_path), f"{job_id}_audio.wav")
                    temp_files.append(audio_path)  # Track for cleanup
                    
                    # Enhanced audio extraction command with better settings for hour-long videos
                    max_audio_duration = min(duration, settings.VIDEO_PROCESSING['max_audio_duration'])
                    extract_cmd = [
                        'ffmpeg', '-y',
                        '-i', video_path,
                        '-vn',  # No video
                        '-acodec', 'pcm_s16le',  # Better quality for Whisper
                        '-ar', '16000',  # 16kHz sample rate
                        '-ac', '1',  # Mono
                        '-t', str(max_audio_duration),  # Support up to 1 hour
                        audio_path
                    ]
                    
                    logger.info(f"🔧 Extracting audio ({max_audio_duration:.1f}s): {' '.join(extract_cmd)}")
                    result = subprocess.run(extract_cmd, capture_output=True, text=True, 
                                          timeout=settings.VIDEO_PROCESSING['audio_extraction_timeout'])
                    
                    if result.returncode != 0:
                        logger.error(f"❌ Audio extraction failed: {result.stderr}")
                        logger.error(f"❌ Audio extraction stdout: {result.stdout}")
                        add_captions = False
                    elif not os.path.exists(audio_path):
                        logger.error(f"❌ Audio file not created: {audio_path}")
                        add_captions = False
                    else:
                        audio_size = os.path.getsize(audio_path)
                        logger.info(f"✅ Audio extracted: {audio_path} ({audio_size:,} bytes)")
                    
                    # ENHANCED transcription with better error handling
                    with get_db_session() as db:
                        crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                            progress_details={"description": "Transcribing audio with Whisper...", "percentage": 30})
                    
                    logger.info(f"🎤 Starting transcription...")
                    transcript_result = utils.transcribe_local_audio_file_sync(audio_path, user_id, job_id)
                    
                    if transcript_result and transcript_result.get('success'):
                        transcript_data = transcript_result.get('data', {})
                        words_data = transcript_data.get('words', [])
                        logger.info(f"🎉 Transcription complete: {len(words_data)} words")
                        
                        if len(words_data) > 0:
                            captions_actually_added = True
                            logger.info(f"✅ Captions will be added to clips")
                        else:
                            logger.warning(f"⚠️ No words in transcription")
                            add_captions = False
                    else:
                        error_msg = transcript_result.get('error', 'Unknown transcription error') if transcript_result else 'No transcription response'
                        logger.error(f"❌ Transcription failed: {error_msg}")
                        add_captions = False
            else:
                logger.info(f"🚫 Captions disabled by user")

            # STEP 4: Generate clips with enhanced progress tracking and atomic operations
            with get_db_session() as db:
                db.begin()
                try:
                    crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                        progress_details={"description": "Creating video clips...", "percentage": 50})
                    db.commit()
                except Exception as e:
                    db.rollback()
                    logger.warning(f"Failed to update progress: {e}")

            # Calculate clip parameters - IMPROVED: Better logic for short videos
            clip_duration = min(60, max(15, duration * 0.4))  # 15-60 seconds
            # Enhanced logic: Always generate at least 1 clip, better scaling
            if duration < 15:
                num_clips = 1  # Always create 1 clip for very short videos
                clip_duration = max(5, duration * 0.8)  # Use most of the video for very short clips
            else:
                num_clips = min(5, max(1, int(duration // 20)))  # 1 clip per 20 seconds, max 5
            
            logger.info(f"📊 Will create {num_clips} clips of {clip_duration:.1f}s each")
            logger.info(f"🎤 Captions enabled: {add_captions}, Words available: {len(words_data)}")
            
            # STEP 4.1: AI-Powered Viral Moment Detection
            moments = []
            if words_data and len(words_data) > 0:
                logger.info(f"🤖 Using AI to detect viral moments from transcript...")
                try:
                    # Create text chunks from transcript for viral analysis
                    chunk_size = 50  # words per chunk
                    text_chunks = []
                    chunk_timestamps = []
                    
                    for i in range(0, len(words_data), chunk_size):
                        chunk_words = words_data[i:i + chunk_size]
                        if chunk_words:
                            chunk_text = ' '.join([word.get('word', '') for word in chunk_words])
                            text_chunks.append(chunk_text)
                            
                            # Store start and end times for this chunk
                            start_time = chunk_words[0].get('start', 0)
                            end_time = chunk_words[-1].get('end', start_time + 30)
                            chunk_timestamps.append({'start': start_time, 'end': end_time})
                    
                    # Analyze chunks for viral potential
                    if text_chunks:
                        viral_indices = utils.analyze_content_chunks_sync(text_chunks, user_id)
                        logger.info(f"🔥 Found {len(viral_indices)} viral moments from {len(text_chunks)} chunks")
                        
                        # Convert viral chunk indices to video moments
                        for idx in viral_indices[:num_clips]:  # Limit to requested number of clips
                            if idx < len(chunk_timestamps):
                                chunk_time = chunk_timestamps[idx]
                                # Center the clip around the viral moment
                                center_time = (chunk_time['start'] + chunk_time['end']) / 2
                                start_time = max(0, center_time - clip_duration / 2)
                                start_time = min(start_time, duration - clip_duration)
                                
                                moments.append({
                                    'start': start_time,
                                    'duration': clip_duration,
                                    'viral_score': 'high',
                                    'source': 'ai_analysis'
                                })
                        
                        logger.info(f"✨ Generated {len(moments)} AI-detected viral moments")
                    
                except Exception as e:
                    logger.error(f"❌ AI viral detection failed: {e}")
                    moments = []  # Fall back to evenly spaced clips
            
            # Fallback to evenly spaced clips if AI detection failed or no transcript
            if not moments:
                logger.info(f"📐 Falling back to evenly spaced clips")
                for i in range(num_clips):
                    # Distribute clips evenly across the video
                    start_time = (duration / (num_clips + 1)) * (i + 1) - (clip_duration / 2)
                    start_time = max(0, min(start_time, duration - clip_duration))
                    
                    moments.append({
                        'start': start_time,
                        'duration': clip_duration,
                        'viral_score': 'medium',
                        'source': 'evenly_spaced'
                    })
            
            clips_created = []
        
            for i, moment in enumerate(moments):
                
                logger.info(f"🎬 Processing clip {i+1}/{len(moments)} at {moment['start']:.1f}s (source: {moment.get('source', 'unknown')})")
                
                # Update progress
                progress = 50 + (i / len(moments)) * 40  # 50-90%
                with get_db_session() as db:
                    crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                        progress_details={"description": f"Processing clip {i+1}/{len(moments)}...", "percentage": progress})
                
                # Process single clip with GPU acceleration
                result = video_engine.process_single_clip_gpu(
                    source_video_path=video_path,
                    moment=moment,
                    flags={
                        'add_captions': add_captions,
                        'aspect_ratio': aspect_ratio,
                        'platforms': platforms
                    },
                    user_id=user_id,
                    clip_id=f"{job_id}_clip_{i+1}",
                    words_data=words_data
                )
                
                if result['success']:
                    # Add viral detection metadata to result
                    result['viral_info'] = {
                        'source': moment.get('source', 'unknown'),
                        'viral_score': moment.get('viral_score', 'unknown'),
                        'start_time': moment['start'],
                        'duration': moment['duration']
                    }
                    clips_created.append(result)
                    logger.info(f"✅ Clip {i+1} created successfully (source: {moment.get('source', 'unknown')})")
                    logger.info(f"🎤 Clip {i+1} captions: {result.get('captions_added', False)}")
                else:
                    logger.error(f"❌ Clip {i+1} failed: {result.get('error', 'Unknown error')}")
                    # Continue with other clips instead of failing completely

            # Cleanup temporary files
            cleanup_temp_files(*temp_files)

            if not clips_created:
                raise ValueError("No clips were successfully generated")

            # STEP 5: Create final results with proper structure for frontend compatibility
            results = {
                "clips_by_platform": {
                    "all": clips_created,  # ✅ CRITICAL: Frontend expects this exact key
                    "all_platforms": clips_created,  # Keep for backward compatibility
                    "TikTok": clips_created,
                    "Instagram": clips_created,
                    "YouTube": clips_created
                },
                "total_clips": len(clips_created),
                "video_duration": duration,
                "captions_added": captions_actually_added,
                "transcript": {
                    "words": words_data
                } if words_data else {},
                "processing_details": {
                    "aspect_ratio": aspect_ratio,
                    "clip_duration": clip_duration,
                    "karaoke_words": len(words_data),
                    "caption_type": "live_karaoke" if captions_actually_added else "none",
                    "original_file_size": file_size,
                    "audio_extracted": audio_path is not None and os.path.exists(audio_path) if audio_path else False,
                    "processing_method": video_engine.FFMPEG_CONFIG.get('type', 'unknown'),  # Show actual GPU status
                    "clip_selection_method": "ai_viral_detection" if any(clip.get('viral_info', {}).get('source') == 'ai_analysis' for clip in clips_created) else "evenly_spaced",
                    "viral_moments_detected": len([clip for clip in clips_created if clip.get('viral_info', {}).get('source') == 'ai_analysis']),
                    "transcript_available": len(words_data) > 0
                }
            }

            logger.info(f"📋 Final results: total_clips={len(clips_created)}, captions={captions_actually_added}")

            # Atomic database update for job completion
            with get_db_session() as db:
                db.begin()
                try:
                    crud.update_job_full_status(db, job_id, "COMPLETED", 
                        progress_details={
                            "description": f"🎉 Generated {len(clips_created)} clips" + (f" with live karaoke captions!" if captions_actually_added else "!"), 
                            "percentage": 100
                        },
                        results=results)
                    db.commit()
                    logger.info(f"🎉 Video job {job_id} completed successfully")
                except Exception as e:
                    db.rollback()
                    logger.error(f"Failed to update job completion status: {e}")
                    raise

        except Exception as e:
            error_msg = f"Video processing failed: {str(e)}"
            logger.error(f"❌ Video job {job_id} failed: {error_msg}")
            logger.exception("Full error traceback:")
            
            # Categorize errors for retry logic
            retryable_errors = [
                "Connection", "timeout", "network", "temporary", "busy", "locked",
                "ffmpeg", "GPU", "memory", "disk space", "permission denied"
            ]
            
            is_retryable = any(keyword.lower() in str(e).lower() for keyword in retryable_errors)
            
            if is_retryable and self.request.retries < self.max_retries:
                logger.warning(f"🔄 Retrying job {job_id} (attempt {self.request.retries + 1}/{self.max_retries})")
                # Atomic database update for retry status
                with get_db_session() as db:
                    db.begin()
                    try:
                        crud.update_job_full_status(db, job_id, "RETRYING", 
                            error_message=f"Retry {self.request.retries + 1}: {error_msg}")
                        db.commit()
                    except Exception as db_error:
                        db.rollback()
                        logger.error(f"Failed to update retry status: {db_error}")
                raise self.retry(countdown=60 * (2 ** self.request.retries))  # Exponential backoff
            
            # Mark as permanently failed with atomic transaction
            with get_db_session() as db:
                db.begin()
                try:
                    crud.update_job_full_status(db, job_id, "FAILED", error_message=error_msg)
                    db.commit()
                except Exception as db_error:
                    db.rollback()
                    logger.error(f"Failed to update failure status: {db_error}")
            raise
        
        finally:
            # Enhanced cleanup with memory management
            try:
                # Clean up temporary files
                cleanup_temp_files(*temp_files)
                
                # Force garbage collection to free memory
                gc.collect()
                
                # Log final memory usage
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                logger.info(f"🧹 Cleanup complete. Final memory usage: {memory_mb:.1f}MB")
                
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")


def run_videoclip_upload_job_sync(job_id: str, user_id: int, video_path: str, add_captions: bool, aspect_ratio: str, platforms: list[str]):
    """Synchronous version of video processing job for when Redis/Celery is not available."""
    audio_path = None
    temp_files = []  # Track temporary files for cleanup
    
    try:
        logger.info(f"🎬 Starting sync video job {job_id} for user {user_id}")
        logger.info(f"📋 Parameters: add_captions={add_captions}, aspect_ratio={aspect_ratio}")
        
        # STEP 1: Enhanced file validation and disk space check
        if not os.path.exists(video_path):
            raise ValueError(f"Video file not found: {video_path}")
        
        file_size = os.path.getsize(video_path)
        if file_size < 1024:  # Less than 1KB
            raise ValueError(f"Video file too small: {file_size} bytes")
        
        logger.info(f"📹 Video file: {video_path} ({file_size:,} bytes)")
        
        # Update initial status
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                progress_details={"description": "Validating video file...", "percentage": 5})

        # STEP 2: Enhanced video info extraction with better error handling
        info_cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', video_path]
        logger.info(f"🔍 Running: {' '.join(info_cmd)}")
        
        result = subprocess.run(info_cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logger.error(f"❌ ffprobe failed: {result.stderr}")
            raise ValueError(f"Invalid video file - ffprobe error: {result.stderr}")
    
        video_info = json.loads(result.stdout)
        duration = float(video_info['format']['duration'])
        logger.info(f"📹 Video duration: {duration:.1f} seconds")

        # STEP 3: Basic processing without advanced features for sync mode
        words_data = []
        captions_actually_added = False
    
        if add_captions:
            logger.info(f"🎤 Starting caption processing...")
            
            # Verify OpenAI client is available
            if not utils.client:
                logger.error("❌ OpenAI client not configured - check OPENAI_API_KEY")
                raise ValueError("OpenAI API key not configured")
            
            with get_db_session() as db:
                crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                    progress_details={"description": "Extracting audio for transcription...", "percentage": 15})
            
            # Extract audio for transcription
            audio_path = video_path.replace('.mkv', '_audio.wav').replace('.mp4', '_audio.wav')
            temp_files.append(audio_path)
            
            audio_cmd = [
                'ffmpeg', '-i', video_path, '-vn', '-acodec', 'pcm_s16le', 
                '-ar', '16000', '-ac', '1', '-y', audio_path
            ]
            
            result = subprocess.run(audio_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning(f"⚠️ Audio extraction failed: {result.stderr}")
                add_captions = False
            else:
                logger.info(f"🎵 Audio extracted: {audio_path}")
                
                # Transcribe with OpenAI Whisper
                with get_db_session() as db:
                    crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                        progress_details={"description": "Transcribing audio with AI...", "percentage": 30})
                
                try:
                    with open(audio_path, 'rb') as audio_file:
                        transcript = utils.client.audio.transcriptions.create(
                            model="whisper-1",
                            file=audio_file,
                            response_format="verbose_json",
                            timestamp_granularities=["word"]
                        )
                    
                    if hasattr(transcript, 'words') and transcript.words:
                        words_data = [{
                            'word': word.word,
                            'start': word.start,
                            'end': word.end
                        } for word in transcript.words]
                        captions_actually_added = True
                        logger.info(f"✅ Transcription complete: {len(words_data)} words")
                    else:
                        logger.warning("⚠️ No word-level timestamps in transcription")
                        add_captions = False
                        
                except Exception as e:
                    logger.error(f"❌ Transcription failed: {e}")
                    add_captions = False
        
        # STEP 4: Video processing with clips
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                progress_details={"description": "Creating video clips...", "percentage": 50})
        
        # Use video engine for processing
        output_files = video_engine.process_video_sync(
            video_path=video_path,
            job_id=job_id,
            user_id=user_id,
            add_captions=captions_actually_added,
            aspect_ratio=aspect_ratio,
            platforms=platforms,
            words_data=words_data
        )
        
        # STEP 5: Create proper results structure for frontend compatibility
        results = {
            "clips_by_platform": {
                "all": output_files,  # ✅ CRITICAL: Frontend expects this exact key
                "all_platforms": output_files,  # Keep for backward compatibility
                "TikTok": output_files,
                "Instagram": output_files,
                "YouTube": output_files
            },
            "total_clips": len(output_files),
            "video_duration": duration,
            "captions_added": captions_actually_added,
            "transcript": {
                "words": words_data
            } if words_data else {},
            "processing_details": {
                "aspect_ratio": aspect_ratio,
                "processing_method": "sync_mode",
                "captions_added": captions_actually_added
            }
        }
        
        # Finalize job with proper results structure
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "COMPLETED", 
                progress_details={
                    "description": f"🎉 Generated {len(output_files)} clips" + (f" with captions!" if captions_actually_added else "!"), 
                    "percentage": 100
                },
                results=results)
        
        logger.info(f"✅ Sync video job {job_id} completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Sync video job {job_id} failed: {str(e)}")
        
        # Update job status to failed
        try:
            with get_db_session() as db:
                crud.update_job_full_status(db, job_id, "FAILED", 
                    progress_details={
                        "description": f"Processing failed: {str(e)}", 
                        "percentage": 0,
                        "error": str(e)
                    })
        except Exception as db_error:
            logger.error(f"Failed to update job status: {db_error}")
        
        return False
        
    finally:
        try:
            # Clean up temporary files
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    logger.info(f"🧹 Cleaned up: {temp_file}")
            
            # Force garbage collection to free memory
            gc.collect()
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def run_content_repurpose_job_sync(job_id: str, user_id: int, content_input: str, platforms: list[str], tone: str, style: str, additional_instructions: str):
    """Synchronous version of content repurpose job for when Redis/Celery is not available."""
    try:
        logger.info(f"Starting content job {job_id} for user {user_id}")
        
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                progress_details={"description": "Ingesting content...", "percentage": 5})
        
        # Ingest content (handles URLs or raw text)
        content_to_process = utils.ingest_content(content_input)
        if not content_to_process or content_to_process.startswith("Error:"):
            raise ValueError(f"Failed to ingest content: {content_to_process}")

        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                progress_details={"description": "Analyzing content...", "percentage": 20})
        
        # Analyze content
        analysis_prompt = f"""Analyze the provided content in depth. Identify and summarize:

Core message & main themes (the underlying ideas driving the content)

Target audience (demographics, interests, pain points, and motivations)

Tone & voice (formal/informal, playful/serious, authoritative/conversational)

Engagement drivers (specific hooks, emotions, formats, or storytelling techniques that make it compelling)

Then:

Explain why these elements work together to capture attention.

Suggest how they could be adapted for social media to preserve authenticity while maximizing engagement on different platforms.
        
        CONTENT:
        {content_to_process[:4000]}"""
        
        content_analysis = utils.run_ai_generation_sync(analysis_prompt, user_id, model="gpt-4o")
        if not content_analysis: 
            raise Exception("AI content analysis failed - check your OpenAI API key and credits.")
        
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                progress_details={"description": "Generating social media posts...", "percentage": 60})
        
        # Generate content for platforms
        platform_str = ", ".join(platforms)
        generation_prompt = f"""You are an expert-level social media content strategist and copywriter with a deep understanding of how creators speak naturally to their audiences. Transform the provided content into posts for {platform_str}, ensuring each one feels like it was written by a real creator, not a brand or marketer.

TONE: {tone}
STYLE: {style}
ADDITIONAL INSTRUCTIONS: {additional_instructions}

GUIDELINES:

Make every post platform-native, using formatting, pacing, and language that matches how real creators post there.

Avoid generic marketing speak or overly polished "ad" language—favor authenticity, relatability, and audience connection.

Embed subtle personality quirks, casual language, or creator habits that make posts feel human.

Platform Breakdown:

LinkedIn: Professional but human; thought-provoking with a personal takeaway. Use bullet points or short paragraphs for scanability.

Twitter/X: Concise, hook-first. Use threads where needed. Blend wit, insight, or curiosity gaps to encourage replies.

Instagram: Tell a story in a visual way. Break text for readability. Include 5–10 hashtags relevant to the niche.

TikTok: Write as if scripting a creator's voiceover or caption. Use trending hook styles and natural speech flow.

YouTube: Write engaging, SEO-aware video descriptions that encourage watch time and subscriptions, without feeling keyword-stuffed.

Facebook: Conversational, community-driven, and designed to spark discussion. Reference shared experiences or relatable moments.

SOURCE CONTENT:
{content_to_process[:8000]}

Generate compelling posts for each platform. Use markdown headings to separate platforms (e.g., ## LinkedIn, ## Twitter, ## YouTube, ## Facebook)."""
        
        drafts = utils.run_ai_generation_sync(generation_prompt, user_id, model="gpt-4o", max_tokens=3000)
        if not drafts: 
            raise Exception("AI content generation failed - check your OpenAI API key and credits.")
        
        results = {
            "analysis": content_analysis, 
            "posts": drafts,
            "platforms": platforms,
            "settings": {
                "tone": tone,
                "style": style,
                "additional_instructions": additional_instructions
            }
        }
        
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "COMPLETED", 
                progress_details={"description": "Content suite generated!", "percentage": 100}, 
                results=results)

        logger.info(f"Content job {job_id} completed successfully")

    except Exception as e:
        logger.error(f"Content job {job_id} failed: {str(e)}")
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "FAILED", 
                error_message=f"Content repurposing failed: {str(e)}")
        raise

@celery_app.task(bind=True)
def monitoring_task(self):
    """Continuous monitoring task that runs every minute"""
    from app.services.monitoring import monitor
    
    try:
        logger.info("Running monitoring check...")
        
        # Collect metrics
        metrics = monitor.collect_system_metrics()
        if not metrics:
            logger.error("Failed to collect system metrics")
            return
        
        # Analyze and send alerts
        alerts = monitor.analyze_metrics(metrics)
        alerts_sent = 0
        
        for alert in alerts:
            if monitor.send_alert(alert):
                alerts_sent += 1
        
        # Log summary
        logger.info(
            f"Monitoring check complete - "
            f"CPU: {metrics.cpu_percent:.1f}%, "
            f"Memory: {metrics.memory_percent:.1f}%, "
            f"Disk: {metrics.disk_percent:.1f}%, "
            f"Active Jobs: {metrics.active_jobs}, "
            f"Failed Jobs (24h): {metrics.failed_jobs_24h}, "
            f"Alerts Sent: {alerts_sent}"
        )
        
        return {
            "status": "success",
            "metrics_collected": True,
            "alerts_sent": alerts_sent,
            "system_status": {
                "cpu_percent": metrics.cpu_percent,
                "memory_percent": metrics.memory_percent,
                "disk_percent": metrics.disk_percent,
                "active_jobs": metrics.active_jobs,
                "failed_jobs_24h": metrics.failed_jobs_24h
            }
        }
        
    except Exception as e:
        logger.error(f"Monitoring task failed: {e}")
        return {"status": "error", "error": str(e)}

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 30}, retry_backoff=True)
def run_content_repurpose_job(self, job_id: str, user_id: int, content_input: str, platforms: list[str], tone: str, style: str, additional_instructions: str):
    """Generate repurposed content for multiple social media platforms."""
    try:
        logger.info(f"Starting content job {job_id} for user {user_id}")
        
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                progress_details={"description": "Ingesting content...", "percentage": 5})
        
        # Ingest content (handles URLs or raw text)
        content_to_process = utils.ingest_content(content_input)
        if not content_to_process or content_to_process.startswith("Error:"):
            raise ValueError(f"Failed to ingest content: {content_to_process}")

        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                progress_details={"description": "Analyzing content...", "percentage": 20})
        
        # Analyze content
        analysis_prompt = f"""Analyze the provided content in depth. Identify and summarize:

Core message & main themes (the underlying ideas driving the content)

Target audience (demographics, interests, pain points, and motivations)

Tone & voice (formal/informal, playful/serious, authoritative/conversational)

Engagement drivers (specific hooks, emotions, formats, or storytelling techniques that make it compelling)

Then:

Explain why these elements work together to capture attention.

Suggest how they could be adapted for social media to preserve authenticity while maximizing engagement on different platforms.
        
        CONTENT:
        {content_to_process[:4000]}"""
        
        content_analysis = utils.run_ai_generation_sync(analysis_prompt, user_id, model="gpt-4o")
        if not content_analysis: 
            raise Exception("AI content analysis failed - check your OpenAI API key and credits.")
        
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                progress_details={"description": "Generating social media posts...", "percentage": 60})
        
        # Generate content for platforms
        platform_str = ", ".join(platforms)
        generation_prompt = f"""You are an expert-level social media content strategist and copywriter with a deep understanding of how creators speak naturally to their audiences. Transform the provided content into posts for {platform_str}, ensuring each one feels like it was written by a real creator, not a brand or marketer.

TONE: {tone}
STYLE: {style}
ADDITIONAL INSTRUCTIONS: {additional_instructions}

GUIDELINES:

Make every post platform-native, using formatting, pacing, and language that matches how real creators post there.

Avoid generic marketing speak or overly polished "ad" language—favor authenticity, relatability, and audience connection.

Embed subtle personality quirks, casual language, or creator habits that make posts feel human.

Platform Breakdown:

LinkedIn: Professional but human; thought-provoking with a personal takeaway. Use bullet points or short paragraphs for scanability.

Twitter/X: Concise, hook-first. Use threads where needed. Blend wit, insight, or curiosity gaps to encourage replies.

Instagram: Tell a story in a visual way. Break text for readability. Include 5–10 hashtags relevant to the niche.

TikTok: Write as if scripting a creator's voiceover or caption. Use trending hook styles and natural speech flow.

YouTube: Write engaging, SEO-aware video descriptions that encourage watch time and subscriptions, without feeling keyword-stuffed.

Facebook: Conversational, community-driven, and designed to spark discussion. Reference shared experiences or relatable moments.

SOURCE CONTENT:
{content_to_process[:8000]}

Generate compelling posts for each platform. Use markdown headings to separate platforms (e.g., ## LinkedIn, ## Twitter, ## YouTube, ## Facebook)."""
        
        drafts = utils.run_ai_generation_sync(generation_prompt, user_id, model="gpt-4o", max_tokens=3000)
        if not drafts: 
            raise Exception("AI content generation failed - check your OpenAI API key and credits.")
        
        results = {
            "analysis": content_analysis, 
            "posts": drafts,
            "platforms": platforms,
            "settings": {
                "tone": tone,
                "style": style,
                "additional_instructions": additional_instructions
            }
        }
        
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "COMPLETED", 
                progress_details={"description": "Content suite generated!", "percentage": 100}, 
                results=results)

        logger.info(f"Content job {job_id} completed successfully")

    except Exception as e:
        logger.error(f"Content job {job_id} failed: {str(e)}")
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "FAILED", 
                error_message=f"Content repurposing failed: {str(e)}")
        raise

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 2, 'countdown': 30}, retry_backoff=True)
def generate_thumbnail_job(self, job_id: str, user_id: int, prompt_text: str):
    """Generate thumbnail images based on content."""
    try:
        logger.info(f"Starting thumbnail job {job_id} for user {user_id}")
        
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                progress_details={"description": "Generating thumbnail prompts...", "percentage": 10})

        # Generate image prompts
        prompt_gen_prompt = f'''Based on the following content, generate 3 striking visual prompts for thumbnail images.
        Return them as a JSON array of strings. Each prompt should be vivid, specific, and thumbnail-worthy.
        
        CONTENT: {prompt_text[:2000]}
        
        Return format: ["prompt1", "prompt2", "prompt3"]'''
        
        image_prompts = []
        for attempt in range(3):
            response_str = utils.run_ai_generation_sync(prompt_gen_prompt, user_id, "gpt-4o-mini", 500, expect_json=True)
            if response_str:
                try:
                    prompts = json.loads(response_str)
                    if isinstance(prompts, list) and prompts:
                        image_prompts = prompts
                        break
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Failed to parse prompts on attempt {attempt + 1}: {e}")
        
        if not image_prompts: 
            raise Exception("Failed to generate valid image prompts after 3 attempts.")
        
        # Generate images
        urls = []
        for i, prompt in enumerate(image_prompts):
            with get_db_session() as db:
                progress = 20 + int(((i + 1) / len(image_prompts)) * 75)
                crud.update_job_full_status(db, job_id, "IN_PROGRESS", 
                    progress_details={"description": f"Generating thumbnail {i+1}/{len(image_prompts)}...", "percentage": progress})

            url = video_engine.sd_generator.generate_image(prompt, 1280, 720)
            if url:
                urls.append(url)
                utils.track_usage("stable-diffusion-local", user_id, 'thumbnail', custom_cost=0.0)
            else:
                logger.warning(f"Failed to generate image for prompt: {prompt}")

        if not urls: 
            raise Exception("No thumbnails were successfully generated.")
        
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "COMPLETED", 
                progress_details={"description": f"Generated {len(urls)} thumbnails!", "percentage": 100}, 
                results={"thumbnail_urls": urls, "prompts_used": image_prompts})
        
        logger.info(f"Thumbnail job {job_id} completed with {len(urls)} images")
            
    except Exception as e:
        logger.error(f"Thumbnail job {job_id} failed: {str(e)}")
        with get_db_session() as db:
            crud.update_job_full_status(db, job_id, "FAILED", 
                error_message=f"Thumbnail generation failed: {str(e)}")
        raise

@celery_app.task
def cleanup_old_files():
    """Clean up old files to prevent disk space issues."""
    logger.info("🧹 Starting daily cleanup of old files...")
    
    try:
        from app.core.config import settings
        
        cleanup_age_days = 1 
        cutoff = datetime.now() - timedelta(days=cleanup_age_days)
        
        upload_dir = os.path.join(settings.STATIC_GENERATED_DIR, "uploads")
        temp_clips_dir = settings.STATIC_GENERATED_DIR
        
        patterns = [
            os.path.join(upload_dir, '*'),
            os.path.join(temp_clips_dir, 'temp_*.mp4'),
            os.path.join(temp_clips_dir, 'final_*.mp4'),
            os.path.join(temp_clips_dir, 'captions_*.srt'),
            os.path.join(temp_clips_dir, 'captions_*.ass'),
            os.path.join(temp_clips_dir, '*_audio.mp3')
        ]
        
        files_removed = 0
        total_size_freed = 0
        
        # Get list of active jobs to avoid deleting files in use
        active_job_ids = set()
        with get_db_session() as db:
            active_jobs = crud.get_jobs_by_status(db, ["IN_PROGRESS", "RETRYING"])
            active_job_ids = {job.id for job in active_jobs}
        
        for pattern in patterns:
            for file_path in glob.glob(pattern):
                try:
                    # Check if file is associated with an active job
                    filename = os.path.basename(file_path)
                    is_active_job_file = any(job_id in filename for job_id in active_job_ids)
                    
                    if is_active_job_file:
                        logger.debug(f"Skipping active job file: {file_path}")
                        continue
                    
                    file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if file_mod_time < cutoff:
                        # Additional safety check - try to open file to see if it's in use
                        try:
                            with open(file_path, 'rb') as f:
                                pass  # Just test if we can open it
                        except (PermissionError, OSError):
                            logger.debug(f"File in use, skipping: {file_path}")
                            continue
                        
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        files_removed += 1
                        total_size_freed += file_size
                        logger.info(f"Removed old file: {file_path}")
                except Exception as e:
                    logger.error(f"Error removing file {file_path}: {e}")
        
        # Convert bytes to MB for logging
        size_mb = total_size_freed / (1024 * 1024)
        logger.info(f"✅ Daily cleanup finished. Removed {files_removed} files, freed {size_mb:.1f}MB")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")