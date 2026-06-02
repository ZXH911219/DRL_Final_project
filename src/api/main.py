"""
FastAPI application for multi-agent PPT retrieval system
"""

import logging
import sys
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic_settings import BaseSettings

from src.api import routes_vision, routes_reasoning, routes_verification
from src.api import routes_retrieval, routes_pipeline, routes_ws, routes_auth
from src.api.schemas import HealthCheckResponse, SystemMetricsResponse, ErrorResponse
from src.api.auth import AuthorizationMiddleware, jwt_manager, audit_logger
from src.api.errors import setup_exception_handlers
from src.configs.config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class APISettings(BaseSettings):
    """API configuration"""
    api_version: str = "1.0.0"
    api_title: str = "Multi-Agent PPT Retrieval System API"
    api_description: str = "API for vision, reasoning, and verification agents"
    api_port: int = 8000
    api_host: str = "0.0.0.0"
    enable_cors: bool = True
    cors_origins: list = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8080",
    ]
    
    class Config:
        case_sensitive = False


# Global metrics
class SystemMetrics:
    def __init__(self):
        self.total_requests = 0
        self.vision_extraction_total_ms = 0
        self.vision_extraction_count = 0
        self.retrieval_total_ms = 0
        self.retrieval_count = 0
        self.reasoning_total_ms = 0
        self.reasoning_count = 0
        self.verification_total_ms = 0
        self.verification_count = 0
        self.errors = 0
    
    @property
    def vision_extraction_avg_ms(self) -> float:
        return (
            self.vision_extraction_total_ms / self.vision_extraction_count
            if self.vision_extraction_count > 0
            else 0.0
        )
    
    @property
    def retrieval_avg_ms(self) -> float:
        return (
            self.retrieval_total_ms / self.retrieval_count
            if self.retrieval_count > 0
            else 0.0
        )
    
    @property
    def reasoning_avg_ms(self) -> float:
        return (
            self.reasoning_total_ms / self.reasoning_count
            if self.reasoning_count > 0
            else 0.0
        )
    
    @property
    def verification_avg_ms(self) -> float:
        return (
            self.verification_total_ms / self.verification_count
            if self.verification_count > 0
            else 0.0
        )
    
    @property
    def error_rate(self) -> float:
        return (
            self.errors / self.total_requests
            if self.total_requests > 0
            else 0.0
        )


# Global state
metrics = SystemMetrics()
settings = APISettings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Redis integration
    from src.storage.redis_cache import redis_cache
    await redis_cache.connect()
    
    # Startup
    logger.info("=" * 60)
    logger.info("Multi-Agent PPT Retrieval System API Starting")
    logger.info("=" * 60)
    logger.info(f"API Version: {settings.api_version}")
    logger.info(f"Starting on {settings.api_host}:{settings.api_port}")
    
    # Warm up agents
    try:
        logger.info("Warming up agents...")
        from src.agents.vision_ingestion.colpali_real import RealColPaliVisionAgent
        from src.agents.reasoning_reranker.mm_r5_real import MM_R5ReasoningReranker
        from src.agents.verification.argos_real import ArgosVerificationAgent
        
        vision_agent = RealColPaliVisionAgent(device="cuda")
        vision_agent.initialize()
        logger.info("\u2713 Vision agent ready")
        
        reasoning_agent = MM_R5ReasoningReranker(device="cuda")
        logger.info("\u2713 Reasoning agent ready")
        
        verification_agent = ArgosVerificationAgent(device="cuda")
        verification_agent.initialize()
        logger.info("\u2713 Verification agent ready")
        
    except Exception as e:
        logger.warning(f"Agent warm-up partially failed: {e}")
    
    yield
    
    # Shutdown
    from src.storage.redis_cache import redis_cache
    await redis_cache.close()
    logger.info("=" * 60)
    logger.info("Multi-Agent PPT Retrieval System API Shutting Down")
    logger.info(f"Total Requests: {metrics.total_requests}")
    logger.info(f"Error Rate: {metrics.error_rate:.1%}")
    logger.info("=" * 60)


# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
    lifespan=lifespan
)

# Configure CORS
if settings.enable_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Task 35: Gzip Compression Middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add authorization middleware
app.add_middleware(AuthorizationMiddleware)

# Task 29: Exception Handlers setup
setup_exception_handlers(app)

# Include routers
app.include_router(routes_auth.router)
app.include_router(routes_vision.router)
app.include_router(routes_reasoning.router)
app.include_router(routes_verification.router)
app.include_router(routes_retrieval.router)
app.include_router(routes_pipeline.router)
app.include_router(routes_ws.router)

# Root endpoint
@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": settings.api_title,
        "version": settings.api_version,
        "description": settings.api_description,
        "endpoints": {
            "vision": "/api/v1/vision/docs",
            "reasoning": "/api/v1/reasoning/docs",
            "verification": "/api/v1/verification/docs",
            "health": "/health",
            "metrics": "/metrics"
        }
    }


# Health check endpoint
@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """
    Comprehensive health check for all agents
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.api_version
    }
