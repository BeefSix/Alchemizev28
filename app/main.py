# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from app.core.config import settings
from app.api.v1.api import api_router
from app.db.base import init_db
from app.services import video_engine # Keep this import
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Alchemize AI starting up...")
    print("📊 Initializing database...")
    init_db()
    
    # --- THIS BLOCK IS REMOVED ---
    # The Stable Diffusion model will now be loaded on-demand
    # the first time a thumbnail generation is requested.
    # This makes startup faster and more reliable.
    
    yield
    print("🌙 Alchemize AI shutting down...")

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan
)

# Mount the static files directory
app.mount("/static", StaticFiles(directory=settings.STATIC_FILES_ROOT_DIR), name="static")

@app.get("/health")
async def health_check():
    return {"status": "ok"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def read_root():
    return {"message": f"Welcome to {settings.APP_NAME}"}