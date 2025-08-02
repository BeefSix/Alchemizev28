import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Union
from pydantic import AnyHttpUrl, Field

class Settings(BaseSettings):
    APP_NAME: str = "Alchemize AI"
    API_V1_STR: str = "/api/v1"

    # --- SECURITY FIX ---
    # The SECRET_KEY no longer has a default value.
    # The application will fail to start if this is not set in the .env file.
    SECRET_KEY: str

    # --- DATABASE SETTINGS ---
    # This will be read from your .env file
    DATABASE_URL: str

    # JWT settings
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8 # 8 days

    # CORS settings
    CORS_ORIGINS: List[Union[AnyHttpUrl, str]] = ["http://localhost:8501", "http://127.0.0.1:8501"]

    # OpenAI API Key
    OPENAI_API_KEY: str

    # Firebase Credentials
    FIREBASE_CREDENTIALS_JSON: str = ""
    FIREBASE_STORAGE_BUCKET: str = ""

    # Celery Settings
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # AI Model Pricing
    TOKEN_PRICES: dict = {
        "gpt-4o": {"input": 5.00, "output": 15.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "whisper-1": {"input": 0.0, "output": 0.006},
    }

    # Daily Usage Limits
    DAILY_LIMITS: dict = {
        'videos_per_user': 10,
        'total_daily_cost': 15.00,
        'max_video_duration': 3600
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
            return os.path.join(self.STATIC_FILES_ROOT_DIR, "generated")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()