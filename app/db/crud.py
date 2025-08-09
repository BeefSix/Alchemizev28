# app/db/crud.py
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db import models
from app.core.security_utils import get_password_hash
from datetime import datetime, date
import json
import logging

logger = logging.getLogger(__name__)

# --- User CRUD ---
def get_user_by_id(db: Session, user_id: int):
    try:
        return db.query(models.User).filter(models.User.id == user_id).first()
    except Exception as e:
        logger.error(f"Failed to get user by id {user_id}: {e}")
        return None

def get_user_by_email(db: Session, email: str):
    try:
        return db.query(models.User).filter(models.User.email == email).first()
    except Exception as e:
        logger.error(f"Failed to get user by email {email}: {e}")
        return None

def get_user(db: Session, user_id: int):
    """Alias for get_user_by_id for backward compatibility"""
    return get_user_by_id(db, user_id)

def create_user(db: Session, email: str, password: str, full_name: str | None = None):
    try:
        hashed_password = get_password_hash(password)
        db_user = models.User(email=email, hashed_password=hashed_password, full_name=full_name)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except Exception as e:
        logger.error(f"Failed to create user {email}: {e}")
        db.rollback()
        raise

# --- Job CRUD ---
def create_job(db: Session, job_id: str, user_id: int, job_type: str, progress_details: dict | None = None):
    try:
        progress_details_json = json.dumps(progress_details) if progress_details else None
        
        db_job = models.Job(
            id=job_id, 
            user_id=user_id, 
            status="PENDING", 
            job_type=job_type,
            progress_details=progress_details_json
        )
        db.add(db_job)
        db.commit()
        db.refresh(db_job)
        return db_job
    except Exception as e:
        logger.error(f"Failed to create job {job_id}: {e}")
        db.rollback()
        raise

def get_job(db: Session, job_id: str):
    try:
        job = db.query(models.Job).filter(models.Job.id == job_id).first()
        if job:
            # Parse JSON fields safely
            if job.progress_details and isinstance(job.progress_details, str):
                try: 
                    job.progress_details = json.loads(job.progress_details)
                except json.JSONDecodeError: 
                    job.progress_details = {"error": "Could not parse progress."}
            
            if job.results and isinstance(job.results, str):
                try: 
                    job.results = json.loads(job.results)
                except json.JSONDecodeError: 
                    job.results = {"error": "Could not parse results."}
        return job
    except Exception as e:
        logger.error(f"Failed to get job {job_id}: {e}")
        return None

def update_job_full_status(
    db: Session, 
    job_id: str, 
    status: str | None = None,
    progress_details: dict | None = None, 
    results: dict | None = None, 
    error_message: str | None = None
):
    try:
        job = db.query(models.Job).filter(models.Job.id == job_id).first()
        if not job:
            logger.warning(f"Job {job_id} not found for status update")
            return None
            
        if status is not None:
            job.status = status
        
        if progress_details is not None:
            job.progress_details = json.dumps(progress_details)
        
        if results is not None:
            job.results = json.dumps(results)
        
        if error_message is not None:
            job.error_message = error_message
        
        db.commit()
        db.refresh(job)
        return job
    except Exception as e:
        logger.error(f"Failed to update job {job_id}: {e}")
        db.rollback()
        raise

# --- Brand Profile CRUD ---
def get_brand_profile(db: Session, user_id: int):
    try:
        profile = db.query(models.BrandProfile).filter(models.BrandProfile.user_id == user_id).first()
        if profile:
            return {"brand_voice": profile.brand_voice, "brand_cta": profile.brand_cta}
        return {}
    except Exception as e:
        logger.error(f"Failed to get brand profile for user {user_id}: {e}")
        return {}

def update_brand_profile(db: Session, user_id: int, brand_voice: str | None = None, brand_cta: str | None = None):
    try:
        profile = db.query(models.BrandProfile).filter(models.BrandProfile.user_id == user_id).first()
        if profile:
            if brand_voice is not None:
                profile.brand_voice = brand_voice
            if brand_cta is not None:
                profile.brand_cta = brand_cta
        else:
            profile = models.BrandProfile(user_id=user_id, brand_voice=brand_voice, brand_cta=brand_cta)
            db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile
    except Exception as e:
        logger.error(f"Failed to update brand profile for user {user_id}: {e}")
        db.rollback()
        raise

# --- Usage Log CRUD ---
def track_usage(db: Session, user_id: int, model: str, operation: str, cost: float):
    try:
        log = models.UsageLog(user_id=user_id, model=model, operation=operation, cost=cost)
        db.add(log)
        db.commit()
        db.refresh(log)
        return log
    except Exception as e:
        logger.error(f"Failed to track usage for user {user_id}: {e}")
        db.rollback()
        raise

