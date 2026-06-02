"""
FastAPI schemas for request/response validation
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime


# Vision Extraction Schemas
class VisionExtractionRequest(BaseModel):
    """Request for vision feature extraction"""
    image_base64: str = Field(..., description="Base64 encoded image")
    image_format: str = Field(default="png", description="Image format (png, jpg, etc.)")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata")


class EvidenceRegionSchema(BaseModel):
    """Evidence region location"""
    patch_x_min: int
    patch_y_min: int
    patch_x_max: int
    patch_y_max: int
    region_type: str
    confidence: float


class VisionExtractionResponse(BaseModel):
    """Response with extracted vision features"""
    slide_id: str
    multi_vectors_shape: tuple = (1024, 128)
    imagebind_vectors_shape: tuple = (1024,)
    colpali_confidence: float
    alignment_confidence: float
    quality_score: float
    processing_time_ms: float
    status: str = "success"


# Reasoning Schemas
class ReasoningStep(BaseModel):
    """Single reasoning step"""
    step_id: int
    step_name: str
    reasoning_text: str
    local_score: float
    confidence: float


class ReasoningRerankerRequest(BaseModel):
    """Request for reasoning-based reranking"""
    query: str = Field(..., description="User query")
    candidates: List[Dict[str, Any]] = Field(
        ..., 
        description="List of candidates with slide_id, content, score"
    )
    max_candidates: Optional[int] = Field(default=20, description="Max candidates to rerank")


class ReasoningRerankerResponse(BaseModel):
    """Response with reasoning-based reranking"""
    query: str
    reranked_candidates: List[Dict[str, Any]]
    total_candidates: int
    processing_time_ms: float
    status: str = "success"

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Verification Schemas
class VerificationRequest(BaseModel):
    """Request for verification and hallucination detection"""
    slide_id: str
    image_base64: str
    reasoning_text: str
    reasoning_steps: Optional[List[Dict[str, str]]] = None
    original_score: float = Field(..., ge=0.0, le=1.0)


class VerificationResponse(BaseModel):
    """Response with verification result"""
    slide_id: str
    verification_status: str  # pass, warn, fail
    hallucination_risk_score: float
    hallucination_risk_level: str  # low, medium, high
    evidence_coverage_ratio: float
    semantic_consistency: float
    original_score: float
    adjusted_score: float
    adjustment_factor: float
    verified_claims_count: int
    unverified_claims_count: int
    processing_time_ms: float
    status: str = "success"


# Retrieval Schemas
class RetrievalRequest(BaseModel):
    """Request for vector-based retrieval"""
    query: str = Field(..., description="Search query")
    query_image_base64: Optional[str] = Field(
        None, 
        description="Optional query image (for visual search)"
    )
    top_k: int = Field(default=20, ge=1, le=100, description="Number of results to return")
    use_fts: bool = Field(default=False, description="Use full-text search in addition to vectors")


class RetrievalCandidate(BaseModel):
    """Single retrieval result"""
    slide_id: str
    page_index: int
    maxsim_score: float
    evidence_regions: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}


class RetrievalResponse(BaseModel):
    """Response with retrieval results"""
    query: str
    num_results: int
    candidates: List[RetrievalCandidate]
    retrieval_latency_ms: float
    total_latency_ms: float
    status: str = "success"


# Pipeline Schemas
class EndToEndPipelineRequest(BaseModel):
    """Request for full end-to-end pipeline"""
    query: str = Field(..., description="User query")
    image_base64: str = Field(..., description="Slide image")
    include_reasoning: bool = Field(default=True, description="Include reasoning stage")
    include_verification: bool = Field(default=True, description="Include verification stage")


class EndToEndPipelineResponse(BaseModel):
    """Response with full pipeline results"""
    query: str
    retrieval_results: Optional[List[Dict[str, Any]]] = None
    reasoning_results: Optional[List[Dict[str, Any]]] = None
    verification_results: Optional[List[Dict[str, Any]]] = None
    total_latency_ms: float
    status: str = "success"


# Health Check Schemas
class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    services: Dict[str, Dict[str, Any]] = {
        "vision_agent": {"ready": False, "last_check": None},
        "retrieval_agent": {"ready": False, "last_check": None},
        "reasoning_agent": {"ready": False, "last_check": None},
        "verification_agent": {"ready": False, "last_check": None},
    }


# Error Response Schema
class ErrorResponse(BaseModel):
    """Standard error response"""
    status: str = "error"
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Metrics Schemas
class SystemMetricsResponse(BaseModel):
    """System performance metrics"""
    timestamp: datetime
    vision_extraction_avg_ms: float
    retrieval_avg_ms: float
    reasoning_avg_ms: float
    verification_avg_ms: float
    total_requests: int
    error_rate: float
    cache_hit_rate: float = 0.0


class ModelStatusResponse(BaseModel):
    """Model status and information"""
    model_name: str
    loaded: bool
    model_size_gb: float
    last_loaded: Optional[datetime] = None
    inference_hardware: str  # "cuda", "cpu", "mps"
