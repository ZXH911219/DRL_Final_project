"""
Hybrid Retrieval Fusion for Lakehouse-Retrieval-Agent
Combine vector scores and FTS scores using weighted fusion strategy.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import numpy as np


logger = logging.getLogger(__name__)


@dataclass
class HybridRetrievalConfig:
    """Configuration for hybrid retrieval fusion."""

    # Weighting parameters
    vector_weight: float = 0.7  # Weight for vector similarity
    fts_weight: float = 0.3    # Weight for FTS relevance
    
    # Normalization parameters
    normalize_vector_scores: bool = True
    normalize_fts_scores: bool = True
    
    # Score clamping
    min_score: float = 0.0
    max_score: float = 1.0
    
    # Fusion strategy
    fusion_strategy: str = "weighted_sum"  # Options: "weighted_sum", "harmonic_mean", "product"


class ScoreNormalizer:
    """Normalize scores to [0, 1] range."""

    @staticmethod
    def min_max_normalize(scores: np.ndarray) -> np.ndarray:
        """
        Min-max normalization to [0, 1].

        Args:
            scores: Array of scores

        Returns:
            Normalized scores
        """
        if len(scores) == 0:
            return scores

        min_score = np.min(scores)
        max_score = np.max(scores)
        
        if max_score == min_score:
            return np.ones_like(scores) * 0.5

        return (scores - min_score) / (max_score - min_score)

    @staticmethod
    def z_score_normalize(scores: np.ndarray) -> np.ndarray:
        """
        Z-score normalization with clipping to [0, 1].

        Args:
            scores: Array of scores

        Returns:
            Normalized scores (clipped to [0, 1])
        """
        if len(scores) == 0:
            return scores

        mean = np.mean(scores)
        std = np.std(scores)

        if std == 0:
            return np.ones_like(scores) * 0.5

        z_scores = (scores - mean) / std
        # Sigmoid transformation to [0, 1]
        return 1.0 / (1.0 + np.exp(-z_scores))

    @staticmethod
    def sigmoid_normalize(scores: np.ndarray, temperature: float = 1.0) -> np.ndarray:
        """
        Sigmoid normalization to [0, 1].

        Args:
            scores: Array of scores
            temperature: Temperature parameter for sigmoid

        Returns:
            Normalized scores
        """
        return 1.0 / (1.0 + np.exp(-scores / temperature))


class ScoreFusionEngine:
    """Fuse vector and FTS scores using various strategies."""

    def __init__(self, config: HybridRetrievalConfig):
        """Initialize fusion engine."""
        self.config = config
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate configuration."""
        assert (
            abs(self.config.vector_weight + self.config.fts_weight - 1.0) < 1e-6
        ), "Vector and FTS weights must sum to 1.0"
        
        assert (
            self.config.fusion_strategy in ["weighted_sum", "harmonic_mean", "product"]
        ), f"Unknown fusion strategy: {self.config.fusion_strategy}"

    def fuse_scores(
        self,
        vector_scores: List[float],
        fts_scores: Optional[List[float]] = None,
    ) -> List[float]:
        """
        Fuse vector and FTS scores.

        Args:
            vector_scores: List of vector similarity scores
            fts_scores: List of FTS relevance scores (optional)

        Returns:
            List of fused scores
        """
        if not vector_scores:
            return []

        # Convert to numpy arrays
        vec_scores = np.array(vector_scores)

        if fts_scores is None or len(fts_scores) == 0:
            # Pure vector retrieval
            if self.config.normalize_vector_scores:
                vec_scores = ScoreNormalizer.min_max_normalize(vec_scores)
            return np.clip(vec_scores, self.config.min_score, self.config.max_score).tolist()

        fts_scores = np.array(fts_scores)

        # Ensure same length
        assert len(vec_scores) == len(fts_scores), "Score arrays must have same length"

        # Normalize scores
        if self.config.normalize_vector_scores:
            vec_scores = ScoreNormalizer.min_max_normalize(vec_scores)

        if self.config.normalize_fts_scores:
            fts_scores = ScoreNormalizer.min_max_normalize(fts_scores)

        # Apply fusion strategy
        if self.config.fusion_strategy == "weighted_sum":
            fused = (
                self.config.vector_weight * vec_scores
                + self.config.fts_weight * fts_scores
            )

        elif self.config.fusion_strategy == "harmonic_mean":
            # Harmonic mean: 2 / (1/a + 1/b)
            vec_safe = np.where(vec_scores > 0, vec_scores, 1e-6)
            fts_safe = np.where(fts_scores > 0, fts_scores, 1e-6)
            fused = 2.0 / (1.0 / vec_safe + 1.0 / fts_safe)

        elif self.config.fusion_strategy == "product":
            fused = vec_scores * fts_scores

        # Clip to [min, max] range
        fused = np.clip(fused, self.config.min_score, self.config.max_score)

        return fused.tolist()

    def get_strategy_stats(
        self,
        candidates: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        """
        Get statistics for fusion strategy.

        Args:
            candidates: List of retrieval candidates

        Returns:
            Dictionary with stats
        """
        if not candidates:
            return {}

        vec_scores = [c.get("vector_score", 0.0) for c in candidates]
        fts_scores = [c.get("fts_score", 0.0) for c in candidates]
        fused_scores = [c.get("fused_score", 0.0) for c in candidates]

        return {
            "avg_vector_score": float(np.mean(vec_scores)) if vec_scores else 0.0,
            "avg_fts_score": float(np.mean(fts_scores)) if fts_scores else 0.0,
            "avg_fused_score": float(np.mean(fused_scores)) if fused_scores else 0.0,
            "max_vector_score": float(np.max(vec_scores)) if vec_scores else 0.0,
            "max_fts_score": float(np.max(fts_scores)) if fts_scores else 0.0,
            "max_fused_score": float(np.max(fused_scores)) if fused_scores else 0.0,
            "vector_weight": self.config.vector_weight,
            "fts_weight": self.config.fts_weight,
            "fusion_strategy": self.config.fusion_strategy,
        }


class HybridRetriever:
    """Unified hybrid retrieval combining vector and FTS results."""

    def __init__(self, config: Optional[HybridRetrievalConfig] = None):
        """Initialize hybrid retriever."""
        self.config = config or HybridRetrievalConfig()
        self.fusion_engine = ScoreFusionEngine(self.config)

    def combine_results(
        self,
        vector_results: List[Dict[str, Any]],
        fts_results: Optional[List[Dict[str, Any]]] = None,
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Combine vector and FTS retrieval results.

        Args:
            vector_results: Results from vector retrieval
            fts_results: Results from FTS retrieval (optional)
            top_k: Number of top results to return

        Returns:
            Combined and re-ranked results
        """
        if not vector_results:
            return []

        # Create result map
        result_map: Dict[str, Dict[str, Any]] = {}

        # Add vector results
        for i, result in enumerate(vector_results):
            slide_id = result.get("slide_id")
            result_map[slide_id] = {
                **result,
                "vector_score": result.get("score", 0.0),
                "vector_rank": i + 1,
                "fts_score": 0.0,
                "fts_rank": None,
            }

        # Add/merge FTS results
        if fts_results:
            for i, result in enumerate(fts_results):
                slide_id = result.get("slide_id")
                if slide_id in result_map:
                    result_map[slide_id]["fts_score"] = result.get("score", 0.0)
                    result_map[slide_id]["fts_rank"] = i + 1
                else:
                    result_map[slide_id] = {
                        **result,
                        "vector_score": 0.0,
                        "vector_rank": None,
                        "fts_score": result.get("score", 0.0),
                        "fts_rank": i + 1,
                    }

        # Fuse scores
        combined_list = list(result_map.values())
        vec_scores = [r["vector_score"] for r in combined_list]
        fts_scores = [r["fts_score"] for r in combined_list]

        fused_scores = self.fusion_engine.fuse_scores(vec_scores, fts_scores)

        for i, result in enumerate(combined_list):
            result["fused_score"] = fused_scores[i]

        # Sort by fused score
        combined_list.sort(key=lambda x: x["fused_score"], reverse=True)

        # Return top-k
        return combined_list[:top_k]

    def explain_fusion(
        self,
        candidate: Dict[str, Any],
    ) -> str:
        """
        Generate human-readable explanation of fusion.

        Args:
            candidate: Result candidate

        Returns:
            Explanation string
        """
        vec_score = candidate.get("vector_score", 0.0)
        fts_score = candidate.get("fts_score", 0.0)
        fused_score = candidate.get("fused_score", 0.0)

        explanation = (
            f"Slide {candidate.get('slide_id')}: "
            f"Vector={vec_score:.3f} (rank {candidate.get('vector_rank')}), "
            f"FTS={fts_score:.3f} (rank {candidate.get('fts_rank')}), "
            f"Fused={fused_score:.3f} "
            f"(strategy={self.config.fusion_strategy})"
        )

        return explanation

    def get_statistics(
        self,
        combined_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Get statistics for combined results."""
        if not combined_results:
            return {}

        return self.fusion_engine.get_strategy_stats(combined_results)
