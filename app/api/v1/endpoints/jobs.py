from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from datetime import datetime, timedelta
import json
import asyncio
import time

from app.db import crud, models
from app.db.base import get_db
from app.services.auth import get_current_active_user
from app.services.rate_limiter import rate_limiter
from fastapi import Request

router = APIRouter()

@router.get("/history")
def get_job_history(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    limit: int = 50,
    offset: int = 0
):
    """Get job history for the current user"""
    try:
        # Get jobs for the current user
        jobs = db.query(models.Job).filter(
            models.Job.user_id == current_user.id
        ).order_by(
            models.Job.created_at.desc()
        ).offset(offset).limit(limit).all()
        
        # Format jobs for frontend
        formatted_jobs = []
        for job in jobs:
            # Parse progress details and results safely
            progress_details = {}
            results = None
            
            if job.progress_details:
                try:
                    import json
                    if isinstance(job.progress_details, str):
                        progress_details = json.loads(job.progress_details)
                    else:
                        progress_details = job.progress_details
                except:
                    progress_details = {}
            
            if job.results:
                try:
                    import json
                    if isinstance(job.results, str):
                        results = json.loads(job.results)
                    else:
                        results = job.results
                except:
                    results = None
            
            # Calculate duration (mock for now)
            duration = "N/A"
            if job.created_at:
                # Simple duration calculation - in real implementation, 
                # you'd track start/end times
                elapsed = datetime.utcnow() - job.created_at
                if job.status == "COMPLETED":
                    minutes = int(elapsed.total_seconds() // 60)
                    seconds = int(elapsed.total_seconds() % 60)
                    duration = f"{minutes}m {seconds}s"
            
            formatted_job = {
                "job_id": job.id,
                "job_type": job.job_type,
                "filename": f"{job.job_type}_job_{job.id[:8]}",  # Mock filename
                "file_size": "N/A",  # Would need to store this
                "status": job.status,
                "created_at": job.created_at.strftime("%Y-%m-%d %H:%M") if job.created_at else "N/A",
                "duration": duration,
                "results": results,
                "error": job.error_message
            }
            formatted_jobs.append(formatted_job)
        
        return {
            "jobs": formatted_jobs,
            "total": len(formatted_jobs),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch job history: {str(e)}"
        )

@router.get("/{job_id}")
def get_job_by_id(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Get a specific job by ID for the current user"""
    try:
        # Get the job for the current user
        job = db.query(models.Job).filter(
            models.Job.id == job_id,
            models.Job.user_id == current_user.id
        ).first()
        
        if not job:
            raise HTTPException(
                status_code=404,
                detail="Job not found"
            )
        
        # Parse progress details and results safely
        progress_details = {}
        results = None
        
        if job.progress_details:
            try:
                import json
                if isinstance(job.progress_details, str):
                    progress_details = json.loads(job.progress_details)
                else:
                    progress_details = job.progress_details
            except:
                progress_details = {}
        
        if job.results:
            try:
                import json
                if isinstance(job.results, str):
                    results = json.loads(job.results)
                else:
                    results = job.results
            except:
                results = None
        
        # Format job for frontend
        formatted_job = {
            "id": job.id,
            "job_type": job.job_type,
            "status": job.status,
            "created_at": job.created_at.strftime("%Y-%m-%d %H:%M") if job.created_at else "N/A",
            "progress_details": progress_details,
            "results": results,
            "error_message": job.error_message
        }
        
        return formatted_job
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch job: {str(e)}"
        )

@router.get("/{job_id}/events")
async def get_job_events(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Server-Sent Events endpoint for real-time job progress updates"""
    
    async def event_generator():
        last_status = None
        last_progress = None
        
        while True:
            try:
                # Check if client disconnected
                if await request.is_disconnected():
                    break
                    
                # Get current job status
                job = db.query(models.Job).filter(
                    models.Job.id == job_id,
                    models.Job.user_id == current_user.id
                ).first()
                
                if not job:
                    yield f"event: error\ndata: {{\"error\": \"Job not found\"}}\n\n"
                    break
                
                # Parse progress details
                progress_details = {}
                if job.progress_details:
                    try:
                        if isinstance(job.progress_details, str):
                            progress_details = json.loads(job.progress_details)
                        else:
                            progress_details = job.progress_details
                    except:
                        progress_details = {}
                
                # Create event data
                event_data = {
                    "job_id": job.id,
                    "status": job.status.lower() if job.status else "unknown",
                    "percent": progress_details.get("percentage", 0),
                    "stage": progress_details.get("stage", "processing"),
                    "description": progress_details.get("description", "Processing..."),
                    "timestamp": int(time.time())
                }
                
                # Add error if job failed
                if job.status == "FAILED" and job.error_message:
                    event_data["error"] = job.error_message
                
                # Only send if status or progress changed
                current_status = job.status
                current_progress = progress_details.get("percentage", 0)
                
                if (current_status != last_status or 
                    current_progress != last_progress or 
                    last_status is None):
                    
                    yield f"data: {json.dumps(event_data)}\n\n"
                    last_status = current_status
                    last_progress = current_progress
                
                # If job is completed or failed, send final event and close
                if job.status in ["COMPLETED", "FAILED"]:
                    await asyncio.sleep(1)  # Give client time to process
                    break
                    
                # Wait before next check
                await asyncio.sleep(2)
                
            except Exception as e:
                yield f"event: error\ndata: {{\"error\": \"Connection error: {str(e)}\"}}\n\n"
                break
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

@router.get("/stats")
def get_job_stats(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Get job statistics for the current user"""
    try:
        # Get all jobs for the user
        all_jobs = db.query(models.Job).filter(
            models.Job.user_id == current_user.id
        ).all()
        
        # Get jobs from this week
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_jobs = db.query(models.Job).filter(
            models.Job.user_id == current_user.id,
            models.Job.created_at >= week_ago
        ).all()
        
        # Calculate statistics
        total_jobs = len(all_jobs)
        jobs_this_week = len(recent_jobs)
        
        completed_jobs = len([j for j in all_jobs if j.status == "COMPLETED"])
        failed_jobs = len([j for j in all_jobs if j.status == "FAILED"])
        active_jobs = len([j for j in all_jobs if j.status in ["IN_PROGRESS", "PENDING"]])
        
        success_rate = (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0
        
        return {
            "total_jobs": total_jobs,
            "jobs_this_week": jobs_this_week,
            "success_rate": round(success_rate, 1),
            "active_jobs": active_jobs
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch job statistics: {str(e)}"
        )

@router.post("/test-job")
def create_test_job(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Create a test job for development/testing"""
    import uuid
    
    # Create a test job with transcript data
    test_job = models.Job(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        job_type="video_processing",
        status="COMPLETED",
        results=json.dumps({
            "video_duration": 120,
            "total_clips": 5,
            "transcript": {
                "words": [
                    {"word": "Hello", "start": 0.0, "end": 0.5},
                    {"word": "everyone", "start": 0.5, "end": 1.0},
                    {"word": "welcome", "start": 1.0, "end": 1.5},
                    {"word": "to", "start": 1.5, "end": 2.0},
                    {"word": "our", "start": 2.0, "end": 2.5},
                    {"word": "important", "start": 2.5, "end": 3.0},
                    {"word": "presentation", "start": 3.0, "end": 3.5},
                    {"word": "about", "start": 3.5, "end": 4.0},
                    {"word": "success", "start": 4.0, "end": 4.5},
                    {"word": "strategies", "start": 4.5, "end": 5.0},
                    {"word": "and", "start": 5.0, "end": 5.5},
                    {"word": "key", "start": 5.5, "end": 6.0},
                    {"word": "insights", "start": 6.0, "end": 6.5},
                    {"word": "for", "start": 6.5, "end": 7.0},
                    {"word": "achieving", "start": 7.0, "end": 7.5},
                    {"word": "your", "start": 7.5, "end": 8.0},
                    {"word": "goals", "start": 8.0, "end": 8.5}
                ]
            }
        }),
        progress_details=json.dumps({
            "percentage": 100,
            "description": "Processing complete"
        })
    )
    
    db.add(test_job)
    db.commit()
    db.refresh(test_job)
    
    return {
        "job_id": test_job.id,
        "status": "created",
        "message": "Test job created successfully"
    }