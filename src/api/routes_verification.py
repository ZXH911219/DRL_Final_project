"""
Verification & Hallucination Detection API routes
"""

import logging
import time
import base64
import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict, Any

from src.api.schemas import (
    VerificationRequest,
    VerificationResponse,
)
from src.agents.verification.argos_real import ArgosVerificationAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/verification", tags=["Verification & Hallucination Detection"])

# Initialize verification agent (lazy loading)
_verification_agent: Optional[ArgosVerificationAgent] = None


def get_verification_agent() -> ArgosVerificationAgent:
    """Get or initialize verification agent"""
    global _verification_agent
    if _verification_agent is None:
        _verification_agent = ArgosVerificationAgent(device="cuda")
        _verification_agent.initialize()
        logger.info("Verification agent initialized")
    return _verification_agent


def decode_image(image_base64: str) -> np.ndarray:
    """Decode base64 image to numpy array"""
    try:
        image_data = base64.b64decode(image_base64)
        nparr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise ValueError("Failed to decode image")
        
        return image
        
    except Exception as e:
        logger.error(f"Image decode error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid image data: {str(e)}")


@router.post("/verify", response_model=VerificationResponse)
async def verify_reasoning(request: VerificationRequest):
    """
    Verify reasoning against visual evidence and detect hallucinations
    
    Args:
        request: VerificationRequest with slide image and reasoning
        
    Returns:
        VerificationResponse with verification results
    """
    start_time = time.time()
    
    try:
        # Decode image
        slide_image = decode_image(request.image_base64)
        
        # Get verification agent
        agent = get_verification_agent()
        
        # Perform verification
        report = agent.verify_reasoning(
            slide_image=slide_image,
            reasoning_text=request.reasoning_text,
            reasoning_steps=request.reasoning_steps or [],
            original_score=request.original_score,
            slide_id=request.slide_id
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        return VerificationResponse(
            slide_id=request.slide_id,
            verification_status=report.verification_status,
            hallucination_risk_score=report.hallucination_risk_score,
            hallucination_risk_level=report.hallucination_risk_level,
            evidence_coverage_ratio=report.evidence_coverage_ratio,
            semantic_consistency=report.semantic_consistency,
            original_score=report.original_score,
            adjusted_score=report.adjusted_score,
            adjustment_factor=report.adjustment_factor,
            verified_claims_count=len(report.verified_claims),
            unverified_claims_count=len(report.unverified_claims),
            processing_time_ms=processing_time,
            status="success"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verification error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@router.post("/batch-verify")
async def batch_verify(requests: List[VerificationRequest]):
    """
    Batch verify multiple reasoning results
    
    Args:
        requests: List of VerificationRequest
        
    Returns:
        List of verification results
    """
    results = []
    errors = []
    
    for idx, request in enumerate(requests):
        try:
            response = await verify_reasoning(request)
            results.append(response)
        except Exception as e:
            logger.error(f"Batch verification error at index {idx}: {e}")
            errors.append({"index": idx, "slide_id": request.slide_id, "error": str(e)})
    
    return {
        "successful": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors
    }


@router.post("/hallucination-risk-analysis")
async def analyze_hallucination_risk(
    reasoning_text: str,
    slide_image_base64: str,
    original_score: float
):
    """
    Detailed hallucination risk analysis
    
    Args:
        reasoning_text: The reasoning text to analyze
        slide_image_base64: Base64 encoded slide image
        original_score: Original retrieval/reasoning score
        
    Returns:
        Detailed risk analysis
    """
    try:
        # Decode image
        slide_image = decode_image(slide_image_base64)
        
        # Get agent
        agent = get_verification_agent()
        
        # Perform verification
        report = agent.verify_reasoning(
            slide_image=slide_image,
            reasoning_text=reasoning_text,
            reasoning_steps=[],
            original_score=original_score,
            slide_id="analysis"
        )
        
        return {
            "hallucination_risk_score": report.hallucination_risk_score,
            "risk_level": report.hallucination_risk_level,
            "evidence_coverage": report.evidence_coverage_ratio,
            "semantic_consistency": report.semantic_consistency,
            "verified_claims": len(report.verified_claims),
            "unverified_claims": len(report.unverified_claims),
            "adjustment_factor": report.adjustment_factor,
            "adjusted_score": report.adjusted_score,
            "recommendation": self._generate_recommendation(
                report.hallucination_risk_level,
                report.adjusted_score
            ),
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Risk analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    @staticmethod
    def _generate_recommendation(risk_level: str, adjusted_score: float) -> str:
        """Generate recommendation based on risk and score"""
        if risk_level == "low" and adjusted_score > 0.8:
            return "ACCEPT - High confidence result"
        elif risk_level == "low" and adjusted_score > 0.6:
            return "ACCEPT - Moderate confidence result"
        elif risk_level == "medium":
            return "REVIEW - Manual review recommended"
        else:
            return "REJECT - Low confidence result"


@router.post("/evidence-mapping")
async def get_evidence_mapping(
    slide_image_base64: str,
    reasoning_text: str
):
    """
    Get visual evidence mapping for reasoning claims
    
    Args:
        slide_image_base64: Base64 encoded slide image
        reasoning_text: Reasoning text with claims
        
    Returns:
        Evidence mapping with visual regions
    """
    try:
        slide_image = decode_image(slide_image_base64)
        agent = get_verification_agent()
        
        # Extract claims and ground them
        claims = reasoning_text.split(".")[:5]  # Simple split
        evidence_regions, verified_claims = agent._ground_claims_in_image(
            slide_image,
            [c.strip() for c in claims if c.strip()]
        )
        
        return {
            "total_claims": len(claims),
            "verified_claims": len(verified_claims),
            "evidence_regions": [
                {
                    "claim": e.referenced_claim,
                    "region": {
                        "x_min": e.patch_x_min,
                        "y_min": e.patch_y_min,
                        "x_max": e.patch_x_max,
                        "y_max": e.patch_y_max
                    },
                    "type": e.region_type,
                    "confidence": e.confidence
                }
                for e in evidence_regions
            ],
            "coverage_ratio": len(verified_claims) / max(len(claims), 1),
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Evidence mapping error: {e}")
        raise HTTPException(status_code=500, detail=f"Mapping failed: {str(e)}")


@router.get("/health")
async def health_check():
    """Check verification agent health"""
    try:
        agent = get_verification_agent()
        return {
            "status": "ok",
            "agent_ready": True,
            "model_name": "Argos",
            "ocr_ready": agent.ocr_engine is not None
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
    """Warm up the verification model"""
    start_time = time.time()
    
    try:
        agent = get_verification_agent()
        
        # Create dummy image
        dummy_image = np.random.randint(0, 255, (768, 1024, 3), dtype=np.uint8)
        
        # Perform verification
        report = agent.verify_reasoning(
            slide_image=dummy_image,
            reasoning_text="test reasoning",
            reasoning_steps=[],
            original_score=0.85,
            slide_id="warm_up"
        )
        
        elapsed = time.time() - start_time
        
        return {
            "status": "warmed_up",
            "time_ms": elapsed * 1000,
            "agent_ready": True,
            "test_risk_score": report.hallucination_risk_score
        }
        
    except Exception as e:
        logger.error(f"Warm-up error: {e}")
        raise HTTPException(status_code=500, detail=f"Warm-up failed: {str(e)}")
