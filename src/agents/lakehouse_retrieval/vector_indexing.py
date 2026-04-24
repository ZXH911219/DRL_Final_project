"""
Vector Quantization and Indexing Module
Handles 8-bit quantization and IVF/LSH hybrid index construction.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple


class VectorQuantizer:
    """Vector quantization for efficient indexing."""

    def __init__(self, bits: int = 8):
        """Initialize quantizer."""
        self.bits = bits
        self.max_val = (1 << bits) - 1
        self.scales: Dict[str, float] = {}
        self.offsets: Dict[str, float] = {}

    def quantize(self, vectors: np.ndarray, vector_id: str) -> np.ndarray:
        """
        Quantize vectors to 8-bit integers.

        Args:
            vectors: Original vectors (N, D) as float32
            vector_id: Identifier for storing scale/offset

        Returns:
            Quantized vectors (N, D) as uint8
        """
        # Calculate scale and offset
        min_val = np.min(vectors)
        max_val = np.max(vectors)

        scale = (max_val - min_val) / self.max_val if max_val > min_val else 1.0
        offset = min_val

        # Store for later dequantization
        self.scales[vector_id] = scale
        self.offsets[vector_id] = offset

        # Quantize
        quantized = ((vectors - offset) / (scale + 1e-8) * self.max_val).astype(np.uint8)

        return quantized

    def dequantize(self, quantized: np.ndarray, vector_id: str) -> np.ndarray:
        """Dequantize vectors back to float32."""
        scale = self.scales.get(vector_id, 1.0)
        offset = self.offsets.get(vector_id, 0.0)

        dequantized = quantized.astype(np.float32) / self.max_val * scale + offset
        return dequantized


class IndexBuilder:
    """Build IVF/LSH hybrid index for fast retrieval."""

    def __init__(self, num_clusters: int = 100, hash_codes: int = 8):
        """
        Initialize index builder.

        Args:
            num_clusters: Number of IVF clusters
            hash_codes: Number of hash functions for LSH
        """
        self.num_clusters = num_clusters
        self.hash_codes = hash_codes
        self.centroids: Optional[np.ndarray] = None
        self.cluster_assignments: List[List[int]] = [[] for _ in range(num_clusters)]
        self.lsh_tables: List[Dict] = [{} for _ in range(hash_codes)]

    def build_ivf_index(self, vectors: np.ndarray) -> None:
        """
        Build Inverted File (IVF) index using k-means clustering.

        Args:
            vectors: Vector array (N, D)
        """
        from sklearn.cluster import KMeans

        # K-means clustering
        kmeans = KMeans(n_clusters=self.num_clusters, random_state=42, n_init=10)
        assignments = kmeans.fit_predict(vectors)
        self.centroids = kmeans.cluster_centers_

        # Build inverted list
        self.cluster_assignments = [[] for _ in range(self.num_clusters)]
        for idx, cluster_id in enumerate(assignments):
            self.cluster_assignments[cluster_id].append(idx)

    def build_lsh_index(self, vectors: np.ndarray) -> None:
        """
        Build Locality Sensitive Hashing (LSH) index.

        Args:
            vectors: Vector array (N, D)
        """
        for i in range(self.hash_codes):
            # Generate random projection
            np.random.seed(42 + i)
            projection = np.random.randn(vectors.shape[1])
            projection = projection / np.linalg.norm(projection)

            # Compute hash codes
            hash_values = (vectors @ projection) > 0
            self.lsh_tables[i] = {}

            for idx, hash_val in enumerate(hash_values):
                hash_key = int(hash_val)
                if hash_key not in self.lsh_tables[i]:
                    self.lsh_tables[i][hash_key] = []
                self.lsh_tables[i][hash_key].append(idx)

    def query_ivf(self, query: np.ndarray, top_k: int = 100) -> List[int]:
        """
        Query using IVF index.

        Args:
            query: Query vector (D,)
            top_k: Number of results to return

        Returns:
            List of candidate indices
        """
        if self.centroids is None:
            return []

        # Find nearest cluster
        distances = np.linalg.norm(self.centroids - query, axis=1)
        nearest_cluster = np.argmin(distances)

        # Get candidates from nearest cluster
        candidates = self.cluster_assignments[nearest_cluster]
        return candidates[:top_k]

    def query_lsh(self, query: np.ndarray) -> List[int]:
        """
        Query using LSH index.

        Args:
            query: Query vector (D,)

        Returns:
            List of candidate indices
        """
        candidates_set = None

        for i in range(self.hash_codes):
            # Generate random projection
            np.random.seed(42 + i)
            projection = np.random.randn(query.shape[0])
            projection = projection / np.linalg.norm(projection)

            # Compute hash
            hash_val = int((query @ projection) > 0)

            if hash_val in self.lsh_tables[i]:
                bucket = set(self.lsh_tables[i][hash_val])
                if candidates_set is None:
                    candidates_set = bucket
                else:
                    candidates_set |= bucket

        return list(candidates_set) if candidates_set else []


class HybridIndexManager:
    """Manage both IVF and LSH indices."""

    def __init__(self, num_clusters: int = 100):
        """Initialize hybrid index manager."""
        self.quantizer = VectorQuantizer(bits=8)
        self.index_builder = IndexBuilder(num_clusters=num_clusters)
        self.vector_store: Dict[str, np.ndarray] = {}

    def build(self, vectors: np.ndarray) -> None:
        """Build both IVF and LSH indices."""
        # Build IVF
        self.index_builder.build_ivf_index(vectors)

        # Build LSH
        self.index_builder.build_lsh_index(vectors)

    def query_hybrid(
        self, query: np.ndarray, top_k: int = 500
    ) -> Tuple[List[int], str]:
        """
        Query using hybrid IVF + LSH.

        Args:
            query: Query vector (D,)
            top_k: Number of resultsReturns:
            Candidate indices and used strategy
        """
        # Try IVF first (faster)
        ivf_candidates = self.index_builder.query_ivf(query, top_k)

        if len(ivf_candidates) >= top_k:
            return ivf_candidates[:top_k], "IVF"

        # Supplement with LSH
        lsh_candidates = self.index_builder.query_lsh(query)
        all_candidates = list(set(ivf_candidates) | set(lsh_candidates))
        all_candidates = all_candidates[:top_k]

        return all_candidates, "IVF+LSH"
