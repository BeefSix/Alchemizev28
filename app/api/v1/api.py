# app/api/v1/api.py

from fastapi import APIRouter
from app.api.v1 import endpoints

api_router = APIRouter()

# Include the routers from the modules that actually exist.
api_router.include_router(endpoints.auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(endpoints.content.router, prefix="/content", tags=["content"])
api_router.include_router(endpoints.video.router, prefix="/video", tags=["video"])