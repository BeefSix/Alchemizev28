# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from app.core.config import settings
from app.api.v1.api import api_router
from app.db.base import init_db
from app.services import video_engine
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Alchemize AI starting up...")
    
    try:
        # Validate required settings
        required_settings = [
            'SECRET_KEY', 'DATABASE_URL', 'OPENAI_API_KEY', 
            'CELERY_BROKER_URL', 'CELERY_RESULT_BACKEND'
        ]
        missing_settings = [s for s in required_settings if not getattr(settings, s, None)]
        if missing_settings:
            raise ValueError(f"Missing required settings: {missing_settings}")
        
        logger.info("📊 Initializing database...")
        init_db()
        
        logger.info("🔧 Setting up static directories...")
        os.makedirs(settings.STATIC_GENERATED_DIR, exist_ok=True)
        
        logger.info("✅ Startup complete!")
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise
    
    yield
    
    logger.info("🌙 Alchemize AI shutting down...")

app = FastAPI(
    title=settings.APP_NAME,
    description="Transform your videos into viral social media content",
    version="1.0.0",
    lifespan=lifespan
)

# Set up rate limiting
from app.core.limiter import limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Mount static files
app.mount("/static", StaticFiles(directory=settings.STATIC_FILES_ROOT_DIR), name="static")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": "1.0.0"
    }

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix=settings.API_V1_STR)

# Root endpoint
@app.get("/")
def read_root():
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "docs": "/docs",
        "health": "/health"
    }