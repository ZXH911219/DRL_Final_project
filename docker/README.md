# DRL Multi-Agent System - Docker Deployment Guide

This guide covers deployment of the DRL (Deep Reasoning Learning) Multi-Agent PPT Vision & Reasoning Retrieval System using Docker.

## System Architecture

```
┌─────────────────────────────────────┐
│   DRL API Server (FastAPI)          │
│   - Vision Ingestion Agent          │
│   - Lakehouse Retrieval Agent       │
│   - Reasoning Reranker Agent        │
│   - Argos Verification Agent        │
└─────────────────────────────────────┘
                 │
    ┌────────────┼────────────┐
    ▼            ▼            ▼
 PostgreSQL   Redis      RabbitMQ
 (Metadata)  (Cache)    (Messages)
    │            │            │
    └────────────┼────────────┘
                 │
         ┌───────┴────────┐
         ▼                ▼
      LanceDB        Prometheus/Grafana
    (Vectors)         (Monitoring)
```

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- Nvidia GPU (recommended, CPU fallback supported)
- Nvidia Docker Runtime (for GPU support)
- 32GB+ RAM
- 100GB+ disk space

## Quick Start

### 1. Validate Configuration

```bash
bash docker/validate.sh
```

This script checks:
- Docker installation
- docker-compose.yml syntax
- Required files presence
- Dockerfile structure

### 2. Build Docker Images

```bash
docker-compose -f docker-compose-new.yml build
```

Expected build time: ~15-30 minutes (depends on internet speed and system resources)

**Build Output Example:**
```
Building api
Step 1/15 : FROM python:3.10-slim as builder
Step 2/15 : WORKDIR /app
...
Successfully built [image-hash]
Successfully tagged drl-final-project-api:latest
```

### 3. Start All Services

```bash
bash docker/start.sh
```

This starts:
- **API Server** (8000): FastAPI application
- **RabbitMQ** (5672/15672): Message queue with management UI
- **Redis** (6379): Cache and session store
- **PostgreSQL** (5432): Metadata database
- **LanceDB** (8081): Vector database
- **Prometheus** (9090): Metrics collection
- **Grafana** (3000): Visualization dashboard

**Expected Output:**
```
========================================
DRL Multi-Agent System Started!
========================================

Services available at:
  - API Server:         http://localhost:8000
  - API Docs:           http://localhost:8000/docs
  - RabbitMQ UI:        http://localhost:15672 (guest:guest)
  - Grafana:            http://localhost:3000 (admin:admin)
  - Prometheus:         http://localhost:9090
  - PostgreSQL:         localhost:5432 (drl_user:drl_password)
```

### 4. Verify Service Health

```bash
# Check API health
curl http://localhost:8000/health

# Expected response:
# {
#   "status": "healthy",
#   "timestamp": "2024-04-17T10:30:00Z",
#   "services": {
#     "vision": "ready",
#     "reasoning": "ready",
#     "verification": "ready",
#     "database": "connected",
#     "cache": "connected"
#   }
# }

# View API documentation
open http://localhost:8000/docs
```

## Configuration

### Environment Variables

Create a `.env` file based on `.env.docker`:

```bash
cp .env.docker .env
```

Key configuration options:

```env
# API
API_WORKERS=4
DEVICE=cuda:0  # or cpu

# Database
DATABASE_URL=postgresql://drl_user:drl_password@postgres:5432/drl_ppt_db

# Model Configuration
VISION_MODEL=colpali
REASONING_MODEL=mm-r5
VERIFICATION_MODEL=argos

# Thresholds
HALLUCINATION_RISK_THRESHOLD=0.45
EVIDENCE_COVERAGE_THRESHOLD=0.88
```

### Docker Compose Customization

Edit `docker-compose.yml` to customize:

1. **Port Mappings**: Change exposed ports
2. **Resource Limits**: Adjust CPU/GPU allocation
3. **Volume Mounts**: Add persistent data paths
4. **Environment Variables**: Custom settings

Example - Limit API to 2 CPU cores:

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 16G
```

## Common Tasks

### View API Logs

```bash
# Real-time logs from API service
docker-compose logs -f api

# Last 100 lines
docker-compose logs --tail=100 api

# Logs from all services
docker-compose logs -f
```

### Access Service UIs

| Service | URL | Credentials |
|---------|-----|-------------|
| API Docs | http://localhost:8000/docs | None |
| RabbitMQ | http://localhost:15672 | guest:guest |
| Grafana | http://localhost:3000 | admin:admin |
| Prometheus | http://localhost:9090 | None |
| PostgreSQL | localhost:5432 | drl_user:drl_password |

### Execute Commands in Container

```bash
# Run Python script in API container
docker-compose exec api python -c "import torch; print(torch.cuda.is_available())"

