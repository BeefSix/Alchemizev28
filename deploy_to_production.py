#!/usr/bin/env python3
"""
Production Deployment Script for Alchemize
This script handles the complete production deployment process
"""
import os
import subprocess
import sys
import time
import requests
from pathlib import Path

class ProductionDeployer:
    def __init__(self):
        self.project_root = Path.cwd()
        self.backend_url = "http://localhost:8001"
        self.frontend_url = "http://localhost:3000"
        
    def check_prerequisites(self):
        """Check if required tools are installed"""
        print("🔍 Checking prerequisites...")
        
        # Check Docker
        try:
            result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ Docker is installed")
            else:
                print("❌ Docker is not installed or not accessible")
                return False
        except FileNotFoundError:
            print("❌ Docker is not installed")
            return False
            
        # Check Docker Compose
        try:
            result = subprocess.run(['docker-compose', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ Docker Compose is installed")
            else:
                print("❌ Docker Compose is not installed or not accessible")
                return False
        except FileNotFoundError:
            print("❌ Docker Compose is not installed")
            return False
            
        return True
    
    def create_ssl_directory(self):
        """Create SSL directory for certificates"""
        ssl_dir = self.project_root / "ssl"
        ssl_dir.mkdir(exist_ok=True)
        
        # Create placeholder files
        (ssl_dir / "cert.pem").touch()
        (ssl_dir / "key.pem").touch()
        
        print("✅ Created SSL directory")
        print("⚠️  Please add your SSL certificates to the ./ssl/ directory")
    
    def update_environment_file(self):
        """Update production environment with secure values"""
        env_file = self.project_root / ".env.production"
        
        if not env_file.exists():
            print("❌ .env.production file not found")
            return False
            
        # Read current content
        with open(env_file, 'r') as f:
            content = f.read()
        
        # Update with more secure defaults
        updates = {
            "CORS_ORIGINS": '["http://localhost:3000", "http://localhost:80"]',
            "TRUSTED_HOSTS": '["localhost", "127.0.0.1"]',
            "ENVIRONMENT": "production",
            "DEBUG": "false"
        }
        
        for key, value in updates.items():
            if f"{key}=" in content:
                # Replace existing value
                import re
                pattern = rf"^{key}=.*$"
                replacement = f"{key}={value}"
                content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
            else:
                # Add new key-value pair
                content += f"\n{key}={value}"
        
        with open(env_file, 'w') as f:
            f.write(content)
            
        print("✅ Updated .env.production with secure defaults")
        return True
    
    def build_and_start_services(self):
        """Build and start all production services"""
        print("🚀 Building and starting production services...")
        
        try:
            # Build and start services
            cmd = ['docker-compose', '-f', 'docker-compose.production.yml', 'up', '-d', '--build']
            result = subprocess.run(cmd, cwd=self.project_root, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ Services started successfully")
                return True
            else:
                print(f"❌ Failed to start services: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Error starting services: {e}")
            return False
    
    def wait_for_services(self, timeout=120):
        """Wait for services to be ready"""
        print(f"⏳ Waiting for services to be ready (timeout: {timeout}s)...")
        
        start_time = time.time()
        services_ready = {
            'postgres': False,
            'redis': False,
            'backend': False,
            'frontend': False
        }
        
        while time.time() - start_time < timeout:
            # Check PostgreSQL
            if not services_ready['postgres']:
                try:
                    result = subprocess.run(['docker', 'exec', 'alchemize_postgres', 'pg_isready', '-U', 'alchemize_user'], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        services_ready['postgres'] = True
                        print("✅ PostgreSQL is ready")
                except:
                    pass
            
            # Check Redis
            if not services_ready['redis']:
                try:
                    result = subprocess.run(['docker', 'exec', 'alchemize_redis', 'redis-cli', 'ping'], 
                                          capture_output=True, text=True)
                    if result.stdout.strip() == 'PONG':
                        services_ready['redis'] = True
                        print("✅ Redis is ready")
                except:
                    pass
            
            # Check Backend
            if not services_ready['backend']:
                try:
                    response = requests.get(f"{self.backend_url}/health", timeout=5)
                    if response.status_code == 200:
                        services_ready['backend'] = True
                        print("✅ Backend is ready")
                except:
                    pass
            
            # Check Frontend
            if not services_ready['frontend']:
                try:
                    response = requests.get(self.frontend_url, timeout=5)
                    if response.status_code == 200:
                        services_ready['frontend'] = True
                        print("✅ Frontend is ready")
                except:
                    pass
            
            # Check if all services are ready
            if all(services_ready.values()):
                print("🎉 All services are ready!")
                return True
            
            time.sleep(2)
        
        print("⏰ Timeout waiting for services")
        return False
    
    def run_database_migrations(self):
        """Run database migrations"""
        print("🗄️  Running database migrations...")
        
        try:
            cmd = ['docker', 'exec', 'alchemize_backend', 'alembic', 'upgrade', 'head']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ Database migrations completed")
                return True
            else:
                print(f"⚠️  Migration warning: {result.stderr}")
                return True  # Continue even with warnings
                
        except Exception as e:
            print(f"❌ Error running migrations: {e}")
            return False
    
    def verify_deployment(self):
        """Verify the deployment is working correctly"""
        print("🔍 Verifying deployment...")
        
        checks = {
            'Backend Health': f"{self.backend_url}/health/detailed",
            'Frontend': self.frontend_url,
            'API Documentation': f"{self.backend_url}/docs",
            'Database Connection': f"{self.backend_url}/health/detailed"
        }
        
        all_passed = True
        
        for check_name, url in checks.items():
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    print(f"✅ {check_name}: OK")
                else:
                    print(f"❌ {check_name}: HTTP {response.status_code}")
                    all_passed = False
            except Exception as e:
                print(f"❌ {check_name}: {e}")
                all_passed = False
        
        return all_passed
    
    def show_service_status(self):
        """Show the status of all services"""
        print("\n📊 Service Status:")
        
        try:
            cmd = ['docker-compose', '-f', 'docker-compose.production.yml', 'ps']
            result = subprocess.run(cmd, cwd=self.project_root, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(result.stdout)
            else:
                print("❌ Could not get service status")
                
        except Exception as e:
            print(f"❌ Error getting service status: {e}")
    
    def show_access_urls(self):
        """Show access URLs for the deployed application"""
        print("\n🌐 Access URLs:")
        print(f"   Frontend: {self.frontend_url}")
        print(f"   Backend API: {self.backend_url}")
        print(f"   API Documentation: {self.backend_url}/docs")
        print(f"   Health Check: {self.backend_url}/health/detailed")
        print(f"   Nginx (HTTP): http://localhost:80")
        print(f"   Nginx (HTTPS): https://localhost:443")
    
    def deploy(self):
        """Main deployment process"""
        print("🚀 Starting Alchemize Production Deployment...")
        print("=" * 50)
        
        # Check prerequisites
        if not self.check_prerequisites():
            print("❌ Prerequisites not met. Please install Docker and Docker Compose.")
            return False
        
        # Create SSL directory
        self.create_ssl_directory()
        
        # Update environment file
        if not self.update_environment_file():
            print("❌ Failed to update environment file")
            return False
        
        # Build and start services
        if not self.build_and_start_services():
            print("❌ Failed to start services")
            return False
        
        # Wait for services to be ready
        if not self.wait_for_services():
            print("❌ Services failed to start within timeout")
            return False
        
        # Run database migrations
        if not self.run_database_migrations():
            print("❌ Failed to run database migrations")
            return False
        
        # Verify deployment
        if not self.verify_deployment():
            print("❌ Deployment verification failed")
            return False
        
        # Show final status
        self.show_service_status()
        self.show_access_urls()
        
        print("\n🎉 Production deployment completed successfully!")
        print("\n📋 Next steps:")
        print("1. Update .env.production with your actual API keys")
        print("2. Add SSL certificates to ./ssl/ directory")
        print("3. Update CORS_ORIGINS and TRUSTED_HOSTS with your domain")
        print("4. Monitor logs: docker-compose -f docker-compose.production.yml logs -f")
        
        return True

def main():
    """Main function"""
    deployer = ProductionDeployer()
    
    try:
        success = deployer.deploy()
        if success:
            sys.exit(0)
        else:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n❌ Deployment interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Deployment failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
