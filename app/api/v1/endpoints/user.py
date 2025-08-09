# app/api/v1/endpoints/user.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

from app.db.base import get_db
from app.db import crud, models
from app.services.auth import get_current_active_user
from app.core.security_utils import verify_password, get_password_hash, validate_password_strength
from app.core.logger import logger

router = APIRouter()

# Pydantic models
class UserProfile(BaseModel):
    """User profile response model"""
    id: int
    email: str
    full_name: Optional[str] = None
    is_active: bool
    subscription_plan: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class UserProfileUpdate(BaseModel):
    """User profile update request model"""
    full_name: Optional[str] = Field(None, max_length=100, description="User's full name")
    email: Optional[EmailStr] = Field(None, description="User's email address")

class PasswordChangeRequest(BaseModel):
    """Password change request model"""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")
    confirm_password: str = Field(..., description="Confirm new password")

class UserStats(BaseModel):
    """User statistics model"""
    total_videos_processed: int
    total_content_generated: int
    storage_used_mb: float
    account_age_days: int

class BrandProfileResponse(BaseModel):
    """Brand profile response model"""
    brand_voice: Optional[Dict[str, Any]] = None
    brand_cta: Optional[str] = None

class BrandProfileUpdate(BaseModel):
    """Brand profile update request model"""
    tone: Optional[str] = Field(None, description="Brand tone (e.g., professional, casual, friendly)")
    energy_level: Optional[str] = Field(None, description="Energy level (low, medium, high)")
    personality_traits: Optional[List[str]] = Field(None, description="List of personality traits")
    target_audience: Optional[str] = Field(None, description="Target audience description")
    call_to_action_style: Optional[str] = Field(None, description="Preferred call-to-action style")
    emoji_usage: Optional[str] = Field(None, description="Emoji usage preference (none, minimal, moderate, heavy)")
    sample_posts: Optional[List[str]] = Field(None, description="Sample posts that represent the brand voice")
    brand_cta: Optional[str] = Field(None, description="Default call-to-action text")

