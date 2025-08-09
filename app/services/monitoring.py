import logging
import smtplib
import json
import os
import psutil
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from contextlib import contextmanager
from sqlalchemy import text

from app.core.config import settings
from app.db.base import get_db_session
from app.services.redis_security import redis_security
from app.db import crud

logger = logging.getLogger(__name__)

@dataclass
class Alert:
    """Alert data structure"""
    level: str  # 'critical', 'warning', 'info'
    component: str
    message: str
    timestamp: datetime
    metadata: Dict[str, Any] = None

@dataclass
class SystemMetrics:
    """System metrics data structure"""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    active_jobs: int
    failed_jobs_24h: int
    redis_status: bool
    db_status: bool
    timestamp: datetime

class ProductionMonitor:
    """Production monitoring and alerting system"""
    
    def __init__(self):
        self.alerts_sent = {}  # Track sent alerts to avoid spam
        self.alert_cooldown = 300  # 5 minutes cooldown between same alerts
        
    def collect_system_metrics(self) -> SystemMetrics:
        """Collect comprehensive system metrics"""
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            # Use appropriate disk path based on OS
            disk_path = '/' if os.name != 'nt' else 'C:\\'
            disk = psutil.disk_usage(disk_path)
            
            # Database metrics
            db_status = self._check_database_health()
            
            # Redis metrics
            try:
                redis_status = redis_security.connection_healthy
            except Exception as e:
                logger.warning(f"Failed to get Redis status: {e}")
                redis_status = False
            
            # Job metrics
            active_jobs, failed_jobs_24h = self._get_job_metrics()
            
            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                disk_percent=(disk.used / disk.total) * 100,
                active_jobs=active_jobs,
                failed_jobs_24h=failed_jobs_24h,
                redis_status=redis_status,
                db_status=db_status,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            return None
    
    def _check_database_health(self) -> bool:
        """Check database connectivity and health"""
        try:
            with get_db_session() as db:
                # Simple query to test connection
                result = db.execute(text("SELECT 1")).fetchone()
                return result is not None
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    def _get_job_metrics(self) -> tuple[int, int]:
        """Get job-related metrics"""
        try:
            with get_db_session() as db:
                # Count active jobs
                active_jobs = crud.count_active_jobs(db)
                
                # Count failed jobs in last 24 hours
                since = datetime.utcnow() - timedelta(hours=24)
                failed_jobs = crud.count_failed_jobs_since(db, since)
                
                return active_jobs, failed_jobs
        except Exception as e:
            logger.error(f"Failed to get job metrics: {e}")
            return 0, 0
    
    def analyze_metrics(self, metrics: SystemMetrics) -> List[Alert]:
        """Analyze metrics and generate alerts"""
        alerts = []
        
        if not metrics:
            alerts.append(Alert(
                level='critical',
                component='monitoring',
                message='Failed to collect system metrics',
                timestamp=datetime.utcnow()
            ))
            return alerts
        
        # CPU alerts
        if metrics.cpu_percent > 90:
            alerts.append(Alert(
                level='critical',
                component='cpu',
                message=f'CPU usage critical: {metrics.cpu_percent:.1f}%',
                timestamp=metrics.timestamp,
                metadata={'cpu_percent': metrics.cpu_percent}
            ))
        elif metrics.cpu_percent > 80:
            alerts.append(Alert(
                level='warning',
                component='cpu',
                message=f'CPU usage high: {metrics.cpu_percent:.1f}%',
                timestamp=metrics.timestamp,
                metadata={'cpu_percent': metrics.cpu_percent}
            ))
        
        # Memory alerts
        if metrics.memory_percent > 95:
            alerts.append(Alert(
                level='critical',
                component='memory',
                message=f'Memory usage critical: {metrics.memory_percent:.1f}%',
                timestamp=metrics.timestamp,
                metadata={'memory_percent': metrics.memory_percent}
            ))
        elif metrics.memory_percent > 85:
            alerts.append(Alert(
                level='warning',
                component='memory',
                message=f'Memory usage high: {metrics.memory_percent:.1f}%',
                timestamp=metrics.timestamp,
                metadata={'memory_percent': metrics.memory_percent}
            ))
        
        # Disk alerts
        if metrics.disk_percent > 95:
            alerts.append(Alert(
                level='critical',
                component='disk',
                message=f'Disk usage critical: {metrics.disk_percent:.1f}%',
                timestamp=metrics.timestamp,
                metadata={'disk_percent': metrics.disk_percent}
            ))
        elif metrics.disk_percent > 85:
            alerts.append(Alert(
                level='warning',
                component='disk',
                message=f'Disk usage high: {metrics.disk_percent:.1f}%',
                timestamp=metrics.timestamp,
                metadata={'disk_percent': metrics.disk_percent}
            ))
        
        # Service alerts
        if not metrics.db_status:
            alerts.append(Alert(
                level='critical',
                component='database',
                message='Database connection failed',
                timestamp=metrics.timestamp
            ))
        
        if not metrics.redis_status:
            alerts.append(Alert(
                level='critical',
                component='redis',
                message='Redis connection failed',
                timestamp=metrics.timestamp
            ))
        
        # Job processing alerts
        if metrics.failed_jobs_24h > 10:
            alerts.append(Alert(
                level='warning',
                component='jobs',
                message=f'High number of failed jobs: {metrics.failed_jobs_24h} in 24h',
                timestamp=metrics.timestamp,
                metadata={'failed_jobs_24h': metrics.failed_jobs_24h}
            ))
        
        if metrics.active_jobs > 50:
            alerts.append(Alert(
                level='warning',
                component='jobs',
                message=f'High number of active jobs: {metrics.active_jobs}',
                timestamp=metrics.timestamp,
                metadata={'active_jobs': metrics.active_jobs}
            ))
        
        return alerts
    
    def send_alert(self, alert: Alert) -> bool:
        """Send alert via configured channels"""
        try:
            # Check cooldown to avoid spam
            alert_key = f"{alert.component}_{alert.level}_{alert.message[:50]}"
            now = time.time()
            
            if alert_key in self.alerts_sent:
                if now - self.alerts_sent[alert_key] < self.alert_cooldown:
                    return False  # Skip due to cooldown
            
            self.alerts_sent[alert_key] = now
            
            # Log alert
            log_level = logging.CRITICAL if alert.level == 'critical' else logging.WARNING
            logger.log(log_level, f"ALERT [{alert.level.upper()}] {alert.component}: {alert.message}")
            
            # Send email if configured
            if hasattr(settings, 'ALERT_EMAIL_TO') and settings.ALERT_EMAIL_TO:
                self._send_email_alert(alert)
            
            # Send to monitoring service if configured
            if hasattr(settings, 'MONITORING_WEBHOOK_URL') and settings.MONITORING_WEBHOOK_URL:
                self._send_webhook_alert(alert)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False
    
    def _send_email_alert(self, alert: Alert):
        """Send alert via email"""
        try:
            if not all([settings.SMTP_HOST, settings.SMTP_PORT, settings.ALERT_EMAIL_FROM, settings.ALERT_EMAIL_TO]):
                return
            
            msg = MIMEMultipart()
            msg['From'] = settings.ALERT_EMAIL_FROM
            msg['To'] = settings.ALERT_EMAIL_TO
            msg['Subject'] = f"[ZUEXIS {alert.level.upper()}] {alert.component} Alert"
            
            body = f"""
            Alert Details:
            Level: {alert.level.upper()}
            Component: {alert.component}
            Message: {alert.message}
            Timestamp: {alert.timestamp}
            
            Metadata: {json.dumps(alert.metadata, indent=2) if alert.metadata else 'None'}
            
            --
            Zuexis Production Monitoring
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if hasattr(settings, 'SMTP_USERNAME') and settings.SMTP_USERNAME:
                    server.starttls()
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(msg)
            
            logger.info(f"Email alert sent for {alert.component}")
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
    
    def _send_webhook_alert(self, alert: Alert):
        """Send alert via webhook (e.g., Slack, Discord, PagerDuty)"""
        try:
            import requests
            
            payload = {
                'level': alert.level,
                'component': alert.component,
                'message': alert.message,
                'timestamp': alert.timestamp.isoformat(),
                'metadata': alert.metadata,
                'service': 'zuexis'
            }
            
            response = requests.post(
                settings.MONITORING_WEBHOOK_URL,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Webhook alert sent for {alert.component}")
            else:
                logger.error(f"Webhook alert failed: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status for health endpoint"""
        metrics = self.collect_system_metrics()
        alerts = self.analyze_metrics(metrics) if metrics else []
        
        critical_alerts = [a for a in alerts if a.level == 'critical']
        warning_alerts = [a for a in alerts if a.level == 'warning']
        
        status = 'healthy'
        if critical_alerts:
            status = 'critical'
        elif warning_alerts:
            status = 'warning'
        
        return {
            'status': status,
            'timestamp': datetime.utcnow().isoformat(),
            'metrics': {
                'cpu_percent': metrics.cpu_percent if metrics else None,
                'memory_percent': metrics.memory_percent if metrics else None,
                'disk_percent': metrics.disk_percent if metrics else None,
                'active_jobs': metrics.active_jobs if metrics else None,
                'failed_jobs_24h': metrics.failed_jobs_24h if metrics else None,
                'redis_status': metrics.redis_status if metrics else None,
                'db_status': metrics.db_status if metrics else None
            },
            'alerts': {
                'critical': len(critical_alerts),
                'warning': len(warning_alerts),
                'recent': [{
                    'level': a.level,
                    'component': a.component,
                    'message': a.message,
                    'timestamp': a.timestamp.isoformat()
                } for a in alerts[-5:]]  # Last 5 alerts
            }
        }

