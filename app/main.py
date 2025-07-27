# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles # <-- ADDED IMPORT
from contextlib import asynccontextmanager
from app.core.config import settings
from app.api.v1.api import api_router
from app.db.base import init_db
from app.services import video_engine
import os # <-- ADDED IMPORT

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Alchemize AI starting up...")
    print("📊 Initializing database...")
    init_db()
    print("🧠 Attempting to load Stable Diffusion model...")
    success, message = video_engine.sd_generator.load_model()
    if success:
        print(f"✅ Stable Diffusion model loaded successfully: {message}")
    else:
        print(f"⚠️ Stable Diffusion model failed to load: {message}")
    yield
    print("🌙 Alchemize AI shutting down...")

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan
)

# Mount the static files directory to be served at /static
# This makes files in 'static/generated' accessible via /static/generated/...
# Ensure your STATIC_FILES_ROOT_DIR is properly set in config.py
app.mount("/static", StaticFiles(directory=settings.STATIC_FILES_ROOT_DIR), name="static")

@app.get("/health")
async def health_check():
    """
    Health check endpoint for Docker Compose.
    Returns 200 OK if the application is running.
    """
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