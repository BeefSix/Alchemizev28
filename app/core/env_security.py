# app/core/env_security.py
"""
Secure Environment Variable Management

This module provides secure handling of environment variables with validation,
fallbacks, and security best practices.
"""

import os
import logging
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class EnvironmentSecurityError(Exception):
    """Raised when environment security validation fails"""
    pass

class SecureEnvironment:
    """Secure environment variable manager with validation"""
    
    # Critical environment variables that must be set in production
    CRITICAL_VARS = {
        'SECRET_KEY': 'Application secret key for JWT and encryption',
        'DATABASE_URL': 'Database connection string',
        'OPENAI_API_KEY': 'OpenAI API key for content generation'
    }
    
    # Default values for non-critical variables
    DEFAULTS = {
        'DEBUG': 'false',
        'ENVIRONMENT': 'development',
        'ALLOWED_HOSTS': 'localhost,127.0.0.1',
        'CORS_ORIGINS': 'http://localhost:3000,http://localhost:8501',
        'MAX_FILE_SIZE_MB': '500',
        'RATE_LIMIT_ENABLED': 'true',
        'MAX_REQUESTS_PER_MINUTE': '60',
        'CSP_ENABLED': 'true',
        'HSTS_ENABLED': 'true',
        'SECURE_COOKIES': 'true'
    }
    
    # Sensitive variables that should never be logged
    SENSITIVE_VARS = {
        'SECRET_KEY', 'OPENAI_API_KEY', 'POSTGRES_PASSWORD', 
        'REDIS_PASSWORD', 'FIREBASE_CREDENTIALS_JSON', 'STRIPE_SECRET_KEY',
        'SMTP_PASSWORD', 'ALERT_EMAIL_PASSWORD'
    }
    
    @classmethod
    def get(cls, key: str, default: Optional[str] = None, required: bool = False) -> str:
        """Securely get environment variable with validation"""
        value = os.getenv(key, default or cls.DEFAULTS.get(key))
        
        if required and not value:
            raise EnvironmentSecurityError(
                f"Critical environment variable '{key}' is not set. "
                f"Description: {cls.CRITICAL_VARS.get(key, 'Required for application')}"
            )
        
        if value and key in cls.SENSITIVE_VARS:
            # Log that sensitive var was accessed but not the value
            logger.debug(f"Accessed sensitive environment variable: {key}")
        
        return value or ''
    
    @classmethod
    def get_bool(cls, key: str, default: bool = False) -> bool:
        """Get boolean environment variable"""
        value = cls.get(key, str(default).lower())
        return value.lower() in ('true', '1', 'yes', 'on')
    
    @classmethod
    def get_int(cls, key: str, default: int = 0) -> int:
        """Get integer environment variable"""
        value = cls.get(key, str(default))
        try:
            return int(value)
        except ValueError:
            logger.warning(f"Invalid integer value for {key}: {value}, using default: {default}")
            return default
    
    @classmethod
    def get_float(cls, key: str, default: float = 0.0) -> float:
        """Get float environment variable"""
        value = cls.get(key, str(default))
        try:
            return float(value)
        except ValueError:
            logger.warning(f"Invalid float value for {key}: {value}, using default: {default}")
            return default
    
    @classmethod
    def get_list(cls, key: str, default: Optional[list] = None, separator: str = ',') -> list:
        """Get list environment variable (comma-separated by default)"""
        value = cls.get(key, separator.join(default or []))
        if not value:
            return default or []
        return [item.strip() for item in value.split(separator) if item.strip()]
    
    @classmethod
    def validate_critical_vars(cls) -> Dict[str, Any]:
        """Validate all critical environment variables are set"""
        missing_vars = []
        validation_results = {}
        
        for var, description in cls.CRITICAL_VARS.items():
            value = os.getenv(var)
            if not value:
                missing_vars.append(f"{var}: {description}")
                validation_results[var] = {'status': 'missing', 'description': description}
            else:
                # Basic validation for known patterns
                is_valid = cls._validate_var_format(var, value)
                validation_results[var] = {
                    'status': 'valid' if is_valid else 'invalid_format',
                    'description': description
                }
        
        if missing_vars:
            error_msg = (
                "Critical environment variables are missing:\n" +
                "\n".join(f"  - {var}" for var in missing_vars) +
                "\n\nPlease set these variables in your .env file or environment."
            )
            raise EnvironmentSecurityError(error_msg)
        
        return validation_results
    
    @classmethod
    def _validate_var_format(cls, var: str, value: str) -> bool:
        """Validate environment variable format"""
        if var == 'SECRET_KEY':
            # Should be at least 32 characters for security
            return len(value) >= 32
        elif var == 'OPENAI_API_KEY':
            # Should start with 'sk-' for OpenAI API keys
            return value.startswith('sk-') and len(value) > 20
        elif var == 'DATABASE_URL':
            # Should contain database connection info
            return any(db in value.lower() for db in ['postgresql://', 'sqlite:///', 'mysql://'])
        return True
    
    @classmethod
    def get_security_headers_config(cls) -> Dict[str, Any]:
        """Get security headers configuration"""
        return {
            'csp_enabled': cls.get_bool('CSP_ENABLED', True),
            'hsts_enabled': cls.get_bool('HSTS_ENABLED', True),
            'secure_cookies': cls.get_bool('SECURE_COOKIES', True),
            'x_frame_options': cls.get('X_FRAME_OPTIONS', 'DENY'),
            'x_content_type_options': cls.get('X_CONTENT_TYPE_OPTIONS', 'nosniff')
        }
    
    @classmethod
    def get_rate_limit_config(cls) -> Dict[str, Any]:
        """Get rate limiting configuration"""
        return {
            'enabled': cls.get_bool('RATE_LIMIT_ENABLED', True),
            'requests_per_minute': cls.get_int('MAX_REQUESTS_PER_MINUTE', 60),
            'burst_limit': cls.get_int('RATE_LIMIT_BURST', 10),
            'brute_force_protection': cls.get_bool('BRUTE_FORCE_PROTECTION', True)
        }
    
    @classmethod
    def is_production(cls) -> bool:
        """Check if running in production environment"""
        return cls.get('ENVIRONMENT', 'development').lower() == 'production'
    
    @classmethod
    def is_debug(cls) -> bool:
        """Check if debug mode is enabled"""
        return cls.get_bool('DEBUG', not cls.is_production())
    
    @classmethod
    def log_environment_status(cls) -> None:
        """Log environment status (without sensitive values)"""
        env_status = {
            'environment': cls.get('ENVIRONMENT'),
            'debug': cls.is_debug(),
            'rate_limiting': cls.get_bool('RATE_LIMIT_ENABLED'),
            'security_headers': cls.get_bool('CSP_ENABLED'),
            'database_type': 'postgresql' if 'postgresql' in cls.get('DATABASE_URL', '').lower() else 'sqlite'
        }
        
        logger.info(f"Environment configuration: {env_status}")
        
        # Check for potential security issues
        if cls.is_production() and cls.is_debug():
            logger.warning("DEBUG mode is enabled in production - this is a security risk!")
        
        if not cls.get_bool('RATE_LIMIT_ENABLED'):
            logger.warning("Rate limiting is disabled - this may allow abuse")

# Convenience functions for common usage
def get_env(key: str, default: Optional[str] = None, required: bool = False) -> str:
    """Get environment variable securely"""
    return SecureEnvironment.get(key, default, required)

def get_env_bool(key: str, default: bool = False) -> bool:
    """Get boolean environment variable"""
    return SecureEnvironment.get_bool(key, default)

def get_env_int(key: str, default: int = 0) -> int:
    """Get integer environment variable"""
    return SecureEnvironment.get_int(key, default)

def validate_environment() -> Dict[str, Any]:
    """Validate critical environment variables"""
    return SecureEnvironment.validate_critical_vars()