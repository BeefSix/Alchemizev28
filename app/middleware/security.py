import logging
import time
from typing import Callable, Dict, Any
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings
from app.services.rate_limiter import rate_limiter
from app.services.database_security import db_security
import re
import json

logger = logging.getLogger(__name__)

class SecurityMiddleware(BaseHTTPMiddleware):
    """Comprehensive security middleware"""
    
    def __init__(self, app, security_config: Dict[str, Any] = None):
        super().__init__(app)
        self.security_config = security_config or {}
        
        # Security headers with enhanced CSP
        csp_policy = self._build_csp_policy()
        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "SAMEORIGIN",  # Changed from DENY to SAMEORIGIN
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=(), usb=(), magnetometer=(), gyroscope=(), accelerometer=()",
            "Content-Security-Policy": csp_policy,
            "Cross-Origin-Embedder-Policy": "require-corp",
            "Cross-Origin-Opener-Policy": "same-origin",
            "Cross-Origin-Resource-Policy": "same-origin"
        }
        
        # Only add HSTS in production
        if not settings.DEBUG and settings.ENVIRONMENT == "production":
            self.security_headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        
        # Paths that don't require rate limiting
        self.rate_limit_exempt_paths = {
            "/health",
            "/health/detailed",
            "/docs",
            "/openapi.json",
            "/favicon.ico",
            "/api/v1/jobs/history",
            "/api/v1/jobs/stats"
        }
        
        # Paths with custom rate limits - development-friendly settings
        self.custom_rate_limits = {
            "/api/v1/auth/login": {"requests": 100, "window": 900, "burst": 20},  # 100/15min (dev-friendly)
            "/api/v1/auth/register": {"requests": 50, "window": 3600, "burst": 10},  # 50/hour (dev-friendly)
            "/api/v1/video/upload-and-clip": {"requests": 30, "window": 3600, "burst": 5},  # 30/hour
            "/api/v1/magic/magic-edit": {"requests": 60, "window": 3600, "burst": 10},  # 60/hour
            "/api/v1/content/repurpose": {"requests": 100, "window": 3600, "burst": 15},  # 100/hour
            "/api/v1/video/upload/init": {"requests": 50, "window": 3600, "burst": 10},  # 50/hour
            "/api/v1/video/upload/chunk": {"requests": 1000, "window": 3600, "burst": 50},  # 1000/hour
            "/api/v1/video/upload/complete": {"requests": 50, "window": 3600, "burst": 10},  # 50/hour
            # File upload endpoints
            "/api/v1/file-upload/init": {"requests": 50, "window": 3600, "burst": 10},  # 50/hour
            "/api/v1/file-upload/chunk": {"requests": 1000, "window": 3600, "burst": 50},  # 1000/hour
            "/api/v1/file-upload/complete": {"requests": 50, "window": 3600, "burst": 10},  # 50/hour
        }
        
        # Suspicious patterns to monitor
        self.suspicious_patterns = [
            re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
            re.compile(r"javascript:", re.IGNORECASE),
            re.compile(r"on\w+\s*=", re.IGNORECASE),
            re.compile(r"(union|select|insert|delete|update|drop)\s+", re.IGNORECASE),
            re.compile(r"\.\.[\/\\]", re.IGNORECASE),
            re.compile(r"\x00"),  # Null bytes
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        try:
            # Security checks
            await self._perform_security_checks(request)
            
            # Rate limiting (if not exempt)
            rate_info = None
            if not self._is_rate_limit_exempt(request):
                rate_info = await self._apply_rate_limiting(request)
            
            # Process request
            response = await call_next(request)
            
            # Add security headers
            self._add_security_headers(response)
            
            # Add rate limit headers if applicable
            if rate_info:
                self._add_rate_limit_headers(response, rate_info)
            
            # Add performance headers
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)
            
            # Log request
            await self._log_request(request, response, process_time)
            
            return response
            
        except HTTPException as e:
            # Handle rate limiting and other HTTP exceptions
            response = JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail},
                headers=getattr(e, 'headers', {})
            )
            self._add_security_headers(response)
            return response
            
        except Exception as e:
            logger.error(f"Security middleware error: {e}")
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )
            self._add_security_headers(response)
            return response
    
    async def _perform_security_checks(self, request: Request):
        """Perform various security checks"""
        
        # Check for suspicious patterns in URL and headers
        url_str = str(request.url)
        for pattern in self.suspicious_patterns:
            if pattern.search(url_str):
                logger.warning(f"Suspicious URL pattern detected: {url_str}")
                raise HTTPException(status_code=400, detail="Invalid request")
        
        # Check User-Agent
        user_agent = request.headers.get("User-Agent", "")
        if not user_agent or len(user_agent) < 10:
            logger.warning(f"Suspicious or missing User-Agent: {user_agent}")
        
        # Check for common attack headers
        dangerous_headers = ["X-Forwarded-Host", "X-Original-URL", "X-Rewrite-URL"]
        for header in dangerous_headers:
            if header in request.headers:
                logger.warning(f"Potentially dangerous header detected: {header}")
        
        # Validate Content-Length for POST requests
        if request.method in ["POST", "PUT", "PATCH"]:
            content_length = request.headers.get("Content-Length")
            if content_length:
                try:
                    length = int(content_length)
                    max_size = 500 * 1024 * 1024  # 500MB
                    if length > max_size:
                        raise HTTPException(
                            status_code=413, 
                            detail=f"Request too large. Maximum size: {max_size // (1024*1024)}MB"
                        )
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid Content-Length header")
    
    async def _apply_rate_limiting(self, request: Request) -> Dict[str, Any]:
        """Apply rate limiting based on endpoint and user"""
        path = request.url.path
        
        # Get user ID if authenticated
        user_id = None
        if hasattr(request.state, 'user'):
            user_id = str(request.state.user.id)
        
        # Determine endpoint category
        endpoint_category = self._get_endpoint_category(path)
        
        # Get custom limits if defined
        custom_limit = self.custom_rate_limits.get(path)
        
        # Apply rate limiting
        rate_info = await rate_limiter.check_rate_limit(
            request, 
            endpoint_category, 
            user_id=user_id,
            custom_limit=custom_limit
        )
        
        return rate_info
    
    def _get_endpoint_category(self, path: str) -> str:
        """Categorize endpoint for rate limiting"""
        if "/auth/" in path:
            return "auth"
        elif "/upload" in path or "/video/" in path:
            return "upload"
        elif "/download" in path or "/static/" in path:
            return "download"
        else:
            return "api_general"
    
    def _is_rate_limit_exempt(self, request: Request) -> bool:
        """Check if path is exempt from rate limiting"""
        path = request.url.path
        return any(exempt_path in path for exempt_path in self.rate_limit_exempt_paths)
    
    def _add_security_headers(self, response: Response):
        """Add security headers to response"""
        for header, value in self.security_headers.items():
            response.headers[header] = value
        
        # Add server identification
        response.headers["Server"] = "Zuexis/1.0"
        response.headers["X-Powered-By"] = "FastAPI"
    
    def _add_rate_limit_headers(self, response: Response, rate_info: Dict[str, Any]):
        """Add rate limiting headers to response"""
        response.headers["X-RateLimit-Limit"] = str(rate_info.get("limit", 0))
        response.headers["X-RateLimit-Remaining"] = str(rate_info.get("remaining", 0))
        response.headers["X-RateLimit-Reset"] = str(rate_info.get("reset", 0))
        
        if "burst_limit" in rate_info:
            response.headers["X-RateLimit-Burst-Limit"] = str(rate_info["burst_limit"])
            response.headers["X-RateLimit-Burst-Remaining"] = str(rate_info.get("burst_remaining", 0))
    
    async def _log_request(self, request: Request, response: Response, process_time: float):
        """Log request details for monitoring"""
        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if not client_ip:
            client_ip = getattr(request.client, "host", "unknown")
        
        log_data = {
            "method": request.method,
            "path": request.url.path,
            "client_ip": client_ip,
            "user_agent": request.headers.get("User-Agent", "")[:100],
            "status_code": response.status_code,
            "process_time": round(process_time, 4),
            "content_length": response.headers.get("Content-Length", "0")
        }
        
        # Log based on status code
        if response.status_code >= 500:
            logger.error(f"Server error: {log_data}")
        elif response.status_code >= 400:
            logger.warning(f"Client error: {log_data}")
        elif process_time > 5.0:  # Slow requests
            logger.warning(f"Slow request: {log_data}")
        else:
            logger.info(f"Request: {request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")
    
    def _build_csp_policy(self) -> str:
        """Build Content Security Policy based on environment and configuration"""
        if settings.DEBUG:
            # More permissive CSP for development with media support
            return (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' localhost:* 127.0.0.1:*; "
                "style-src 'self' 'unsafe-inline' fonts.googleapis.com; "
                "font-src 'self' fonts.gstatic.com data:; "
                "img-src 'self' data: blob: https:; "
                "media-src 'self' blob: data: https:; "
                "connect-src 'self' localhost:* 127.0.0.1:* ws: wss:; "
                "object-src 'none'; "
                "frame-src 'self'; "  # Allow same-origin frames
                "base-uri 'self'; "
                "form-action 'self';"
            )
        else:
            # Strict CSP for production with media support
            return (
                "default-src 'self'; "
                "script-src 'self' 'nonce-{nonce}'; "
                "style-src 'self' 'nonce-{nonce}' fonts.googleapis.com; "
                "font-src 'self' fonts.gstatic.com; "
                "img-src 'self' data: blob: https:; "
                "media-src 'self' blob: data: https:; "  # Allow blob and data for media
                "connect-src 'self'; "
                "object-src 'none'; "
                "frame-src 'self'; "  # Allow same-origin frames
                "base-uri 'self'; "
                "form-action 'self'; "
                "upgrade-insecure-requests;"
            )

