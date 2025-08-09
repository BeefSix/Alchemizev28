import logging
import asyncio
import json
from typing import Optional, Dict, Any, Union
from datetime import datetime, timedelta
import redis
from redis.exceptions import ConnectionError, TimeoutError, RedisError
from app.core.config import settings

logger = logging.getLogger(__name__)

class RedisSecurityValidator:
    """Redis connection validation and fallback service"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.connection_healthy = False
        self.last_health_check = None
        self.fallback_cache = {}  # In-memory fallback
        self.max_fallback_items = 1000
        
    async def validate_redis_connection(self) -> Dict[str, Any]:
        """Validate Redis connection and configuration"""
        result = {
            "status": "unknown",
            "connection": False,
            "ping_successful": False,
            "info_accessible": False,
            "error": None,
            "details": {},
            "fallback_active": False
        }
        
        try:
            # Parse Redis URL
            if not settings.CELERY_BROKER_URL:
                result["error"] = "Redis URL not configured"
                result["status"] = "not_configured"
                result["fallback_active"] = True
                return result
            
            # Create Redis client
            redis_url = settings.CELERY_BROKER_URL
            if redis_url.startswith('redis://'):
                self.redis_client = redis.from_url(
                    redis_url,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
            else:
                result["error"] = f"Invalid Redis URL format: {redis_url[:20]}..."
                result["status"] = "invalid_url"
                result["fallback_active"] = True
                return result
            
            # Test basic connection
            ping_result = self.redis_client.ping()
            result["connection"] = True
            result["ping_successful"] = ping_result
            
            # Get Redis info
            info = self.redis_client.info()
            result["info_accessible"] = True
            result["details"] = {
                "redis_version": info.get("redis_version", "unknown"),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "uptime_in_seconds": info.get("uptime_in_seconds", 0)
            }
            
            # Test basic operations
            test_key = "health_check_test"
            test_value = f"test_{datetime.now().isoformat()}"
            
            # Set and get test
            self.redis_client.setex(test_key, 60, test_value)
            retrieved_value = self.redis_client.get(test_key)
            
            if retrieved_value and retrieved_value.decode() == test_value:
                result["details"]["read_write_test"] = "passed"
            else:
                result["details"]["read_write_test"] = "failed"
                result["error"] = "Redis read/write test failed"
            
            # Clean up test key
            self.redis_client.delete(test_key)
            
            self.connection_healthy = True
            self.last_health_check = datetime.now()
            result["status"] = "healthy"
            
        except ConnectionError as e:
            result["error"] = f"Redis connection failed: {str(e)}"
            result["status"] = "connection_failed"
            result["fallback_active"] = True
            self.connection_healthy = False
            logger.warning(f"Redis connection failed, activating fallback: {e}")
            
        except TimeoutError as e:
            result["error"] = f"Redis timeout: {str(e)}"
            result["status"] = "timeout"
            result["fallback_active"] = True
            self.connection_healthy = False
            logger.warning(f"Redis timeout, activating fallback: {e}")
            
        except RedisError as e:
            result["error"] = f"Redis error: {str(e)}"
            result["status"] = "redis_error"
            result["fallback_active"] = True
            self.connection_healthy = False
            logger.error(f"Redis error, activating fallback: {e}")
            
        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"
            result["status"] = "error"
            result["fallback_active"] = True
            self.connection_healthy = False
            logger.error(f"Unexpected Redis validation error: {e}")
        
        return result
    
    async def get_with_fallback(self, key: str) -> Optional[str]:
        """Get value from Redis with fallback to in-memory cache"""
        try:
            if self.connection_healthy and self.redis_client:
                value = self.redis_client.get(key)
                if value:
                    # Also cache in fallback for future use
                    self._set_fallback(key, value.decode())
                    return value.decode()
            
            # Use fallback cache
            return self._get_fallback(key)
            
        except Exception as e:
            logger.warning(f"Redis get failed for key {key}, using fallback: {e}")
            return self._get_fallback(key)
    
    async def set_with_fallback(self, key: str, value: str, expire: Optional[int] = None) -> bool:
        """Set value in Redis with fallback to in-memory cache"""
        try:
            if self.connection_healthy and self.redis_client:
                if expire:
                    result = self.redis_client.setex(key, expire, value)
                else:
                    result = self.redis_client.set(key, value)
                
                # Also set in fallback cache
                self._set_fallback(key, value, expire)
                return bool(result)
            
            # Use fallback cache only
            self._set_fallback(key, value, expire)
            return True
            
        except Exception as e:
            logger.warning(f"Redis set failed for key {key}, using fallback: {e}")
            self._set_fallback(key, value, expire)
            return True
    
    async def delete_with_fallback(self, key: str) -> bool:
        """Delete key from Redis with fallback cleanup"""
        try:
            result = False
            if self.connection_healthy and self.redis_client:
                result = bool(self.redis_client.delete(key))
            
            # Also delete from fallback
            self._delete_fallback(key)
            return result
            
        except Exception as e:
            logger.warning(f"Redis delete failed for key {key}: {e}")
            self._delete_fallback(key)
            return True
    
    def _get_fallback(self, key: str) -> Optional[str]:
        """Get value from in-memory fallback cache"""
        if key in self.fallback_cache:
            item = self.fallback_cache[key]
            # Check expiration
            if item.get('expires') and datetime.now() > item['expires']:
                del self.fallback_cache[key]
                return None
            return item['value']
        return None
    
    def _set_fallback(self, key: str, value: str, expire: Optional[int] = None):
        """Set value in in-memory fallback cache"""
        # Limit cache size
        if len(self.fallback_cache) >= self.max_fallback_items:
            # Remove oldest items (simple FIFO)
            oldest_keys = list(self.fallback_cache.keys())[:100]
            for old_key in oldest_keys:
                del self.fallback_cache[old_key]
        
        expires = None
        if expire:
            expires = datetime.now() + timedelta(seconds=expire)
        
        self.fallback_cache[key] = {
            'value': value,
            'expires': expires,
            'created': datetime.now()
        }
    
    def _delete_fallback(self, key: str):
        """Delete key from in-memory fallback cache"""
        if key in self.fallback_cache:
            del self.fallback_cache[key]
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {
            "redis_healthy": self.connection_healthy,
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
            "fallback_cache_size": len(self.fallback_cache),
            "fallback_max_size": self.max_fallback_items,
            "redis_stats": {}
        }
        
        # Get Redis stats if available
        if self.connection_healthy and self.redis_client:
            try:
                info = self.redis_client.info()
                stats["redis_stats"] = {
                    "used_memory": info.get("used_memory", 0),
                    "connected_clients": info.get("connected_clients", 0),
                    "total_commands_processed": info.get("total_commands_processed", 0),
                    "keyspace_hits": info.get("keyspace_hits", 0),
                    "keyspace_misses": info.get("keyspace_misses", 0)
                }
            except Exception as e:
                stats["redis_stats"]["error"] = str(e)
        
        return stats
    
    async def cleanup_expired_fallback(self):
        """Clean up expired items from fallback cache"""
        now = datetime.now()
        expired_keys = []
        
        for key, item in self.fallback_cache.items():
            if item.get('expires') and now > item['expires']:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.fallback_cache[key]
        
        logger.info(f"Cleaned up {len(expired_keys)} expired fallback cache items")
        return len(expired_keys)
    
    async def test_redis_operations(self) -> Dict[str, Any]:
        """Test various Redis operations for functionality"""
        result = {
            "status": "unknown",
            "operations_tested": 0,
            "operations_passed": 0,
            "errors": [],
            "details": {}
        }
        
        test_operations = [
            ("set_get", self._test_set_get),
            ("expire", self._test_expire),
            ("delete", self._test_delete),
            ("increment", self._test_increment),
            ("list_operations", self._test_list_operations)
        ]
        
        for op_name, test_func in test_operations:
            try:
                result["operations_tested"] += 1
                success = await test_func()
                if success:
                    result["operations_passed"] += 1
                    result["details"][op_name] = "passed"
                else:
                    result["details"][op_name] = "failed"
                    result["errors"].append(f"{op_name} test failed")
            except Exception as e:
                result["details"][op_name] = "error"
                result["errors"].append(f"{op_name} test error: {str(e)}")
        
        # Determine overall status
        if result["operations_passed"] == result["operations_tested"]:
            result["status"] = "all_passed"
        elif result["operations_passed"] > 0:
            result["status"] = "partial_pass"
        else:
            result["status"] = "all_failed"
        
        return result
    
    async def _test_set_get(self) -> bool:
        """Test basic set/get operations"""
        test_key = "test_set_get"
        test_value = "test_value_123"
        
        await self.set_with_fallback(test_key, test_value)
        retrieved = await self.get_with_fallback(test_key)
        await self.delete_with_fallback(test_key)
        
        return retrieved == test_value
    
    async def _test_expire(self) -> bool:
        """Test expiration functionality"""
        test_key = "test_expire"
        test_value = "expire_test"
        
        await self.set_with_fallback(test_key, test_value, expire=1)
        immediate_get = await self.get_with_fallback(test_key)
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        expired_get = await self.get_with_fallback(test_key)
        
        return immediate_get == test_value and expired_get is None
    
    async def _test_delete(self) -> bool:
        """Test delete operations"""
        test_key = "test_delete"
        test_value = "delete_test"
        
        await self.set_with_fallback(test_key, test_value)
        before_delete = await self.get_with_fallback(test_key)
        await self.delete_with_fallback(test_key)
        after_delete = await self.get_with_fallback(test_key)
        
        return before_delete == test_value and after_delete is None
    
    async def _test_increment(self) -> bool:
        """Test increment operations (Redis-specific)"""
        if not self.connection_healthy or not self.redis_client:
            return True  # Skip if Redis not available
        
        try:
            test_key = "test_incr"
            self.redis_client.delete(test_key)
            
            result1 = self.redis_client.incr(test_key)
            result2 = self.redis_client.incr(test_key)
            
            self.redis_client.delete(test_key)
            return result1 == 1 and result2 == 2
        except Exception:
            return False
    
    async def _test_list_operations(self) -> bool:
        """Test list operations (Redis-specific)"""
        if not self.connection_healthy or not self.redis_client:
            return True  # Skip if Redis not available
        
        try:
            test_key = "test_list"
            self.redis_client.delete(test_key)
            
            # Push items
            self.redis_client.lpush(test_key, "item1", "item2")
            length = self.redis_client.llen(test_key)
            
            # Pop item
            popped = self.redis_client.rpop(test_key)
            
            self.redis_client.delete(test_key)
            return length == 2 and popped.decode() == "item1"
        except Exception:
            return False

# Global Redis security validator
redis_security = RedisSecurityValidator()