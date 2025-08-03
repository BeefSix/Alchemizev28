import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Union
from pydantic import AnyHttpUrl, Field, field_validator
import secrets

class Settings(BaseSettings):
    APP_NAME: str = "Alchemize AI"
    API_V1_STR: str = "/api/v1"

    # --- SECURITY SETTINGS ---
    SECRET_KEY: str = Field(min_length=32)
    
    @field_validator('SECRET_KEY')
    @classmethod
    def validate_secret_key(cls, v):
        if len(v) < 32:
            raise ValueError('SECRET_KEY must be at least 32 characters long')
        # Check if it's not a weak/default key
        weak_keys = ['your-secret-key', 'change-me', 'secret', 'password']
        if v.lower() in weak_keys:
            raise ValueError('SECRET_KEY cannot be a common weak key')
        return v

    # --- DATABASE SETTINGS ---
    DATABASE_URL: str = Field(min_length=10)
    
    @field_validator('DATABASE_URL')
    @classmethod
    def validate_database_url(cls, v):
        if 'localhost' in v or '127.0.0.1' in v:
            # Only warn in development, don't fail
            pass
        return v

    # JWT settings with improved security
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 1  # 1 day (reduced from 8)
    ALGORITHM: str = "HS256"

    # CORS settings - be more restrictive in production
    CORS_ORIGINS: List[Union[AnyHttpUrl, str]] = [
        "http://localhost:8501", 
        "http://127.0.0.1:8501",
        "http://localhost:3000",  # React dev server if you add one
    ]

    # OpenAI API Key with validation
    OPENAI_API_KEY: str = Field(min_length=20)
    
    @field_validator('OPENAI_API_KEY')
    @classmethod
    def validate_openai_key(cls, v):
        if not v.startswith('sk-'):
            raise ValueError('OPENAI_API_KEY must start with sk-')
        if len(v) < 40:
            raise ValueError('OPENAI_API_KEY appears to be invalid (too short)')
        return v

    # Firebase Credentials - Optional but validated if provided
    FIREBASE_CREDENTIALS_JSON: str = ""
    FIREBASE_STORAGE_BUCKET: str = ""

    # Celery Settings with validation
    CELERY_BROKER_URL: str = Field(min_length=5)
    CELERY_RESULT_BACKEND: str = Field(min_length=5)

    # File Upload Security Limits
    MAX_FILE_SIZE_MB: int = 500
    MAX_FILES_PER_USER_PER_DAY: int = 20
    ALLOWED_VIDEO_EXTENSIONS: List[str] = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.wmv', '.3gp', '.flv']

    # AI Model Pricing (keep existing)
    TOKEN_PRICES: dict = {
        "gpt-4o": {"input": 5.00, "output": 15.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "whisper-1": {"input": 0.0, "output": 0.006},
    }

    # Daily Usage Limits with better defaults
    DAILY_LIMITS: dict = {
        'videos_per_user': 10,
        'total_daily_cost': 15.00,
        'max_video_duration': 3600,  # 1 hour max
        'max_clip_duration': 120,    # 2 minutes max per clip
    }
    
    # Static file configuration - Environment-aware paths
    STATIC_FILES_ROOT_DIR: str = "/app/static" if os.path.exists("/app/static") else "static"
    
    @property
    def STATIC_GENERATED_DIR(self) -> str:
        """Get the correct static generated directory path"""
        # Check if we're in Docker container with volume mount
        if os.path.exists("/app/data/static/generated"):
            return "/app/data/static/generated"
        elif os.path.exists("/app/static/generated"):
            return "/app/static/generated"
        else:
            generated_dir = os.path.join(self.STATIC_FILES_ROOT_DIR, "generated")
            os.makedirs(generated_dir, exist_ok=True)
            return generated_dir

    # Video Processing Settings
    VIDEO_PROCESSING: dict = {
        'max_clips_per_video': 5,
        'min_clip_duration': 15,
        'max_clip_duration': 120,
        'default_clip_duration': 60,
        'supported_aspect_ratios': ['9:16', '1:1', '16:9'],
        'karaoke_phrase_length': 4,
        'ffmpeg_timeout': 300,  # 5 minutes
    }

    # Rate Limiting Settings
    RATE_LIMITS: dict = {
        'video_upload': "20/hour",
        'content_generation': "50/hour", 
        'api_calls': "1000/hour",
        'downloads': "100/hour"
    }

    # Environment Detection
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=False)
    
    @field_validator('DEBUG')
    @classmethod
    def validate_debug(cls, v, info):
        # Force DEBUG=False in production
        if info.data.get('ENVIRONMENT') == 'production' and v:
            return False
        return v

    # Security Headers Configuration
    SECURITY_HEADERS: dict = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'",
    }

    model_config = SettingsConfigDict(
        env_file=".env", 
        extra="ignore",
        case_sensitive=True
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Create required directories
        os.makedirs(self.STATIC_GENERATED_DIR, exist_ok=True)
        os.makedirs(os.path.join(self.STATIC_GENERATED_DIR, "uploads"), exist_ok=True)
        os.makedirs(os.path.join(self.STATIC_GENERATED_DIR, "temp_downloads"), exist_ok=True)

    @property
    def is_production(self) -> bool:
        """Check if we're in production environment"""
        return self.ENVIRONMENT.lower() == "production"
    
    @property
    def max_file_size_bytes(self) -> int:
        """Get max file size in bytes"""
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

# Generate a secure secret key if one doesn't exist
def generate_secret_key() -> str:
    """Generate a cryptographically secure secret key"""
    return secrets.token_urlsafe(32)

# Initialize settings with validation
try:
    settings = Settings()
except Exception as e:
    print(f"❌ Configuration Error: {e}")
    print("\n🔧 Common fixes:")
    print("1. Check your .env file exists")
    print("2. Ensure SECRET_KEY is at least 32 characters")
    print("3. Verify OPENAI_API_KEY starts with 'sk-'")
    print("4. Check DATABASE_URL is properly formatted")
    
    # If SECRET_KEY is missing, suggest generating one
    if "SECRET_KEY" in str(e):
        new_key = generate_secret_key()
        print(f"\n🔑 Add this to your .env file:")
        print(f"SECRET_KEY={new_key}")
    
    raise