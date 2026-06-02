"""
Vision Extraction API routes
"""

import logging
import time
import base64
import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional

from src.api.schemas import (
    VisionExtractionRequest,
    VisionExtractionResponse,
    ErrorResponse,
)
from src.agents.vision_ingestion.colpali_real import RealColPaliVisionAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/vision", tags=["Vision Extraction"])

# Initialize vision agent (lazy loading)
_vision_agent: Optional[RealColPaliVisionAgent] = None


def get_vision_agent() -> RealColPaliVisionAgent:
    """Get or initialize vision agent"""
    global _vision_agent
    if _vision_agent is None:
        _vision_agent = RealColPaliVisionAgent(device="cuda")
        _vision_agent.initialize()
        logger.info("Vision agent initialized")
    return _vision_agent


@router.post("/extract", response_model=VisionExtractionResponse)
async def extract_vision_features(request: VisionExtractionRequest):
    """
    Extract vision features from image using ColPali
    
    Args:
        request: VisionExtractionRequest with base64 image
        
    Returns:
        VisionExtractionResponse with extracted features
    """
    start_time = time.time()
    
    try:
        # Decode base64 image
        try:
            image_data = base64.b64decode(request.image_base64)
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                raise ValueError("Failed to decode image")
                
        except Exception as e:
            logger.error(f"Image decode error: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid image data: {str(e)}"
            )
        
        # Extract features
        agent = get_vision_agent()
        multi_vectors, col_confidence = agent.extractor.extract_features_from_image(image)
        
        # Get ImageBind alignment
        imagebind_vector, alignment_confidence = agent.imagebind_aligner.align_vectors(
            multi_vectors
        )
        
        # Quality check
        quality_report = agent.quality_checker.comprehensive_check(
            multi_vectors, imagebind_vector
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        return VisionExtractionResponse(
            slide_id=request.metadata.get("slide_id", "unknown") if request.metadata else "unknown",
            multi_vectors_shape=(1024, 128),
            imagebind_vectors_shape=(1024,),
            colpali_confidence=float(col_confidence),
            alignment_confidence=float(alignment_confidence),
            quality_score=quality_report.get("overall_score", 0.0) / 100.0,
            processing_time_ms=processing_time,
            status="success"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vision extraction error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Vision extraction failed: {str(e)}"
        )


@router.post("/batch-extract")
async def batch_extract_vision_features(requests: list[VisionExtractionRequest]):
    """
    Batch extract vision features from multiple images
    
    Args:
        requests: List of VisionExtractionRequest
        
    Returns:
        List of VisionExtractionResponse
    """
    results = []
    errors = []
    
    for idx, request in enumerate(requests):
        try:
            response = await extract_vision_features(request)
            results.append(response)
        except Exception as e:
            logger.error(f"Batch extraction error at index {idx}: {e}")
            errors.append({"index": idx, "error": str(e)})
    
    return {
        "successful": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors
    }


@router.get("/health")
async def health_check():
    """Check vision agent health"""
    try:
        agent = get_vision_agent()
        return {
            "status": "ok",
            "agent_ready": agent.extractor.is_ready,
            "model_name": "ColPali"
        }
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "error",
            "agent_ready": False,
            "error": str(e)
        }


@router.post("/warm-up")
async def warm_up():
    """Warm up the vision model"""
    start_time = time.time()
    
    try:
        agent = get_vision_agent()
        
        # Create dummy image and extract
        dummy_image = np.random.randint(0, 255, (768, 1024, 3), dtype=np.uint8)
        multi_vectors, _ = agent.extractor.extract_features_from_image(dummy_image)
        
        elapsed = time.time() - start_time
        
        return {
            "status": "warmed_up",
            "time_ms": elapsed * 1000,
            "model_ready": agent.extractor.is_ready
        }
        
    except Exception as e:
        logger.error(f"Warm-up error: {e}")
        raise HTTPException(status_code=500, detail=f"Warm-up failed: {str(e)}")
