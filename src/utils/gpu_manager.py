"""
GPU and Compute Resource Configuration
Manage PyTorch GPU allocation, batch processing, and memory optimization.
"""

import os
from typing import Dict, Optional

import numpy as np


class GPUResourceManager:
    """Manage GPU resources and compute allocation."""

    def __init__(self):
        """Initialize GPU resource manager."""
        self.pytorch_available = False
        self.torch = None
        self.cuda_available = False
        self.device_count = 0

        self._initialize()

    def _initialize(self):
        """Initialize GPU detection and configuration."""
        try:
            import torch

            self.torch = torch
            self.pytorch_available = True
            self.cuda_available = torch.cuda.is_available()
            self.device_count = torch.cuda.device_count() if self.cuda_available else 0

        except ImportError:
            print("WARNING: PyTorch not installed. GPU features disabled.")

    def is_available(self) -> bool:
        """Check if GPU is available."""
        return self.cuda_available and self.pytorch_available

    def get_device_count(self) -> int:
        """Get number of GPUs."""
        return self.device_count

    def get_device_name(self, device_id: int = 0) -> str:
        """Get GPU device name."""
        if not self.is_available():
            return "cpu"

        if device_id >= self.device_count:
            return "cpu"

        return self.torch.cuda.get_device_name(device_id)

    def get_device_memory(self, device_id: int = 0) -> Dict[str, float]:
        """Get GPU memory information (in GB)."""
        if not self.is_available():
            return {"total": 0, "allocated": 0, "reserved": 0, "free": 0}

        try:
            total = self.torch.cuda.get_device_properties(device_id).total_memory / 1e9
            allocated = self.torch.cuda.memory_allocated(device_id) / 1e9
            reserved = self.torch.cuda.memory_reserved(device_id) / 1e9
            free = total - allocated

            return {
                "total": total,
                "allocated": allocated,
                "reserved": reserved,
                "free": free,
            }
        except Exception as e:
            print(f"ERROR getting GPU memory: {e}")
            return {"total": 0, "allocated": 0, "reserved": 0, "free": 0}

    def get_device_utilization(self, device_id: int = 0) -> float:
        """Get GPU memory utilization percentage."""
        mem_info = self.get_device_memory(device_id)
        if mem_info["total"] == 0:
            return 0.0

        return (mem_info["allocated"] / mem_info["total"]) * 100

    def set_memory_fraction(self, fraction: float = 0.8, device_id: int = 0) -> bool:
        """Set memory fraction for GPU."""
        if not self.is_available():
            return False

        try:
            self.torch.cuda.set_per_process_memory_fraction(fraction, device=device_id)
            return True
        except Exception as e:
            print(f"ERROR setting memory fraction: {e}")
            return False

    def clear_cache(self, device_id: int = 0) -> bool:
        """Clear GPU cache."""
        if not self.is_available():
            return True

        try:
            self.torch.cuda.empty_cache()
            return True
        except Exception as e:
            print(f"ERROR clearing GPU cache: {e}")
            return False

    def get_optimal_batch_size(
        self,
        model_params: int,
        device_id: int = 0,
        utilization_target: float = 0.8,
    ) -> int:
        """Estimate optimal batch size for model."""
        if not self.is_available():
            return 1

        mem_info = self.get_device_memory(device_id)
        available_mem = mem_info["free"] * 1e9  # Convert to bytes

        # Rough estimation: 4 bytes per parameter + gradients (2x)
        bytes_per_sample = model_params * 4 * 2

        batch_size = max(1, int((available_mem * utilization_target) / bytes_per_sample))
        return batch_size

    def get_device_properties(self, device_id: int = 0) -> Dict[str, str]:
        """Get full GPU device properties."""
        if not self.is_available():
            return {"device": "cpu", "status": "GPU not available"}

        try:
            props = self.torch.cuda.get_device_properties(device_id)
            return {
                "name": props.name,
                "compute_capability": f"{props.major}.{props.minor}",
                "total_memory_gb": str(props.total_memory / 1e9),
                "max_threads_per_block": str(props.max_threads_per_block),
            }
        except Exception as e:
            print(f"ERROR getting device properties: {e}")
            return {}

    def status(self) -> Dict[str, str]:
        """Get GPU status summary."""
        if not self.is_available():
            return {
                "status": "No GPU available",
                "device": "CPU",
                "cuda_available": "False",
            }

        status = {
            "status": "GPU Available",
            "device_count": str(self.device_count),
            "cuda_version": self.torch.version.cuda if self.pytorch_available else "N/A",
        }

        for i in range(self.device_count):
            mem = self.get_device_memory(i)
            status[f"gpu_{i}_name"] = self.get_device_name(i)
            status[f"gpu_{i}_memory_gb"] = f"{mem['total']:.1f} (Free: {mem['free']:.1f})"
            status[f"gpu_{i}_utilization"] = f"{self.get_device_utilization(i):.1f}%"

        return status


# Global GPU manager instance
_gpu_manager: Optional[GPUResourceManager] = None


def get_gpu_manager() -> GPUResourceManager:
    """Get or create global GPU resource manager."""
    global _gpu_manager
    if _gpu_manager is None:
        _gpu_manager = GPUResourceManager()
    return _gpu_manager
