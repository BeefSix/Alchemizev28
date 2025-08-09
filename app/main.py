from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.api.v1.api import api_router
from app.db.base import init_db
from app.services import video_engine
from app.services.startup_validator import validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.middleware.security import SecurityMiddleware, DatabaseSecurityMiddleware
from app.services.monitoring import monitor, performance_monitor
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
    logger.info("🚀 Zuexis AI starting up...")
    
    try:
        # Run comprehensive startup validation
        validation_results = await validator.validate_all()
        
        logger.info("📊 Initializing database...")
        init_db()
        
        logger.info("🔧 Setting up static directories...")
        os.makedirs(settings.STATIC_GENERATED_DIR, exist_ok=True)
        
        # Store validation results in app state
        app.state.startup_validation = validation_results
        app.state.validator = validator
        
        logger.info("✅ Startup complete!")
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise
    
    yield
    
    logger.info("🌙 Zuexis AI shutting down...")

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

# Mount static files using standardized config
static_dir = settings.STATIC_FILES_ROOT_DIR
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check():
    """Comprehensive health check endpoint with production monitoring"""
    from datetime import datetime
    
    try:
        with performance_monitor("health_check", alert_threshold_seconds=5.0):
            # Get comprehensive system status from monitoring service
            system_status = monitor.get_system_status()
            
            # Get basic health status from validator for backward compatibility
            validator_status = validator.get_health_status()
            
            # Combine monitoring data with validator data
            health_data = {
                "overall_status": system_status["status"],
                "timestamp": system_status["timestamp"],
                "monitoring": system_status,
                "validator": validator_status
            }
            
            return health_data
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "overall_status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@app.get("/health/detailed", tags=["health"])
async def detailed_health_check():
    """Detailed health check for monitoring systems"""
    if not settings.DEBUG and settings.ENVIRONMENT.lower() == 'production':
        raise HTTPException(status_code=404, detail="Not found")
    
    try:
        from app.services.rate_limiter import rate_limiter
        from app.services.database_security import db_security
        from app.services.redis_security import redis_security
        
        health_status = validator.get_health_status()
        
        # Add security service status
        rate_limit_stats = await rate_limiter.get_global_stats()
        db_pool_status = await db_security.get_connection_pool_status()
        redis_cache_stats = await redis_security.get_cache_stats()
        
        return {
            "health_status": health_status,
            "security_services": {
                "rate_limiting": rate_limit_stats,
                "database_pool": db_pool_status,
                "redis_cache": redis_cache_stats
            }
        }
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Security middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Trusted Host Middleware - Production Ready
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.TRUSTED_HOSTS,
)

# CORS Configuration - Production Ready
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Content-Language",
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "X-CSRF-Token",
    ] if settings.is_production else ["*"],
    expose_headers=["X-Total-Count", "X-Page-Count"] if settings.is_production else [],
)

# Add comprehensive security middleware
app.add_middleware(SecurityMiddleware)
app.add_middleware(DatabaseSecurityMiddleware)

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

