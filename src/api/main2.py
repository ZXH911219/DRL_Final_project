"""
FastAPI application for multi-agent PPT retrieval system
"""

import logging
import sys
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic_settings import BaseSettings

from src.api import routes_vision, routes_reasoning, routes_verification
from src.api import routes_retrieval, routes_pipeline, routes_ws, routes_auth
from src.api.schemas import HealthCheckResponse, SystemMetricsResponse, ErrorResponse
from src.api.auth import AuthorizationMiddleware, jwt_manager, audit_logger
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
    # Startup
    logger.info("=" * 60)
    logger.info("Multi-Agent PPT Retrieval System API Starting")
    logger.info("=" * 60)
    logger.info(f"API Version: {settings.api_version}")
    logger.info(f"Starting on {settings.api_host}:{settings.api_port}")
    
    # Warm up agents
    try:
        logger.info("Warming up agents...")
        # Import and initialize agents
        from src.agents.vision_ingestion.colpali_real import RealColPaliVisionAgent
        from src.agents.reasoning_reranker.mm_r5_real import MM_R5ReasoningReranker
        from src.agents.verification.argos_real import ArgosVerificationAgent
        
        vision_agent = RealColPaliVisionAgent(device="cuda")
        vision_agent.initialize()
        logger.info("??Vision agent ready")
        
        reasoning_agent = MM_R5ReasoningReranker(device="cuda")
        logger.info("??Reasoning agent ready")
        
        verification_agent = ArgosVerificationAgent(device="cuda")
        verification_agent.initialize()
        logger.info("??Verification agent ready")
        
    except Exception as e:
        logger.warning(f"Agent warm-up partially failed: {e}")
    
    yield
    
    # Shutdown
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

# Add authorization middleware
app.add_middleware(AuthorizationMiddleware)

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
    
    Returns:
        HealthCheckResponse with status of all services
    """
    try:
        from src.agents.vision_ingestion.colpali_real import RealColPaliVisionAgent
        from src.agents.reasoning_reranker.mm_r5_real import MM_R5ReasoningReranker
        from src.agents.verification.argos_real import ArgosVerificationAgent
        
        # Check vision agent
        try:
            vision_agent = RealColPaliVisionAgent(device="cuda")
            vision_ready = vision_agent.extractor is not None
        except:
            vision_ready = False
        
        # Check reasoning agent
        try:
            reasoning_agent = MM_R5ReasoningReranker(device="cuda")
            reasoning_ready = True
        except:
            reasoning_ready = False
        
        # Check verification agent
        try:
            verification_agent = ArgosVerificationAgent(device="cuda")
            verification_ready = True
        except:
            verification_ready = False
        
        return HealthCheckResponse(
            status="healthy" if all([vision_ready, reasoning_ready, verification_ready]) else "degraded",
            timestamp=datetime.utcnow(),
            services={
                "vision_agent": {
                    "ready": vision_ready,
                    "last_check": datetime.utcnow().isoformat()
                },
                "reasoning_agent": {
                    "ready": reasoning_ready,
                    "last_check": datetime.utcnow().isoformat()
                },
                "verification_agent": {
                    "ready": verification_ready,
                    "last_check": datetime.utcnow().isoformat()
                },
            }
        )
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return HealthCheckResponse(
            status="unhealthy",
            timestamp=datetime.utcnow(),
            services={}
        )


# Metrics endpoint
@app.get("/metrics", response_model=SystemMetricsResponse)
async def get_metrics():
    """
    Get system performance metrics
    
    Returns:
        SystemMetricsResponse with aggregate metrics
    """
    return SystemMetricsResponse(
        timestamp=datetime.utcnow(),
        vision_extraction_avg_ms=metrics.vision_extraction_avg_ms,
        retrieval_avg_ms=metrics.retrieval_avg_ms,
        reasoning_avg_ms=metrics.reasoning_avg_ms,
        verification_avg_ms=metrics.verification_avg_ms,
        total_requests=metrics.total_requests,
        error_rate=metrics.error_rate,
        cache_hit_rate=0.0
    )


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    metrics.errors += 1
    
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            status="error",
            code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            details={"error": str(exc)}
        ).model_dump()
    )


# Request/response logging middleware
@app.middleware("http")
async def log_requests(request, call_next):
    """Log requests and responses"""
    import time
    
    metrics.total_requests += 1
    
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    # Log request info
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Duration: {process_time*1000:.1f}ms"
    )
    
    return response


if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting API server on {settings.api_host}:{settings.api_port}")
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level="info"
    )

