#!/usr/bin/env python3
"""
Production Environment Setup Script

This script helps set up secure environment variables for production deployment.
It generates secure keys, validates configuration, and creates production-ready
environment files.
"""

import os
import secrets
import string
import sys
from pathlib import Path
from typing import Dict, List, Optional
import re
import subprocess
import json

class ProductionEnvSetup:
    """Setup production environment configuration."""
    
    def __init__(self, project_root: str = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.env_file = self.project_root / '.env.production'
        self.required_vars = {
            'SECRET_KEY': 'Application secret key (auto-generated if not provided)',
            'DATABASE_URL': 'Database connection URL',
            'OPENAI_API_KEY': 'OpenAI API key for AI features',
            'ENVIRONMENT': 'Application environment (production)',
            'DEBUG': 'Debug mode (should be false in production)',
        }
        self.optional_vars = {
            'STRIPE_SECRET_KEY': 'Stripe secret key for payments',
            'STRIPE_PUBLISHABLE_KEY': 'Stripe publishable key',
            'STRIPE_WEBHOOK_SECRET': 'Stripe webhook secret',
            'FIREBASE_CREDENTIALS_JSON': 'Firebase service account credentials',
            'FIREBASE_STORAGE_BUCKET': 'Firebase storage bucket URL',
            'SMTP_HOST': 'SMTP server host for email',
            'SMTP_PORT': 'SMTP server port',
            'SMTP_USERNAME': 'SMTP username',
            'SMTP_PASSWORD': 'SMTP password',
            'ALERT_EMAIL_FROM': 'Alert email sender address',
            'ALERT_EMAIL_TO': 'Alert email recipient address',
            'MONITORING_WEBHOOK_URL': 'Monitoring webhook URL',
            'REDIS_URL': 'Redis connection URL',
            'CELERY_BROKER_URL': 'Celery broker URL',
            'CELERY_RESULT_BACKEND': 'Celery result backend URL',
        }
    
    def setup(self, interactive: bool = True) -> bool:
        """Setup production environment."""
        print("🚀 Production Environment Setup")
        print("=" * 40)
        
        if interactive:
            print("\nThis script will help you set up a secure production environment.")
            print("You'll be prompted for required configuration values.")
            print("\n⚠️  WARNING: This will create a .env.production file with sensitive data.")
            print("Make sure to keep this file secure and never commit it to version control.")
            
            if not self._confirm("Continue with setup?"):
                print("Setup cancelled.")
                return False
        
        # Collect configuration
        config = self._collect_configuration(interactive)
        
        # Validate configuration
        if not self._validate_configuration(config):
            print("❌ Configuration validation failed.")
            return False
        
        # Generate secure values
        config = self._generate_secure_values(config)
        
        # Create production environment file
        self._create_env_file(config)
        
        # Set file permissions
        self._set_secure_permissions()
        
        # Display security recommendations
        self._display_security_recommendations()
        
        print("\n✅ Production environment setup completed successfully!")
        print(f"📄 Configuration saved to: {self.env_file}")
        
        return True
    
    def _collect_configuration(self, interactive: bool) -> Dict[str, str]:
        """Collect configuration values from user."""
        config = {}
        
        print("\n📝 Required Configuration")
        print("-" * 25)
        
        for var, description in self.required_vars.items():
            if interactive:
                if var == 'SECRET_KEY':
                    print(f"\n{var}: {description}")
                    print("(Leave empty to auto-generate a secure key)")
                    value = input(f"{var}: ").strip()
                    if not value:
                        value = self._generate_secret_key()
                        print(f"Generated secure key: {value[:20]}...")
                elif var == 'ENVIRONMENT':
                    value = 'production'
                    print(f"{var}: {value} (auto-set)")
                elif var == 'DEBUG':
                    value = 'false'
                    print(f"{var}: {value} (auto-set)")
                else:
                    print(f"\n{var}: {description}")
                    value = input(f"{var}: ").strip()
                    
                    # Validate required fields
                    while not value and var in ['DATABASE_URL', 'OPENAI_API_KEY']:
                        print(f"❌ {var} is required for production.")
                        value = input(f"{var}: ").strip()
            else:
                # Non-interactive mode - use environment or defaults
                value = os.getenv(var, '')
                if var == 'SECRET_KEY' and not value:
                    value = self._generate_secret_key()
                elif var == 'ENVIRONMENT':
                    value = 'production'
                elif var == 'DEBUG':
                    value = 'false'
            
            config[var] = value
        
        if interactive:
            print("\n📝 Optional Configuration")
            print("-" * 25)
            print("(Press Enter to skip optional settings)")
            
            for var, description in self.optional_vars.items():
                print(f"\n{var}: {description}")
                value = input(f"{var} (optional): ").strip()
                if value:
                    config[var] = value
        
        return config
    
    def _validate_configuration(self, config: Dict[str, str]) -> bool:
        """Validate configuration values."""
        print("\n🔍 Validating configuration...")
        
        errors = []
        warnings = []
        
        # Validate required fields
        for var in self.required_vars:
            if not config.get(var):
                errors.append(f"Missing required variable: {var}")
        
        # Validate specific formats
        if 'DATABASE_URL' in config:
            db_url = config['DATABASE_URL']
            if not self._validate_database_url(db_url):
                errors.append("Invalid DATABASE_URL format")
        
        if 'OPENAI_API_KEY' in config:
            api_key = config['OPENAI_API_KEY']
            if not api_key.startswith('sk-') or len(api_key) < 40:
                errors.append("Invalid OPENAI_API_KEY format")
        
        if 'SECRET_KEY' in config:
            secret_key = config['SECRET_KEY']
            if len(secret_key) < 32:
                warnings.append("SECRET_KEY should be at least 32 characters long")
        
        # Validate email addresses
        email_vars = ['ALERT_EMAIL_FROM', 'ALERT_EMAIL_TO']
        for var in email_vars:
            if var in config and config[var]:
                if not self._validate_email(config[var]):
                    warnings.append(f"Invalid email format for {var}")
        
        # Display validation results
        if errors:
            print("\n❌ Validation Errors:")
            for error in errors:
                print(f"  - {error}")
        
        if warnings:
            print("\n⚠️  Validation Warnings:")
            for warning in warnings:
                print(f"  - {warning}")
        
        if not errors:
            print("✅ Configuration validation passed!")
        
        return len(errors) == 0
    
    def _generate_secure_values(self, config: Dict[str, str]) -> Dict[str, str]:
        """Generate secure values for configuration."""
        print("\n🔐 Generating secure values...")
        
        # Ensure SECRET_KEY is secure
        if not config.get('SECRET_KEY') or len(config['SECRET_KEY']) < 32:
            config['SECRET_KEY'] = self._generate_secret_key()
            print("Generated new SECRET_KEY")
        
        # Set production defaults
        config['ENVIRONMENT'] = 'production'
        config['DEBUG'] = 'false'
        
        # Generate default Redis/Celery URLs if not provided
        if not config.get('REDIS_URL'):
            config['REDIS_URL'] = 'redis://localhost:6379/0'
        
        if not config.get('CELERY_BROKER_URL'):
            config['CELERY_BROKER_URL'] = config['REDIS_URL']
        
        if not config.get('CELERY_RESULT_BACKEND'):
            config['CELERY_RESULT_BACKEND'] = config['REDIS_URL']
        
        return config
    
    def _create_env_file(self, config: Dict[str, str]):
        """Create production environment file."""
        print("\n📄 Creating production environment file...")
        
        content = self._generate_env_content(config)
        
        # Backup existing file if it exists
        if self.env_file.exists():
            backup_file = self.env_file.with_suffix('.env.production.backup')
            self.env_file.rename(backup_file)
            print(f"Backed up existing file to: {backup_file}")
        
        # Write new file
        with open(self.env_file, 'w') as f:
            f.write(content)
        
        print(f"Created: {self.env_file}")
    
    def _generate_env_content(self, config: Dict[str, str]) -> str:
        """Generate environment file content."""
        content = [
            "# Production Environment Configuration",
            "# Generated by setup_production_env.py",
            f"# Created: {self._get_timestamp()}",
            "#",
            "# ⚠️  WARNING: This file contains sensitive information!",
            "# - Never commit this file to version control",
            "# - Restrict file permissions (600)",
            "# - Keep secure backups",
            "# - Rotate secrets regularly",
            "",
            "# =============================================================================",
            "# APPLICATION SETTINGS",
            "# =============================================================================",
            f"ENVIRONMENT={config.get('ENVIRONMENT', 'production')}",
            f"DEBUG={config.get('DEBUG', 'false')}",
            "",
            "# =============================================================================",
            "# SECURITY (CRITICAL)",
            "# =============================================================================",
            f"SECRET_KEY={config.get('SECRET_KEY', '')}",
            "",
            "# =============================================================================",
            "# DATABASE",
            "# =============================================================================",
            f"DATABASE_URL={config.get('DATABASE_URL', '')}",
            "",
            "# =============================================================================",
            "# API KEYS & EXTERNAL SERVICES",
            "# =============================================================================",
            f"OPENAI_API_KEY={config.get('OPENAI_API_KEY', '')}",
        ]
        
        # Add optional payment settings
        if any(config.get(var) for var in ['STRIPE_SECRET_KEY', 'STRIPE_PUBLISHABLE_KEY', 'STRIPE_WEBHOOK_SECRET']):
            content.extend([
                "",
                "# =============================================================================",
                "# PAYMENT (STRIPE)",
                "# =============================================================================",
                f"STRIPE_SECRET_KEY={config.get('STRIPE_SECRET_KEY', '')}",
                f"STRIPE_PUBLISHABLE_KEY={config.get('STRIPE_PUBLISHABLE_KEY', '')}",
                f"STRIPE_WEBHOOK_SECRET={config.get('STRIPE_WEBHOOK_SECRET', '')}",
            ])
        
        # Add optional Firebase settings
        if any(config.get(var) for var in ['FIREBASE_CREDENTIALS_JSON', 'FIREBASE_STORAGE_BUCKET']):
            content.extend([
                "",
                "# =============================================================================",
                "# FIREBASE",
                "# =============================================================================",
                f"FIREBASE_CREDENTIALS_JSON={config.get('FIREBASE_CREDENTIALS_JSON', '')}",
                f"FIREBASE_STORAGE_BUCKET={config.get('FIREBASE_STORAGE_BUCKET', '')}",
            ])
        
        # Add Redis/Celery settings
        content.extend([
            "",
            "# =============================================================================",
            "# REDIS & CELERY",
            "# =============================================================================",
            f"REDIS_URL={config.get('REDIS_URL', 'redis://localhost:6379/0')}",
            f"CELERY_BROKER_URL={config.get('CELERY_BROKER_URL', config.get('REDIS_URL', 'redis://localhost:6379/0'))}",
            f"CELERY_RESULT_BACKEND={config.get('CELERY_RESULT_BACKEND', config.get('REDIS_URL', 'redis://localhost:6379/0'))}",
        ])
        
        # Add optional email settings
        if any(config.get(var) for var in ['SMTP_HOST', 'SMTP_USERNAME', 'SMTP_PASSWORD']):
            content.extend([
                "",
                "# =============================================================================",
                "# EMAIL & ALERTS",
                "# =============================================================================",
                f"SMTP_HOST={config.get('SMTP_HOST', '')}",
                f"SMTP_PORT={config.get('SMTP_PORT', '587')}",
                f"SMTP_USERNAME={config.get('SMTP_USERNAME', '')}",
                f"SMTP_PASSWORD={config.get('SMTP_PASSWORD', '')}",
                f"ALERT_EMAIL_FROM={config.get('ALERT_EMAIL_FROM', '')}",
                f"ALERT_EMAIL_TO={config.get('ALERT_EMAIL_TO', '')}",
            ])
        
        # Add optional monitoring
        if config.get('MONITORING_WEBHOOK_URL'):
            content.extend([
                "",
                "# =============================================================================",
                "# MONITORING",
                "# =============================================================================",
                f"MONITORING_WEBHOOK_URL={config.get('MONITORING_WEBHOOK_URL', '')}",
            ])
        
        return "\n".join(content) + "\n"
    
    def _set_secure_permissions(self):
        """Set secure file permissions."""
        try:
            # Set file permissions to 600 (owner read/write only)
            os.chmod(self.env_file, 0o600)
            print(f"Set secure permissions (600) on {self.env_file}")
        except Exception as e:
            print(f"⚠️  Warning: Could not set file permissions: {e}")
            print("Please manually set secure permissions on the environment file.")
    
    def _display_security_recommendations(self):
        """Display security recommendations."""
        print("\n🛡️  Security Recommendations")
        print("=" * 30)
        print("1. 🔒 Keep the .env.production file secure:")
        print("   - Never commit to version control")
        print("   - Restrict file permissions (chmod 600)")
        print("   - Store secure backups")
        print("\n2. 🔄 Rotate secrets regularly:")
        print("   - Change SECRET_KEY periodically")
        print("   - Rotate API keys as recommended by providers")
        print("   - Update database passwords regularly")
        print("\n3. 🌐 Production deployment:")
        print("   - Use HTTPS in production")
        print("   - Enable security headers")
        print("   - Configure proper firewall rules")
        print("   - Monitor for security incidents")
        print("\n4. 📊 Monitoring:")
        print("   - Set up log monitoring")
        print("   - Configure security alerts")
        print("   - Regular security audits")
    
    def _generate_secret_key(self, length: int = 64) -> str:
        """Generate a secure secret key."""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    def _validate_database_url(self, url: str) -> bool:
        """Validate database URL format."""
        # Basic validation for common database URL formats
        patterns = [
            r'^postgresql://[^:]+:[^@]+@[^:]+:\d+/\w+$',
            r'^mysql://[^:]+:[^@]+@[^:]+:\d+/\w+$',
            r'^sqlite:///.*\.db$',
        ]
        return any(re.match(pattern, url) for pattern in patterns)
    
    def _validate_email(self, email: str) -> bool:
        """Validate email address format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
    
    def _confirm(self, message: str) -> bool:
        """Get user confirmation."""
        while True:
            response = input(f"{message} (y/n): ").lower().strip()
            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no']:
                return False
            else:
                print("Please enter 'y' or 'n'")

def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Setup production environment')
    parser.add_argument('--non-interactive', action='store_true',
                       help='Run in non-interactive mode')
    parser.add_argument('--project-root', type=str,
                       help='Project root directory')
    
    args = parser.parse_args()
    
    setup = ProductionEnvSetup(args.project_root)
    
    try:
        success = setup.setup(interactive=not args.non_interactive)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()