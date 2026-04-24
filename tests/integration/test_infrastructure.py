"""
Integration test for infrastructure modules.
Test LanceDB, Message Queue, and GPU Manager initialization.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.configs import get_config
from src.utils import (
    get_logger,
    get_lancedb_manager,
    get_gpu_manager,
    MessageQueue,
)


def test_lancedb_initialization():
    """Test LanceDB manager initialization."""
    logger = get_logger("test_lancedb")
    logger.info("Testing LanceDB initialization...")

    try:
        manager = get_lancedb_manager()
        if manager.is_connected():
            logger.info("✓ LanceDB connected successfully")
            tables = manager.list_tables()
            logger.info(f"✓ Available tables: {tables}")
            return True
        else:
            logger.warning("⚠ LanceDB not connected (lancedb package may not be installed)")
            return False
    except Exception as e:
        logger.error(f"✗ LanceDB initialization failed: {e}")
        return False


def test_gpu_manager():
    """Test GPU resource manager."""
    logger = get_logger("test_gpu")
    logger.info("Testing GPU manager...")

    try:
        gpu_mgr = get_gpu_manager()
        status = gpu_mgr.status()

        logger.info(f"GPU Status:")
        for key, value in status.items():
            logger.info(f"  {key}: {value}")

        if gpu_mgr.is_available():
            logger.info("✓ GPU is available")
            return True
        else:
            logger.warning("⚠ GPU not available (PyTorch may not be installed or CUDA not available)")
            return False

    except Exception as e:
        logger.error(f"✗ GPU manager initialization failed: {e}")
        return False


def test_message_queue():
    """Test message queue factory."""
    logger = get_logger("test_mq")
    logger.info("Testing message queue factory...")

    try:
        # Test RabbitMQ creation
        mq_rabbit = MessageQueue.create("rabbitmq", host="localhost", port=5672)
        logger.info(f"✓ RabbitMQ manager created: {type(mq_rabbit).__name__}")

        # Test Kafka creation
        mq_kafka = MessageQueue.create("kafka", brokers="localhost:9092")
        logger.info(f"✓ Kafka manager created: {type(mq_kafka).__name__}")

        return True
    except Exception as e:
        logger.error(f"✗ Message queue initialization failed: {e}")
        return False


def test_configuration():
    """Test configuration system."""
    logger = get_logger("test_config")
    logger.info("Testing configuration system...")

    try:
        config = get_config()

        logger.info(f"Configuration loaded:")
        logger.info(f"  Environment: {config.system.python_env}")
        logger.info(f"  Log Level: {config.system.log_level}")
        logger.info(f"  GPU Device: {config.gpu.device}")
        logger.info(f"  LanceDB Path: {config.database.lancedb_path}")
        logger.info(f"  RabbitMQ Host: {config.message_queue.rabbitmq_host}")

        return True
    except Exception as e:
        logger.error(f"✗ Configuration test failed: {e}")
        return False


def main():
    """Run all infrastructure tests."""
    logger = get_logger("infrastructure_test")
    logger.info("=" * 80)
    logger.info("DRL Infrastructure Integration Test")
    logger.info("=" * 80)

    results = {
        "Configuration": test_configuration(),
        "LanceDB": test_lancedb_initialization(),
        "GPU Manager": test_gpu_manager(),
        "Message Queue": test_message_queue(),
    }

    logger.info("\n" + "=" * 80)
    logger.info("Test Summary:")
    logger.info("=" * 80)

    passed = 0
    for test_name, result in results.items():
        status = "PASS ✓" if result else "FAIL ✗"
        logger.info(f"  {test_name:20s}: {status}")
        if result:
            passed += 1

    logger.info("=" * 80)
    logger.info(f"Results: {passed}/{len(results)} tests passed")
    logger.info("=" * 80)

    return passed == len(results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
