# app/core/config.py
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Union
from pydantic import AnyHttpUrl

class Settings(BaseSettings):
    APP_NAME: str = "Alchemize AI"
    API_V1_STR: str = "/api/v1"

    # Database settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./alchemize.db")

    # JWT settings for authentication
    SECRET_KEY: str = os.getenv("SECRET_KEY", "a_very_secret_key_that_should_be_changed")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS settings
    CORS_ORIGINS: List[Union[AnyHttpUrl, str]] = ["http://localhost:8501", "http://127.0.0.1:8501"]

    # OpenAI API Key
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Firebase Credentials
    FIREBASE_CREDENTIALS_JSON: str = os.getenv("FIREBASE_CREDENTIALS_JSON", "")
    FIREBASE_STORAGE_BUCKET: str = os.getenv("FIREBASE_STORAGE_BUCKET", "")

    # Celery Settings
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

    # ADDED: AI Model Pricing - CRITICAL FOR UTILS.PY
    TOKEN_PRICES: dict = {
        "gpt-4o": {"input": 5.00, "output": 15.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "whisper-1": {"input": 0.0, "output": 0.006}, # Cost per minute
    }

    # ADDED: Daily Usage Limits - CRITICAL FOR UTILS.PY
    DAILY_LIMITS: dict = {
        'videos_per_user': 10,
        'total_daily_cost': 15.00,
        'max_video_duration': 3600 # in seconds
    }
    
    # Define STATIC_GENERATED_DIR directly here, as it's a configuration
    STATIC_FILES_ROOT_DIR: str = "static" # Directory where FastAPI will mount static files
    STATIC_GENERATED_DIR: str = os.path.join(STATIC_FILES_ROOT_DIR, "generated")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()