class DatabaseSecurityMiddleware(BaseHTTPMiddleware):
    """Middleware for database security monitoring"""
    
    def __init__(self, app):
        super().__init__(app)
        self.query_patterns = [
            re.compile(r"(union|select|insert|delete|update|drop|create|alter)\s+", re.IGNORECASE),
            re.compile(r"(--|#|/\*|\*/)", re.IGNORECASE),
            re.compile(r"(exec|execute|sp_|xp_)", re.IGNORECASE),
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Monitor for potential SQL injection in request data
        if request.method in ["POST", "PUT", "PATCH"]:
            await self._check_request_body(request)
        
        # Check query parameters
        for param, value in request.query_params.items():
            if self._contains_sql_injection(str(value)):
                logger.warning(f"Potential SQL injection in query param {param}: {value}")
                raise HTTPException(status_code=400, detail="Invalid request parameters")
        
        return await call_next(request)
    
    async def _check_request_body(self, request: Request):
        """Check request body for SQL injection patterns"""
        try:
            # Only check JSON bodies
            if request.headers.get("Content-Type", "").startswith("application/json"):
                body = await request.body()
                if body:
                    body_str = body.decode('utf-8')
                    if self._contains_sql_injection(body_str):
                        logger.warning(f"Potential SQL injection in request body: {body_str[:200]}")
                        raise HTTPException(status_code=400, detail="Invalid request data")
        except Exception as e:
            logger.error(f"Error checking request body: {e}")
    
    def _contains_sql_injection(self, text: str) -> bool:
        """Check if text contains potential SQL injection patterns"""
        for pattern in self.query_patterns:
            if pattern.search(text):
                return True
        return False