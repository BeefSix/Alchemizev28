import re
import logging
from typing import List, Dict, Set, Optional
from urllib.parse import urlparse
from app.core.config import settings

logger = logging.getLogger(__name__)

class NetworkSecurityConfig:
    """Network security configuration and domain allowlisting"""
    
    # Approved domains for URL fetching and yt_dlp
    APPROVED_DOMAINS = {
        # YouTube domains
        'youtube.com',
        'www.youtube.com', 
        'youtu.be',
        'm.youtube.com',
        'youtube-nocookie.com',
        
        # Educational/News domains (add as needed)
        'wikipedia.org',
        'en.wikipedia.org',
        'news.ycombinator.com',
        'github.com',
        'stackoverflow.com',
        
        # Add production domains here
        # 'yourdomain.com',
        # 'api.yourdomain.com'
    }
    
    # Blocked URL schemes
    BLOCKED_SCHEMES = {
        'file', 'ftp', 'sftp', 'ssh', 'telnet', 'ldap', 'ldaps',
        'gopher', 'dict', 'imap', 'imaps', 'pop3', 'pop3s',
        'smtp', 'smtps', 'rtsp', 'rtmp', 'sip', 'sips'
    }
    
    # Private/Internal IP ranges to block
    BLOCKED_IP_PATTERNS = [
        r'^127\.',          # Loopback
        r'^10\.',           # Private Class A
        r'^172\.(1[6-9]|2[0-9]|3[0-1])\.',  # Private Class B
        r'^192\.168\.',     # Private Class C
        r'^169\.254\.',     # Link-local
        r'^224\.',          # Multicast
        r'^::1$',           # IPv6 loopback
        r'^fc00:',          # IPv6 private
        r'^fe80:',          # IPv6 link-local
    ]
    
    @classmethod
    def is_domain_approved(cls, url: str) -> bool:
        """Check if domain is in approved list"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Remove port if present
            if ':' in domain:
                domain = domain.split(':')[0]
                
            # Check exact match and subdomain match
            if domain in cls.APPROVED_DOMAINS:
                return True
                
            # Check if it's a subdomain of approved domain
            for approved_domain in cls.APPROVED_DOMAINS:
                if domain.endswith('.' + approved_domain):
                    return True
                    
            return False
            
        except Exception as e:
            logger.warning(f"Domain validation error for {url}: {e}")
            return False
    
    @classmethod
    def is_scheme_allowed(cls, url: str) -> bool:
        """Check if URL scheme is allowed"""
        try:
            parsed = urlparse(url)
            scheme = parsed.scheme.lower()
            
            if scheme in cls.BLOCKED_SCHEMES:
                return False
                
            # Only allow http/https
            return scheme in {'http', 'https'}
            
        except Exception:
            return False
    
    @classmethod
    def is_ip_blocked(cls, url: str) -> bool:
        """Check if URL contains blocked IP address"""
        try:
            parsed = urlparse(url)
            host = parsed.netloc.lower()
            
            # Remove port if present
            if ':' in host:
                host = host.split(':')[0]
            
            # Check against blocked IP patterns
            for pattern in cls.BLOCKED_IP_PATTERNS:
                if re.match(pattern, host):
                    return True
                    
            return False
            
        except Exception:
            return False
    
    @classmethod
    def validate_url(cls, url: str) -> tuple[bool, str]:
        """Comprehensive URL validation"""
        if not url or not isinstance(url, str):
            return False, "Invalid URL format"
            
        # Check scheme
        if not cls.is_scheme_allowed(url):
            return False, "URL scheme not allowed"
            
        # Check for blocked IPs
        if cls.is_ip_blocked(url):
            return False, "IP address not allowed"
            
        # Check domain approval
        if not cls.is_domain_approved(url):
            return False, "Domain not in approved list"
            
        return True, "URL approved"
    
    @classmethod
    def get_yt_dlp_security_config(cls) -> Dict:
        """Get security-hardened yt_dlp configuration"""
        return {
            'restrictfilenames': True,
            'no_warnings': True,
            'extract_flat': False,
            'noplaylist': True,
            'max_downloads': 1,
            'socket_timeout': 30,
            'retries': 3,
            'fragment_retries': 3,
            'skip_unavailable_fragments': True,
            'abort_on_unavailable_fragment': False,
            'keep_fragments': False,
            'buffersize': 1024 * 16,  # 16KB buffer
            'http_chunk_size': 1024 * 1024,  # 1MB chunks
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'sleep_interval': 1,
            'max_sleep_interval': 5,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'writedescription': False,
            'writeinfojson': False,
            'writethumbnail': False,
            'writecomments': False,
            'getcomments': False,
            'ignoreerrors': False,
            'no_color': True,
            'quiet': True,
        }
    
    @classmethod
    def get_requests_security_config(cls) -> Dict:
        """Get security-hardened requests configuration"""
        return {
            'timeout': 15,
            'allow_redirects': True,
            'max_redirects': 3,
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            },
            'stream': False,
            'verify': True,  # Always verify SSL certificates
        }

# Production-specific network restrictions
class ProductionNetworkConfig(NetworkSecurityConfig):
    """Production network configuration with stricter rules"""
    
    # More restrictive approved domains for production
    APPROVED_DOMAINS = {
        'youtube.com',
        'www.youtube.com',
        'youtu.be',
        'm.youtube.com',
        'youtube-nocookie.com',
        # Add your production domains here
    }

# Get appropriate config based on environment
def get_network_config():
    """Get network configuration based on environment"""
    if settings.ENVIRONMENT.lower() == 'production':
        return ProductionNetworkConfig
    return NetworkSecurityConfig