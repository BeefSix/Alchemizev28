import os
import logging
import asyncio
from typing import Dict, List, Optional
from sqlalchemy import text
from app.core.config import settings
from app.db.base import engine
from app.services.database_security import db_security
from app.services.redis_security import redis_security
import redis
import openai
import subprocess
import psutil

logger = logging.getLogger(__name__)

class StartupValidator:
    """Comprehensive startup validation for critical system components"""
    
    def __init__(self):
        self.validation_results = {}
        self.critical_failures = []
        self.warnings = []
    
    async def validate_all(self) -> Dict[str, bool]:
        """Run all validation checks"""
        logger.info("🔍 Running comprehensive startup validation...")
        
        validations = [
            ("environment", self._validate_environment),
            ("database", self._validate_database),
            ("redis", self._validate_redis),
            ("openai", self._validate_openai),
            ("gpu", self._validate_gpu),
            ("file_system", self._validate_file_system),
            ("security", self._validate_security),
        ]
        
        for name, validator in validations:
            try:
                result = await validator()
                self.validation_results[name] = result
                if result:
                    logger.info(f"✅ {name.title()} validation passed")
                else:
                    logger.error(f"❌ {name.title()} validation failed")
            except Exception as e:
                logger.error(f"💥 {name.title()} validation crashed: {e}")
                self.validation_results[name] = False
                self.critical_failures.append(f"{name}: {str(e)}")
        
        # Report summary
        self._report_summary()
        
        # Check if we have any critical failures
        critical_components = ["environment", "database"]
        has_critical_failures = any(
            not self.validation_results.get(comp, False) 
            for comp in critical_components
        )
        
        if has_critical_failures:
            raise RuntimeError(f"Critical startup failures: {self.critical_failures}")
        
        return self.validation_results
    
    async def _validate_environment(self) -> bool:
        """Validate all required environment variables"""
        required_vars = {
            'SECRET_KEY': 'JWT secret key',
            'DATABASE_URL': 'Database connection string',
            'OPENAI_API_KEY': 'OpenAI API access',
            'CELERY_BROKER_URL': 'Task queue broker',
            'CELERY_RESULT_BACKEND': 'Task result storage'
        }
        
        missing = []
        weak_configs = []
        
        for var, description in required_vars.items():
            value = getattr(settings, var, None)
            if not value:
                missing.append(f"{var} ({description})")
            elif var == 'SECRET_KEY' and len(value) < 32:
                weak_configs.append(f"{var} is too short (< 32 chars)")
            elif var == 'OPENAI_API_KEY' and not value.startswith('sk-'):
                weak_configs.append(f"{var} format appears invalid")
        
        # Check optional but important vars
        if not settings.FIREBASE_CREDENTIALS_JSON:
            self.warnings.append("Firebase credentials not configured - file uploads may fail")
        
        if missing:
            self.critical_failures.extend(missing)
            return False
        
        if weak_configs:
            self.warnings.extend(weak_configs)
        
        return True
    
    async def _validate_database(self) -> bool:
        """Test database connectivity and basic operations"""
        try:
            # Use comprehensive database security validator
            db_result = await db_security.validate_database_connection()
            
            if not db_result.get("connection", False):
                self.critical_failures.append(f"Database connection failed: {db_result.get('error', 'Unknown error')}")
                return False
            
            # Add connection pool status
            pool_status = await db_security.get_connection_pool_status()
            if pool_status.get("status") != "healthy":
                self.warnings.append(f"Database pool status: {pool_status.get('status')}")
            
            # Test CRUD operations for security
            crud_result = await db_security.test_crud_operations()
            if crud_result.get("status") != "all_passed":
                self.warnings.append(f"Database CRUD test issues: {crud_result.get('status')}")
            
            # Check for missing tables
            if not db_result.get("tables_exist", False):
                self.warnings.append("Missing database tables - run migrations")
            
            return True
            
        except Exception as e:
            self.critical_failures.append(f"Database validation failed: {str(e)}")
            return False
    
    async def _validate_redis(self) -> bool:
        """Test Redis connectivity with fallback handling"""
        try:
            # Use comprehensive Redis security validator
            redis_result = await redis_security.validate_redis_connection()
            
            if not redis_result.get("connection", False):
                if redis_result.get("fallback_active", False):
                    self.warnings.append(f"Redis unavailable, fallback active: {redis_result.get('error')}")
                    return True  # Non-critical with fallback
                else:
                    self.warnings.append(f"Redis connection failed: {redis_result.get('error')} - task queue may not work")
                    return True  # Non-critical, app can run without Redis
            
            # Add cache statistics
            cache_stats = await redis_security.get_cache_stats()
            fallback_size = cache_stats.get("fallback_cache_size", 0)
            if fallback_size > 0:
                self.warnings.append(f"Using fallback cache with {fallback_size} items")
            
            # Test Redis operations
            operations_result = await redis_security.test_redis_operations()
            if operations_result.get("status") != "all_passed":
                self.warnings.append(f"Redis operations test issues: {operations_result.get('status')}")
            
            return True
            
        except Exception as e:
            self.warnings.append(f"Redis validation failed: {str(e)} - task queue may not work")
            return True  # Non-critical, app can run without Redis
    
    async def _validate_openai(self) -> bool:
        """Test OpenAI API connectivity and quota"""
        try:
            # Test API key format
            if not settings.OPENAI_API_KEY.startswith('sk-'):
                self.critical_failures.append("OpenAI API key format invalid")
                return False
            
            # Test API connectivity (lightweight call)
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            models = client.models.list()
            
            # Check for required models
            model_names = [model.id for model in models.data]
            required_models = ['gpt-4o-mini', 'whisper-1']
            missing_models = [m for m in required_models if m not in model_names]
            
            if missing_models:
                self.warnings.append(f"Some AI models unavailable: {missing_models}")
            
            return True
            
        except Exception as e:
            self.critical_failures.append(f"OpenAI API validation failed: {str(e)}")
            return False
    
    async def _validate_gpu(self) -> bool:
        """Check GPU availability with graceful fallback"""
        try:
            # Check NVIDIA drivers
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                gpu_info = result.stdout.strip().split('\n')
                logger.info(f"🎮 GPU detected: {gpu_info[0]}")
                return True
            else:
                self.warnings.append("No NVIDIA GPU detected - using CPU for video processing")
                return False
                
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.warnings.append("NVIDIA drivers not found - using CPU fallback")
            return False
        except Exception as e:
            self.warnings.append(f"GPU detection failed: {str(e)} - using CPU fallback")
            return False
    
    async def _validate_file_system(self) -> bool:
        """Validate file system permissions and disk space"""
        try:
            # Check static directories
            directories = [
                settings.STATIC_FILES_ROOT_DIR,
                settings.STATIC_GENERATED_DIR,
                "uploads",
                "data"
            ]
            
            for directory in directories:
                os.makedirs(directory, exist_ok=True)
                
                # Test write permissions
                test_file = os.path.join(directory, ".write_test")
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
            
            # Check disk space (warn if < 1GB free)
            disk_usage = psutil.disk_usage('.')
            free_gb = disk_usage.free / (1024**3)
            
            if free_gb < 1.0:
                self.warnings.append(f"Low disk space: {free_gb:.1f}GB free")
            
            return True
            
        except Exception as e:
            self.critical_failures.append(f"File system validation failed: {str(e)}")
            return False
    
    async def _validate_security(self) -> bool:
        """Validate security configuration"""
        security_issues = []
        
        # Check SECRET_KEY strength
        if len(settings.SECRET_KEY) < 32:
            security_issues.append("SECRET_KEY too short")
        
        # Check if running in debug mode in production
        if settings.DEBUG and settings.ENVIRONMENT.lower() == 'production':
            security_issues.append("DEBUG mode enabled in production")
        
        # Check CORS configuration
        if "*" in [str(origin) for origin in settings.CORS_ORIGINS]:
            security_issues.append("CORS allows all origins - security risk")
        
        # Check file upload limits
        if settings.MAX_FILE_SIZE_MB > 1000:  # 1GB
            self.warnings.append(f"Large file upload limit: {settings.MAX_FILE_SIZE_MB}MB")
        
        if security_issues:
            self.warnings.extend([f"Security: {issue}" for issue in security_issues])
        
        return len(security_issues) == 0
    
    def _report_summary(self):
        """Report validation summary"""
        total_checks = len(self.validation_results)
        passed_checks = sum(self.validation_results.values())
        
        logger.info(f"📊 Validation Summary: {passed_checks}/{total_checks} checks passed")
        
        if self.critical_failures:
            logger.error("💥 Critical Failures:")
            for failure in self.critical_failures:
                logger.error(f"  - {failure}")
        
        if self.warnings:
            logger.warning("⚠️  Warnings:")
            for warning in self.warnings:
                logger.warning(f"  - {warning}")
    
    def get_health_status(self) -> Dict:
        """Get current health status for health endpoint"""
        return {
            "status": "healthy" if not self.critical_failures else "unhealthy",
            "checks": self.validation_results,
            "warnings": len(self.warnings),
            "critical_failures": len(self.critical_failures),
            "details": {
                "warnings": self.warnings,
                "failures": self.critical_failures
            }
        }

# Global validator instance
validator = StartupValidator()