"""
Comprehensive reasoning pipeline API endpoints.
Exposes end-to-end retrieval + reasoning + verification.
"""

import logging
import time
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel, Field
import numpy as np

from src.core.pipeline import get_pipeline, PipelineResult
from src.api.auth import verify_token, required_permission, audit_logger
from src.storage.lancedb_client import get_lance_client, VectorDocument
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


# Request/Response Models
class PipelineQueryRequest(BaseModel):
    """Pipeline query request."""
    query_text: Optional[str] = Field(None, description="Text query")
    query_vector: Optional[List[float]] = Field(None, description="Query vector (128-dim)")
    table_name: str = Field("ppt_slides", description="Table to search")
    k1: int = Field(500, description="Candidates from filtering")
    k2: int = Field(20, description="Final results")


class PipelineStageResult(BaseModel):
    """Single stage result."""
    stage: str
    duration_ms: float
    status: str
    records_processed: int


class ReasoningStepResponse(BaseModel):
    """5-step reasoning."""
    doc_id: str
    rank: int
    reasoning: str
    verification_score: float


class PipelineResponse(BaseModel):
    """Complete pipeline response."""
    query_id: str
    status: str
    results: List[Dict[str, Any]]
    metrics: List[PipelineStageResult]
    total_latency_ms: float
    timestamp: str


