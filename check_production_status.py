#!/usr/bin/env python3
"""Production Status Checker for Alchemize"""

import os
import sys
import subprocess
import requests
import time
import json
from typing import Dict, List, Tuple
from dataclasses import dataclass

@dataclass
class ServiceStatus:
    name: str
    status: str  # "running", "stopped", "error"
    details: str
    port: int = None
    url: str = None

class ProductionChecker:
    def __init__(self):
        self.services = []
        self.gpu_status = None
        self.dependencies_status = {}
    
    def check_all(self) -> Dict:
        """Run comprehensive production readiness check"""
        print("🔍 Alchemize Production Status Check")
        print("=" * 50)
        
        # Check dependencies
        self.check_dependencies()
        
        # Check GPU
        self.check_gpu()
        
        # Check services
        self.check_services()
        
        # Check configuration
        self.check_configuration()
        
        # Generate report
        return self.generate_report()
    
    def check_dependencies(self):
        """Check critical dependencies"""
        print("\n📦 Checking Dependencies...")
        
        deps = {
            "python": ["python", "--version"],
            "ffmpeg": ["ffmpeg", "-version"],
            "redis": ["redis-server", "--version"],
            "pip": ["pip", "--version"]
        }
        
        for name, cmd in deps.items():
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    version = result.stdout.split('\n')[0] if result.stdout else "Unknown version"
                    self.dependencies_status[name] = {"status": "✅", "version": version}
                    print(f"  {name}: ✅ {version}")
                else:
                    self.dependencies_status[name] = {"status": "❌", "error": result.stderr}
                    print(f"  {name}: ❌ Not working")
            except (FileNotFoundError, subprocess.TimeoutExpired):
                self.dependencies_status[name] = {"status": "❌", "error": "Not found"}
                print(f"  {name}: ❌ Not installed")
        
        # Check Python packages
        critical_packages = [
            "fastapi", "streamlit", "celery", "redis", "torch", 
            "python-magic-bin", "nvidia-ml-py3"
        ]
        
        print("\n📚 Checking Python Packages...")
        for package in critical_packages:
            try:
                result = subprocess.run(["pip", "show", package], capture_output=True, text=True)
                if result.returncode == 0:
                    version_line = [line for line in result.stdout.split('\n') if line.startswith('Version:')]
                    version = version_line[0].split(': ')[1] if version_line else "Unknown"
                    print(f"  {package}: ✅ v{version}")
                else:
                    print(f"  {package}: ❌ Not installed")
            except Exception:
                print(f"  {package}: ❌ Check failed")
    
    def check_gpu(self):
        """Check GPU status and capabilities"""
        print("\n🎮 Checking GPU Status...")
        
        try:
            # Try to import and use the GPU manager
            sys.path.append(os.getcwd())
            from app.services.gpu_manager import get_gpu_manager
            
            gpu_manager = get_gpu_manager()
            
            if gpu_manager.is_gpu_available():
                gpu_info = gpu_manager.gpu_info
                config = gpu_manager.get_processing_config()
                
                print(f"  GPU: ✅ {gpu_info.name}")
                print(f"  VRAM: ✅ {gpu_info.memory_total}MB total, {gpu_info.memory_free}MB free")
                print(f"  CUDA: ✅ Available" if gpu_info.cuda_available else "  CUDA: ❌ Not available")
                print(f"  Processing Mode: {config.get('processing_method', 'Unknown')}")
                print(f"  Parallel Encoding: {'✅' if config.get('parallel_encode') else '❌'}")
                
                # Monitor current usage
                usage = gpu_manager.monitor_gpu_usage()
                print(f"  Current Usage: {usage.get('gpu_utilization', 0)}% GPU, {usage.get('memory_used_percent', 0):.1f}% VRAM")
                print(f"  Temperature: {usage.get('temperature', 0)}°C")
                
                self.gpu_status = "available"
            else:
                print("  GPU: ❌ Not available or not detected")
                self.gpu_status = "unavailable"
                
        except ImportError as e:
            print(f"  GPU Manager: ❌ Import failed - {e}")
            self.gpu_status = "error"
        except Exception as e:
            print(f"  GPU Check: ❌ Failed - {e}")
            self.gpu_status = "error"
    
    def check_services(self):
        """Check if services are running"""
        print("\n🔧 Checking Services...")
        
        services_to_check = [
            {"name": "Redis", "url": "redis://localhost:6379", "port": 6379},
            {"name": "Backend API", "url": "http://localhost:8000/health", "port": 8000},
            {"name": "Frontend", "url": "http://localhost:8501", "port": 8501}
        ]
        
        for service in services_to_check:
            status = self.check_service_health(service)
            self.services.append(status)
            
            status_icon = "✅" if status.status == "running" else "❌"
            print(f"  {service['name']}: {status_icon} {status.details}")
    
    def check_service_health(self, service: Dict) -> ServiceStatus:
        """Check individual service health"""
        name = service["name"]
        url = service["url"]
        port = service["port"]
        
        try:
            if "redis://" in url:
                # Check Redis
                import redis
                r = redis.Redis(host='localhost', port=port, decode_responses=True)
                r.ping()
                return ServiceStatus(name, "running", f"Connected on port {port}", port, url)
            else:
                # Check HTTP services
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    return ServiceStatus(name, "running", f"Responding on port {port}", port, url)
                else:
                    return ServiceStatus(name, "error", f"HTTP {response.status_code}", port, url)
                    
        except requests.exceptions.ConnectionError:
            return ServiceStatus(name, "stopped", f"Not responding on port {port}", port, url)
        except Exception as e:
            return ServiceStatus(name, "error", f"Error: {str(e)}", port, url)
    
    def check_configuration(self):
        """Check configuration files"""
        print("\n⚙️ Checking Configuration...")
        
        # Check .env file
        if os.path.exists(".env"):
            print("  .env file: ✅ Found")
            
            # Check critical environment variables
            with open(".env", "r") as f:
                env_content = f.read()
                
            critical_vars = [
                "OPENAI_API_KEY", "SECRET_KEY", "DATABASE_URL", 
                "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"
            ]
            
            for var in critical_vars:
                if var in env_content and not env_content.split(f"{var}=")[1].split("\n")[0].strip() == "":
                    print(f"    {var}: ✅ Set")
                else:
                    print(f"    {var}: ❌ Missing or empty")
        else:
            print("  .env file: ❌ Not found")
        
        # Check startup scripts
        startup_scripts = [
            "start_production.bat", "start_redis.bat", 
            "start_backend.bat", "start_worker.bat", "start_frontend.bat"
        ]
        
        for script in startup_scripts:
            if os.path.exists(script):
                print(f"  {script}: ✅ Available")
            else:
                print(f"  {script}: ❌ Missing")
    
    def generate_report(self) -> Dict:
        """Generate comprehensive status report"""
        print("\n" + "=" * 50)
        print("📊 PRODUCTION READINESS REPORT")
        print("=" * 50)
        
        # Overall status
        running_services = len([s for s in self.services if s.status == "running"])
        total_services = len(self.services)
        
        gpu_ready = self.gpu_status == "available"
        services_ready = running_services >= 2  # At least backend and frontend
        
        overall_status = "🟢 READY" if (gpu_ready and services_ready) else "🟡 PARTIAL" if services_ready else "🔴 NOT READY"
        
        print(f"\nOverall Status: {overall_status}")
        print(f"Services Running: {running_services}/{total_services}")
        print(f"GPU Acceleration: {'✅ Available' if gpu_ready else '❌ Unavailable'}")
        
        # Recommendations
        print("\n🎯 RECOMMENDATIONS:")
        
        if not gpu_ready:
            print("  • Install NVIDIA drivers and CUDA toolkit")
            print("  • Run: pip install nvidia-ml-py3")
            print("  • Verify GPU with: nvidia-smi")
        
        if running_services < total_services:
            print("  • Start missing services using start_production.bat")
            print("  • Check service logs for errors")
        
        if running_services == 0:
            print("  • Run setup_production.ps1 first")
            print("  • Install missing dependencies")
        
        if gpu_ready and services_ready:
            print("  • ✅ System is production ready!")
            print("  • Upload a test video to verify GPU acceleration")
            print("  • Monitor GPU usage during processing")
        
        # Next steps
        print("\n🚀 NEXT STEPS:")
        print("  1. Fix any ❌ issues above")
        print("  2. Run start_production.bat to start all services")
        print("  3. Open http://localhost:8501 in browser")
        print("  4. Test video upload and Magic Editor")
        
        return {
            "overall_status": overall_status,
            "gpu_ready": gpu_ready,
            "services_ready": services_ready,
            "running_services": running_services,
            "total_services": total_services,
            "gpu_status": self.gpu_status,
            "services": [s.__dict__ for s in self.services],
            "dependencies": self.dependencies_status
        }

if __name__ == "__main__":
    checker = ProductionChecker()
    report = checker.check_all()
    
    # Save report
    with open("production_status.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Detailed report saved to: production_status.json")