@router.get("/profile", response_model=UserProfile)
async def get_user_profile(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's profile information"""
    try:
        logger.info(f"User {current_user.email} requested profile information")
        return UserProfile.from_orm(current_user)
    except Exception as e:
        logger.error(f"Error retrieving profile for user {current_user.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve profile information"
        )

@router.put("/profile", response_model=UserProfile)
async def update_user_profile(
    profile_update: UserProfileUpdate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update current user's profile information"""
    try:
        # Check if email is being changed and if it's already taken
        if profile_update.email and profile_update.email != current_user.email:
            existing_user = crud.get_user_by_email(db, email=profile_update.email)
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email address is already registered"
                )
        
        # Update user fields
        update_data = profile_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(current_user, field, value)
        
        db.commit()
        db.refresh(current_user)
        
        logger.info(f"User {current_user.email} updated profile: {list(update_data.keys())}")
        return UserProfile.from_orm(current_user)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating profile for user {current_user.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile information"
        )

@router.post("/change-password")
async def change_password(
    password_request: PasswordChangeRequest,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Change user's password"""
    try:
        # Verify current password
        if not verify_password(password_request.current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Check if new password matches confirmation
        if password_request.new_password != password_request.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password and confirmation do not match"
            )
        
        # Validate new password strength (this will raise HTTPException if invalid)
        is_valid, message = validate_password_strength(password_request.new_password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password validation failed: {message}"
            )
        
        # Check if new password is different from current
        if verify_password(password_request.new_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different from current password"
            )
        
        # Update password
        current_user.hashed_password = get_password_hash(password_request.new_password)
        db.commit()
        
        logger.info(f"User {current_user.email} changed password successfully")
        return {"message": "Password changed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error changing password for user {current_user.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )

@router.get("/stats", response_model=UserStats)
async def get_user_stats(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user statistics and usage information"""
    try:
        # Calculate account age
        account_age = (datetime.utcnow() - current_user.created_at).days
        
        # Implement actual statistics calculation
        try:
            # Count total videos processed by this user
            total_videos = db.query(models.Job).filter(
                models.Job.user_id == current_user.id,
                models.Job.job_type.in_(['video_processing', 'video_clipping'])
            ).count()
            
            # Count total content generation jobs
            total_content = db.query(models.Job).filter(
                models.Job.user_id == current_user.id,
                models.Job.job_type == 'content_generation'
            ).count()
            
            # Calculate storage usage (simplified - would need actual file size tracking)
            # For now, estimate based on job count
            estimated_storage = total_videos * 50.0  # Estimate 50MB per video job
            
            stats = UserStats(
                total_videos_processed=total_videos,
                total_content_generated=total_content,
                storage_used_mb=estimated_storage,
                account_age_days=account_age
            )
        except Exception as calc_error:
            logger.error(f"Error calculating user stats: {calc_error}")
            # Fallback to basic stats if calculation fails
            stats = UserStats(
                total_videos_processed=0,
                total_content_generated=0,
                storage_used_mb=0.0,
                account_age_days=account_age
            )
        
        logger.info(f"User {current_user.email} requested usage statistics")
        return stats
        
    except Exception as e:
        logger.error(f"Error retrieving stats for user {current_user.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user statistics"
        )

@router.delete("/account")
async def delete_account(
    current_password: str,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete user account (soft delete by deactivating)"""
    try:
        # Verify password before account deletion
        if not verify_password(current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password verification failed"
            )
        
        # Soft delete by deactivating account
        current_user.is_active = False
        db.commit()
        
        logger.warning(f"User account deactivated: {current_user.email}")
        return {"message": "Account has been deactivated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deactivating account for user {current_user.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate account"
        )

@router.get("/brand-profile", response_model=BrandProfileResponse)
async def get_brand_profile(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's brand profile"""
    try:
        brand_profile = crud.get_brand_profile(db, current_user.id)
        
        # Parse brand_voice JSON if it exists
        brand_voice = None
        if brand_profile.get('brand_voice'):
            try:
                brand_voice = json.loads(brand_profile['brand_voice'])
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Invalid brand voice JSON for user {current_user.id}")
                brand_voice = None
        
        response = BrandProfileResponse(
            brand_voice=brand_voice,
            brand_cta=brand_profile.get('brand_cta')
        )
        
        logger.info(f"User {current_user.email} requested brand profile")
        return response
        
    except Exception as e:
        logger.error(f"Error retrieving brand profile for user {current_user.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve brand profile"
        )

@router.put("/brand-profile", response_model=BrandProfileResponse)
async def update_brand_profile(
    profile_update: BrandProfileUpdate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update current user's brand profile"""
    try:
        # Build brand voice JSON from individual fields
        brand_voice_data = {}
        update_data = profile_update.dict(exclude_unset=True)
        
        # Extract brand_cta separately
        brand_cta = update_data.pop('brand_cta', None)
        
        # Build brand voice object from remaining fields
        if update_data:
            brand_voice_data = update_data
        
        # Convert to JSON string if we have data
        brand_voice_json = json.dumps(brand_voice_data) if brand_voice_data else None
        
        # Update brand profile
        updated_profile = crud.update_brand_profile(
            db=db,
            user_id=current_user.id,
            brand_voice=brand_voice_json,
            brand_cta=brand_cta
        )
        
        # Parse response
        brand_voice = None
        if brand_voice_json:
            try:
                brand_voice = json.loads(brand_voice_json)
            except (json.JSONDecodeError, TypeError):
                brand_voice = None
        
        response = BrandProfileResponse(
            brand_voice=brand_voice,
            brand_cta=brand_cta
        )
        
        logger.info(f"User {current_user.email} updated brand profile")
        return response
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating brand profile for user {current_user.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update brand profile"
        )