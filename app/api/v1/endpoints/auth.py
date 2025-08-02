# app/api/v1/endpoints/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db import crud
from app.db.base import get_db
from app.services.auth import create_access_token, verify_password, get_current_active_user
from app.db import models
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class UserCreate(models.UserBase):
    password: str

class User(models.UserBase):
    id: int
    is_active: bool

class TokenResponse(models.BaseModel):
    access_token: str
    token_type: str
    user_email: str

@router.post("/register", response_model=User)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user account"""
    # Validate email format (basic check)
    if "@" not in user.email or "." not in user.email:
        raise HTTPException(
            status_code=400, 
            detail="Please provide a valid email address"
        )
    
    # Check password strength (basic check)
    if len(user.password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long"
        )
    
    # Check if user already exists
    db_user = crud.get_user_by_email(db, email=user.email.lower())
    if db_user:
        raise HTTPException(
            status_code=400, 
            detail="An account with this email already exists"
        )
    
    try:
        new_user = crud.create_user(
            db=db, 
            email=user.email.lower(), 
            password=user.password, 
            full_name=user.full_name
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

@router.get("/me", response_model=User)
def read_users_me(current_user: models.User = Depends(get_current_active_user)):
    """Get current user profile"""
    return current_user

@router.post("/logout")
def logout():
    """Logout endpoint (client-side token removal)"""
    return {"message": "Successfully logged out"}