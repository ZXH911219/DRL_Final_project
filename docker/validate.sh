#!/bin/bash
# Docker configuration validation script

echo "=========================================="
echo "Validating Docker Configuration"
echo "=========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "ERROR: Docker Compose is not installed"
    exit 1
fi

echo "✓ Docker version: $(docker --version)"
echo "✓ Docker Compose version: $(docker-compose --version)"
echo ""

# Check if required files exist
echo "Checking required files..."

required_files=(
    "Dockerfile"
    "docker-compose-new.yml"
    "requirements.txt"
    "docker/prometheus.yml"
    "docker/start.sh"
    "docker/stop.sh"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo "✓ $file"
    else
        echo "✗ Missing: $file"
        exit 1
    fi
done

echo ""
echo "Validating docker-compose.yml..."

# Validate docker-compose file
if docker-compose -f docker-compose-new.yml config > /dev/null 2>&1; then
    echo "✓ docker-compose.yml is valid"
else
    echo "✗ docker-compose.yml validation failed"
    docker-compose -f docker-compose-new.yml config
    exit 1
fi

echo ""
echo "Checking Dockerfile..."

# Basic Dockerfile validation
if grep -q "FROM python:3.10" Dockerfile && \
   grep -q "EXPOSE 8000" Dockerfile && \
   grep -q "HEALTHCHECK" Dockerfile; then
    echo "✓ Dockerfile structure looks good"
else
    echo "✗ Dockerfile validation failed"
    exit 1
fi

echo ""
echo "=========================================="
echo "✓ All Docker configurations are valid!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Backup existing docker-compose.yml:"
echo "   mv docker-compose.yml docker-compose.yml.backup"
echo ""
echo "2. Deploy new configuration:"
echo "   mv docker-compose-new.yml docker-compose.yml"
echo ""
echo "3. Build and start services:"
echo "   bash docker/start.sh"
echo ""