# Access PostgreSQL CLI
docker-compose exec postgres psql -U drl_user -d drl_ppt_db

# Access Redis CLI
docker-compose exec redis redis-cli
```

### Scale Services

```bash
# Scale to 2 API instances (with load balancer)
docker-compose up -d --scale api=2
```

### Restart Services

```bash
# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart api

# Soft restart (graceful)
docker-compose restart -t 30 api
```

## Troubleshooting

### API Container Won't Start

**Issue**: Container exits immediately
**Solution**:
```bash
# Check logs
docker-compose logs api

# Verify GPU availability
docker run --rm --gpus all nvidia/cuda:11.8.0-runtime-ubuntu22.04 nvidia-smi

# Fall back to CPU
docker-compose exec api python -c "import torch; torch.cuda.is_available()" 
# Edit docker-compose.yml: DEVICE=cpu
```

### Database Connection Failed

**Issue**: PostgreSQL connection refused
**Solution**:
```bash
# Ensure PostgreSQL is healthy
docker-compose ps postgres

# Check logs
docker-compose logs postgres

# Verify connectivity
docker-compose exec api psql -h postgres -U drl_user -d drl_ppt_db -c "SELECT 1;"
```

### Out of Memory

**Issue**: Containers killed due to OOM
**Solution**:
```bash
# Check memory usage
docker stats

# Reduce batch sizes in .env
BATCH_SIZE=8

# Reduce model precision
MODEL_PRECISION=int8

# Limit container memory
docker-compose down
# Edit docker-compose.yml
services:
  api:
    deploy:
      resources:
        limits:
          memory: 24G
docker-compose up -d
```

### GPU Not Detected

**Issue**: CUDA not available in container
**Solution**:
```bash
# Verify Nvidia Docker runtime
docker run --rm --gpus all ubuntu nvidia-smi

# Explicit GPU configuration
docker-compose exec api python -c "import torch; print(torch.cuda.get_device_name(0))"

# Use CPU fallback
DEVICE=cpu
```

## Production Deployment

### Pre-deployment Checklist

- [ ] All tests pass (87/87)
- [ ] Docker images built successfully
- [ ] All services start without errors
- [ ] API health check returns 200
- [ ] PostgreSQL initialization complete
- [ ] Redis cache working
- [ ] LanceDB vector store accessible
- [ ] Prometheus metrics being collected
- [ ] Grafana dashboards configured

### Deployment Steps

1. **Backup Current Data**
   ```bash
   docker-compose down -v  # This REMOVES volumes!
   # Use instead:
   docker-compose exec postgres pg_dump -U drl_user drl_ppt_db > backup.sql
   ```

2. **Update Configuration**
   ```bash
   # Production settings
   ENVIRONMENT=production
   DEBUG=false
   API_WORKERS=8
   DEVICE=cuda:0
   ```

3. **Scale Services**
   ```bash
   # Multiple API instances behind load balancer
   docker-compose up -d --scale api=3
   ```

4. **Monitor During Deployment**
   ```bash
   docker-compose logs -f api
   # Check metrics at http://localhost:9090
   ```

## Stopping Services

```bash
# Stop all containers (keep volumes)
docker-compose down

# Stop and remove all data
docker-compose down -v

# Using convenience script
bash docker/stop.sh
```

## Performance Tuning

### API Performance

```env
# Increase workers for concurrent requests
API_WORKERS=8

# Batch processing
BATCH_SIZE=32

# Cache size
REDIS_MAX_MEMORY=2gb
```

### Database Performance

```env
# PostgreSQL connection pool
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10

# Query timeout
DB_QUERY_TIMEOUT=30000
```

### Monitoring

Access Prometheus metrics:
- CPU Usage: `container_cpu_usage_seconds_total`
- Memory: `container_memory_usage_bytes`
- Network: `container_network_bytes_total`

## Cleanup

```bash
# Remove unused images
docker image prune -a

# Remove stopped containers
docker container prune

# Remove unused volumes
docker volume prune

# Complete cleanup (CAREFUL!)
docker system prune -a --volumes
```

## Support

For issues or questions, refer to:
- API Documentation: http://localhost:8000/docs
- Project README: README.md
- Implementation Progress: IMPLEMENTATION_PROGRESS.md

---

**Last Updated**: 2024-04-17
**Version**: 1.0.0
**Status**: Production Ready
