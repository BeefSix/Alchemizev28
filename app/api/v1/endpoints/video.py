# app/api/v1/endpoints/video.py - UPDATED VIDEO ENDPOINT
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File
from sqlalchemy.orm import Session
from app.db import crud, models
from app.db.base import get_db
from app.services.auth import get_current_active_user
from app.workers import tasks
import uuid
import json
import os
import shutil
from app.core.config import settings

router = APIRouter()

class VideoClipRequest(models.BaseModel):
    # Remove video_url, we're doing uploads now
    add_captions: bool = True
    aspect_ratio: str = "9:16"
    platforms: list[str] = ["youtube_shorts", "tiktok", "instagram_reels", "twitter", "linkedin"]

@router.post("/upload-and-clip", status_code=status.HTTP_202_ACCEPTED, response_model=models.JobResponse)
async def create_videoclip_job_upload(
    file: UploadFile = File(...),
    add_captions: bool = True,
    aspect_ratio: str = "9:16",
    platforms: str = "youtube_shorts,tiktok,instagram_reels",  # comma-separated
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Upload a video file and create clips for multiple platforms"""
    
    # Validate file
    if not file.filename.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload a video file.")
    
    # Check file size (max 500MB for now)
    file_size = 0
    file_content = await file.read()
    file_size = len(file_content)
    await file.seek(0)  # Reset file pointer
    
    if file_size > 500 * 1024 * 1024:  # 500MB
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 500MB.")
    
    # Save uploaded file
    job_id = str(uuid.uuid4())
    upload_dir = os.path.join(settings.STATIC_GENERATED_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, f"{job_id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Parse platforms
    platform_list = [p.strip() for p in platforms.split(",")]
    
    # Create job
    crud.create_job(db, job_id=job_id, user_id=current_user.id, job_type="videoclip")
    
    # Start processing
    tasks.run_videoclip_upload_job.delay(
        job_id=job_id,
        user_id=current_user.id,
        video_path=file_path,
        original_filename=file.filename,
        add_captions=add_captions,
        aspect_ratio=aspect_ratio,
        platforms=platform_list
    )
    
    return {"job_id": job_id, "message": "Video processing started. This may take a few minutes."}

# Keep the existing job status endpoint
@router.get("/jobs/{job_id}", response_model=models.JobStatusResponse)
def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    job = crud.get_job(db, job_id=job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this job")
    
    response_data = {
        "id": job.id,
        "status": job.status,
        "error_message": job.error_message,
        "results": None,
        "progress_details": None
    }
    if job.results:
        try:
            response_data["results"] = json.loads(job.results) if isinstance(job.results, str) else job.results
        except json.JSONDecodeError:
            response_data["results"] = None
    if job.progress_details:
        try:
            response_data["progress_details"] = json.loads(job.progress_details) if isinstance(job.progress_details, str) else job.progress_details
        except json.JSONDecodeError:
            response_data["progress_details"] = None
            
    return response_data
from typing import List

@router.post("/batch-upload", status_code=status.HTTP_202_ACCEPTED)
async def create_batch_videoclip_jobs(
    files: List[UploadFile] = File(...),
    add_captions: bool = True,
    platforms: str = "youtube_shorts,tiktok,instagram_reels",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Process multiple videos in batch - perfect for agencies!"""
    
    # Validate all files first
    total_size = 0
    for file in files:
        if not file.filename.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
            raise HTTPException(status_code=400, detail=f"Invalid file: {file.filename}")
        
        file_content = await file.read()
        total_size += len(file_content)
        await file.seek(0)
    
    # Check total size (2GB limit for batch)
    if total_size > 2 * 1024 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Total batch size exceeds 2GB limit")
    
    # Check user limits
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 videos per batch")
    
    # Create batch job
    batch_id = str(uuid.uuid4())
    job_ids = []
    platform_list = [p.strip() for p in platforms.split(",")]
    
    # Save and process each file
    upload_dir = os.path.join(settings.STATIC_GENERATED_DIR, "uploads", batch_id)
    os.makedirs(upload_dir, exist_ok=True)
    
    for i, file in enumerate(files):
        job_id = str(uuid.uuid4())
        file_path = os.path.join(upload_dir, f"{job_id}_{file.filename}")
        
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Create individual job
        crud.create_job(db, job_id=job_id, user_id=current_user.id, job_type="videoclip")
        job_ids.append(job_id)
        
        # Queue the task
        tasks.run_videoclip_upload_job.delay(
            job_id=job_id,
            user_id=current_user.id,
            video_path=file_path,
            original_filename=file.filename,
            add_captions=add_captions,
            aspect_ratio="9:16",  # Default for batch
            platforms=platform_list
        )
    
    # Create a batch tracking job
    crud.create_job(db, job_id=batch_id, user_id=current_user.id, job_type="batch")
    crud.update_job_full_status(db, batch_id, "IN_PROGRESS", 
        results={"job_ids": job_ids, "total_videos": len(files)})
    
    return {
        "batch_id": batch_id,
        "job_ids": job_ids,
        "message": f"Processing {len(files)} videos. This may take several minutes."
    }

@router.get("/batch/{batch_id}/status")
async def get_batch_status(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Get status of all jobs in a batch"""
    
    batch_job = crud.get_job(db, job_id=batch_id)
    if not batch_job or batch_job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    job_ids = batch_job.results.get("job_ids", [])
    statuses = []
    
    for job_id in job_ids:
        job = crud.get_job(db, job_id=job_id)
        if job:
            statuses.append({
                "job_id": job_id,
                "status": job.status,
                "progress": job.progress_details.get("percentage", 0) if job.progress_details else 0,
                "clips_ready": len(job.results.get("clips_by_platform", {}).get("youtube_shorts", [])) if job.results else 0
            })
    
    completed = sum(1 for s in statuses if s["status"] == "COMPLETED")
    failed = sum(1 for s in statuses if s["status"] == "FAILED")
    
    return {
        "batch_id": batch_id,
        "total_jobs": len(job_ids),
        "completed": completed,
        "failed": failed,
        "in_progress": len(job_ids) - completed - failed,
        "job_statuses": statuses
    }