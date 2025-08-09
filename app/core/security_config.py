import os
from typing import Dict, List, Any
from app.core.config import settings

class SecurityConfig:
    """Centralized security configuration"""
    
    # Password policy
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_MAX_LENGTH = 128
    PASSWORD_REQUIRE_UPPERCASE = True
    PASSWORD_REQUIRE_LOWERCASE = True
    PASSWORD_REQUIRE_DIGITS = True
    PASSWORD_REQUIRE_SPECIAL = True
    PASSWORD_SPECIAL_CHARS = "!@#$%^&*(),.?\":{}|<>"
    
    # Session security
    SESSION_TIMEOUT_MINUTES = 60
    JWT_EXPIRY_MINUTES = 60
    REFRESH_TOKEN_EXPIRY_DAYS = 7
    
    # Rate limiting (requests per hour unless specified)
    RATE_LIMITS = {
        "auth": {"requests": 50, "window": 900, "burst": 10},  # 50/15min
        "upload": {"requests": 10, "window": 3600, "burst": 3},  # 10/hour
        "api_general": {"requests": 100, "window": 3600, "burst": 20},  # 100/hour
        "download": {"requests": 50, "window": 3600, "burst": 10},  # 50/hour
        "global_ip": {"requests": 1000, "window": 3600, "burst": 100},  # 1000/hour per IP
    }
    
    # File upload security
    MAX_FILE_SIZE_MB = 500
    ALLOWED_VIDEO_EXTENSIONS = [".mp4", ".avi", ".mov", ".mkv", ".webm"]
    ALLOWED_IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
    ALLOWED_DOCUMENT_EXTENSIONS = [".pdf", ".docx", ".txt"]
    
    # Security headers
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=(), usb=()",
    }
    
    # Content Security Policy
    CSP_POLICY = {
        "default-src": ["'self'"],
        "script-src": ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"],
        "style-src": ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
        "font-src": ["'self'", "https://fonts.gstatic.com"],
        "img-src": ["'self'", "data:", "https:"],
        "connect-src": ["'self'", "https://api.openai.com"],
        "media-src": ["'self'"],
        "object-src": ["'none'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
        "frame-ancestors": ["'none'"],
    }
    
    # Input validation patterns
    VALIDATION_PATTERNS = {
        "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        "username": r"^[a-zA-Z0-9_-]{3,30}$",
        "filename": r"^[a-zA-Z0-9._-]+$",
        "safe_string": r"^[a-zA-Z0-9\s._-]+$",
    }
    
    # SQL injection patterns to block
    SQL_INJECTION_PATTERNS = [
        r"('|(\-\-)|(;)|(\||\|)|(\*|\*))",
        r"(union|select|insert|delete|update|drop|create|alter|exec|execute)",
        r"(script|javascript|vbscript|onload|onerror|onclick)",
        r"(\<|\>|\%3C|\%3E)",
        r"(eval\s*\(|expression\s*\()",
    ]
    
    # Blocked user agents (bots, scrapers)
    BLOCKED_USER_AGENTS = [
        "bot", "crawler", "spider", "scraper", "curl", "wget",
        "python-requests", "postman", "insomnia"
    ]
    
    # Environment-specific settings
    @classmethod
    def get_environment_config(cls) -> Dict[str, Any]:
        """Get security config based on environment"""
        is_production = getattr(settings, 'ENVIRONMENT', 'development') == 'production'
        
        config = {
            "enforce_https": is_production,
            "secure_cookies": is_production,
            "debug_mode": not is_production,
            "log_level": "WARNING" if is_production else "INFO",
            "enable_cors": not is_production,
            "strict_csp": is_production,
        }
        
        return config
    
    @classmethod
    def build_csp_header(cls) -> str:
        """Build Content Security Policy header string"""
        csp_parts = []
        for directive, sources in cls.CSP_POLICY.items():
            sources_str = " ".join(sources)
            csp_parts.append(f"{directive} {sources_str}")
        return "; ".join(csp_parts)
    
    @classmethod
    def validate_environment_security(cls) -> List[str]:
        """Validate security configuration and return warnings"""
        warnings = []
        
        # Check if running in production with debug mode
        env_config = cls.get_environment_config()
        if not env_config["enforce_https"] and getattr(settings, 'ENVIRONMENT', '') == 'production':
            warnings.append("HTTPS not enforced in production environment")
        
        # Check for weak secret key
        secret_key = getattr(settings, 'SECRET_KEY', '')
        if len(secret_key) < 32:
            warnings.append("Secret key is too short (< 32 characters)")
        
        # Check for default/weak passwords in environment
        weak_indicators = ['password', 'secret', 'key', '123', 'admin']
        for attr in ['SECRET_KEY', 'POSTGRES_PASSWORD']:
            value = getattr(settings, attr, '').lower()
            if any(weak in value for weak in weak_indicators):
                warnings.append(f"{attr} appears to contain weak/default values")
        
        return warnings

# Global security config instance
security_config = SecurityConfig()