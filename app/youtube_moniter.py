# app/services/youtube_monitor.py
import json
from datetime import datetime, timedelta
from collections import defaultdict

class YouTubeDownloadMonitor:
    """Monitor and track YouTube download success rates and failures"""
    
    def __init__(self):
        self.stats = defaultdict(int)
        self.failures = []
        self.last_reset = datetime.now()
    
    def log_attempt(self, url: str, method: str, success: bool, error: str = None):
        """Log a download attempt"""
        timestamp = datetime.now()
        
        self.stats[f'{method}_attempts'] += 1
        if success:
            self.stats[f'{method}_success'] += 1
            self.stats['total_success'] += 1
        else:
            self.stats[f'{method}_failures'] += 1
            self.stats['total_failures'] += 1
            self.failures.append({
                'timestamp': timestamp.isoformat(),
                'url': url,
                'method': method,
                'error': error
            })
        
        self.stats['total_attempts'] += 1
        
        if timestamp - self.last_reset > timedelta(days=1):
            self.reset_daily_stats()

    def reset_daily_stats(self):
        self.stats.clear()
        self.failures = []
        self.last_reset = datetime.now()

    def get_success_rate(self, method: str = None) -> float:
        if method:
            attempts = self.stats[f'{method}_attempts']
            success = self.stats[f'{method}_success']
        else:
            attempts = self.stats['total_attempts']
            success = self.stats['total_success']
        
        return (success / attempts * 100) if attempts > 0 else 0

    def get_best_method(self) -> str:
        methods = ['standard_download', 'alternative_extractor', 'proxy_rotation', 'selenium_assisted']
        best_method = 'standard_download'
        best_rate = -1.0
        
        for method in methods:
            rate = self.get_success_rate(method)
            if self.stats[f'{method}_attempts'] > 0 and rate > best_rate:
                best_rate = rate
                best_method = method
        
        return best_method

    def should_skip_method(self, method: str) -> bool:
        """Determine if a method should be skipped based on recent failures"""
        recent_failures = sum(1 for f in self.failures
                              if f['method'] == method
                              and datetime.fromisoformat(f['timestamp']) > datetime.now() - timedelta(hours=1))
        
        return recent_failures >= 3 # Skip if 3+ failures in the last hour

# Global monitor instance
monitor = YouTubeDownloadMonitor()