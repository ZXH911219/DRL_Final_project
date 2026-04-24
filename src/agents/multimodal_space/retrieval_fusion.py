"""
Hybrid Retrieval Fusion
Combine vector and FTS search results with configurable fusion.
"""

from typing import Dict, List, Optional, Tuple

import numpy as np


class RetrievalFuser:
    """Fuse results from vector and FTS retrieval."""

    def __init__(self, alpha: float = 0.7, beta: float = 0.3):
        """
        Initialize fusion strategy.

        Args:
            alpha: Weight for vector scores
            beta: Weight for FTS scores
        """
        self.alpha = alpha
        self.beta = beta

    def normalize_scores(self, scores: List[float]) -> List[float]:
        """Normalize scores to [0, 1]."""
        if not scores:
            return []

        min_score = min(scores)
        max_score = max(scores)

        if max_score == min_score:
            return [0.5] * len(scores)

        return [(s - min_score) / (max_score - min_score) for s in scores]

    def fuse_rankings(
        self,
        vector_ranking: List[Dict],
        fts_ranking: Optional[List[Dict]] = None,
    ) -> List[Dict]:
        """
        Fuse vector and FTS rankings.

        Args:
            vector_ranking: List of ranked results from vector search
            fts_ranking: Optional list of ranked results from FTS search

        Returns:
            Fused and re-ranked results
        """
        # Create score map for vector results
        vector_scores = {r["slide_id"]: r.get("score", 0.5) for r in vector_ranking}

        if fts_ranking is None:
            # No FTS results, return vectors as-is
            return sorted(vector_ranking, key=lambda x: x.get("score", 0), reverse=True)

        # Create score map for FTS results
        fts_scores = {r["slide_id"]: r.get("score", 0.5) for r in fts_ranking}

        # Combine results
        all_ids = set(vector_scores.keys()) | set(fts_scores.keys())

        # Normalize scores separately
        vec_values = list(vector_scores.values())
        fts_values = list(fts_scores.values())

        vec_normalized = self.normalize_scores(vec_values)
        fts_normalized = self.normalize_scores(fts_values)

        vec_norm_map = {
            slide_id: vec_normalized[i] for i, slide_id in enumerate(vector_scores.keys())
        }
        fts_norm_map = {
            slide_id: fts_normalized[i] for i, slide_id in enumerate(fts_scores.keys())
        }

        # Compute fused scores
        fused_results = []
        for slide_id in all_ids:
            vec_score = vec_norm_map.get(slide_id, 0.0)
            fts_score = fts_norm_map.get(slide_id, 0.0)

            fused_score = self.alpha * vec_score + self.beta * fts_score

            fused_results.append({
                "slide_id": slide_id,
                "fused_score": fused_score,
                "vector_score": vec_score,
                "fts_score": fts_score,
            })

        # Sort by fused score
        fused_results.sort(key=lambda x: x["fused_score"], reverse=True)

        return fused_results


class DiversityRanker:
    """Promote diversity in rankings (MMR algorithm)."""

    def __init__(self, lambda_param: float = 0.5):
        """
        Initialize diversity ranker.

        Args:
            lambda_param: Balance between relevance (1-λ) and diversity (λ)
        """
        self.lambda_param = lambda_param

    def mmr_rerank(
        self,
        candidates: List[Dict],
        embeddings: np.ndarray,
        top_k: int = 20,
    ) -> List[Dict]:
        """
        Maximal Marginal Relevance reranking.

        Args:
            candidates: List of candidate results
            embeddings: Embedding matrix (N, D)
            top_k: Number of results to return

        Returns:
            Reranked results with diversity
        """
        if not candidates or len(candidates) == 0:
            return []

        selected = []
        remaining_indices = set(range(len(candidates)))

        # Select top-1 by relevance
        best_idx = max(remaining_indices, key=lambda i: candidates[i].get("score", 0))
        selected.append((best_idx, candidates[best_idx].get("score", 0)))
        remaining_indices.remove(best_idx)

        # Greedy selection
        while len(selected) < min(top_k, len(candidates)) and remaining_indices:
            best_mmr_idx = None
            best_mmr_score = -float("inf")

            for idx in remaining_indices:
                # Relevance component
                relevance = candidates[idx].get("score", 0)

                # Diversity component: max distance to selected
                max_distance = 0.0
                for sel_idx, _ in selected:
                    # Cosine similarity
                    if sel_idx < len(embeddings) and idx < len(embeddings):
                        similarity = np.dot(embeddings[sel_idx], embeddings[idx])
                        distance = 1.0 - similarity
                        max_distance = max(max_distance, distance)

                # MMR score
                mmr_score = (1.0 - self.lambda_param) * relevance + self.lambda_param * max_distance

                if mmr_score > best_mmr_score:
                    best_mmr_score = mmr_score
                    best_mmr_idx = idx

            if best_mmr_idx is not None:
                selected.append((best_mmr_idx, candidates[best_mmr_idx].get("score", 0)))
                remaining_indices.remove(best_mmr_idx)

        # Prepare results
        reranked = []
        for rank, (idx, _) in enumerate(selected):
            result = candidates[idx].copy()
            result["mmr_rank"] = rank + 1
            reranked.append(result)

        return reranked


class DeduplicateEngine:
    """Remove duplicate or near-duplicate results."""

    def __init__(self, threshold: float = 0.95):
        """Initialize deduplication."""
        self.threshold = threshold

    def deduplicate(
        self,
        embeddings: np.ndarray,
        candidates: List[Dict],
    ) -> List[Dict]:
        """
        Remove near-duplicates.

        Args:
            embeddings: Embedding matrix
            candidates: Results

        Returns:
            Deduplicated results
        """
        if len(candidates) <= 1:
            return candidates

        filtered = []
        seen_indices = set()

        for i, candidate in enumerate(candidates):
            if i in seen_indices:
                continue

            filtered.append(candidate)

            # Find similar candidates
            for j in range(i + 1, len(candidates)):
                if j in seen_indices:
                    continue

                if i < len(embeddings) and j < len(embeddings):
                    similarity = np.dot(embeddings[i], embeddings[j])

                    if similarity > self.threshold:
                        seen_indices.add(j)

        return filtered
