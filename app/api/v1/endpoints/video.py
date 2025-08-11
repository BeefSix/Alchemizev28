from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from starlette.background import BackgroundTask
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db import crud, models
from app.db.base import get_db
from app.services.auth import get_current_active_user
from app.services.file_security import file_validator
from app.workers import tasks
import uuid
import json
import os
import shutil
import zipfile
import tempfile
import magic
import hashlib
from pathlib import Path
from typing import Optional
from datetime import datetime
from app.core.config import settings
from app.services.rate_limiter import rate_limiter
from app.services.payment import payment_service
from app.core.logger import logger
from app.core.error_handling import celery_error_handler, with_db_retry

router = APIRouter()

# Legacy constants for backward compatibility
ALLOWED_VIDEO_TYPES = file_validator.ALLOWED_VIDEO_MIMES
ALLOWED_EXTENSIONS = {ext.lower() for ext in settings.ALLOWED_VIDEO_EXTENSIONS}
MAX_FILE_SIZE = settings.MAX_FILE_SIZE_MB * 1024 * 1024
MIN_FILE_SIZE = 1024  # 1KB

@router.post("/upload-and-clip", status_code=status.HTTP_202_ACCEPTED, response_model=models.JobResponse)
async def create_videoclip_job_upload(
    request: Request,
    file: UploadFile = File(...),
    add_captions: bool = Form(...),
    aspect_ratio: str = Form(...),
    platforms: str = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Upload ANY video file and create clips with live karaoke-style captions."""
    # Check payment limits first
    if not payment_service.check_usage_limits(db, current_user.id, "video_processing"):
        user_plan = payment_service.get_user_plan(db, current_user.id)
        raise HTTPException(
            status_code=402,  # Payment Required
            detail=f"Video processing limit reached. You have {user_plan['video_credits_remaining']} credits remaining. Upgrade your plan to continue."
        )
    
    # Get user plan first
    user_plan = payment_service.get_user_plan(db, current_user.id)
    
    # SECURITY: Advanced rate limiting with user-specific limits - skip for enterprise users
    rate_info = None
    if user_plan['plan'] != 'enterprise':
        rate_info = await rate_limiter.check_rate_limit(
            request, 
            "upload", 
            user_id=str(current_user.id)
        )
        logger.info(f"Rate limit status: {rate_info['remaining']}/{rate_info['limit']} remaining")
    else:
        # For enterprise users, set default rate info values
        rate_info = {
            'remaining': 999999,
            'limit': 999999,
            'reset': 0
        }
    
    logger.info(f"Received upload request from user {current_user.id} - File: {file.filename}, Captions: {add_captions}")

    # SECURITY: Comprehensive file validation using new security service
    # For enterprise users, skip user limits check since they have unlimited access
    skip_limits = user_plan['plan'] == 'enterprise'
    
    validation_result = await file_validator.validate_upload(
        file, 
        str(current_user.id), 
        skip_user_limits=skip_limits
    )
    if not validation_result['valid']:
        raise HTTPException(status_code=400, detail=validation_result['error'])
    
    # Generate job ID and get secure file path
    job_id = str(uuid.uuid4())
    
    # Use secure file handling from file_validator
    secure_file_path = file_validator.get_safe_upload_path(file.filename, str(current_user.id))
    file_path = str(secure_file_path)
    sanitized_filename = secure_file_path.name
    
    # Validate aspect ratio
    valid_ratios = ["9:16", "1:1", "16:9"]
    if aspect_ratio not in valid_ratios:
        raise HTTPException(status_code=400, detail=f"Invalid aspect ratio. Must be one of: {valid_ratios}")
    
    # Save the uploaded file securely
    try:
        result = await file_validator.save_upload_securely(file, secure_file_path)
        saved_path, file_size_mb = result
        logger.info(f"File saved securely: {saved_path} ({file_size_mb:.1f}MB)")
    except HTTPException as http_exc:
        # Re-raise HTTP exceptions as-is
        raise http_exc
    except Exception as e:
        logger.error(f"Failed to save file securely: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")
    
    # Create database job record
    try:
        crud.create_job(
            db, 
            job_id=job_id, 
            user_id=current_user.id, 
            job_type="videoclip", 
            progress_details={
                "original_filename": sanitized_filename,
                "file_size_mb": file_size_mb
            }
        )
    except Exception as e:
        logger.error(f"Failed to create job record: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail="Failed to create job record")
    
    # Convert platforms string to list
    platform_list = [p.strip() for p in platforms.split(",") if p.strip()]
    if not platform_list:
        platform_list = ["TikTok", "Instagram", "YouTube"]
    
    # Start background job with enhanced error handling
    success = False  # Initialize success variable
    try:
        # Check if we should use fallback immediately
        if celery_error_handler.state_manager.should_use_fallback():
            logger.info("🔄 Using synchronous processing due to connection issues...")
            success = tasks.run_videoclip_upload_job_sync(
                job_id=job_id,
                user_id=current_user.id,
                video_path=file_path,
                add_captions=add_captions,
                aspect_ratio=aspect_ratio,
                platforms=platform_list
            )
        else:
            # Try Celery task first
            task_result = tasks.run_videoclip_upload_job.apply_async(
                args=[
                    job_id,
                    current_user.id,
                    file_path,
                    add_captions,
                    aspect_ratio,
                    platform_list
                ],
                queue='gpu'
            )
            logger.info(f"Started secure background job {job_id} for video processing")
            success = True
            
    except Exception as e:
        logger.warning(f"⚠️ Celery task failed: {e}")
        
        # Use enhanced error handler for fallback
        try:
            # Fallback to synchronous processing
            logger.info(f"Attempting synchronous fallback for job {job_id}")
            success = tasks.run_videoclip_upload_job_sync(
                job_id=job_id,
                user_id=current_user.id,
                video_path=file_path,
                add_captions=add_captions,
                aspect_ratio=aspect_ratio,
                platforms=platform_list
            )
            
        except Exception as fallback_error:
            success = False
            logger.error(f"❌ Enhanced fallback also failed: {fallback_error}")
            
            # Safe job status update
            try:
                crud.update_job_full_status(db, job_id, "FAILED", error_message=f"Processing failed: {str(fallback_error)}")
            except Exception as update_error:
                logger.error(f"Failed to update job status: {update_error}")
            
            # Clean up uploaded file
            if os.path.exists(file_path):
                os.remove(file_path)
            
            raise HTTPException(
                status_code=500,
                detail="Video processing failed completely"
            )
    
    # Handle synchronous processing result
    if not success:
        logger.error(f"❌ Video processing failed for job {job_id}")
        try:
            crud.update_job_full_status(db, job_id, "FAILED", error_message="Video processing failed")
        except Exception as update_error:
            logger.error(f"Failed to update job status: {update_error}")
        
        # Clean up uploaded file
        if os.path.exists(file_path):
            os.remove(file_path)
        
        raise HTTPException(
            status_code=500,
            detail="Video processing failed"
        )
    
    return {
        "job_id": job_id, 
        "message": f"Video processing started for {sanitized_filename}.",
        "rate_limit": {
            "remaining": rate_info['remaining'] if rate_info else 999999,
            "limit": rate_info['limit'] if rate_info else 999999,
            "reset_time": rate_info['reset'] if rate_info else 0
        }
    }

# Chunked Upload Endpoints for Large Files
@router.post("/upload/init")
async def init_chunked_upload(
    request: Request,
    filename: str = Form(...),
    file_size: int = Form(...),
    chunk_size: int = Form(default=5*1024*1024),  # 5MB default
    file_hash: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Initialize a chunked upload session for large video files."""
    
    # Check user plan first
    user_plan = payment_service.get_user_plan(db, current_user.id)
    
    # Rate limiting - skip for enterprise users
    if user_plan['plan'] != 'enterprise':
        rate_info = await rate_limiter.check_rate_limit(
            request, "upload", user_id=str(current_user.id)
        )
    
    # Validate file size
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400, 
            detail=f"File too large: {file_size / (1024*1024):.1f}MB. Max: {settings.MAX_FILE_SIZE_MB}MB"
        )
    
    if file_size < MIN_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too small")
    
    # Validate filename and extension
    file_ext = Path(filename).suffix.lower()
    if file_ext not in settings.ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file extension: {file_ext}"
        )
    
    # Check user limits
    if not payment_service.check_usage_limits(db, current_user.id, "video_processing"):
        raise HTTPException(
            status_code=402,
            detail="Video processing limit reached. Upgrade your plan to continue."
        )
    
    # Generate upload session
    upload_id = str(uuid.uuid4())
    upload_dir = Path("uploads") / "chunks" / upload_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Calculate total chunks
    total_chunks = (file_size + chunk_size - 1) // chunk_size
    
    # Store upload session metadata
    session_data = {
        "upload_id": upload_id,
        "filename": filename,
        "file_size": file_size,
        "chunk_size": chunk_size,
        "total_chunks": total_chunks,
        "uploaded_chunks": [],
        "user_id": current_user.id,
        "file_hash": file_hash,
        "created_at": json.dumps(datetime.utcnow(), default=str)
    }
    
    session_file = upload_dir / "session.json"
    with open(session_file, 'w') as f:
        json.dump(session_data, f)
    
    logger.info(f"Chunked upload initialized: {upload_id} for user {current_user.id}")
    
    return {
        "upload_id": upload_id,
        "chunk_size": chunk_size,
        "total_chunks": total_chunks,
        "message": "Upload session initialized"
    }

