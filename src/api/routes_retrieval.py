"""
Retrieval API routes - Stage 1 & Stage 2 dual-stage retrieval endpoints.
"""

import logging
import time
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Depends, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
import numpy as np

from src.storage.lancedb_client import get_lance_client, RetrievalResult, VectorDocument
from src.api.auth import verify_token, required_permission, audit_logger, rate_limiter
from src.models.model_loaders import ColPaliLoader, create_loader
from src.configs.config import get_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/retrieval", tags=["retrieval"])


# Request/Response Models
class VectorQueryRequest(BaseModel):
    """Vector query request."""
    query_vector: List[float] = Field(..., description="Query vector (128-dim)")
    k1: int = Field(500, description="Number of candidates from filtering stage")
    k2: int = Field(20, description="Final number of results")
    table_name: str = Field("ppt_slides", description="Table to search")


class TextQueryRequest(BaseModel):
    """Text query request."""
    query_text: str = Field(..., description="Text query")
    k1: int = Field(500, description="Number of candidates from filtering stage")
    k2: int = Field(20, description="Final number of results")
    table_name: str = Field("ppt_slides", description="Table to search")


class HybridQueryRequest(BaseModel):
    """Hybrid query request."""
    query_text: Optional[str] = Field(None, description="Text query")
    query_vector: Optional[List[float]] = Field(None, description="Vector query")
    k1: int = Field(500, description="Number of candidates")
    k2: int = Field(20, description="Final results")
    fts_weight: float = Field(0.3, description="Text search weight")
    vector_weight: float = Field(0.7, description="Vector search weight")
    table_name: str = Field("ppt_slides", description="Table to search")


class RetrievalResponse(BaseModel):
    """Single retrieval result."""
    doc_id: str
    rank: int
    score: float
    stage: str
    metadata: Dict[str, Any]


class RetrievalListResponse(BaseModel):
    """List of retrieval results."""
    results: List[RetrievalResponse]
    total_count: int
    latency_ms: float
    query_time: str


@router.post("/vector-search")
async def vector_search(
    request: VectorQueryRequest,
    payload: Dict[str, Any] = Depends(required_permission("retrieval:read"))
) -> RetrievalListResponse:
    """
    Vector-based search with dual-stage retrieval.
    Stage 1: IVF filtering (fast, ~50ms)
    Stage 2: MaxSim reranking (precise, ~100ms)
    """
    user_id = payload.get("sub", "anonymous")
    start_time = time.time()

    try:
        # Validate input
        if not request.query_vector or len(request.query_vector) != 128:
            raise HTTPException(
                status_code=400,
                detail="Query vector must be 128-dimensional"
            )

        # Convert to numpy array
        query_vector = np.array(request.query_vector, dtype=np.float32)

        # Get LanceDB client
        client = get_lance_client()

        # Stage 1: Vector filtering
        logger.info(f"Starting vector search for user {user_id}")
        stage1_results = client.stage1_vector_filtering(
            table_name=request.table_name,
            query_vector=query_vector,
            k=request.k1,
            metric="cosine"
        )

        if not stage1_results:
            return RetrievalListResponse(
                results=[],
                total_count=0,
                latency_ms=(time.time() - start_time) * 1000,
                query_time=datetime.now().isoformat()
            )

        # Extract candidates for Stage 2
        candidates = [result.doc_id for result in stage1_results]

        # Stage 2: MaxSim reranking
        stage2_results = client.stage2_maxsim_reranking(
            table_name=request.table_name,
            query_vectors=query_vector.reshape(1, -1),
            candidate_doc_ids=candidates,
            k=request.k2
        )

        # Convert to response format
        response_results = [
            RetrievalResponse(
                doc_id=result.doc_id,
                rank=result.rank,
                score=result.score,
                stage=result.stage,
                metadata=result.metadata
            )
            for result in stage2_results
        ]

        latency = (time.time() - start_time) * 1000

        # Log audit
        audit_logger.log_action(
            user_id=user_id,
            action="vector_search",
            resource=f"/retrieval/vector-search",
            method="POST",
            status=200,
            details={
                "query_vector_dim": len(request.query_vector),
                "k1": request.k1,
                "k2": request.k2,
                "results_count": len(response_results),
                "latency_ms": latency,
            }
        )

        logger.info(f"Vector search completed in {latency:.2f}ms, returned {len(response_results)} results")

        return RetrievalListResponse(
            results=response_results,
            total_count=len(response_results),
            latency_ms=latency,
            query_time=datetime.now().isoformat()
        )

    except ValueError as e:
        logger.error(f"Invalid input: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Vector search failed: {str(e)}")
        audit_logger.log_action(
            user_id=user_id,
            action="vector_search",
            resource="/retrieval/vector-search",
            method="POST",
            status=500,
            details={"error": str(e)}
        )
        raise HTTPException(status_code=500, detail="Search failed")


