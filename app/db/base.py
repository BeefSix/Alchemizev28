# app/db/base.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings
from contextlib import contextmanager

# The engine and Base configuration remain the same
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True # Helps manage stale connections
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def init_db():
    Base.metadata.create_all(bind=engine)

# This function is the standard FastAPI dependency and is SAFE for API endpoints
def get_db():
    """Dependency to get a DB session for each API request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- THIS IS THE FIX ---
# This new function is for use in background tasks (Celery)
@contextmanager
def get_db_session():
    """
    Provides a database session for background tasks, ensuring it's
    always closed properly.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()