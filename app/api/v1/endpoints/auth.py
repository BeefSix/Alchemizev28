# app/api/v1/endpoints/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db import crud
from app.db.base import get_db
from app.services.auth import create_access_token, get_current_active_user
from app.core.security_utils import verify_password, validate_password_strength
from app.db import models
from pydantic import BaseModel
import logging
import re

logger = logging.getLogger(__name__)
router = APIRouter()

class UserCreate(models.UserBase):
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str | None = None
    is_active: bool
    subscription_plan: str = "free"
    
    class Config:
        from_attributes = True

class TokenResponse(models.BaseModel):
    access_token: str
    token_type: str
    user_email: str

@router.post("/register", response_model=UserResponse)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user account with comprehensive validation"""
    # Sanitize and validate email
    email = user.email.strip().lower()
    if not email or "@" not in email or "." not in email:
        raise HTTPException(
            status_code=400, 
            detail="Please provide a valid email address"
        )
    
    # Enhanced email validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        raise HTTPException(
            status_code=400,
            detail="Invalid email format"
        )
    
    # Comprehensive password validation
    is_valid, validation_message = validate_password_strength(user.password)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail=f"Password validation failed: {validation_message}"
        )
    
    # Sanitize full name if provided
    full_name = None
    if user.full_name:
        full_name = user.full_name.strip()[:100]  # Limit length and trim whitespace
        # Remove potentially dangerous characters
        full_name = re.sub(r'[<>"\'\/]', '', full_name)
        if not full_name:  # If nothing left after sanitization
            full_name = None
    
    # Check if user already exists
    db_user = crud.get_user_by_email(db, email=email)
    if db_user:
        raise HTTPException(
            status_code=400, 
            detail="An account with this email already exists"
        )
    
    try:
        new_user = crud.create_user(
            db=db, 
            email=email, 
            password=user.password, 
            full_name=full_name
        )
        logger.info(f"New user registered: {user.email}")
        return new_user
    except Exception as e:
        logger.error(f"User registration failed for {user.email}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Registration failed. Please try again."
        )

@router.post("/token", response_model=TokenResponse)
def login_for_access_token(
    db: Session = Depends(get_db), 
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """Authenticate user and return access token"""
    try:
        user = crud.get_user_by_email(db, email=form_data.username.lower())
        if not user or not verify_password(form_data.password, user.hashed_password):
            logger.warning(f"Failed login attempt for: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is disabled",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token = create_access_token(data={"sub": user.email})
        logger.info(f"Successful login: {user.email}")
        
        return {
            "access_token": access_token, 
            "token_type": "bearer",
            "user_email": user.email
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error for {form_data.username}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Login failed. Please try again."
        )

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: models.User = Depends(get_current_active_user)):
    """Get current user profile"""
    return current_user

@router.post("/logout")
def logout():
    """Logout endpoint (client-side token removal)"""
    return {"message": "Successfully logged out"}