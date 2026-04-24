"""
Message Queue Communication Module
Support for RabbitMQ and Kafka async messaging.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional
import json


class MessageQueueBase(ABC):
    """Abstract base for message queue implementations."""

    @abstractmethod
    def connect(self) -> bool:
        """Connect to message queue."""
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from message queue."""
        pass

    @abstractmethod
    def publish(self, queue_name: str, message: Dict[str, Any]) -> bool:
        """Publish a message."""
        pass

    @abstractmethod
    def subscribe(self, queue_name: str, callback: Callable) -> bool:
        """Subscribe to a queue."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check connection status."""
        pass


class RabbitMQManager(MessageQueueBase):
    """RabbitMQ message queue manager."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5672,
        user: str = "guest",
        password: str = "guest",
        vhost: str = "/",
    ):
        """Initialize RabbitMQ manager."""
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.vhost = vhost
        self._connection = None
        self._channel = None

    def connect(self) -> bool:
        """Connect to RabbitMQ."""
        try:
            import pika

            credentials = pika.PlainCredentials(self.user, self.password)
            parameters = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                virtual_host=self.vhost,
                credentials=credentials,
            )
            self._connection = pika.BlockingConnection(parameters)
            self._channel = self._connection.channel()
            return True
        except ImportError:
            print("ERROR: pika (RabbitMQ) not installed. Run: pip install pika")
            return False
        except Exception as e:
            print(f"ERROR connecting to RabbitMQ: {e}")
            return False

    def disconnect(self) -> bool:
        """Disconnect from RabbitMQ."""
        try:
            if self._connection:
                self._connection.close()
            return True
        except Exception as e:
            print(f"ERROR disconnecting: {e}")
            return False

    def is_connected(self) -> bool:
        """Check connection status."""
        return self._connection is not None and not self._connection.is_closed

    def publish(self, queue_name: str, message: Dict[str, Any]) -> bool:
        """Publish a message to RabbitMQ."""
        try:
            if not self.is_connected():
                self.connect()

            # Declare queue
            self._channel.queue_declare(queue=queue_name, durable=True)

            # Publish message
            self._channel.basic_publish(
                exchange="",
                routing_key=queue_name,
                body=json.dumps(message),
                properties=__import__("pika").BasicProperties(delivery_mode=2),  # Persistent
            )
            return True
        except Exception as e:
            print(f"ERROR publishing to RabbitMQ: {e}")
            return False

    def subscribe(self, queue_name: str, callback: Callable) -> bool:
        """Subscribe to a RabbitMQ queue."""
        try:
            if not self.is_connected():
                self.connect()

            # Declare queue
            self._channel.queue_declare(queue=queue_name, durable=True)

            def message_callback(ch, method, properties, body):
                message = json.loads(body)
                callback(message)
                ch.basic_ack(delivery_tag=method.delivery_tag)

            self._channel.basic_consume(queue=queue_name, on_message_callback=message_callback)
            self._channel.start_consuming()
            return True
        except Exception as e:
            print(f"ERROR subscribing to RabbitMQ: {e}")
            return False


class KafkaManager(MessageQueueBase):
    """Kafka message queue manager."""

    def __init__(self, brokers: str = "localhost:9092"):
        """Initialize Kafka manager."""
        self.brokers = brokers.split(",")
        self._producer = None
        self._consumer = None

    def connect(self) -> bool:
        """Connect to Kafka."""
        try:
            from kafka import KafkaProducer

            self._producer = KafkaProducer(
                bootstrap_servers=self.brokers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            return True
        except ImportError:
            print("ERROR: kafka-python not installed. Run: pip install kafka-python")
            return False
        except Exception as e:
            print(f"ERROR connecting to Kafka: {e}")
            return False

    def disconnect(self) -> bool:
        """Disconnect from Kafka."""
        try:
            if self._producer:
                self._producer.close()
            return True
        except Exception as e:
            print(f"ERROR disconnecting: {e}")
            return False

    def is_connected(self) -> bool:
        """Check connection status."""
        return self._producer is not None

    def publish(self, topic: str, message: Dict[str, Any]) -> bool:
        """Publish a message to Kafka."""
        try:
            if not self.is_connected():
                self.connect()

            self._producer.send(topic, value=message)
            return True
        except Exception as e:
            print(f"ERROR publishing to Kafka: {e}")
            return False

    def subscribe(self, topic: str, callback: Callable) -> bool:
        """Subscribe to a Kafka topic."""
        try:
            from kafka import KafkaConsumer

            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=self.brokers,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            )

            for message in consumer:
                callback(message.value)

            return True
        except Exception as e:
            print(f"ERROR subscribing to Kafka: {e}")
            return False


class MessageQueue:
    """Factory for message queue implementations."""

    @staticmethod
    def create(
        mq_type: str = "rabbitmq",
        **kwargs,
    ) -> MessageQueueBase:
        """Create message queue instance."""
        if mq_type.lower() == "rabbitmq":
            return RabbitMQManager(**kwargs)
        elif mq_type.lower() == "kafka":
            return KafkaManager(**kwargs)
        else:
            raise ValueError(f"Unknown message queue type: {mq_type}")
