"""
Global configuration management for DRL Multi-Agent PPT Retrieval System.
Uses pydantic for validation and pydantic-settings for environment-based configuration.
"""

import os
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings


class GPUConfig(BaseSettings):
    """GPU and compute resource configuration."""

    device: Literal["cuda", "cpu"] = "cuda"
    cuda_visible_devices: Optional[str] = None
    batch_size_retrieval: int = 500
    batch_size_reasoning: int = 4
    batch_size_verification: int = 10
    pytorch_cuda_alloc_conf: str = "expandable_segments:True"

    class Config:
        env_prefix = "GPU_"


class ModelConfig(BaseSettings):
    """Model configuration."""

    colpali_model_name: str = "colpali-base"
    colpali_device: str = "cuda:0"
    imagebind_model: str = "imagebind_large"
    mm_r5_model_path: str = "./models/mm-r5-7b"
    mm_r5_device: str = "cuda:1"
    mm_r5_batch_size: int = 4

    class Config:
        env_prefix = "MODEL_"


class DatabaseConfig(BaseSettings):
    """Database configuration."""

    # LanceDB
    lancedb_path: str = "./data/vector_store/lancedb"
    lancedb_mode: Literal["local", "remote"] = "local"

    # PostgreSQL
    database_url: Optional[str] = None

    # Redis
    redis_url: str = "redis://localhost:6379"

    class Config:
        env_prefix = "DB_"


class MessageQueueConfig(BaseSettings):
    """Message queue configuration."""

    # RabbitMQ
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "guest"
    rabbitmq_password: str = "guest"
    rabbitmq_vhost: str = "/"

    # Kafka (alternative)
    kafka_brokers: str = "localhost:9092"

    class Config:
        env_prefix = "MQ_"


class APIConfig(BaseSettings):
    """API configuration."""

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    class Config:
        env_prefix = "API_"


class TimeoutConfig(BaseSettings):
    """Timeout configuration (in milliseconds)."""

    retrieval: int = 200
    reasoning: int = 30000
    verification: int = 2000

    class Config:
        env_prefix = "TIMEOUT_"


class SystemConfig(BaseSettings):
    """System-level configuration."""

    python_env: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "text"] = "json"
    log_output_dir: str = "./logs"

    # Feature flags
    enable_reasoning: bool = True
    enable_verification: bool = True
    enable_hybrid_retrieval: bool = True
    enable_diversity_ranking: bool = False

    class Config:
        env_prefix = "SYS_"


class PathConfig(BaseSettings):
    """Path configuration."""

    ppt_data_path: str = "./data/ppt_samples"
    vector_store_path: str = "./data/vector_store"
    model_cache_path: str = "./models"
    log_path: str = "./logs"

    # Computed paths
    project_root: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent)

    class Config:
        env_prefix = "PATH_"
        protected_namespaces = ("settings_",)  # Suppress pydantic namespace warning

    @validator("project_root", always=True)
    def set_project_root(cls, v):
        """Ensure project root is properly set."""
        if isinstance(v, str):
            return Path(v)
        return v if isinstance(v, Path) else Path(__file__).parent.parent.parent


class Config(BaseSettings):
    """
    Master configuration class combining all config sections.
    Loads from .env file and environment variables.
    """

    # Sections
    gpu: GPUConfig = Field(default_factory=GPUConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    message_queue: MessageQueueConfig = Field(default_factory=MessageQueueConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    timeout: TimeoutConfig = Field(default_factory=TimeoutConfig)
    system: SystemConfig = Field(default_factory=SystemConfig)
    paths: PathConfig = Field(default_factory=PathConfig)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def __init__(self, **data):
        """Initialize configuration from environment and .env file."""
        super().__init__(**data)
        # Create necessary directories
        self._ensure_directories()

    def _ensure_directories(self):
        """Ensure all required directories exist."""
        dirs = [
            self.paths.ppt_data_path,
            self.paths.vector_store_path,
            self.paths.model_cache_path,
            self.paths.log_path,
        ]
        for dir_path in dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def load_config(config_path: Optional[str] = None) -> "Config":
        """
        Load configuration from .env file or defaults.

        Args:
            config_path: Optional path to .env file

        Returns:
            Config instance
        """
        if config_path:
            os.environ["__CONFIG_PATH__"] = config_path

        return Config()


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create global config instance."""
    global _config
    if _config is None:
        _config = Config.load_config()
    return _config


def load_config(config_path: Optional[str] = None) -> Config:
    """Load and set global config instance."""
    global _config
    _config = Config.load_config(config_path)
    return _config
