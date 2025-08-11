import logging
import asyncio
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque
from fastapi import HTTPException, Request
from app.services.redis_security import redis_security
import hashlib
import json

logger = logging.getLogger(__name__)

class AdvancedRateLimiter:
    """Advanced rate limiting with Redis fallback and multiple strategies"""
    
    def __init__(self):
        self.local_cache = defaultdict(lambda: defaultdict(deque))
        self.blocked_ips = defaultdict(datetime)
        self.user_limits = {
            "upload": {"requests": 500, "window": 3600, "burst": 100},  # 500/hour, burst 100 (very dev-friendly)
            "api_general": {"requests": 1000, "window": 3600, "burst": 200},  # 1000/hour, burst 200 (very dev-friendly)
            "auth": {"requests": 500, "window": 900, "burst": 100},  # 500/15min, burst 100 (very dev-friendly)
            "download": {"requests": 500, "window": 3600, "burst": 100},  # 500/hour, burst 100 (very dev-friendly)
        }
        self.ip_limits = {
            "global": {"requests": 10000, "window": 3600, "burst": 1000},  # 10000/hour per IP (very dev-friendly)
            "upload": {"requests": 1000, "window": 3600, "burst": 200},  # 1000/hour per IP (very dev-friendly)
        }
    
    def _get_client_id(self, request: Request, user_id: Optional[str] = None) -> str:
        """Get unique client identifier"""
        # Use user ID if authenticated, otherwise IP
        if user_id:
            return f"user:{user_id}"
        
        # Get real IP (considering proxies)
        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if not client_ip:
            client_ip = request.headers.get("X-Real-IP", "")
        if not client_ip:
            client_ip = getattr(request.client, "host", "unknown")
        
        return f"ip:{client_ip}"
    
    def _get_rate_key(self, client_id: str, endpoint: str, window_start: int) -> str:
        """Generate Redis key for rate limiting"""
        return f"rate_limit:{client_id}:{endpoint}:{window_start}"
    
    async def _check_redis_limit(self, key: str, limit: int, window: int) -> Tuple[bool, int, int]:
        """Check rate limit using Redis with fallback"""
        try:
            # Try Redis first
            current_count = await redis_security.get_with_fallback(key)
            if current_count is None:
                # First request in window
                await redis_security.set_with_fallback(key, "1", expire=window)
                return True, 1, limit - 1
            
            count = int(current_count)
            if count >= limit:
                return False, count, 0
            
            # Increment counter
            new_count = count + 1
            await redis_security.set_with_fallback(key, str(new_count), expire=window)
            return True, new_count, limit - new_count
            
        except Exception as e:
            logger.warning(f"Redis rate limit check failed, using local fallback: {e}")
            return self._check_local_limit(key, limit, window)
    
    def _check_local_limit(self, key: str, limit: int, window: int) -> Tuple[bool, int, int]:
        """Fallback rate limiting using local memory"""
        now = datetime.now()
        window_start = now - timedelta(seconds=window)
        
        # Clean old entries
        if key in self.local_cache:
            timestamps = self.local_cache[key]["timestamps"]
            while timestamps and timestamps[0] < window_start:
                timestamps.popleft()
        
        current_count = len(self.local_cache[key]["timestamps"])
        
        if current_count >= limit:
            return False, current_count, 0
        
        # Add new request
        self.local_cache[key]["timestamps"].append(now)
        return True, current_count + 1, limit - current_count - 1
    
    async def check_rate_limit(
        self, 
        request: Request, 
        endpoint: str, 
        user_id: Optional[str] = None,
        custom_limit: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
        """Check if request is within rate limits"""
        client_id = self._get_client_id(request, user_id)
        now = datetime.now()
        
        # Check if IP is temporarily blocked
        if client_id.startswith("ip:"):
            ip = client_id[3:]
            if ip in self.blocked_ips and now < self.blocked_ips[ip]:
                remaining_block = (self.blocked_ips[ip] - now).total_seconds()
                raise HTTPException(
                    status_code=429,
                    detail=f"IP temporarily blocked. Try again in {int(remaining_block)} seconds.",
                    headers={"Retry-After": str(int(remaining_block))}
                )
        
        # Get rate limit configuration
        if custom_limit:
            limits = custom_limit
        elif user_id and endpoint in self.user_limits:
            limits = self.user_limits[endpoint]
        elif endpoint in self.ip_limits:
            limits = self.ip_limits[endpoint]
        else:
            limits = self.ip_limits["global"]
        
        # Calculate window start
        window = limits["window"]
        window_start = int(now.timestamp()) // window * window
        
        # Check main rate limit
        rate_key = self._get_rate_key(client_id, endpoint, window_start)
        allowed, current_count, remaining = await self._check_redis_limit(
            rate_key, limits["requests"], window
        )
        
        # Check burst limit (shorter window)
        burst_window = min(60, window // 10)  # 1 minute or 1/10 of main window
        burst_window_start = int(now.timestamp()) // burst_window * burst_window
        burst_key = self._get_rate_key(client_id, f"{endpoint}_burst", burst_window_start)
        
        burst_allowed, burst_count, burst_remaining = await self._check_redis_limit(
            burst_key, limits["burst"], burst_window
        )
        
        # Determine if request is allowed
        request_allowed = allowed and burst_allowed
        
        # Handle rate limit exceeded
        if not request_allowed:
            # Implement progressive blocking for repeated violations
            violation_key = f"violations:{client_id}"
            violations = await redis_security.get_with_fallback(violation_key)
            violation_count = int(violations) if violations else 0
            
            # Increment violations
            new_violation_count = violation_count + 1
            await redis_security.set_with_fallback(violation_key, str(new_violation_count), expire=3600)
            
            # Progressive blocking: 1min, 5min, 15min, 1hour
            block_durations = [60, 300, 900, 3600]
            block_duration = block_durations[min(new_violation_count - 1, len(block_durations) - 1)]
            
            if client_id.startswith("ip:"):
                ip = client_id[3:]
                self.blocked_ips[ip] = now + timedelta(seconds=block_duration)
            
            # Determine which limit was exceeded
            if not allowed:
                retry_after = window - (int(now.timestamp()) % window)
                detail = f"Rate limit exceeded: {current_count}/{limits['requests']} requests per {window}s"
            else:
                retry_after = burst_window - (int(now.timestamp()) % burst_window)
                detail = f"Burst limit exceeded: {burst_count}/{limits['burst']} requests per {burst_window}s"
            
            raise HTTPException(
                status_code=429,
                detail=detail,
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limits["requests"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(window_start + window)
                }
            )
        
        # Return rate limit info for headers
        return {
            "allowed": True,
            "limit": limits["requests"],
            "remaining": remaining,
            "reset": window_start + window,
            "burst_limit": limits["burst"],
            "burst_remaining": burst_remaining,
            "client_id": client_id
        }
    
    async def get_rate_limit_status(self, client_id: str, endpoint: str) -> Dict[str, Any]:
        """Get current rate limit status for monitoring"""
        now = datetime.now()
        
        # Get limits
        if endpoint in self.user_limits:
            limits = self.user_limits[endpoint]
        elif endpoint in self.ip_limits:
            limits = self.ip_limits[endpoint]
        else:
            limits = self.ip_limits["global"]
        
        window = limits["window"]
        window_start = int(now.timestamp()) // window * window
        
        # Get current usage
        rate_key = self._get_rate_key(client_id, endpoint, window_start)
        current_usage = await redis_security.get_with_fallback(rate_key)
        usage_count = int(current_usage) if current_usage else 0
        
        return {
            "client_id": client_id,
            "endpoint": endpoint,
            "limit": limits["requests"],
            "used": usage_count,
            "remaining": max(0, limits["requests"] - usage_count),
            "reset_time": window_start + window,
            "window_seconds": window,
            "burst_limit": limits["burst"]
        }
    
    async def reset_rate_limit(self, client_id: str, endpoint: str) -> bool:
        """Reset rate limit for a client (admin function)"""
        try:
            now = datetime.now()
            window = self.user_limits.get(endpoint, self.ip_limits["global"])["window"]
            window_start = int(now.timestamp()) // window * window
            
            rate_key = self._get_rate_key(client_id, endpoint, window_start)
            burst_key = self._get_rate_key(client_id, f"{endpoint}_burst", window_start)
            violation_key = f"violations:{client_id}"
            
            # Reset all related keys
            await redis_security.delete_with_fallback(rate_key)
            await redis_security.delete_with_fallback(burst_key)
            await redis_security.delete_with_fallback(violation_key)
            
            # Remove from blocked IPs
            if client_id.startswith("ip:"):
                ip = client_id[3:]
                if ip in self.blocked_ips:
                    del self.blocked_ips[ip]
            
            logger.info(f"Rate limit reset for {client_id} on {endpoint}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset rate limit for {client_id}: {e}")
            return False
    
    async def get_global_stats(self) -> Dict[str, Any]:
        """Get global rate limiting statistics"""
        stats = {
            "blocked_ips_count": len(self.blocked_ips),
            "local_cache_size": len(self.local_cache),
            "active_blocks": [],
            "rate_limits_configured": {
                "user_endpoints": list(self.user_limits.keys()),
                "ip_endpoints": list(self.ip_limits.keys())
            }
        }
        
        # Get currently blocked IPs
        now = datetime.now()
        for ip, block_until in self.blocked_ips.items():
            if now < block_until:
                remaining = (block_until - now).total_seconds()
                stats["active_blocks"].append({
                    "ip": ip,
                    "remaining_seconds": int(remaining)
                })
        
        return stats
    
    def cleanup_expired_blocks(self):
        """Clean up expired IP blocks"""
        now = datetime.now()
        expired_ips = [ip for ip, block_until in self.blocked_ips.items() if now >= block_until]
        
        for ip in expired_ips:
            del self.blocked_ips[ip]
        
        logger.info(f"Cleaned up {len(expired_ips)} expired IP blocks")
        return len(expired_ips)

# Global rate limiter instance
rate_limiter = AdvancedRateLimiter()