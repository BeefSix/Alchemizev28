from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from starlette.background import BackgroundTask
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db import crud, models
from app.db.base import get_db
from app.services.auth import get_current_active_user
from app.workers import tasks
import uuid
import json
import os
import shutil
import zipfile
import tempfile
import magic
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logger import logger

router = APIRouter()

# Security constants
ALLOWED_VIDEO_TYPES = {
    'video/mp4', 'video/quicktime', 'video/x-msvideo', 
    'video/x-matroska', 'video/webm', 'video/avi',
    'video/x-ms-wmv', 'video/3gpp', 'video/x-flv'
}
ALLOWED_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.wmv', '.3gp', '.flv'}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
MIN_FILE_SIZE = 1024  # 1KB

def validate_video_file(file: UploadFile) -> None:
    """Validate uploaded video file for security and format"""
    
    # Check if file exists
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Check file extension
    file_ext = os.path.splitext(file.filename.lower())[1]
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Check content type
    if file.content_type and file.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Invalid content type. Must be a video file."
        )
    
    # Check file size (this checks the size as it's being uploaded)
    if hasattr(file, 'size') and file.size:
        if file.size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
            )
        if file.size < MIN_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail="File too small. Minimum size: 1KB"
            )

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal attacks"""
    # Remove any path components
    filename = os.path.basename(filename)
    # Remove or replace dangerous characters
    dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
    for char in dangerous_chars:
        filename = filename.replace(char, '_')
    # Limit length
    name, ext = os.path.splitext(filename)
    if len(name) > 100:
        name = name[:100]
    return name + ext

@limiter.limit("20/hour")
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
    logger.info(f"Received upload request from user {current_user.id} - File: {file.filename}, Captions: {add_captions}")

    # SECURITY: Validate the uploaded file
    validate_video_file(file)
    
    # Generate job ID and sanitize filename
    job_id = str(uuid.uuid4())
    sanitized_filename = sanitize_filename(file.filename)
    
    # Create secure file path
    upload_dir = os.path.join(settings.STATIC_GENERATED_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    
    file_extension = os.path.splitext(sanitized_filename)[1].lower() or '.mp4'
    secure_filename = f"{job_id}{file_extension}"
    file_path = os.path.join(upload_dir, secure_filename)
    
    # Validate aspect ratio
    valid_ratios = ["9:16", "1:1", "16:9"]
    if aspect_ratio not in valid_ratios:
        raise HTTPException(status_code=400, detail=f"Invalid aspect ratio. Must be one of: {valid_ratios}")
    
    file_size_mb = 0
    try:
        # Save file securely with size tracking
        with open(file_path, "wb") as buffer:
            chunk_size = 8192  # 8KB chunks
            total_size = 0
            
            while chunk := await file.read(chunk_size):
                total_size += len(chunk)
                
                # Check size during upload to prevent DoS
                if total_size > MAX_FILE_SIZE:
                    buffer.close()
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    raise HTTPException(
                        status_code=400,
                        detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
                    )
                
                buffer.write(chunk)
            
            file_size_mb = total_size / (1024 * 1024)
            
        # Final size check
        if total_size < MIN_FILE_SIZE:
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(status_code=400, detail="File too small")
            
        logger.info(f"File saved securely: {file_path} ({file_size_mb:.1f}MB)")
        
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
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
    
    # Start background job on GPU queue
    try:
        tasks.run_videoclip_upload_job.apply_async(
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
    except Exception as e:
        logger.error(f"Failed to enqueue background task: {e}")
        # Cleanup on failure
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail="Failed to start video processing")
    
    return {
        "job_id": job_id, 
        "message": f"Video processing started for {sanitized_filename}."
    }

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
        zip_filename = f"alchemize_clips_{job_id[:8]}.zip"
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