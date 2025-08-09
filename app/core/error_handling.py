"""
Error handling utilities for the Alchemize application
"""
import functools
import logging
from typing import Callable, Any, TypeVar, ParamSpec
from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from celery.exceptions import CeleryError

logger = logging.getLogger(__name__)

P = ParamSpec('P')
T = TypeVar('T')

def celery_error_handler(func: Callable[P, T]) -> Callable[P, T]:
    """
    Decorator to handle Celery errors gracefully
    """
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return func(*args, **kwargs)
        except CeleryError as e:
            logger.error(f"Celery operation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Background processing service is temporarily unavailable"
            )
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred"
            )
    return wrapper

def with_db_retry(max_retries: int = 3, delay: float = 0.1):
    """
    Decorator to retry database operations with exponential backoff
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except SQLAlchemyError as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(delay * (2 ** attempt))  # Exponential backoff
                        logger.warning(f"Database operation failed, retrying ({attempt + 1}/{max_retries}): {e}")
                        continue
                    else:
                        logger.error(f"Database operation failed after {max_retries} attempts: {e}")
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Database service is temporarily unavailable"
                        )
                except Exception as e:
                    # Don't retry non-database errors
                    raise e
            
            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            
        return wrapper
    return decorator

def handle_file_errors(func: Callable[P, T]) -> Callable[P, T]:
    """
    Decorator to handle file operation errors
    """
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return func(*args, **kwargs)
        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Requested file not found"
            )
        except PermissionError as e:
            logger.error(f"Permission denied: {e}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to requested file"
            )
        except OSError as e:
            logger.error(f"File system error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="File system error occurred"
            )
        except Exception as e:
            logger.error(f"Unexpected file error in {func.__name__}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while processing the file"
            )
    return wrapper

def handle_validation_errors(func: Callable[P, T]) -> Callable[P, T]:
    """
    Decorator to handle validation errors
    """
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return func(*args, **kwargs)
        except ValueError as e:
            logger.warning(f"Validation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Unexpected validation error in {func.__name__}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred during validation"
            )
    return wrapper
