import logging
import asyncio
from typing import Optional, Dict, Any, List
from sqlalchemy import text, inspect
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from app.db.base import engine, get_db
from app.core.config import settings
import re

logger = logging.getLogger(__name__)

class DatabaseSecurityValidator:
    """Comprehensive database security and validation service"""
    
    # SQL injection patterns to detect
    SQL_INJECTION_PATTERNS = [
        r"('|(\-\-)|(;)|(\||\|)|(\*|\*))",
        r"(union|select|insert|delete|update|drop|create|alter|exec|execute)",
        r"(script|javascript|vbscript|onload|onerror|onclick)",
        r"(\<|\>|\%3C|\%3E)",
        r"(eval\s*\(|expression\s*\()",
    ]
    
    def __init__(self):
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.SQL_INJECTION_PATTERNS]
    
    async def validate_database_connection(self) -> Dict[str, Any]:
        """Validate database connection and health"""
        result = {
            "status": "unknown",
            "connection": False,
            "tables_exist": False,
            "migrations_current": False,
            "error": None,
            "details": {}
        }
        
        try:
            # Test basic connection
            with engine.connect() as conn:
                # Simple connectivity test
                conn.execute(text("SELECT 1"))
                result["connection"] = True
                
                # Check if tables exist
                inspector = inspect(engine)
                tables = inspector.get_table_names()
                result["tables_exist"] = len(tables) > 0
                result["details"]["table_count"] = len(tables)
                result["details"]["tables"] = tables[:10]  # First 10 tables
                
                # Check database version/info
                if settings.DATABASE_URL.startswith("postgresql"):
                    version_result = conn.execute(text("SELECT version()"))
                    result["details"]["database_version"] = version_result.scalar()
                elif settings.DATABASE_URL.startswith("sqlite"):
                    version_result = conn.execute(text("SELECT sqlite_version()"))
                    result["details"]["database_version"] = f"SQLite {version_result.scalar()}"
                
                # Check for alembic version table (migrations)
                if "alembic_version" in tables:
                    version_result = conn.execute(text("SELECT version_num FROM alembic_version"))
                    current_version = version_result.scalar()
                    result["migrations_current"] = current_version is not None
                    result["details"]["migration_version"] = current_version
                
                result["status"] = "healthy"
                
        except OperationalError as e:
            result["error"] = f"Database connection failed: {str(e)}"
            result["status"] = "connection_failed"
            logger.error(f"Database connection error: {e}")
            
        except SQLAlchemyError as e:
            result["error"] = f"Database error: {str(e)}"
            result["status"] = "error"
            logger.error(f"Database error: {e}")
            
        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"
            result["status"] = "error"
            logger.error(f"Unexpected database validation error: {e}")
        
        return result
    
    def validate_query_safety(self, query: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Validate SQL query for potential injection attacks"""
        result = {
            "safe": True,
            "warnings": [],
            "blocked_patterns": [],
            "recommendation": "Query appears safe"
        }
        
        # Check for SQL injection patterns
        for i, pattern in enumerate(self.compiled_patterns):
            if pattern.search(query):
                result["safe"] = False
                result["blocked_patterns"].append(self.SQL_INJECTION_PATTERNS[i])
        
        # Check for parameterized queries
        if not params and (":" in query or "?" in query or "%s" in query):
            result["warnings"].append("Query contains parameter placeholders but no parameters provided")
        
        # Check for dynamic SQL construction
        if "format" in query.lower() or "%" in query:
            result["warnings"].append("Potential string formatting detected - use parameterized queries")
        
        # Recommendations
        if not result["safe"]:
            result["recommendation"] = "BLOCKED: Query contains potential SQL injection patterns"
        elif result["warnings"]:
            result["recommendation"] = "Use parameterized queries for better security"
        
        return result
    
    def sanitize_user_input(self, user_input: str, max_length: int = 255) -> str:
        """Sanitize user input for database operations"""
        if not isinstance(user_input, str):
            user_input = str(user_input)
        
        # Remove null bytes
        user_input = user_input.replace('\x00', '')
        
        # Limit length
        if len(user_input) > max_length:
            user_input = user_input[:max_length]
        
        # Remove potentially dangerous characters
        dangerous_chars = ['<', '>', '"', "'", '&', ';', '(', ')', '|', '*']
        for char in dangerous_chars:
            user_input = user_input.replace(char, '')
        
        return user_input.strip()
    
    async def test_crud_operations(self) -> Dict[str, Any]:
        """Test basic CRUD operations for security"""
        result = {
            "status": "unknown",
            "operations_tested": 0,
            "operations_passed": 0,
            "errors": [],
            "details": {}
        }
        
        try:
            db = next(get_db())
            
            # Test basic SELECT operation
            try:
                # Safe parameterized query
                safe_query = text("SELECT 1 as test_value WHERE :param = :param")
                db.execute(safe_query, {"param": "test"})
                result["operations_tested"] += 1
                result["operations_passed"] += 1
                result["details"]["select_test"] = "passed"
            except Exception as e:
                result["errors"].append(f"SELECT test failed: {str(e)}")
                result["details"]["select_test"] = "failed"
            
            # Test injection prevention
            try:
                # This should be safe due to parameterization
                injection_attempt = "'; DROP TABLE users; --"
                safe_query = text("SELECT :input as sanitized_input")
                result_set = db.execute(safe_query, {"input": injection_attempt})
                sanitized_result = result_set.scalar()
                
                result["operations_tested"] += 1
                if sanitized_result == injection_attempt:  # Should be treated as literal string
                    result["operations_passed"] += 1
                    result["details"]["injection_prevention"] = "passed"
                else:
                    result["errors"].append("Injection prevention test unexpected result")
                    result["details"]["injection_prevention"] = "unexpected"
                    
            except Exception as e:
                result["errors"].append(f"Injection prevention test failed: {str(e)}")
                result["details"]["injection_prevention"] = "failed"
            
            # Determine overall status
            if result["operations_passed"] == result["operations_tested"]:
                result["status"] = "all_passed"
            elif result["operations_passed"] > 0:
                result["status"] = "partial_pass"
            else:
                result["status"] = "all_failed"
                
        except Exception as e:
            result["status"] = "error"
            result["errors"].append(f"CRUD test setup failed: {str(e)}")
            logger.error(f"CRUD operations test error: {e}")
        
        return result
    
    async def get_connection_pool_status(self) -> Dict[str, Any]:
        """Get database connection pool status"""
        result = {
            "pool_size": "unknown",
            "checked_out": "unknown",
            "overflow": "unknown",
            "checked_in": "unknown",
            "status": "unknown"
        }
        
        try:
            pool = engine.pool
            result["pool_size"] = pool.size()
            result["checked_out"] = pool.checkedout()
            result["overflow"] = pool.overflow()
            result["checked_in"] = pool.checkedin()
            
            # Determine pool health
            if result["checked_out"] < result["pool_size"]:
                result["status"] = "healthy"
            elif result["overflow"] > 0:
                result["status"] = "using_overflow"
            else:
                result["status"] = "pool_exhausted"
                
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            logger.error(f"Connection pool status error: {e}")
        
        return result

# Global database security validator
db_security = DatabaseSecurityValidator()