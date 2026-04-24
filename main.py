#!/usr/bin/env python
"""
DRL Multi-Agent PPT Retrieval System - Main Application Entry Point
"""

import sys
import argparse
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.configs import get_config, load_config
from src.utils import setup_logger, get_logger


def init_system():
    """Initialize system and load configuration."""
    config = get_config()
    setup_logger(
        name="drl_system",
        level=config.system.log_level,
        log_dir=config.system.log_output_dir,
        format_type=config.system.log_format,
    )
    logger = get_logger(__name__)
    logger.info(f"DRL System initialized in {config.system.python_env} mode")
    return config, logger


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="DRL Multi-Agent PPT Retrieval System",
        prog="drl",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to .env configuration file",
    )

    parser.add_argument(
        "--mode",
        choices=["development", "staging", "production"],
        default="development",
        help="System mode",
    )

    parser.add_argument(
        "command",
        nargs="?",
        choices=["init", "ingest", "retrieve", "reason", "verify", "serve"],
        default="serve",
        help="Command to run",
    )

    args = parser.parse_args()

    # Load custom config if provided
    if args.config:
        load_config(args.config)

    config, logger = init_system()

    logger.info(f"Command: {args.command}")
    logger.info(f"Configuration loaded from: {config.paths.project_root}")

    # Command handlers
    if args.command == "init":
        logger.info("Initializing system...")
        logger.info("Creating necessary directories...")
        config._ensure_directories()
        logger.info("System initialized successfully")

    elif args.command == "serve":
        logger.info("Starting Streamlit UI server...")
        logger.info("Server would run on http://localhost:8501")
        # TODO: Start Streamlit app

    elif args.command == "ingest":
        logger.info("Starting PPT ingestion pipeline...")
        # TODO: Run Vision-Ingestion-Agent

    elif args.command == "retrieve":
        logger.info("Starting retrieval mode (interactive)...")
        # TODO: Start interactive retrieval

    elif args.command == "reason":
        logger.info("Starting reasoning mode...")
        # TODO: Run Reasoning-Reranker-Agent

    elif args.command == "verify":
        logger.info("Starting verification mode...")
        # TODO: Run Argos-Verification-Agent

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
