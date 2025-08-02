from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from app.core.config import settings

# --- THIS IS THE FIX ---
# We've added connection pooling parameters to the engine.
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600
)
# --- END FIX ---

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

# This is the single, correct version of the context manager for background tasks
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