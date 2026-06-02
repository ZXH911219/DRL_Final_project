#!/bin/bash
# Docker compose stop script for DRL System

echo "Stopping DRL Multi-Agent System..."

# Stop and remove containers, networks, and volumes
docker-compose down -v

echo "All containers stopped and volumes removed."
echo ""
echo "To restart, run:"
echo "  bash docker/start.sh"
echo ""
