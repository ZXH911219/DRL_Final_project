"""
MLOps, Caching, and Experiment Tracking Manager.
Satisfies Tasks 20 (Caching), 24 (Monitoring), and 25 (Experiment Tracking).
"""

import os
import time
import json
import logging
from typing import Any, Dict, Optional
from pathlib import Path

try:
    import mlflow
except ImportError:
    mlflow = None

import redis

logger = logging.getLogger(__name__)

class MLOpsManager:
    """Handles Redis Caching and MLflow Experiment Tracking."""

    def __init__(self, use_redis: bool = False, redis_url: str = "redis://localhost:6379/0"):
        self.use_redis = use_redis
        self.redis_client = None
        if self.use_redis:
            try:
                self.redis_client = redis.StrictRedis.from_url(redis_url, decode_responses=True)
                self.redis_client.ping()
                logger.info("Connected to Redis cache successfully.")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis, falling back to in-memory cache. Error: {e}")
                self.redis_client = None
        
        self.local_cache = {}

        # MLflow setup
        self.mlflow_enabled = mlflow is not None
        if self.mlflow_enabled:
            os.environ["MLFLOW_TRACKING_URI"] = "file:./mlruns"
            mlflow.set_tracking_uri("file:./mlruns")
            mlflow.set_experiment("DRL_PPT_Retrieval")
            logger.info("MLflow tracking initialized.")
        else:
            logger.warning("MLflow not installed. Experiment tracking disabled.")

    def get_cache(self, key: str) -> Optional[Any]:
        """Fetch result from cache."""
        if self.redis_client:
            val = self.redis_client.get(key)
            return json.loads(val) if val else None
        return self.local_cache.get(key)

    def set_cache(self, key: str, value: Any, expire_seconds: int = 3600):
        """Set result to cache."""
        if self.redis_client:
            self.redis_client.setex(key, expire_seconds, json.dumps(value))
        else:
            self.local_cache[key] = value
            
    def log_inference_metrics(self, model_name: str, latency_ms: float, confidence_score: float = None):
        """Log inference performance metrics to MLflow."""
        if not self.mlflow_enabled:
            return

        try:
            with mlflow.start_run(nested=True):
                mlflow.log_param("model_name", model_name)
                mlflow.log_metric("latency_ms", latency_ms)
                if confidence_score is not None:
                    mlflow.log_metric("confidence_score", confidence_score)
        except Exception as e:
            logger.error(f"Failed to log metrics to MLflow: {e}")

# Global singleton
mlops_manager = MLOpsManager()
