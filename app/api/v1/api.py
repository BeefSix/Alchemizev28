from fastapi import APIRouter
from app.api.v1.endpoints import auth, content, video, magic, payment, file_upload, user, jobs

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(user.router, prefix="/user", tags=["user"])
api_router.include_router(content.router, prefix="/content", tags=["content"])
api_router.include_router(video.router, prefix="/video", tags=["video"])
api_router.include_router(magic.router, prefix="/magic", tags=["magic"])
api_router.include_router(payment.router, prefix="/payment", tags=["payment"])
api_router.include_router(file_upload.router, prefix="/file-upload", tags=["file_upload"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])