"""
MaxSim Late Interaction Algorithm
Implements fine-grained similarity matching using MaxSim.
"""

import numpy as np
from typing import List, Tuple


class MaxSimMatcher:
    """MaxSim algorithm for late interaction matching."""

    def __init__(self, batch_size: int = 32):
        """Initialize matcher."""
        self.batch_size = batch_size

    def compute_maxsim_scores(
        self,
        query_vectors: np.ndarray,
        doc_vectors: np.ndarray,
    ) -> Tuple[float, List[int]]:
        """
        Compute MaxSim score between query and document.

        MaxSim(q, d) = mean(max_j(sim(q_i, d_j)) for each q_i)

        Args:
            query_vectors: Query multi-vectors (Q, 128)
            doc_vectors: Document multi-vectors (1024, 128)

        Returns:
            Score and evidence regions (top 5 matching patches)
        """
        if query_vectors.shape[0] == 0 or doc_vectors.shape[0] == 0:
            return 0.0, []

        # Compute similarity matrix (Q, 1024)
        # Use cosine similarity
        query_norm = query_vectors / (np.linalg.norm(query_vectors, axis=1, keepdims=True) + 1e-8)
        doc_norm = doc_vectors / (np.linalg.norm(doc_vectors, axis=1, keepdims=True) + 1e-8)

        similarity_matrix = query_norm @ doc_norm.T  # (Q, 1024)

        # MaxSim: for each query vector, find max similarity
        max_sims = np.max(similarity_matrix, axis=1)  # (Q,)

        # Final score: mean of max similarities
        score = float(np.mean(max_sims))

        # Evidence regions: patches with highest scores
        evidence = []
        for q_idx in range(query_vectors.shape[0]):
            max_idx = np.argmax(similarity_matrix[q_idx])
            max_score = similarity_matrix[q_idx, max_idx]
            evidence.append((q_idx, max_idx, float(max_score)))

        # Sort by score and return top 5
        evidence.sort(key=lambda x: x[2], reverse=True)
        top_evidence = [e[1] for e in evidence[:5]]  # Patch indices

        return score, top_evidence

    def batch_compute_maxsim(
        self,
        query_vectors: np.ndarray,
        doc_vectors_list: List[np.ndarray],
    ) -> List[Tuple[float, List[int]]]:
        """
        Compute MaxSim scores for batch of documents.

        Args:
            query_vectors: Query multi-vectors (Q, 128)
            doc_vectors_list: List of document multi-vectors

        Returns:
            List of (score, evidence_regions) tuples
        """
        results = []
        for doc_vectors in doc_vectors_list:
            score, evidence = self.compute_maxsim_scores(query_vectors, doc_vectors)
            results.append((score, evidence))
        return results
