# app/core/security_utils.py
from passlib.context import CryptContext
from fastapi import HTTPException, status
import re

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password strength with simplified checks.
    Returns (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if len(password) > 128:
        return False, "Password must be less than 128 characters long"
    
    # Check for at least one uppercase letter
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    # Check for at least one lowercase letter
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    # Check for at least one digit
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    
    # Check for at least one special character
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character (!@#$%^&*(),.?\":{}|<>)"
    
    # Optional: Check for common weak passwords
    common_passwords = {
        'password', 'password123', '123456', '123456789', 'qwerty', 
        'abc123', 'password1', 'admin', 'letmein', 'welcome',
        'monkey', '1234567890', 'dragon', 'master', 'hello',
        'login', 'pass', 'admin123', 'root', 'user'
    }
    
    if password.lower() in common_passwords:
        return False, "Password is too common. Please choose a more secure password"
    
    return True, "Password is strong"

def get_password_hash(password: str) -> str:
    """Hash password after validation."""
    is_valid, message = validate_password_strength(password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password validation failed: {message}"
        )
    return pwd_context.hash(password)
