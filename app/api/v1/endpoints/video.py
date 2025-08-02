# app/api/v1/endpoints/video.py
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
import requests
import zipfile
import tempfile
import logging
from typing import List
from app.core.config import settings
from app.core.limiter import limiter

# Set up logging
logger = logging.getLogger(__name__)
router = APIRouter()

@limiter.limit("5/hour")
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
    """Upload a single video file and create clips for multiple platforms."""
    logger.info(f"Received upload request - File: {file.filename}, Platforms: {platforms}, Captions: {add_captions}, Aspect: {aspect_ratio}")

    # Validate file format
    if not file.filename.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload a video file.")

    # Check file size
    file_content = await file.read()
    if len(file_content) > 500 * 1024 * 1024:  # 500MB limit
        raise HTTPException(status_code=400, detail="File is too large. Maximum size is 500MB.")
    await file.seek(0)

    # Create job and upload directory
    job_id = str(uuid.uuid4())
    upload_dir = os.path.join(settings.STATIC_GENERATED_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save uploaded file
    _, extension = os.path.splitext(file.filename)
    sanitized_filename = f"{job_id}{extension}"
    file_path = os.path.join(upload_dir, sanitized_filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")
    
    # Parse platforms
    platform_list = [p.strip() for p in platforms.split(",")]
    if not platform_list:
        raise HTTPException(status_code=400, detail="At least one platform must be specified")
    
    # Validate platforms
    valid_platforms = ["youtube_shorts", "tiktok", "instagram_reels", "instagram_feed", "linkedin", "twitter"]
    invalid_platforms = [p for p in platform_list if p not in valid_platforms]
    if invalid_platforms:
        raise HTTPException(status_code=400, detail=f"Invalid platforms: {invalid_platforms}")
    
    # Create database job record
    try:
        crud.create_job(db, job_id=job_id, user_id=current_user.id, job_type="videoclip", 
                        progress_details={"original_filename": file.filename})
    except Exception as e:
        logger.error(f"Failed to create job record: {e}")
        # Clean up uploaded file
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail="Failed to create job record")
    
    # Start background task
    try:
        tasks.run_videoclip_upload_job.delay(
            job_id=job_id,
            user_id=current_user.id,
            video_path=file_path,
            add_captions=add_captions,
            aspect_ratio=aspect_ratio,
            platforms=platform_list
        )
    except Exception as e:
        logger.error(f"Failed to start background task: {e}")
        raise HTTPException(status_code=500, detail="Failed to start video processing")
    
    return {"job_id": job_id, "message": "Video processing has started. This may take a few minutes."}

@router.post("/batch-upload", status_code=status.HTTP_202_ACCEPTED, response_model=models.JobResponse)
async def create_batch_videoclip_jobs(
    files: List[UploadFile] = File(...),
    add_captions: bool = True,
    platforms: str = "youtube_shorts,tiktok,instagram_reels",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Process multiple videos in a batch."""
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 videos per batch.")
    
    batch_id = str(uuid.uuid4())
    job_ids = []
    platform_list = [p.strip() for p in platforms.split(",")]
    upload_dir = os.path.join(settings.STATIC_GENERATED_DIR, "uploads", batch_id)
    os.makedirs(upload_dir, exist_ok=True)
    
    try:
        for file in files:
            if not file.filename.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
                raise HTTPException(status_code=400, detail=f"Invalid file format for {file.filename}.")

            job_id = str(uuid.uuid4())
            
            _, extension = os.path.splitext(file.filename)
            sanitized_filename = f"{job_id}{extension}"
            file_path = os.path.join(upload_dir, sanitized_filename)
            
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            
            crud.create_job(db, job_id=job_id, user_id=current_user.id, job_type="videoclip",
                            progress_details={"original_filename": file.filename})
            job_ids.append(job_id)
            
            tasks.run_videoclip_upload_job.delay(
                job_id=job_id,
                user_id=current_user.id,
                video_path=file_path,
                add_captions=add_captions,
                aspect_ratio="9:16",
                platforms=platform_list
            )
        
        crud.create_job(db, job_id=batch_id, user_id=current_user.id, job_type="batch")
        crud.update_job_full_status(db, batch_id, "IN_PROGRESS", results={"job_ids": job_ids, "total_videos": len(files)})
        
    except Exception as e:
        logger.error(f"Batch upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch upload failed: {str(e)}")
    
    return {"job_id": batch_id, "message": f"Batch job started for {len(files)} videos."}

@router.get("/jobs/{job_id}", response_model=models.JobStatusResponse)
def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Get the status of a specific job."""
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
        zip_path = os.path.join(temp_dir, f"alchemize_clips_{job_id[:8]}.zip")
        
        unique_urls = set(url for urls in clips_by_platform.values() for url in urls)
        
        files_added = 0
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for i, url in enumerate(unique_urls):
                file_path = os.path.join(settings.STATIC_FILES_ROOT_DIR, url.strip('/'))
                if os.path.exists(file_path):
                    arcname = f"clip_{i+1}.mp4"
                    zipf.write(file_path, arcname)
                    files_added += 1
        
        if files_added == 0:
            raise HTTPException(status_code=404, detail="No clip files found on disk.")

        return FileResponse(
            path=zip_path,
            media_type='application/zip',
            filename=f"alchemize_clips_{job_id[:8]}.zip",
            background=BackgroundTask(shutil.rmtree, temp_dir)
        )
        
    except Exception as e:
        logger.error(f"Download failed for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create download: {str(e)}")