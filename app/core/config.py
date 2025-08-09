import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Union
from pydantic import AnyHttpUrl, Field, field_validator
import secrets
from dotenv import load_dotenv
from .env_security import SecureEnvironment, get_env, get_env_bool, get_env_int

# Load .env.local first (for local development), then .env (for defaults)
if os.path.exists('.env.local'):
    load_dotenv('.env.local', override=True)
load_dotenv('.env')

# Validate critical environment variables on startup
try:
    SecureEnvironment.validate_critical_vars()
    SecureEnvironment.log_environment_status()
except Exception as e:
    print(f"⚠️  Environment Security Warning: {e}")
    print("Application will continue but some features may not work properly.")
    print("Please check your .env file and ensure all required variables are set.")

class Settings(BaseSettings):
    APP_NAME: str = "Zuexis AI"
    API_V1_STR: str = "/api/v1"

    # --- SECURITY SETTINGS ---
    SECRET_KEY: str = Field(default_factory=lambda: get_env('SECRET_KEY', secrets.token_urlsafe(32), required=True))
    
    @field_validator('SECRET_KEY')
    @classmethod
    def validate_secret_key(cls, v):
        if len(v) < 32:
            # Auto-generate if too short instead of crashing
            return secrets.token_urlsafe(32)
        # Check if it's not a weak/default key
        weak_keys = ['your-secret-key', 'change-me', 'secret', 'password', 'your_secret_key_here_generate_with_openssl_rand_hex_32']
        if v.lower() in weak_keys:
            return secrets.token_urlsafe(32)
        return v

    # --- DATABASE SETTINGS ---
    DATABASE_URL: str = Field(default_factory=lambda: get_env('DATABASE_URL', ''))
    
    @field_validator('DATABASE_URL')
    @classmethod
    def validate_database_url(cls, v, info):
        # Fail fast in production if DATABASE_URL is missing
        if info.data.get('ENVIRONMENT') == 'production' and not v:
            raise ValueError('DATABASE_URL is required in production environment')
        
        # In development, allow SQLite fallback
        if not v and info.data.get('ENVIRONMENT') != 'production':
            return 'sqlite:///./app.db'
        
        # Validate URL format
        if v and ('localhost' in v or '127.0.0.1' in v) and info.data.get('ENVIRONMENT') == 'production':
            print("⚠️  Warning: Using localhost database in production environment")
        
        return v

    # JWT settings with improved security
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 1  # 1 day (reduced from 8)
    ALGORITHM: str = "HS256"

    # CORS settings - Production Ready Configuration
    @property
    def CORS_ORIGINS(self) -> List[Union[AnyHttpUrl, str]]:
        """Get CORS origins based on environment"""
        if self.is_production:
            # Production: Restrict to exact domains
            origins = [
                get_env('FRONTEND_URL', 'https://yourdomain.com'),
                get_env('ADMIN_URL', 'https://admin.yourdomain.com'),
            ]
            # Remove placeholder domains
            origins = [origin for origin in origins if origin and not origin.startswith('https://yourdomain.com')]
            
            # Add localhost only if explicitly enabled in production
            if get_env_bool('ALLOW_LOCALHOST_IN_PROD', False):
                origins.extend([
                    "http://localhost:3000",
                    "http://127.0.0.1:3000",
                ])
            return origins
        else:
            # Development: Allow localhost
            return [
                "http://localhost:3000",  # Next.js dev server
                "http://localhost:3001",  # Next.js dev server (alternate port)
                "http://127.0.0.1:3000",
                "http://127.0.0.1:3001",
            ]
    
    # Trusted hosts for production
    @property
    def TRUSTED_HOSTS(self) -> List[str]:
        """Get trusted hosts based on environment"""
        if self.is_production:
            return get_env('TRUSTED_HOSTS', 'yourdomain.com,api.yourdomain.com').split(',')
        else:
            return get_env('TRUSTED_HOSTS', 'localhost,127.0.0.1').split(',')

    # OpenAI API Key with validation
    OPENAI_API_KEY: str = Field(default_factory=lambda: get_env('OPENAI_API_KEY', '', required=True))
    
    # Payment settings (Stripe) - Enhanced validation
    STRIPE_SECRET_KEY: str = Field(default_factory=lambda: get_env('STRIPE_SECRET_KEY', ''))
    STRIPE_PUBLISHABLE_KEY: str = Field(default_factory=lambda: get_env('STRIPE_PUBLISHABLE_KEY', ''))
    STRIPE_WEBHOOK_SECRET: str = Field(default_factory=lambda: get_env('STRIPE_WEBHOOK_SECRET', ''))
    
    @field_validator('OPENAI_API_KEY')
    @classmethod
    def validate_openai_key(cls, v):
        if not v:  # Allow empty for development
            return v
        # Allow placeholder values for development/testing
        placeholder_values = ['sk-your-openai-api-key-here', 'your-openai-api-key', 'your_openai_api_key_here', 'PLACEHOLDER_OPENAI_API_KEY']
        if v in placeholder_values or v.startswith('PLACEHOLDER_OPENAI_API_KEY'):
            return v
        if not v.startswith('sk-'):
            raise ValueError('OPENAI_API_KEY must start with sk-')
        if len(v) < 40:
            raise ValueError('OPENAI_API_KEY appears to be invalid (too short)')
        return v
    
    @field_validator('STRIPE_SECRET_KEY')
    @classmethod
    def validate_stripe_secret_key(cls, v):
        if v and not v.startswith('sk_') and not v.startswith('PLACEHOLDER_STRIPE_SECRET_KEY'):
            raise ValueError('STRIPE_SECRET_KEY must start with sk_')
        return v
    
    @field_validator('STRIPE_PUBLISHABLE_KEY')
    @classmethod
    def validate_stripe_publishable_key(cls, v):
        if v and not v.startswith('pk_'):
            raise ValueError('STRIPE_PUBLISHABLE_KEY must start with pk_')
        return v
    
    @field_validator('STRIPE_WEBHOOK_SECRET')
    @classmethod
    def validate_stripe_webhook_secret(cls, v):
        if v and not v.startswith('whsec_') and not v.startswith('PLACEHOLDER_STRIPE_WEBHOOK_SECRET'):
            raise ValueError('STRIPE_WEBHOOK_SECRET must start with whsec_')
        return v

    # Firebase Credentials - Optional but validated if provided
    FIREBASE_CREDENTIALS_PATH: str = Field(default_factory=lambda: get_env('FIREBASE_CREDENTIALS_PATH', ''))
    FIREBASE_CREDENTIALS_JSON: str = Field(default_factory=lambda: get_env('FIREBASE_CREDENTIALS_JSON', ''))
    FIREBASE_STORAGE_BUCKET: str = Field(default_factory=lambda: get_env('FIREBASE_STORAGE_BUCKET', ''))

    # Redis Configuration - Unified with single REDIS_URL
    REDIS_URL: str = Field(default_factory=lambda: get_env('REDIS_URL', ''))
    
    # Individual Redis settings (fallback for development)
    REDIS_PASSWORD: str = Field(default_factory=lambda: get_env('REDIS_PASSWORD', ''))
    REDIS_HOST: str = Field(default_factory=lambda: get_env('REDIS_HOST', 'localhost'))
    REDIS_PORT: int = Field(default_factory=lambda: get_env_int('REDIS_PORT', 6379))
    REDIS_DB: int = Field(default_factory=lambda: get_env_int('REDIS_DB', 0))
    
    # Celery Settings - Auto-configured from REDIS_URL
    CELERY_BROKER_URL: str = Field(default_factory=lambda: get_env('CELERY_BROKER_URL', ''))
    CELERY_RESULT_BACKEND: str = Field(default_factory=lambda: get_env('CELERY_RESULT_BACKEND', ''))
    
    @field_validator('REDIS_URL')
    @classmethod
    def validate_redis_url(cls, v, info):
        # Fail fast in production if REDIS_URL is missing
        if info.data.get('ENVIRONMENT') == 'production' and not v:
            raise ValueError('REDIS_URL is required in production environment')
        
        # In development, allow localhost fallback
        if not v and info.data.get('ENVIRONMENT') != 'production':
            return 'redis://localhost:6379/0'
        
        return v
    
    @property
    def get_redis_url(self) -> str:
        """Get Redis URL, building from components if not provided"""
        if self.REDIS_URL:
            return self.REDIS_URL
        
        # Build from individual components
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        else:
            return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    @property
    def get_celery_broker_url(self) -> str:
        """Get Celery broker URL, defaulting to Redis URL"""
        if self.CELERY_BROKER_URL:
            return self.CELERY_BROKER_URL
        return self.get_redis_url
    
    @property
    def get_celery_result_backend(self) -> str:
        """Get Celery result backend URL, defaulting to Redis URL"""
        if self.CELERY_RESULT_BACKEND:
            return self.CELERY_RESULT_BACKEND
        return self.get_redis_url

    # File Upload Security Limits
    MAX_FILE_SIZE_MB: int = Field(default_factory=lambda: get_env_int('MAX_FILE_SIZE_MB', 500))
    MAX_FILES_PER_USER_PER_DAY: int = Field(default_factory=lambda: get_env_int('MAX_FILES_PER_USER_PER_DAY', 20))
    ALLOWED_VIDEO_EXTENSIONS: List[str] = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.wmv', '.3gp', '.flv', '.m4v', '.ogv', '.ts', '.mts', '.m2ts', '.asf', '.rm', '.rmvb', '.vob', '.mpg', '.mpeg', '.m2v']
    
    # Upload Directory Configuration
    UPLOAD_DIR: str = Field(default_factory=lambda: get_env('UPLOAD_DIR', 'uploads'))

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
        'ffmpeg_timeout': 1800,  # 30 minutes for hour-long videos
        'max_audio_duration': 3600,  # 1 hour max for transcription
        'audio_extraction_timeout': 600,  # 10 minutes for audio extraction
    }

    # Rate Limiting Settings
    RATE_LIMITS: dict = {
        'video_upload': "20/hour",
        'content_generation': "50/hour", 
        'api_calls': "1000/hour",
        'downloads': "100/hour"
    }

    # Environment Detection
    ENVIRONMENT: str = Field(default_factory=lambda: get_env('ENVIRONMENT', 'development'))
    DEBUG: bool = Field(default_factory=lambda: get_env_bool('DEBUG', False))
    
    @field_validator('ENVIRONMENT')
    @classmethod
    def validate_environment(cls, v):
        valid_environments = ['development', 'staging', 'production', 'test']
        if v.lower() not in valid_environments:
            raise ValueError(f'ENVIRONMENT must be one of: {", ".join(valid_environments)}')
        return v.lower()
    
    @field_validator('DEBUG')
    @classmethod
    def validate_debug(cls, v, info):
        # Force DEBUG=False in production
        if info.data.get('ENVIRONMENT') == 'production' and v:
            print("⚠️  Warning: DEBUG=True overridden to False in production environment")
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
    
    # Monitoring and Alerting Configuration
    ALERT_EMAIL_FROM: str = Field(default_factory=lambda: get_env('ALERT_EMAIL_FROM', ''))
    ALERT_EMAIL_TO: str = Field(default_factory=lambda: get_env('ALERT_EMAIL_TO', ''))
    SMTP_HOST: str = Field(default_factory=lambda: get_env('SMTP_HOST', ''))
    SMTP_PORT: int = Field(default_factory=lambda: get_env_int('SMTP_PORT', 587))
    SMTP_USERNAME: str = Field(default_factory=lambda: get_env('SMTP_USERNAME', ''))
    SMTP_PASSWORD: str = Field(default_factory=lambda: get_env('SMTP_PASSWORD', ''))
    MONITORING_WEBHOOK_URL: str = Field(default_factory=lambda: get_env('MONITORING_WEBHOOK_URL', ''))
    
    # System thresholds for alerts
    ALERT_THRESHOLDS: dict = {
        'cpu_warning': get_env_int('CPU_WARNING_THRESHOLD', 80),
        'cpu_critical': get_env_int('CPU_CRITICAL_THRESHOLD', 90),
        'memory_warning': get_env_int('MEMORY_WARNING_THRESHOLD', 85),
        'memory_critical': get_env_int('MEMORY_CRITICAL_THRESHOLD', 95),
        'disk_warning': get_env_int('DISK_WARNING_THRESHOLD', 85),
        'disk_critical': get_env_int('DISK_CRITICAL_THRESHOLD', 95),
        'failed_jobs_24h_warning': get_env_int('FAILED_JOBS_WARNING_THRESHOLD', 10),
        'active_jobs_warning': get_env_int('ACTIVE_JOBS_WARNING_THRESHOLD', 50)
    }

    # Storage Configuration - Production Ready
    STORAGE_CONFIG: dict = {
        # Storage backend selection
        'backend': Field(default_factory=lambda: get_env('STORAGE_BACKEND', 'local')),  # 'local', 's3', 'gcs'
        
        # S3 Configuration (if using S3)
        's3_bucket': Field(default_factory=lambda: get_env('S3_BUCKET', '')),
        's3_region': Field(default_factory=lambda: get_env('S3_REGION', 'us-east-1')),
        's3_access_key': Field(default_factory=lambda: get_env('S3_ACCESS_KEY', '')),
        's3_secret_key': Field(default_factory=lambda: get_env('S3_SECRET_KEY', '')),
        's3_endpoint_url': Field(default_factory=lambda: get_env('S3_ENDPOINT_URL', '')),
        
        # Storage quotas and limits
        'max_file_size_mb': Field(default_factory=lambda: get_env_int('MAX_FILE_SIZE_MB', 500)),
        'max_total_storage_gb': Field(default_factory=lambda: get_env_int('MAX_TOTAL_STORAGE_GB', 10)),
        'max_files_per_user': Field(default_factory=lambda: get_env_int('MAX_FILES_PER_USER', 100)),
        'max_file_age_days': Field(default_factory=lambda: get_env_int('MAX_FILE_AGE_DAYS', 30)),
        
        # Retention policies
        'temp_file_retention_hours': Field(default_factory=lambda: get_env_int('TEMP_FILE_RETENTION_HOURS', 24)),
        'processed_file_retention_days': Field(default_factory=lambda: get_env_int('PROCESSED_FILE_RETENTION_DAYS', 7)),
        'user_file_retention_days': Field(default_factory=lambda: get_env_int('USER_FILE_RETENTION_DAYS', 30)),
        
        # Cleanup thresholds
        'cleanup_threshold_percent': Field(default_factory=lambda: get_env_int('CLEANUP_THRESHOLD_PERCENT', 80)),
        'emergency_cleanup_threshold_percent': Field(default_factory=lambda: get_env_int('EMERGENCY_CLEANUP_THRESHOLD_PERCENT', 95)),
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