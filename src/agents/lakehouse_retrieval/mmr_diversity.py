"""
MMR (Maximal Marginal Relevance) Diversity Ranking for Lakehouse-Retrieval-Agent
Rerank results to maximize diversity while maintaining relevance.
"""

import logging
from typing import List, Dict, Any, Optional
import numpy as np
from scipy.spatial.distance import cosine


logger = logging.getLogger(__name__)


class MaximalMarginalRelevanceRanker:
    """Implement MMR diversity reranking."""

    def __init__(self, lambda_factor: float = 0.5):
        """
        Initialize MMR ranker.

        Args:
            lambda_factor: Parameter balancing relevance vs diversity (0-1)
                          lambda=1: pure relevance
                          lambda=0: pure diversity
        """
        self.lambda_factor = lambda_factor

    def rerank_by_mmr(
        self,
        candidates: List[Dict[str, Any]],
        vector_field: str = "vector",
        score_field: str = "fused_score",
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Rerank candidates using MMR.

        Args:
            candidates: List of retrieval candidates (must have vectors)
            vector_field: Name of field containing vectors
            score_field: Name of field containing relevance scores
            top_k: Number of results to return

        Returns:
            Reranked candidates
        """
        if not candidates or len(candidates) == 0:
            return []

        if top_k is None:
            top_k = len(candidates)

        logger.info(f"Applying MMR reranking (lambda={self.lambda_factor})")

        # Extract vectors and initial scores
        vectors = []
        valid_indices = []

        for i, cand in enumerate(candidates):
            if vector_field in cand and cand[vector_field] is not None:
                try:
                    vec = np.array(cand[vector_field], dtype=np.float32)
                    if vec.size > 0:
                        # Normalize vector
                        vec = vec / (np.linalg.norm(vec) + 1e-10)
                        vectors.append(vec)
                        valid_indices.append(i)
                except Exception as e:
                    logger.warning(f"Failed to process vector for candidate {i}: {str(e)}")

        if len(vectors) == 0:
            logger.warning("No valid vectors found, returning original ranking")
            return candidates[:top_k]

        vectors = np.array(vectors)
        initial_scores = np.array(
            [candidates[i].get(score_field, 0.0) for i in valid_indices]
        )

        # Normalize initial scores to [0, 1]
        if np.max(initial_scores) > 1.0:
            initial_scores = initial_scores / (np.max(initial_scores) + 1e-10)

        # Initialize selected set (greedy MMR)
        selected_indices = []
        remaining_indices = set(range(len(vectors)))

        # Select top-k results using MMR
        for _ in range(min(top_k, len(vectors))):
            if not remaining_indices:
                break

            # Compute MMR scores for remaining candidates
            mmr_scores = {}

            for idx in remaining_indices:
                # Relevance score
                relevance = initial_scores[idx]

                # Diversity score (similarity to already selected)
                if selected_indices:
                    max_similarity = max(
                        [
                            self._cosine_similarity(vectors[idx], vectors[sel])
                            for sel in selected_indices
                        ]
                    )
                else:
                    max_similarity = 0.0

                # MMR = λ * relevance - (1-λ) * max_similarity
                mmr_score = (
                    self.lambda_factor * relevance
                    - (1 - self.lambda_factor) * max_similarity
                )

                mmr_scores[idx] = mmr_score

            # Select candidate with highest MMR score
            best_idx = max(mmr_scores, key=mmr_scores.get)
            selected_indices.append(best_idx)
            remaining_indices.remove(best_idx)

        # Build reranked result list
        reranked = []
        for rank, sel_idx in enumerate(selected_indices):
            original_idx = valid_indices[sel_idx]
            result = candidates[original_idx].copy()
            result["mmr_rank"] = rank + 1
            result["mmr_score"] = initial_scores[sel_idx].item()
            reranked.append(result)

        logger.info(f"MMR reranking complete. Selected {len(reranked)} diverse results")
        return reranked

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Compute cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score [0, 1]
        """
        try:
            similarity = 1 - cosine(vec1, vec2)
            return max(0.0, min(1.0, similarity))
        except Exception:
            return 0.0

    def explain_mmr(
        self,
        original_ranking: List[Dict[str, Any]],
        mmr_ranking: List[Dict[str, Any]],
    ) -> str:
        """
        Generate explanation of MMR reranking.

        Args:
            original_ranking: Original ranking
            mmr_ranking: MMR reranked result

        Returns:
            Explanation string
        """
        explanation = (
            f"MMR Reranking (λ={self.lambda_factor}):\n"
            f"  Original ranking: {len(original_ranking)} results\n"
            f"  Reranked results: {len(mmr_ranking)} results\n"
            f"  Strategy: Maximize relevance (λ) while minimizing similarity (1-λ)\n"
        )

        if mmr_ranking:
            top_reranked = mmr_ranking[0]
            explanation += (
                f"  Top result: Slide {top_reranked.get('slide_id')} "
                f"(MMR score: {top_reranked.get('mmr_score', 0.0):.3f})\n"
            )

        return explanation


class DiversityOptimizer:
    """Optimize diversity in retrieval results."""

    @staticmethod
    def compute_diversity_score(
        candidates: List[Dict[str, Any]],
        vector_field: str = "vector",
    ) -> float:
        """
        Compute average pairwise diversity.

        Args:
            candidates: List of candidates
            vector_field: Name of vector field

        Returns:
            Average diversity score [0, 1]
        """
        vectors = []

        for cand in candidates:
            if vector_field in cand and cand[vector_field] is not None:
                try:
                    vec = np.array(cand[vector_field], dtype=np.float32)
                    vec = vec / (np.linalg.norm(vec) + 1e-10)
                    vectors.append(vec)
                except Exception:
                    pass

        if len(vectors) < 2:
            return 0.0

        vectors = np.array(vectors)

        # Compute pairwise distances
        total_distance = 0.0
        count = 0

        for i in range(len(vectors)):
            for j in range(i + 1, len(vectors)):
                dist = cosine(vectors[i], vectors[j])
                total_distance += dist
                count += 1

        avg_diversity = total_distance / count if count > 0 else 0.0

        # Normalize to [0, 1] (max distance is 2 for cosine)
        return min(1.0, avg_diversity / 2.0)

    @staticmethod
    def apply_diversity_penalty(
        candidates: List[Dict[str, Any]],
        cluster_field: str = "source_category",
        penalty_factor: float = 0.1,
    ) -> None:
        """
        Apply penalty to candidates from same cluster.

        Args:
            candidates: List of candidates
            cluster_field: Field grouping candidates by cluster
            penalty_factor: Penalty multiplier per cluster duplicate
        """
        cluster_counts = {}

        for cand in candidates:
            cluster = cand.get(cluster_field, "unknown")
            cluster_counts[cluster] = cluster_counts.get(cluster, 0) + 1

        # Apply penalty
        for cand in candidates:
            cluster = cand.get(cluster_field, "unknown")
            count = cluster_counts[cluster]

            if count > 1:
                original_score = cand.get("fused_score", 0.5)
                penalty = penalty_factor * (count - 1)
                cand["diversity_adjusted_score"] = max(0.0, original_score - penalty)
                cand["cluster_penalty"] = penalty
            else:
                cand["diversity_adjusted_score"] = cand.get("fused_score", 0.5)
                cand["cluster_penalty"] = 0.0


class SimplicityFirstRanker:
    """Alternative simpler ranking strategy for comparison."""

    @staticmethod
    def rank_by_relevance_only(
        candidates: List[Dict[str, Any]],
        score_field: str = "fused_score",
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Simple relevance-based ranking.

        Args:
            candidates: List of candidates
            score_field: Relevance score field
            top_k: Number of results

        Returns:
            Ranked candidates
        """
        ranked = sorted(
            candidates,
            key=lambda x: x.get(score_field, 0.0),
            reverse=True,
        )

        if top_k:
            ranked = ranked[:top_k]

        for i, cand in enumerate(ranked):
            cand["simple_rank"] = i + 1

        return ranked

    @staticmethod
    def rank_by_source_balance(
        candidates: List[Dict[str, Any]],
        source_field: str = "source",
        max_per_source: int = 3,
        score_field: str = "fused_score",
    ) -> List[Dict[str, Any]]:
        """
        Rank while balancing sources.

        Args:
            candidates: List of candidates
            source_field: Field identifying source
            max_per_source: Max results per source
            score_field: Relevance score field

        Returns:
            Balanced ranking
        """
        # Sort by score first
        sorted_cands = sorted(
            candidates,
            key=lambda x: x.get(score_field, 0.0),
            reverse=True,
        )

        source_count = {}
        balanced = []

        for cand in sorted_cands:
            source = cand.get(source_field, "unknown")
            count = source_count.get(source, 0)

            if count < max_per_source:
                balanced.append(cand)
                source_count[source] = count + 1

        for i, cand in enumerate(balanced):
            cand["balanced_rank"] = i + 1

        return balanced
