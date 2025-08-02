# app/db/models.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
from pydantic import BaseModel as PydanticBaseModel
from typing import Optional, Dict, Any, List

# Pydantic models (Schemas) for API validation
class BaseModel(PydanticBaseModel):
    class Config:
        from_attributes = True

class UserBase(BaseModel):
    email: str
    full_name: str | None = None

class JobResponse(BaseModel):
    job_id: str
    message: str

class JobStatusResponse(BaseModel):
    id: str
    status: str
    progress_details: Optional[Dict[str, Any]] = None
    results: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

# SQLAlchemy models (Database Tables)
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    jobs = relationship("Job", back_populates="owner")
    brand_profile = relationship("BrandProfile", back_populates="user", uselist=False)
    usage_logs = relationship("UsageLog", back_populates="user")

class Job(Base):
    __tablename__ = "jobs"
    id = Column(String, primary_key=True, index=True)  # Job ID is a UUID string
    job_type = Column(String, index=True)
    status = Column(String, index=True, default="PENDING")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(Integer, ForeignKey("users.id"))
    progress_details = Column(Text, nullable=True)  # JSON string
    results = Column(Text, nullable=True)  # JSON string
    error_message = Column(String, nullable=True)
    owner = relationship("User", back_populates="jobs")

class BrandProfile(Base):
    __tablename__ = "brand_profiles"
    profile_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    brand_voice = Column(Text, nullable=True)
    brand_cta = Column(Text, nullable=True)
    user = relationship("User", back_populates="brand_profile")

class UsageLog(Base):
    __tablename__ = "usage_logs"
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    model = Column(String)
    operation = Column(String)
    cost = Column(Float, nullable=False)
    user = relationship("User", back_populates="usage_logs")

class APICache(Base):
    __tablename__ = "api_cache"
    cache_id = Column(Integer, primary_key=True, autoincrement=True)
    request_hash = Column(String, unique=True, nullable=False)
    response_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class TranscriptCache(Base):
    __tablename__ = "transcripts"
    source_url = Column(String, primary_key=True)
    transcript_json = Column(Text, nullable=False)  # JSON string
    created_at = Column(DateTime(timezone=True), server_default=func.now())