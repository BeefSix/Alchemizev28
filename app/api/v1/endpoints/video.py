from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from starlette.background import BackgroundTask
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db import crud, models
from app.db.base import get_db
from app.dependencies import get_current_active_user
from app.workers import tasks
import uuid
import json
import os
import shutil
import zipfile
import tempfile
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logger import logger

router = APIRouter()

@limiter.limit("20/hour")
@router.post("/upload-and-clip", status_code=status.HTTP_202_ACCEPTED, response_model=models.JobResponse) # <-- THIS IS THE FIX
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
    logger.info(f"Received upload request - File: {file.filename}, Captions: {add_captions}, Aspect: {aspect_ratio}, Platforms: {platforms}")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Save the uploaded file
    job_id = str(uuid.uuid4())
    upload_dir = os.path.join(settings.STATIC_GENERATED_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    
    file_extension = os.path.splitext(file.filename)[1].lower() or '.mp4'
    sanitized_filename = f"{job_id}{file_extension}"
    file_path = os.path.join(upload_dir, sanitized_filename)
    
    file_size_mb = 0
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            file_size_mb = buffer.tell() / (1024 * 1024)
        logger.info(f"File saved: {file_path} ({file_size_mb:.1f}MB)")
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")
    
    # Create database job record
    try:
        crud.create_job(
            db, 
            job_id=job_id, 
            user_id=current_user.id, 
            job_type="videoclip", 
            progress_details={"original_filename": file.filename}
        )
    except Exception as e:
        logger.error(f"Failed to create job record: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail="Failed to create job record")
    
    # Convert the 'platforms' string from the form into a list for the worker.
    platform_list = [p.strip() for p in platforms.split(",")]
    
    # Use .apply_async to send the job to the correct 'gpu' queue.
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
        logger.info(f"Started background job {job_id} for video processing on 'gpu' queue")
    except Exception as e:
        logger.error(f"Failed to enqueue background task: {e}")
        raise HTTPException(status_code=500, detail="Failed to start video processing")
    
    return {
        "job_id": job_id, 
        "message": f"Video processing started for {file.filename}."
    }

@router.get("/jobs/{job_id}", response_model=models.JobStatusResponse)
def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Get the status of a specific video processing job."""
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
                    
                    if os.path.exists(file_path):
                        file_extension = os.path.splitext(file_path)[1]
                        arcname = f"clip_{i+1}{file_extension}"
                        zipf.write(file_path, arcname)
                        files_added += 1
                except Exception as e:
                    logger.warning(f"Failed to add clip to zip: {url} - {e}")
        
        if files_added == 0:
            raise HTTPException(status_code=404, detail="No clip files found on disk.")

        logger.info(f"Created zip with {files_added} clips for job {job_id}")
        
        return FileResponse(
            path=zip_path,
            media_type='application/zip',
            filename=f"alchemize_clips_{job_id[:8]}.zip",
            background=BackgroundTask(shutil.rmtree, temp_dir)
        )
        
    except Exception as e:
        logger.error(f"Download failed for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create download: {str(e)}")
                        