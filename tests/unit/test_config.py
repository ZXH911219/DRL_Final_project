"""Unit tests for core configuration module."""

import pytest
from src.core.config import Settings, load_config


class TestSettings:
    """Test configuration settings."""
    
    def test_settings_load(self):
        """Test that settings load correctly."""
        settings = Settings()
        assert settings.environment in ["development", "staging", "production"]
        assert settings.log_level in ["DEBUG", "INFO", "WARNING", "ERROR"]
    
    def test_default_values(self):
        """Test default configuration values."""
        settings = Settings()
        assert settings.vision_batch_size == 4
        assert settings.colpali_vector_dim == 128
        assert settings.cuda_enabled is True
    
    def test_env_override(self, monkeypatch):
        """Test environment variable override."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DEBUG_MODE", "true")
        
        settings = Settings()
        assert settings.environment == "production"


class TestLoadConfig:
    """Test config file loading."""
    
    def test_load_yaml_config(self, tmp_path):
        """Test loading YAML config file."""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("""
vision_ingestion:
  batch_size: 8
  render_dpi: 1200
""")
        
        config = load_config(str(config_file))
        assert config["vision_ingestion"]["batch_size"] == 8


if __name__ == "__main__":
    pytest.main([__file__])
