"""
Lakehouse-Retrieval-Agent
Main orchestrator for dual-stage vector retrieval pipeline.
"""

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ...utils import get_logger, get_lancedb_manager
from .vector_indexing import HybridIndexManager
from .maxsim_matcher import MaxSimMatcher
from .fts_engine import FTSQueryEngine, KeywordExtractor


class RetrievalResult:
    """Result from retrieval pipeline."""

    def __init__(
        self,
        ranking: List[Dict[str, Any]],
        total_latency_ms: float,
        stage_1_latency_ms: float,
        stage_2_latency_ms: float,
    ):
        """Initialize result."""
        self.ranking = ranking
        self.total_latency_ms = total_latency_ms
        self.stage_1_latency_ms = stage_1_latency_ms
        self.stage_2_latency_ms = stage_2_latency_ms

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "ranking": self.ranking,
            "total_latency_ms": self.total_latency_ms,
            "stage_1_latency_ms": self.stage_1_latency_ms,
            "stage_2_latency_ms": self.stage_2_latency_ms,
        }


class LakehouseRetrievalAgent:
    """Lakehouse-Retrieval-Agent for two-stage vector retrieval."""

    def __init__(self):
        """Initialize agent."""
        self.logger = get_logger("LakehouseRetrievalAgent")
        self.lancedb = get_lancedb_manager()

        # Initialize components
        self.hybrid_index = HybridIndexManager(num_clusters=100)
        self.maxsim_matcher = MaxSimMatcher(batch_size=32)
        self.fts_engine = FTSQueryEngine()
        self.keyword_extractor = KeywordExtractor()

        self.logger.info("LakehouseRetrievalAgent initialized")

    def build_indices(self, vectors: np.ndarray) -> None:
        """
        Build retrieval indices.

        Args:
            vectors: Vector array to index (N, D)
        """
        self.logger.info(f"Building indices for {vectors.shape[0]} vectors...")
        self.hybrid_index.build(vectors)
        self.logger.info("Indices built successfully")

    def retrieve(
        self,
        query_vector: np.ndarray,
        query_text: Optional[str] = None,
        top_k1: int = 500,
        top_k2: int = 20,
        use_fts: bool = True,
        alpha: float = 0.7,
        beta: float = 0.3,
    ) -> Optional[RetrievalResult]:
        """
        Execute two-stage retrieval pipeline.

        Args:
            query_vector: Query embedding (D,)
            query_text: Optional text query
            top_k1: Number of candidates from stage 1
            top_k2: Final results to return
            use_fts: Whether to use FTS filtering
            alpha: Weight for vector score
            beta: Weight for FTS score (if used)

        Returns:
            RetrievalResult or None on error
        """
        import time

        start_time = time.time()
        self.logger.info(f"Starting retrieval: top_k1={top_k1}, top_k2={top_k2}")

        try:
            # Stage 1: Fast filtering
            stage1_start = time.time()
            self.logger.info("Stage 1: Fast vector filtering...")

            candidates_idx, strategy = self.hybrid_index.query_hybrid(query_vector, top_k1)
            stage1_time = (time.time() - stage1_start) * 1000
            self.logger.info(f"Stage 1 completed: {len(candidates_idx)} candidates ({strategy}), {stage1_time:.2f}ms")

            # Optional: FTS filtering
            fts_candidates = None
            if use_fts and query_text:
                self.logger.info("Applying FTS filter...")
                keywords = self.keyword_extractor.extract_keywords(query_text)
                if keywords:
                    fts_candidates = self.fts_engine.search(keywords, mode="OR")
                    self.logger.info(f"FTS returned {len(fts_candidates)} matches")

                    # Intersect with vector candidates
                    if fts_candidates:
                        candidates_set = set(candidates_idx) & fts_candidates
                        candidates_idx = list(candidates_set)[:top_k1]
                        self.logger.info(f"After FTS intersection: {len(candidates_idx)} candidates")

            # Stage 2: MaxSim fine matching
            stage2_start = time.time()
            self.logger.info("Stage 2: MaxSim fine-grained matching...")

            # Get full vectors for candidates
            # (Placeholder: in production, would fetch from vector store)
            max_sim_scores = []
            evidence_list = []

            for idx in candidates_idx[:top_k2]:
                # Generate placeholder multi-vectors for demo
                doc_vectors = np.random.randn(1024, 128).astype(np.float32)
                query_multi = query_vector[:128] if len(query_vector) >= 128 else query_vector

                # If query_vector is single vector, create multi-vector
                if query_multi.shape[0] < 128:
                    query_multi = np.tile(query_multi, (1, 1))[:, :128]

                score, evidence = self.maxsim_matcher.compute_maxsim_scores(
                    query_multi.reshape(1, -1), doc_vectors
                )
                max_sim_scores.append((idx, score, evidence))

            stage2_time = (time.time() - stage2_start) * 1000
            self.logger.info(f"Stage 2 completed: {len(max_sim_scores)} scored, {stage2_time:.2f}ms")

            # Sort and prepare results
            max_sim_scores.sort(key=lambda x: x[1], reverse=True)

            ranking = []
            for rank, (idx, score, evidence) in enumerate(max_sim_scores[:top_k2]):
                ranking.append({
                    "rank": rank + 1,
                    "slide_id": f"slide_{idx}",
                    "retrieval_score": float(score),
                    "evidence_regions": evidence,
                })

            total_time = (time.time() - start_time) * 1000
            self.logger.info(f"Retrieval completed in {total_time:.2f}ms")

            return RetrievalResult(
                ranking=ranking,
                total_latency_ms=total_time,
                stage_1_latency_ms=stage1_time,
                stage_2_latency_ms=stage2_time,
            )

        except Exception as e:
            self.logger.error(f"Retrieval failed: {e}")
            return None


# Global agent instance
_agent: Optional[LakehouseRetrievalAgent] = None


def get_retrieval_agent() -> LakehouseRetrievalAgent:
    """Get or create global Lakehouse-Retrieval-Agent."""
    global _agent
    if _agent is None:
        _agent = LakehouseRetrievalAgent()
    return _agent