@router.post("/upload/chunk/{upload_id}")
async def upload_chunk(
    upload_id: str,
    chunk_number: int = Form(...),
    chunk: UploadFile = File(...),
    chunk_hash: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Upload a single chunk of a large video file."""
    
    upload_dir = Path("uploads") / "chunks" / upload_id
    session_file = upload_dir / "session.json"
    
    # Validate upload session
    if not session_file.exists():
        raise HTTPException(status_code=404, detail="Upload session not found")
    
    with open(session_file, 'r') as f:
        session_data = json.load(f)
    
    # Verify user ownership
    if session_data["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Validate chunk number
    if chunk_number < 0 or chunk_number >= session_data["total_chunks"]:
        raise HTTPException(status_code=400, detail="Invalid chunk number")
    
    # Check if chunk already uploaded
    if chunk_number in session_data["uploaded_chunks"]:
        return {"message": "Chunk already uploaded", "chunk_number": chunk_number}
    
    # Save chunk
    chunk_path = upload_dir / f"chunk_{chunk_number:06d}"
    chunk_data = await chunk.read()
    
    # Validate chunk hash if provided
    if chunk_hash:
        calculated_hash = hashlib.md5(chunk_data).hexdigest()
        if calculated_hash != chunk_hash:
            raise HTTPException(status_code=400, detail="Chunk hash mismatch")
    
    # Validate chunk size (except last chunk)
    expected_size = session_data["chunk_size"]
    if chunk_number == session_data["total_chunks"] - 1:
        # Last chunk can be smaller
        remaining_size = session_data["file_size"] % session_data["chunk_size"]
        if remaining_size > 0:
            expected_size = remaining_size
    
    if len(chunk_data) != expected_size and chunk_number != session_data["total_chunks"] - 1:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid chunk size: {len(chunk_data)}, expected: {expected_size}"
        )
    
    # Write chunk to disk
    with open(chunk_path, 'wb') as f:
        f.write(chunk_data)
    
    # Update session
    session_data["uploaded_chunks"].append(chunk_number)
    session_data["uploaded_chunks"].sort()
    
    with open(session_file, 'w') as f:
        json.dump(session_data, f)
    
    progress = len(session_data["uploaded_chunks"]) / session_data["total_chunks"] * 100
    
    logger.info(f"Chunk {chunk_number} uploaded for session {upload_id} ({progress:.1f}% complete)")
    
    return {
        "chunk_number": chunk_number,
        "progress": progress,
        "uploaded_chunks": len(session_data["uploaded_chunks"]),
        "total_chunks": session_data["total_chunks"]
    }

@router.post("/upload/complete/{upload_id}")
async def complete_chunked_upload(
    upload_id: str,
    add_captions: bool = Form(...),
    aspect_ratio: str = Form(...),
    platforms: str = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Complete chunked upload and start video processing."""
    
    upload_dir = Path("uploads") / "chunks" / upload_id
    session_file = upload_dir / "session.json"
    
    # Validate upload session
    if not session_file.exists():
        raise HTTPException(status_code=404, detail="Upload session not found")
    
    with open(session_file, 'r') as f:
        session_data = json.load(f)
    
    # Verify user ownership
    if session_data["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if all chunks uploaded
    if len(session_data["uploaded_chunks"]) != session_data["total_chunks"]:
        missing_chunks = set(range(session_data["total_chunks"])) - set(session_data["uploaded_chunks"])
        raise HTTPException(
            status_code=400, 
            detail=f"Missing chunks: {sorted(list(missing_chunks))}"
        )
    
    # Reassemble file
    final_filename = file_validator.get_safe_upload_path(
        session_data["filename"], 
        str(current_user.id)
    )
    
    try:
        with open(final_filename, 'wb') as output_file:
            for chunk_num in range(session_data["total_chunks"]):
                chunk_path = upload_dir / f"chunk_{chunk_num:06d}"
                with open(chunk_path, 'rb') as chunk_file:
                    output_file.write(chunk_file.read())
        
        # Verify file size
        actual_size = os.path.getsize(final_filename)
        if actual_size != session_data["file_size"]:
            os.remove(final_filename)
            raise HTTPException(
                status_code=400, 
                detail=f"File size mismatch: {actual_size} != {session_data['file_size']}"
            )
        
        # Verify file hash if provided
        if session_data.get("file_hash"):
            with open(final_filename, 'rb') as f:
                file_content = f.read()
                calculated_hash = hashlib.md5(file_content).hexdigest()
                if calculated_hash != session_data["file_hash"]:
                    os.remove(final_filename)
                    raise HTTPException(status_code=400, detail="File hash verification failed")
        
        # Clean up chunks
        shutil.rmtree(upload_dir)
        
        # Start video processing
        job_id = str(uuid.uuid4())
        
        # Validate aspect ratio
        valid_ratios = ["9:16", "1:1", "16:9"]
        if aspect_ratio not in valid_ratios:
            os.remove(final_filename)
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid aspect ratio. Must be one of: {valid_ratios}"
            )
        
        # Create database job record
        crud.create_job(
            db, 
            job_id=job_id, 
            user_id=current_user.id, 
            job_type="videoclip", 
            progress_details={
                "original_filename": session_data["filename"],
                "file_size_mb": session_data["file_size"] / (1024*1024),
                "upload_method": "chunked"
            }
        )
        
        # Start background processing
        tasks.run_videoclip_upload_job.delay(
            job_id=job_id,
            file_path=str(final_filename),
            add_captions=add_captions,
            aspect_ratio=aspect_ratio,
            platforms=platforms,
            user_id=current_user.id
        )
        
        logger.info(f"Chunked upload completed and processing started: {job_id}")
        
        return {
            "job_id": job_id,
            "message": f"File uploaded successfully via chunked upload. Processing started.",
            "file_size_mb": session_data["file_size"] / (1024*1024)
        }
        
    except Exception as e:
        # Clean up on error
        if final_filename.exists():
            os.remove(final_filename)
        if upload_dir.exists():
            shutil.rmtree(upload_dir)
        logger.error(f"Chunked upload completion failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload completion failed: {str(e)}")

@router.delete("/upload/{upload_id}")
async def cancel_chunked_upload(
    upload_id: str,
    current_user: models.User = Depends(get_current_active_user)
):
    """Cancel and clean up a chunked upload session."""
    
    upload_dir = Path("uploads") / "chunks" / upload_id
    session_file = upload_dir / "session.json"
    
    if not session_file.exists():
        raise HTTPException(status_code=404, detail="Upload session not found")
    
    with open(session_file, 'r') as f:
        session_data = json.load(f)
    
    # Verify user ownership
    if session_data["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Clean up
    if upload_dir.exists():
        shutil.rmtree(upload_dir)
    
    logger.info(f"Chunked upload cancelled: {upload_id}")
    
    return {"message": "Upload session cancelled and cleaned up"}

@router.get("/jobs/{job_id}", response_model=models.JobStatusResponse)
def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Get the status of a specific video processing job."""
    
    # Validate job_id format (basic UUID check)
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")
    
    job = crud.get_job(db, job_id=job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found or not authorized.")

    return {
        "id": job.id,
        "status": job.status,
        "error_message": job.error_message,
        "results": job.results,
        "progress_details": job.progress_details
    }

@router.get("/jobs/{job_id}/download-all")
async def download_all_clips(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Download all clips for a job as a single ZIP file."""
    
    # Validate job_id format
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")
    
    job = crud.get_job(db, job_id=job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found.")
    
    if job.status != "COMPLETED":
        raise HTTPException(status_code=400, detail="Job is not yet complete.")
    
    try:
        job_results = json.loads(job.results) if isinstance(job.results, str) else job.results
        clips_by_platform = job_results.get("clips_by_platform", {})
        
        if not clips_by_platform:
            raise HTTPException(status_code=404, detail="No clips were generated for this job.")
        
        temp_dir = tempfile.mkdtemp()
        zip_filename = f"zuexis_clips_{job_id[:8]}.zip"
        zip_path = os.path.join(temp_dir, zip_filename)
        
        all_clip_urls = []
        for platform_clips in clips_by_platform.values():
            if isinstance(platform_clips, list):
                all_clip_urls.extend(platform_clips)
        
        unique_urls = list(set(all_clip_urls))
        
        files_added = 0
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for i, url in enumerate(unique_urls):
                try:
                    if url.startswith('/static/'):
                        file_path = os.path.join(settings.STATIC_FILES_ROOT_DIR, url.strip('/'))
                    else:
                        file_path = os.path.join(settings.STATIC_GENERATED_DIR, os.path.basename(url))
                    
                    # Security: Validate file path is within allowed directories
                    file_path = os.path.abspath(file_path)
                    allowed_dirs = [
                        os.path.abspath(settings.STATIC_FILES_ROOT_DIR),
                        os.path.abspath(settings.STATIC_GENERATED_DIR)
                    ]
                    
                    if not any(file_path.startswith(allowed_dir) for allowed_dir in allowed_dirs):
                        logger.warning(f"Attempted path traversal attack: {file_path}")
                        continue
                    
                    if os.path.exists(file_path):
                        file_extension = os.path.splitext(file_path)[1]
                        arcname = f"clip_{i+1}{file_extension}"
                        zipf.write(file_path, arcname)
                        files_added += 1
                except Exception as e:
                    logger.warning(f"Failed to add clip to zip: {url} - {e}")
        
        if files_added == 0:
            raise HTTPException(status_code=404, detail="No clip files found on disk.")

        logger.info(f"Created secure zip with {files_added} clips for job {job_id}")
        
        return FileResponse(
            path=zip_path,
            media_type='application/zip',
            filename=zip_filename,
            background=BackgroundTask(shutil.rmtree, temp_dir)
        )
        
    except Exception as e:
        logger.error(f"Download failed for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create download: {str(e)}")