# Global monitor instance
monitor = ProductionMonitor()

@contextmanager
def performance_monitor(operation_name: str, alert_threshold_seconds: float = 30.0):
    """Context manager to monitor operation performance"""
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        logger.info(f"Operation '{operation_name}' took {duration:.2f}s")
        
        if duration > alert_threshold_seconds:
            alert = Alert(
                level='warning',
                component='performance',
                message=f"Slow operation: {operation_name} took {duration:.2f}s",
                timestamp=datetime.utcnow(),
                metadata={'operation': operation_name, 'duration': duration}
            )
            monitor.send_alert(alert)

def start_monitoring_loop():
    """Start continuous monitoring loop (for background task)"""
    logger.info("Starting production monitoring loop")
    
    while True:
        try:
            metrics = monitor.collect_system_metrics()
            alerts = monitor.analyze_metrics(metrics)
            
            # Send any alerts
            for alert in alerts:
                monitor.send_alert(alert)
            
            # Log system status
            if metrics:
                logger.info(
                    f"System Status - CPU: {metrics.cpu_percent:.1f}%, "
                    f"Memory: {metrics.memory_percent:.1f}%, "
                    f"Disk: {metrics.disk_percent:.1f}%, "
                    f"Active Jobs: {metrics.active_jobs}, "
                    f"Failed Jobs (24h): {metrics.failed_jobs_24h}"
                )
            
            # Wait before next check
            time.sleep(60)  # Check every minute
            
        except Exception as e:
            logger.error(f"Monitoring loop error: {e}")
            time.sleep(60)