def get_usage_summary(db: Session, user_id: int | None = None):
    """Fixed: Much more efficient query using SQL aggregation"""
    try:
        today = datetime.utcnow().date()
        
        # Use SQL aggregation instead of Python sum for efficiency
        if user_id:
            total_cost = db.query(func.sum(models.UsageLog.cost)).filter(
                models.UsageLog.user_id == user_id
            ).scalar() or 0.0
            
            daily_cost = db.query(func.sum(models.UsageLog.cost)).filter(
                models.UsageLog.user_id == user_id,
                models.UsageLog.timestamp >= today
            ).scalar() or 0.0
        else:
            total_cost = db.query(func.sum(models.UsageLog.cost)).scalar() or 0.0
            daily_cost = db.query(func.sum(models.UsageLog.cost)).filter(
                models.UsageLog.timestamp >= today
            ).scalar() or 0.0
        
        return {"total_cost": float(total_cost), "daily_cost": float(daily_cost)}
    except Exception as e:
        logger.error(f"Failed to get usage summary: {e}")
        return {"total_cost": 0.0, "daily_cost": 0.0}

def get_user_videos_today(db: Session, user_id: int):
    try:
        today_start = datetime.combine(date.today(), datetime.min.time())
        count = db.query(models.UsageLog).filter(
            models.UsageLog.user_id == user_id,
            models.UsageLog.operation.in_(['video', 'videoclip']),
            models.UsageLog.timestamp >= today_start
        ).count()
        return count
    except Exception as e:
        logger.error(f"Failed to get user videos today for user {user_id}: {e}")
        return 0

# --- Cache CRUD ---
def get_cached_response(db: Session, request_hash: str):
    try:
        cache_entry = db.query(models.APICache).filter(models.APICache.request_hash == request_hash).first()
        if cache_entry:
            return cache_entry.response_text
        return None
    except Exception as e:
        logger.error(f"Failed to get cached response for hash {request_hash}: {e}")
        return None

def set_cached_response(db: Session, request_hash: str, response_text: str):
    try:
        existing_entry = db.query(models.APICache).filter(models.APICache.request_hash == request_hash).first()
        if existing_entry:
            existing_entry.response_text = response_text
            existing_entry.created_at = datetime.utcnow()
        else:
            new_entry = models.APICache(request_hash=request_hash, response_text=response_text, created_at=datetime.utcnow())
            db.add(new_entry)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to set cached response: {e}")
        db.rollback()

def get_cached_transcript(db: Session, source_url: str):
    try:
        transcript_entry = db.query(models.TranscriptCache).filter(models.TranscriptCache.source_url == source_url).first()
        if transcript_entry and transcript_entry.transcript_json:
            try:
                return json.loads(transcript_entry.transcript_json)
            except json.JSONDecodeError:
                return None
        return None
    except Exception as e:
        logger.error(f"Failed to get cached transcript for {source_url}: {e}")
        return None

def set_cached_transcript(db: Session, source_url: str, transcript_data: dict):
    try:
        transcript_json = json.dumps(transcript_data)
        existing_entry = db.query(models.TranscriptCache).filter(models.TranscriptCache.source_url == source_url).first()
        if existing_entry:
            existing_entry.transcript_json = transcript_json
            existing_entry.created_at = datetime.utcnow()
        else:
            new_entry = models.TranscriptCache(source_url=source_url, transcript_json=transcript_json, created_at=datetime.utcnow())
            db.add(new_entry)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to set cached transcript: {e}")
        db.rollback()
        
def get_first_user(db: Session) -> models.User | None:
    """Get the first user in the database (for testing/admin purposes)"""
    try:
        return db.query(models.User).first()
    except Exception as e:
        logger.error(f"Failed to get first user: {e}")
        return None

def count_active_jobs(db: Session) -> int:
    """Count jobs that are currently active (PENDING or IN_PROGRESS)"""
    try:
        return db.query(models.Job).filter(
            models.Job.status.in_(['PENDING', 'IN_PROGRESS'])
        ).count()
    except Exception as e:
        logger.error(f"Failed to count active jobs: {e}")
        return 0

def count_failed_jobs_since(db: Session, since: datetime) -> int:
    """Count jobs that failed since a given datetime"""
    try:
        return db.query(models.Job).filter(
            models.Job.status == 'FAILED',
            models.Job.updated_at >= since
        ).count()
    except Exception as e:
        logger.error(f"Failed to count failed jobs since {since}: {e}")
        return 0
       