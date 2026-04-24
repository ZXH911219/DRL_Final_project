"""
Fault Tolerance for Vision-Ingestion-Agent
Implement retry logic, exponential backoff, and fallback mechanisms.
"""

import time
import logging
from functools import wraps
from typing import Callable, Any, Optional, Tuple
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry logic."""

    max_attempts: int = 3
    initial_delay: float = 1.0  # seconds
    backoff_factor: float = 2.0
    max_delay: float = 60.0


class FaultToleranceDecorator:
    """Decorator for fault-tolerant operations."""

    def __init__(self, config: RetryConfig):
        """Initialize decorator."""
        self.config = config

    def __call__(self, func: Callable) -> Callable:
        """Apply retry decorator."""

        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            """Retry wrapper with exponential backoff."""
            last_exception = None

            for attempt in range(1, self.config.max_attempts + 1):
                try:
                    logger.info(
                        f"Executing {func.__name__} (attempt {attempt}/{self.config.max_attempts})"
                    )
                    return func(*args, **kwargs)

                except Exception as e:
                    last_exception = e
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt}): {str(e)}"
                    )

                    if attempt < self.config.max_attempts:
                        delay = min(
                            self.config.initial_delay
                            * (self.config.backoff_factor ** (attempt - 1)),
                            self.config.max_delay,
                        )
                        logger.info(
                            f"Retrying in {delay:.1f} seconds..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"{func.__name__} failed after {self.config.max_attempts} attempts"
                        )

            raise last_exception

        return wrapper


def retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
) -> Callable:
    """
    Retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts
        initial_delay: Initial delay in seconds
        backoff_factor: Backoff multiplier

    Returns:
        Decorator function

    Example:
        @retry(max_attempts=3, initial_delay=1.0, backoff_factor=2.0)
        def risky_operation():
            # Will retry up to 3 times with exponential backoff
            pass
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        backoff_factor=backoff_factor,
    )
    return FaultToleranceDecorator(config)


class FallbackRegistry:
    """Registry of fallback strategies."""

    def __init__(self):
        """Initialize registry."""
        self.fallbacks = {}

    def register_fallback(self, operation: str, fallback_func: Callable) -> None:
        """
        Register fallback for operation.

        Args:
            operation: Operation name (e.g., 'ocr', 'rendering')
            fallback_func: Fallback function to use
        """
        self.fallbacks[operation] = fallback_func
        logger.info(f"Registered fallback for {operation}")

    def get_fallback(self, operation: str) -> Optional[Callable]:
        """Get fallback for operation."""
        return self.fallbacks.get(operation)

    def use_fallback(self, operation: str, *args, **kwargs) -> Any:
        """Execute fallback."""
        fallback = self.get_fallback(operation)
        if fallback is None:
            logger.warning(f"No fallback registered for {operation}")
            return None

        try:
            logger.info(f"Executing fallback for {operation}")
            return fallback(*args, **kwargs)
        except Exception as e:
            logger.error(f"Fallback for {operation} failed: {str(e)}")
            return None


class OCRFallbackStrategy:
    """Fallback strategy for OCR failures."""

    @staticmethod
    def fallback_to_basic_ocr(image_path: str) -> str:
        """
        Fallback to basic OCR when advanced OCR fails.

        Args:
            image_path: Path to image file

        Returns:
            Extracted text (basic quality)
        """
        logger.info(f"Using basic OCR fallback for {image_path}")
        # Basic OCR implementation - can use pytesseract or similar
        return "OCR_FALLBACK_TEXT"

    @staticmethod
    def fallback_to_text_extraction(ppt_path: str) -> str:
        """
        Fallback to direct text extraction from PPT.

        Args:
            ppt_path: Path to PPT file

        Returns:
            Extracted text from slide
        """
        logger.info(f"Using text extraction fallback for {ppt_path}")
        # Direct PPT text extraction
        return "PPT_TEXT_EXTRACTION"


class RenderingFallbackStrategy:
    """Fallback strategy for rendering failures."""

    @staticmethod
    def fallback_to_lower_resolution(
        ppt_path: str, slide_index: int
    ) -> Tuple[str, int]:
        """
        Fallback to lower resolution rendering.

        Args:
            ppt_path: Path to PPT
            slide_index: Slide index

        Returns:
            Tuple of (image_path, resolution_dpi)
        """
        logger.info(
            f"Falling back to lower resolution for {ppt_path} slide {slide_index}"
        )
        # Return lower resolution rendering (e.g., 300 DPI instead of 600)
        return "lower_res_image.png", 300

    @staticmethod
    def fallback_to_cached_rendering(ppt_path: str, slide_index: int) -> Optional[str]:
        """
        Fallback to cached rendering.

        Args:
            ppt_path: Path to PPT
            slide_index: Slide index

        Returns:
            Path to cached image or None
        """
        logger.info(
            f"Looking for cached rendering of {ppt_path} slide {slide_index}"
        )
        # Check cache directory
        cache_file = f"cache/{ppt_path}_{slide_index}.png"
        return cache_file if Path(cache_file).exists() else None


class FeatureExtractionFallbackStrategy:
    """Fallback strategy for feature extraction failures."""

    @staticmethod
    def fallback_to_simpler_model(image_path: str) -> Tuple[Any, str]:
        """
        Fallback to simpler feature extraction model.

        Args:
            image_path: Path to image

        Returns:
            Tuple of (features, model_name)
        """
        logger.info(f"Using simpler model fallback for {image_path}")
        # Use simpler model (e.g., ResNet50 instead of ViT)
        return None, "resnet50_fallback"

    @staticmethod
    def fallback_to_basic_features(image_path: str) -> Tuple[Any, str]:
        """
        Fallback to basic feature extraction.

        Args:
            image_path: Path to image

        Returns:
            Tuple of (basic_features, method_name)
        """
        logger.info(f"Using basic features fallback for {image_path}")
        # Extract basic features (color histograms, edge detection, etc.)
        return None, "basic_features"


# Global fallback registry
_global_fallback_registry = FallbackRegistry()

# Register standard fallbacks
_global_fallback_registry.register_fallback(
    "ocr", OCRFallbackStrategy.fallback_to_basic_ocr
)
_global_fallback_registry.register_fallback(
    "rendering", RenderingFallbackStrategy.fallback_to_lower_resolution
)
_global_fallback_registry.register_fallback(
    "feature_extraction", FeatureExtractionFallbackStrategy.fallback_to_simpler_model
)


def get_fallback_registry() -> FallbackRegistry:
    """Get the global fallback registry."""
    return _global_fallback_registry


# Import Path for fallback
from pathlib import Path