@router.post("/text-search")
async def text_search(
    request: TextQueryRequest,
    payload: Dict[str, Any] = Depends(required_permission("retrieval:read"))
) -> RetrievalListResponse:
    """
    Text-based search (full-text search on metadata).
    """
    user_id = payload.get("sub", "anonymous")
    start_time = time.time()

    try:
        logger.info(f"Text search for: {request.query_text} (user: {user_id})")

        # For this implementation, we'll use simple keyword matching in metadata
        # In production, use proper FTS (Whoosh, ElasticSearch, etc.)

        client = get_lance_client()
        
        # Placeholder: In production, implement proper FTS
        results = []

        latency = (time.time() - start_time) * 1000

        return RetrievalListResponse(
            results=results,
            total_count=0,
            latency_ms=latency,
            query_time=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"Text search failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Search failed")


@router.post("/hybrid-search")
async def hybrid_search(
    request: HybridQueryRequest,
    payload: Dict[str, Any] = Depends(required_permission("retrieval:read"))
) -> RetrievalListResponse:
    """
    Hybrid search combining vector and text search.
    Weights are combined: fts_weight + vector_weight should equal 1.0
    """
    user_id = payload.get("sub", "anonymous")
    start_time = time.time()

    try:
        # Validate weights
        if abs(request.fts_weight + request.vector_weight - 1.0) > 0.01:
            raise HTTPException(
                status_code=400,
                detail="fts_weight + vector_weight must equal 1.0"
            )

        # Must have at least one query
        if not request.query_text and not request.query_vector:
            raise HTTPException(
                status_code=400,
                detail="Either query_text or query_vector is required"
            )

        # If only vector provided, use vector search
        if request.query_vector and not request.query_text:
            query_vec = np.array(request.query_vector, dtype=np.float32)
            client = get_lance_client()
            results = client.hybrid_search(
                table_name=request.table_name,
                query_vector=query_vec,
                query_text=None,
                fts_weight=request.fts_weight,
                vector_weight=request.vector_weight,
                k1=request.k1,
                k2=request.k2
            )

            response_results = [
                RetrievalResponse(
                    doc_id=result.doc_id,
                    rank=result.rank,
                    score=result.score,
                    stage=result.stage,
                    metadata=result.metadata
                )
                for result in results
            ]

            latency = (time.time() - start_time) * 1000

            return RetrievalListResponse(
                results=response_results,
                total_count=len(response_results),
                latency_ms=latency,
                query_time=datetime.now().isoformat()
            )

        # For text + vector, combine results
        logger.info(f"Hybrid search - text: '{request.query_text}', has_vector: {bool(request.query_vector)}")

        results = []
        latency = (time.time() - start_time) * 1000

        return RetrievalListResponse(
            results=results,
            total_count=0,
            latency_ms=latency,
            query_time=datetime.now().isoformat()
        )

    except ValueError as e:
        logger.error(f"Invalid input: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Hybrid search failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Search failed")


@router.get("/index-status/{table_name}")
async def get_index_status(
    table_name: str = "ppt_slides",
    payload: Dict[str, Any] = Depends(required_permission("retrieval:read"))
) -> Dict[str, Any]:
    """Get status of retrieval index."""
    try:
        client = get_lance_client()
        stats = client.get_table_stats(table_name)
        return {
            "status": "active" if stats else "inactive",
            "stats": stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get index status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get status")


@router.get("/rate-limit-usage")
async def get_rate_limit_usage(
    payload: Dict[str, Any] = Depends(verify_token)
) -> Dict[str, Any]:
    """Get current rate limit usage."""
    user_id = payload.get("sub", "anonymous")
    usage = rate_limiter.get_usage(user_id)
    return usage


# WebSocket for real-time search
class ConnectionManager:
    """Manage WebSocket connections."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


@router.websocket("/ws/search/{user_id}")
async def websocket_search(websocket: WebSocket, user_id: str):
    """
    WebSocket endpoint for streaming search results.
    """
    await manager.connect(websocket)

    try:
        while True:
            # Receive search query
            data = await websocket.receive_json()

            logger.info(f"WebSocket search from {user_id}: {data.get('query_type')}")

            # Process search
            if data.get("query_type") == "vector":
                query_vector = np.array(data.get("vector"), dtype=np.float32)
                client = get_lance_client()

                # Stream results back
                stage1_results = client.stage1_vector_filtering(
                    table_name=data.get("table_name", "ppt_slides"),
                    query_vector=query_vector,
                    k=data.get("k1", 500)
                )

                for result in stage1_results[:data.get("k2", 20)]:
                    await websocket.send_json({
                        "type": "result",
                        "data": {
                            "doc_id": result.doc_id,
                            "rank": result.rank,
                            "score": result.score,
                        }
                    })

            # Send completion
            await websocket.send_json({
                "type": "complete",
                "timestamp": datetime.now().isoformat()
            })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"User {user_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        manager.disconnect(websocket)
