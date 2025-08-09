"""GPU Management and Acceleration Module for Zuexis"""

import os
import logging
import subprocess
from typing import Dict, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class GPUInfo:
    """GPU information container"""
    name: str
    memory_total: int  # MB
    memory_free: int   # MB
    utilization: int   # Percentage
    temperature: int   # Celsius
    cuda_available: bool
    compute_capability: Optional[str] = None

class GPUManager:
    """Manages GPU detection, monitoring, and optimization for video processing"""
    
    def __init__(self):
        self.gpu_info: Optional[GPUInfo] = None
        self.cuda_available = False
        self.optimal_settings = {}
        self._detect_gpu()
    
    def _detect_gpu(self) -> None:
        """Detect and configure GPU for optimal performance"""
        try:
            # Check for NVIDIA GPU using nvidia-ml-py3
            import pynvml
            pynvml.nvmlInit()
            
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > 0:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)  # Use first GPU
                
                # Get GPU information
                name = pynvml.nvmlDeviceGetName(handle).decode('utf-8')
                memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                
                # Check CUDA availability
                cuda_available = self._check_cuda()
                
                self.gpu_info = GPUInfo(
                    name=name,
                    memory_total=memory_info.total // 1024 // 1024,  # Convert to MB
                    memory_free=memory_info.free // 1024 // 1024,
                    utilization=utilization.gpu,
                    temperature=temperature,
                    cuda_available=cuda_available
                )
                
                # Configure optimal settings based on GPU
                self._configure_optimal_settings()
                
                logger.info(f"🎮 GPU Detected: {name}")
                logger.info(f"💾 VRAM: {self.gpu_info.memory_total}MB total, {self.gpu_info.memory_free}MB free")
                logger.info(f"🔥 Temperature: {temperature}°C")
                logger.info(f"⚡ CUDA Available: {cuda_available}")
                
        except ImportError:
            logger.warning("🔧 pynvml not available, installing...")
            try:
                subprocess.run(["pip", "install", "nvidia-ml-py3"], check=True, capture_output=True)
                self._detect_gpu()  # Retry after installation
            except Exception as e:
                logger.warning(f"⚠️ Could not install GPU monitoring: {e}")
                self._fallback_cpu_mode()
        except Exception as e:
            logger.warning(f"⚠️ GPU detection failed: {e}")
            self._fallback_cpu_mode()
    
    def _check_cuda(self) -> bool:
        """Check if CUDA is available and working"""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False
    
    def _configure_optimal_settings(self) -> None:
        """Configure optimal settings based on detected GPU"""
        if not self.gpu_info:
            return
        
        gpu_name = self.gpu_info.name.lower()
        memory_gb = self.gpu_info.memory_total / 1024
        
        # RTX 4080 specific optimizations
        if "rtx 4080" in gpu_name or "rtx 4090" in gpu_name:
            self.optimal_settings = {
                "parallel_encode": True,
                "max_concurrent_clips": 4,
                "gpu_memory_fraction": 0.8,
                "batch_size": 8,
                "encoder": "h264_nvenc",
                "decoder": "h264_cuvid",
                "processing_method": "rtx_4080_optimized",
                "enable_tensor_cores": True
            }
        elif "rtx" in gpu_name and memory_gb >= 8:
            self.optimal_settings = {
                "parallel_encode": True,
                "max_concurrent_clips": 3,
                "gpu_memory_fraction": 0.7,
                "batch_size": 6,
                "encoder": "h264_nvenc",
                "decoder": "h264_cuvid",
                "processing_method": "nvidia_optimized"
            }
        elif "gtx" in gpu_name or "rtx" in gpu_name:
            self.optimal_settings = {
                "parallel_encode": False,
                "max_concurrent_clips": 2,
                "gpu_memory_fraction": 0.6,
                "batch_size": 4,
                "encoder": "h264_nvenc",
                "processing_method": "nvidia_basic"
            }
        else:
            self._fallback_cpu_mode()
        
        logger.info(f"🚀 Configured for: {self.optimal_settings.get('processing_method', 'cpu')}")
    
    def _fallback_cpu_mode(self) -> None:
        """Configure CPU-only processing"""
        self.optimal_settings = {
            "parallel_encode": False,
            "max_concurrent_clips": 1,
            "batch_size": 2,
            "encoder": "libx264",
            "processing_method": "cpu_optimized"
        }
        logger.info("🔧 Configured for CPU-only processing")
    
    def get_ffmpeg_gpu_args(self) -> List[str]:
        """Get FFmpeg arguments for GPU acceleration"""
        if not self.gpu_info or not self.gpu_info.cuda_available:
            return []
        
        gpu_args = []
        
        # Hardware decoder
        if self.optimal_settings.get("decoder"):
            gpu_args.extend(["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"])
        
        return gpu_args
    
    def get_ffmpeg_encoder_args(self) -> List[str]:
        """Get FFmpeg encoder arguments for GPU"""
        encoder = self.optimal_settings.get("encoder", "libx264")
        
        if "nvenc" in encoder:
            return [
                "-c:v", encoder,
                "-preset", "p4",  # Fastest preset for RTX cards
                "-tune", "hq",   # High quality
                "-rc", "vbr",    # Variable bitrate
                "-cq", "23",     # Quality level
                "-b:v", "0",     # Let CQ control bitrate
                "-maxrate", "10M",
                "-bufsize", "20M"
            ]
        else:
            return ["-c:v", "libx264", "-preset", "fast", "-crf", "23"]
    
    def monitor_gpu_usage(self) -> Dict[str, float]:
        """Monitor current GPU usage"""
        if not self.gpu_info:
            return {"gpu_utilization": 0, "memory_used_percent": 0, "temperature": 0}
        
        try:
            import pynvml
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            
            memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
            temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            
            memory_used_percent = ((memory_info.total - memory_info.free) / memory_info.total) * 100
            
            return {
                "gpu_utilization": utilization.gpu,
                "memory_used_percent": memory_used_percent,
                "temperature": temperature,
                "memory_free_mb": memory_info.free // 1024 // 1024
            }
        except Exception as e:
            logger.warning(f"GPU monitoring failed: {e}")
            return {"gpu_utilization": 0, "memory_used_percent": 0, "temperature": 0}
    
    def is_gpu_available(self) -> bool:
        """Check if GPU is available for processing"""
        return self.gpu_info is not None and self.gpu_info.cuda_available
    
    def get_processing_config(self) -> Dict:
        """Get complete processing configuration"""
        config = self.optimal_settings.copy()
        config["gpu_available"] = self.is_gpu_available()
        config["gpu_info"] = self.gpu_info.__dict__ if self.gpu_info else None
        return config
    
    def log_system_info(self) -> None:
        """Log comprehensive system information"""
        logger.info("🖥️ System Configuration:")
        
        if self.gpu_info:
            logger.info(f"  GPU: {self.gpu_info.name}")
            logger.info(f"  VRAM: {self.gpu_info.memory_total}MB")
            logger.info(f"  CUDA: {self.gpu_info.cuda_available}")
            logger.info(f"  Processing: {self.optimal_settings.get('processing_method')}")
        else:
            logger.info("  GPU: Not detected or unavailable")
            logger.info("  Processing: CPU-only mode")
        
        # Check FFmpeg
        try:
            result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
            if "cuda" in result.stdout.lower():
                logger.info("  FFmpeg: CUDA support detected")
            else:
                logger.info("  FFmpeg: CPU-only version")
        except FileNotFoundError:
            logger.warning("  FFmpeg: Not found in PATH")

# Global GPU manager instance
gpu_manager = GPUManager()

def get_gpu_manager() -> GPUManager:
    """Get the global GPU manager instance"""
    return gpu_manager