"""
Reasoning Reranker API routes
"""

import logging
import time
from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict, Any

from src.api.schemas import (
    ReasoningRerankerRequest,
    ReasoningRerankerResponse,
)
from src.agents.reasoning_reranker.mm_r5_real import MM_R5ReasoningReranker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/reasoning", tags=["Reasoning & Reranking"])

# Initialize reasoning agent (lazy loading)
_reasoning_agent: Optional[MM_R5ReasoningReranker] = None


def get_reasoning_agent() -> MM_R5ReasoningReranker:
    """Get or initialize reasoning agent"""
    global _reasoning_agent
    if _reasoning_agent is None:
        _reasoning_agent = MM_R5ReasoningReranker(device="cuda")
        logger.info("Reasoning agent initialized")
    return _reasoning_agent


@router.post("/rerank", response_model=ReasoningRerankerResponse)
async def rerank_with_reasoning(request: ReasoningRerankerRequest):
    """
    Rerank candidates using MM-R5 reasoning
    
    Args:
        request: ReasoningRerankerRequest with query and candidates
        
    Returns:
        ReasoningRerankerResponse with reranked results
    """
    start_time = time.time()
    
    try:
        # Validate input
        if not request.candidates:
            raise ValueError("Candidates list cannot be empty")
        
        if not request.query:
            raise ValueError("Query cannot be empty")
        
        # Get reasoning agent
        agent = get_reasoning_agent()
        
        # Perform reranking
        reranked = agent.rerank_candidates(
            query=request.query,
            candidates=request.candidates,
            max_candidates_to_reason=request.max_candidates or 20
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        return ReasoningRerankerResponse(
            query=request.query,
            reranked_candidates=reranked,
            total_candidates=len(reranked),
            processing_time_ms=processing_time,
            status="success"
        )
        
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Reasoning error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Reasoning failed: {str(e)}")


@router.post("/explain-reasoning")
async def explain_reasoning(query: str, content: str, slide_id: str = "unknown"):
    """
    Get detailed reasoning explanation for a query-content pair
    
    Args:
        query: User query
        content: Document/slide content
        slide_id: Unique slide identifier
        
    Returns:
        Detailed reasoning chain with explanations
    """
    start_time = time.time()
    
    try:
        agent = get_reasoning_agent()
        
        # Generate reasoning
        result = agent.reasoner.generate_reasoning_chain(
            query=query,
            slide_content=content,
            slide_id=slide_id
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        return {
            "slide_id": slide_id,
            "query": query,
            "reasoning_chain": [
                {
                    "step": step.step_name,
                    "id": step.step_id,
                    "reasoning": step.reasoning_text,
                    "score": step.local_score,
                    "confidence": step.confidence
                }
                for step in result.reasoning_chain
            ],
            "final_score": result.final_score,
            "confidence_level": result.confidence_level,
            "interpretability": result.interpretability_score,
            "key_phrases": result.key_evidence_phrases,
            "processing_time_ms": processing_time,
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Reasoning explanation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Reasoning explanation failed: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """Check reasoning agent health"""
    try:
        agent = get_reasoning_agent()
        return {
            "status": "ok",
            "agent_ready": agent.reasoner.is_ready,
            "model_name": "MM-R5"
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
    """Warm up the reasoning model"""
    start_time = time.time()
    
    try:
        agent = get_reasoning_agent()
        
        # Generate test reasoning
        result = agent.reasoner.generate_reasoning_chain(
            query="test query",
            slide_content="test content",
            slide_id="warm_up"
        )
        
        elapsed = time.time() - start_time
        
        return {
            "status": "warmed_up",
            "time_ms": elapsed * 1000,
            "model_ready": agent.reasoner.is_ready,
            "test_score": result.final_score
        }
        
    except Exception as e:
        logger.error(f"Warm-up error: {e}")
        raise HTTPException(status_code=500, detail=f"Warm-up failed: {str(e)}")


@router.post("/compare-scores")
async def compare_reasoning_scores(
    query: str,
    candidates: List[Dict[str, str]]
):
    """
    Compare reasoning scores across multiple candidates
    
    Args:
        query: User query
        candidates: List of candidates with slide_id and content
        
    Returns:
        Comparison of reasoning scores
    """
    try:
        agent = get_reasoning_agent()
        
        scores = []
        for candidate in candidates:
            result = agent.reasoner.generate_reasoning_chain(
                query=query,
                slide_content=candidate.get("content", ""),
                slide_id=candidate.get("slide_id", "unknown")
            )
            
            scores.append({
                "slide_id": candidate.get("slide_id"),
                "reasoning_score": result.final_score,
                "confidence": result.confidence_level,
                "top_reasoning_step": result.reasoning_chain[0].step_name if result.reasoning_chain else None
            })
        
        # Sort by score
        scores.sort(key=lambda x: x["reasoning_score"], reverse=True)
        
        return {
            "query": query,
            "comparison_results": scores,
            "best_match": scores[0] if scores else None,
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Score comparison error: {e}")
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")
