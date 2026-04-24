"""
Structured logging configuration using Loguru.
"""

import sys
from pathlib import Path

from loguru import logger


def setup_logger(
    name: str,
    level: str = "INFO",
    log_dir: str = "./logs",
    format_type: str = "json",
) -> None:
    """
    Setup structured logging with Loguru.

    Args:
        name: Logger name/identifier
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory to store log files
        format_type: Log format ('json' or 'text')
    """
    # Remove default handler
    logger.remove()

    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Console format
    if format_type == "json":
        console_format = (
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )
    else:
        console_format = (
            "<level>{time:YYYY-MM-DD HH:mm:ss.SSS}</level> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )

    # Add console handler
    logger.add(
        sys.stdout,
        format=console_format,
        level=level,
        colorize=True,
    )

    # Add file handler
    log_file = log_path / f"{name}.log"
    logger.add(
        str(log_file),
        format=console_format,
        level=level,
        rotation="500 MB",
        retention="7 days",
        compression="zip",
    )

    logger.info(f"Logger '{name}' initialized - Level: {level}, Format: {format_type}")


def get_logger(name: str = "drl") -> logger:
    """
    Get logger instance for a module.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance configured via Loguru
    """
    return logger.bind(name=name)