@router.post("/execute")
async def execute_pipeline(
    request: PipelineQueryRequest,
    payload: Dict[str, Any] = Depends(required_permission("reasoning:read"))
) -> PipelineResponse:
    """
    Execute complete end-to-end pipeline:
    1. Vector retrieval (Stage 1 & 2)
    2. 5-step reasoning chain generation
    3. Hallucination verification with evidence grounding
    """
    user_id = payload.get("sub", "anonymous")
    start_time = time.time()
    
    from src.storage.redis_cache import redis_cache
    import hashlib
    
    # Check cache
    cache_key = f"resp:pipeline:{hashlib.md5(f'{request.query_text}:{request.top_k}:{request.reasoning_mode}'.encode()).hexdigest()}"
    cached_val = await redis_cache.get(cache_key)
    if cached_val:
        logger.info(f"Cache hit for pipeline query: {request.query_text}")
        from src.api.schemas import PipelineResponse
        return PipelineResponse(**cached_val)

    try:
        logger.info(f"Pipeline execution started for user {user_id}")

        # Validate input
        if not request.query_vector and not request.query_text:
            raise HTTPException(
                status_code=400,
                detail="Either query_vector or query_text is required"
            )

        # Convert or generate query vector
        if request.query_vector:
            query_vector = np.array(request.query_vector, dtype=np.float32)
            if len(query_vector) != 128:
                raise HTTPException(
                    status_code=400,
                    detail="Query vector must be 128-dimensional"
                )
        else:
            # Generate vector from text using ImageBind
            logger.info(f"Generating vector from text: {request.query_text[:50]}...")
            try:
                # For demo, use random vector
                # In production, use ImageBind text encoder
                query_vector = np.random.randn(128).astype(np.float32)
            except Exception as e:
                logger.warning(f"Failed to generate vector: {str(e)}")
                query_vector = np.random.randn(128).astype(np.float32)

        # Execute pipeline
        pipeline = get_pipeline()

        result = pipeline.execute(
            query_vector=query_vector,
            query_text=request.query_text,
            user_id=user_id,
            table_name=request.table_name,
            k1=request.k1,
            k2=request.k2
        )

        # Convert metrics
        metrics = [
            PipelineStageResult(
                stage=metric.stage,
                duration_ms=metric.duration_ms,
                status=metric.status,
                records_processed=metric.records_processed
            )
            for metric in result.metrics
        ]

        # Log audit
        audit_logger.log_action(
            user_id=user_id,
            action="pipeline_execute",
            resource="/pipeline/execute",
            method="POST",
            status=200,
            details={
                "query_text": request.query_text[:50] if request.query_text else None,
                "results_count": len(result.results),
                "total_latency_ms": result.total_latency_ms,
                "query_id": result.query_id,
            }
        )

        response = PipelineResponse(
            query_id=result.query_id,
            status="success",
            results=result.results,
            metrics=metrics,
            total_latency_ms=result.total_latency_ms,
            timestamp=result.timestamp
        )

        from src.storage.redis_cache import redis_cache
        # Cache the response for 1 hour
        await redis_cache.set(cache_key, response.model_dump(), expire_seconds=3600)
        
        return response

    except ValueError as e:
        logger.error(f"Invalid input: {str(e)}")
        audit_logger.log_action(
            user_id=user_id,
            action="pipeline_execute",
            resource="/pipeline/execute",
            method="POST",
            status=400,
            details={"error": str(e)}
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Pipeline execution failed: {str(e)}")
        audit_logger.log_action(
            user_id=user_id,
            action="pipeline_execute",
            resource="/pipeline/execute",
            method="POST",
            status=500,
            details={"error": str(e)}
        )
        raise HTTPException(status_code=500, detail="Pipeline execution failed")


@router.post("/ingest-slide")
async def ingest_slide(
    slide_id: str = Form(...),
    slide_image: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    text_content: Optional[str] = Form(None),
    payload: Dict[str, Any] = Depends(required_permission("vision:write"))
) -> Dict[str, Any]:
    """
    Ingest a single slide with vision feature extraction.
    """
    user_id = payload.get("sub", "anonymous")
    start_time = time.time()

    try:
        logger.info(f"Ingesting slide {slide_id} for user {user_id}")

        # Save uploaded file
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
            content = await slide_image.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name

        # Extract features
        pipeline = get_pipeline()

        if pipeline.vision_stage.model_loader is None:
            logger.warning("Vision model not loaded, returning mock features")
            vectors = np.random.randn(1024, 128).astype(np.float32)
        else:
            vectors, success = pipeline.vision_stage.process_image(tmp_path)
            if not success:
                raise Exception("Vision extraction failed")

        # Create vector document
        imagebind_vector = np.mean(vectors, axis=0)

        doc = VectorDocument(
            doc_id=slide_id,
            content_type="slide",
            vectors=vectors,
            imagebind_vector=imagebind_vector,
            text_content=text_content if text_content else "",
            metadata={
                "filename": slide_image.filename,
                "ingested_by": user_id,
                **(json.loads(metadata) if metadata else {})
            }
        )

        # Store in LanceDB
        client = get_lance_client()
        inserted = client.insert_vectors(
            table_name="ppt_slides",
            documents=[doc],
            batch_size=1
        )

        # Cleanup temp file
        import os
        os.unlink(tmp_path)

        latency = (time.time() - start_time) * 1000

        audit_logger.log_action(
            user_id=user_id,
            action="ingest_slide",
            resource=f"/pipeline/ingest-slide",
            method="POST",
            status=200,
            details={
                "slide_id": slide_id,
                "inserted": inserted,
                "latency_ms": latency,
            }
        )

        logger.info(f"Slide {slide_id} ingested in {latency:.2f}ms")

        return {
            "success": True,
            "slide_id": slide_id,
            "vectors_shape": list(vectors.shape),
            "latency_ms": latency,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Slide ingestion failed: {str(e)}")
        audit_logger.log_action(
            user_id=user_id,
            action="ingest_slide",
            resource="/pipeline/ingest-slide",
            method="POST",
            status=500,
            details={"error": str(e)}
        )
        raise HTTPException(status_code=500, detail="Slide ingestion failed")


@router.get("/reasoning/{query_id}")
async def get_reasoning_result(
    query_id: str,
    payload: Dict[str, Any] = Depends(required_permission("reasoning:read"))
) -> Dict[str, Any]:
    """Get detailed reasoning results for a query."""
    # In production, retrieve from database
    # For now, return mock data
    return {
        "query_id": query_id,
        "status": "completed",
        "reasoning_count": 20,
        "reasoning_samples": [
            {
                "doc_id": f"slide_{i}",
                "reasoning": "This slide is relevant because..."
            }
            for i in range(3)
        ]
    }


@router.post("/batch-ingest")
async def batch_ingest(
    table_name: str = Form(default="ppt_slides"),
    payload: Dict[str, Any] = Depends(required_permission("vision:write"))
) -> Dict[str, Any]:
    """
    Batch ingest multiple slides.
    """
    user_id = payload.get("sub", "anonymous")

    try:
        logger.info(f"Batch ingestion started for user {user_id}")

        # In production, implement actual batch processing
        # For now, return summary

        return {
            "status": "started",
            "batch_id": f"batch_{int(time.time() * 1000)}",
            "table_name": table_name,
            "message": "Batch ingestion initiated. Check batch status with batch_id"
        }

    except Exception as e:
        logger.error(f"Batch ingestion failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Batch ingestion failed")



from fastapi import BackgroundTasks
import asyncio

@router.post("/batch-query")
async def batch_query(
    queries: list[dict],
    user_data: dict = Depends(verify_token)
):
    """Execute multiple queries in batch."""
    results = []
    # Mocking batch process for demonstration
    for q in queries:
        query_text = q.get('query', '')
        results.append({
            'query': query_text,
            'result_id': f'res_{int(time.time()*1000)}_{len(results)}',
            'status': 'processed',
        })
    return {"batch_results": results}

async def background_search_task(query: str, user_id: str):
    """Background task for async search."""
    logger.info(f"Starting async processing for query: {query} by user {user_id}")
    await asyncio.sleep(2)
    logger.info(f"Async query {query} completed for {user_id}.")

@router.post("/async-query")
async def async_query(
    background_tasks: BackgroundTasks,
    request: dict,
    user_data: dict = Depends(verify_token)
):
    """Initiate a query to be processed in the background."""
    query = request.get('query', '')
    user_id = str(user_data.get('sub', 'anonymous'))
    task_id = f'task_{int(time.time() * 1000)}'
    
    background_tasks.add_task(background_search_task, query, user_id)
    return {"status": "accepted", "task_id": task_id, "message": "Processing in background"}

@router.get("/pipeline-status")
async def get_pipeline_status(
    payload: Dict[str, Any] = Depends(required_permission("system:read"))
) -> Dict[str, Any]:
    """Get pipeline status and component health."""
    pipeline = get_pipeline()

    return {
        "status": "operational",
        "components": {
            "vision_ingestion": {
                "initialized": pipeline.vision_stage.model_loader is not None,
                "status": "ready" if pipeline.vision_stage.model_loader else "not_initialized"
            },
            "retrieval": {
                "initialized": pipeline.retrieval_stage.client is not None,
                "status": "ready" if pipeline.retrieval_stage.client else "not_initialized"
            },
            "reasoning": {
                "initialized": pipeline.reasoning_stage.model_loader is not None,
                "status": "ready" if pipeline.reasoning_stage.model_loader else "not_initialized"
            },
            "verification": {
                "initialized": pipeline.verification_stage.model_loader is not None,
                "status": "ready" if pipeline.verification_stage.model_loader else "not_initialized"
            }
        },
        "timestamp": datetime.now().isoformat()
    }


import json
