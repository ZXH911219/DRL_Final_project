#!/bin/bash
# Docker compose start script for DRL System

set -e

echo "Starting DRL Multi-Agent System..."

# Create necessary directories
mkdir -p data logs models feature_bundles

# Build and start all services
echo "Building Docker images..."
docker-compose build --no-cache

echo "Starting all services..."
docker-compose up -d

echo "Waiting for services to be healthy..."
sleep 10

# Check service health
echo "Checking RabbitMQ health..."
docker-compose exec -T rabbitmq rabbitmq-diagnostics -q ping || echo "RabbitMQ not ready yet"

echo "Checking Redis health..."
docker-compose exec -T redis redis-cli ping || echo "Redis not ready yet"

echo "Checking PostgreSQL health..."
docker-compose exec -T postgres pg_isready -U drl_user || echo "PostgreSQL not ready yet"

echo "Checking API health..."
for i in {1..30}; do
    if curl -f http://localhost:8000/health 2>/dev/null; then
        echo "API is healthy!"
        break
    fi
    echo "Waiting for API to be ready ($i/30)..."
    sleep 2
done

echo ""
echo "=========================================="
echo "DRL Multi-Agent System Started!"
echo "=========================================="
echo ""
echo "Services available at:"
echo "  - API Server:         http://localhost:8000"
echo "  - API Docs:           http://localhost:8000/docs"
echo "  - RabbitMQ UI:        http://localhost:15672 (guest:guest)"
echo "  - Grafana:            http://localhost:3000 (admin:admin)"
echo "  - Prometheus:         http://localhost:9090"
echo "  - PostgreSQL:         localhost:5432 (drl_user:drl_password)"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f api"
echo ""
echo "To stop all services:"
echo "  docker-compose down"
echo ""
