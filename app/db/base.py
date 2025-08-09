from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import logging
from app.core.config import settings
from app.core.logger import logger
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Enhanced connection pooling with database-agnostic configuration
connect_args = {}
if settings.DATABASE_URL.startswith('postgresql'):
    connect_args = {
        'application_name': 'zuexis_app'
    }
elif settings.DATABASE_URL.startswith('sqlite'):
    connect_args = {
        'check_same_thread': False  # Allow SQLite to be used across threads
    }

# Create engine with database-specific configuration
if settings.DATABASE_URL.startswith('sqlite'):
    engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        connect_args=connect_args
    )
else:
    # Production-ready connection pool settings
    pool_size = 20 if settings.is_production else 10
    max_overflow = 30 if settings.is_production else 20
    
    engine = create_engine(
        settings.DATABASE_URL,
        poolclass=QueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_timeout=30,  # Timeout for getting connection from pool
        echo=settings.DEBUG,
        connect_args=connect_args
    )

# Add connection event listeners for better monitoring
@event.listens_for(engine, "connect")
def receive_connect(dbapi_connection, connection_record):
    logger.debug("Database connection established")

@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_connection, connection_record, connection_proxy):
    logger.debug("Database connection checked out from pool")

@event.listens_for(engine, "checkin")
def receive_checkin(dbapi_connection, connection_record):
    logger.debug("Database connection returned to pool")

SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine,
    expire_on_commit=False  # Keep objects usable after commit
)

Base = declarative_base()

def init_db():
    """Initialize database tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        raise

def get_db():
    """FastAPI dependency to get a DB session for each API request."""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

@contextmanager
def get_db_session():
    """
    Context manager for database sessions in workers/background tasks.
    Automatically handles commit/rollback and ensures proper cleanup.
    """
    db = SessionLocal()
    try:
        yield db
        # Only commit if we reach this point (no exceptions)
        db.commit()
        logger.debug("Database transaction committed successfully")
    except Exception as e:
        logger.error(f"Database transaction failed, rolling back: {e}")
        db.rollback()
        raise
    finally:
        db.close()
        logger.debug("Database session closed")

def get_db_session_sync():
    """
    Synchronous version for cases where you need a session object directly.
    REMEMBER: You must call session.close() manually!
    """
    return SessionLocal()

def check_db_connection():
    """Health check function to verify database connectivity"""
    try:
        with get_db_session() as db:
            # Simple query to test connection - fix SQLAlchemy compatibility
            db.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False

# Connection pool monitoring functions
def get_pool_status():
    """Get current database connection pool status"""
    pool = engine.pool
    return {
        "pool_size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "status": "healthy" if pool.checkedin() > 0 else "warning"
    }

def log_pool_status():
    """Log current pool status - useful for debugging"""
    status = get_pool_status()
    logger.info(f"DB Pool Status: {status}")
    return status