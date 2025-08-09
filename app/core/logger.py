import logging
import logging.handlers
import sys
import os
import json
from datetime import datetime
from typing import Dict, Any
from app.core.config import settings

class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging"""
    
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'user_id'):
            log_entry["user_id"] = record.user_id
        if hasattr(record, 'job_id'):
            log_entry["job_id"] = record.job_id
        if hasattr(record, 'request_id'):
            log_entry["request_id"] = record.request_id
            
        return json.dumps(log_entry)

def setup_logging():
    """Setup comprehensive logging configuration"""
    
    # Create logs directory
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler with colored output for development
    console_handler = logging.StreamHandler(sys.stdout)
    if settings.DEBUG:
        console_format = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    else:
        console_format = StructuredFormatter()
    
    console_handler.setFormatter(console_format)
    console_handler.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation for production
    if settings.is_production or not settings.DEBUG:
        # Main application log
        file_handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, "zuexis.log"),
            maxBytes=50*1024*1024,  # 50MB
            backupCount=10
        )
        file_handler.setFormatter(StructuredFormatter())
        file_handler.setLevel(logging.INFO)
        root_logger.addHandler(file_handler)
        
        # Error log
        error_handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, "errors.log"),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        error_handler.setFormatter(StructuredFormatter())
        error_handler.setLevel(logging.ERROR)
        root_logger.addHandler(error_handler)
        
        # Security log
        security_logger = logging.getLogger("security")
        security_handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, "security.log"),
            maxBytes=20*1024*1024,  # 20MB
            backupCount=10
        )
        security_handler.setFormatter(StructuredFormatter())
        security_logger.addHandler(security_handler)
        security_logger.setLevel(logging.WARNING)
    
    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    return logging.getLogger("zuexis")

# Initialize logging
logger = setup_logging()
logger.info("Enhanced logging system initialized", extra={"environment": settings.ENVIRONMENT})

# Convenience function for adding context to logs
def get_logger_with_context(name: str, **context) -> logging.LoggerAdapter:
    """Get a logger with additional context"""
    base_logger = logging.getLogger(name)
    return logging.LoggerAdapter(base_logger, context)