# app/api/v1/api.py
from fastapi import APIRouter
from app.api.v1.endpoints import auth, content, video  # IMPORT THE VIDEO ROUTER

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(content.router, prefix="/content", tags=["content"])
api_router.include_router(video.router, prefix="/video", tags=["video"]) # INCLUDE THE VIDEO ROUTER