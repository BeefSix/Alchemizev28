#!/usr/bin/env python3
"""
Development utility to reset rate limits
"""

import asyncio
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.rate_limiter import rate_limiter
from app.services.redis_security import redis_security

async def reset_all_rate_limits():
    """Reset all rate limits for development"""
    print("🔄 Resetting rate limits for development...")
    
    # Common client IDs to reset
    client_ids = [
        "ip:127.0.0.1",
        "ip:localhost", 
        "ip:::1",
        "ip:unknown"
    ]
    
    # Common endpoints to reset
    endpoints = [
        "api_general",
        "upload", 
        "auth",
        "download"
    ]
    
    reset_count = 0
    
    for client_id in client_ids:
        for endpoint in endpoints:
            try:
                success = await rate_limiter.reset_rate_limit(client_id, endpoint)
                if success:
                    reset_count += 1
                    print(f"✅ Reset {client_id} for {endpoint}")
            except Exception as e:
                print(f"❌ Failed to reset {client_id} for {endpoint}: {e}")
    
    # Clear blocked IPs
    rate_limiter.blocked_ips.clear()
    print(f"🧹 Cleared {len(rate_limiter.blocked_ips)} blocked IPs")
    
    # Get stats
    stats = await rate_limiter.get_global_stats()
    print(f"\n📊 Rate Limit Stats:")
    print(f"   - Reset {reset_count} rate limit entries")
    print(f"   - Blocked IPs: {stats['blocked_ips_count']}")
    print(f"   - Local cache size: {stats['local_cache_size']}")
    
    print("\n✨ Rate limits reset successfully! You can now use the application freely.")

if __name__ == "__main__":
    asyncio.run(reset_all_rate_limits())