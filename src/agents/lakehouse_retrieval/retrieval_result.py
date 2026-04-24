"""
Retrieval Result Output Interface for Lakehouse-Retrieval-Agent
Standardized output structures for retrieval results with full metadata.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import json


@dataclass
class EvidenceRegion:
    """Evidence region in retrieval result."""

    patch_coords: Tuple[int, int, int, int]  # [top_left_x, top_left_y, bottom_right_x, bottom_right_y]
    region_type: str  # "text", "chart", "image", "other"
    confidence: float  # [0.0, 1.0]
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class RetrievalCandidate:
    """Single retrieval candidate result."""

    slide_id: str
    page_index: int
    source_path: str
    
    # Retrieval scores
    vector_score: float  # MaxSim score from Lakehouse
    fts_score: Optional[float] = None  # FTS relevance score
    fused_score: float = 0.0  # Hybrid fusion score
    
    # Ranking information
    retrieval_rank: int = 0  # Original retrieval rank
    final_rank: int = 0  # Final rank after all processing
    
    # Fusion details
    fusion_strategy: Optional[str] = None
    vector_weight: Optional[float] = None
    fts_weight: Optional[float] = None
    
    # Diversity information
    diversity_score: Optional[float] = None
    mmr_rank: Optional[int] = None
    
    # Evidence and explanation
    evidence_regions: List[EvidenceRegion] = None
    key_evidence_phrases: List[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = None
    timestamp: str = ""

    def __post_init__(self):
        """Initialize defaults."""
        if self.evidence_regions is None:
            self.evidence_regions = []
        if self.key_evidence_phrases is None:
            self.key_evidence_phrases = []
        if self.metadata is None:
            self.metadata = {}
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["evidence_regions"] = [r.to_dict() if isinstance(r, EvidenceRegion) else r for r in self.evidence_regions]
        return data

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class RetrievalMetadata:
    """Metadata about retrieval operation."""

    query_id: str
    query_type: str  # "vector", "fts", "hybrid"
    timestamp: str
    
    # Latencies
    total_latency_ms: float
    stage_1_latency_ms: float  # Fast filtering
    stage_2_latency_ms: float  # Fine-grained matching
    fusion_latency_ms: float = 0.0
    
    # Statistics
    total_candidates_examined: int = 0
    candidates_after_stage_1: int = 0
    final_results_count: int = 0
    
    # Quality metrics
    recall_at_k: Dict[int, float] = None  # {10: 0.92, 20: 0.95}
    mrr: float = 0.0  # Mean Reciprocal Rank
    ndcg: float = 0.0  # NDCG@10
    
    # Configuration
    fusion_strategy: Optional[str] = None
    vector_weight: Optional[float] = None
    fts_weight: Optional[float] = None
    mmr_lambda: Optional[float] = None

    def __post_init__(self):
        """Initialize defaults."""
        if self.recall_at_k is None:
            self.recall_at_k = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class RetrievalResult:
    """Complete retrieval result with all metadata."""

    def __init__(
        self,
        candidates: List[RetrievalCandidate],
        metadata: RetrievalMetadata,
    ):
        """
        Initialize retrieval result.

        Args:
            candidates: List of retrieval candidates
            metadata: Retrieval operation metadata
        """
        self.candidates = candidates
        self.metadata = metadata

    def get_top_k(self, k: int = 10) -> List[RetrievalCandidate]:
        """
        Get top-k results.

        Args:
            k: Number of results

        Returns:
            Top-k candidates
        """
        return self.candidates[:k]

    def get_by_rank(self, rank: int) -> Optional[RetrievalCandidate]:
        """
        Get result by rank.

        Args:
            rank: Rank number (1-indexed)

        Returns:
            Candidate at rank or None
        """
        if 0 < rank <= len(self.candidates):
            return self.candidates[rank - 1]
        return None

    def filter_by_score(self, min_score: float = 0.5) -> List[RetrievalCandidate]:
        """
        Filter results by minimum score.

        Args:
            min_score: Minimum fused score threshold

        Returns:
            Filtered candidates
        """
        return [c for c in self.candidates if c.fused_score >= min_score]

    def filter_by_source(self, source_pattern: str) -> List[RetrievalCandidate]:
        """
        Filter results by source path pattern.

        Args:
            source_pattern: Glob pattern for source paths

        Returns:
            Filtered candidates
        """
        from fnmatch import fnmatch

        return [
            c for c in self.candidates
            if fnmatch(c.source_path, source_pattern)
        ]

    def get_summary(self) -> Dict[str, Any]:
        """
        Get result summary.

        Returns:
            Summary dictionary
        """
        return {
            "query_id": self.metadata.query_id,
            "total_results": len(self.candidates),
            "top_score": self.candidates[0].fused_score if self.candidates else 0.0,
            "avg_score": (
                sum(c.fused_score for c in self.candidates) / len(self.candidates)
                if self.candidates
                else 0.0
            ),
            "latency_ms": self.metadata.total_latency_ms,
            "mrr": self.metadata.mrr,
            "ndcg": self.metadata.ndcg,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "candidates": [c.to_dict() for c in self.candidates],
            "metadata": self.metadata.to_dict(),
            "summary": self.get_summary(),
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_compact_json(self) -> str:
        """Convert to compact JSON (single line)."""
        return json.dumps(self.to_dict())

    def save_to_file(self, filepath: str) -> None:
        """
        Save result to JSON file.

        Args:
            filepath: Output file path
        """
        with open(filepath, "w") as f:
            f.write(self.to_json())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RetrievalResult":
        """
        Create from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            RetrievalResult instance
        """
        # Parse candidates
        candidates = []
        for cand_data in data.get("candidates", []):
            evidence_regions = [
                EvidenceRegion(**r) for r in cand_data.get("evidence_regions", [])
            ]
            cand = RetrievalCandidate(
                **{
                    **cand_data,
                    "evidence_regions": evidence_regions,
                }
            )
            candidates.append(cand)

        # Parse metadata
        metadata = RetrievalMetadata(**data.get("metadata", {}))

        return cls(candidates, metadata)

    @classmethod
    def from_json(cls, json_str: str) -> "RetrievalResult":
        """
        Create from JSON string.

        Args:
            json_str: JSON representation

        Returns:
            RetrievalResult instance
        """
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def load_from_file(cls, filepath: str) -> "RetrievalResult":
        """
        Load from JSON file.

        Args:
            filepath: Input file path

        Returns:
            RetrievalResult instance
        """
        with open(filepath) as f:
            json_str = f.read()
        return cls.from_json(json_str)

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"RetrievalResult(candidates={len(self.candidates)}, "
            f"latency={self.metadata.total_latency_ms:.1f}ms, "
            f"mrr={self.metadata.mrr:.3f})"
        )

    def __len__(self) -> int:
        """Number of results."""
        return len(self.candidates)

    def __getitem__(self, index: int) -> RetrievalCandidate:
        """Get result by index."""
        return self.candidates[index]

    def __iter__(self):
        """Iterate over results."""
        return iter(self.candidates)


def create_retrieval_result_example() -> RetrievalResult:
    """Create an example retrieval result for testing."""
    candidates = [
        RetrievalCandidate(
            slide_id="ppt_001_slide_05",
            page_index=5,
            source_path="/data/ppts/finance_101.pptx",
            vector_score=0.92,
            fts_score=0.85,
            fused_score=0.90,
            retrieval_rank=1,
            final_rank=1,
            fusion_strategy="weighted_sum",
            vector_weight=0.7,
            fts_weight=0.3,
            diversity_score=1.0,
            mmr_rank=1,
            evidence_regions=[
                EvidenceRegion(
                    patch_coords=(10, 5, 30, 20),
                    region_type="text",
                    confidence=0.95,
                    description="Title: 'Portfolio Risk Analysis'",
                ),
                EvidenceRegion(
                    patch_coords=(35, 25, 60, 50),
                    region_type="chart",
                    confidence=0.88,
                    description="Risk distribution chart",
                ),
            ],
            key_evidence_phrases=[
                "Portfolio Risk Analysis",
                "Variance-Covariance method",
                "VaR calculation",
            ],
            metadata={
                "slide_title": "Portfolio Risk Analysis",
                "content_category": "Finance",
            },
        ),
        RetrievalCandidate(
            slide_id="ppt_002_slide_12",
            page_index=12,
            source_path="/data/ppts/ai_applications.pptx",
            vector_score=0.85,
            fts_score=0.78,
            fused_score=0.83,
            retrieval_rank=2,
            final_rank=2,
            fusion_strategy="weighted_sum",
            vector_weight=0.7,
            fts_weight=0.3,
            diversity_score=0.85,
            mmr_rank=2,
            key_evidence_phrases=[
                "Machine Learning",
                "Risk prediction",
            ],
        ),
    ]

    metadata = RetrievalMetadata(
        query_id="query_20240424_001",
        query_type="hybrid",
        timestamp=datetime.now().isoformat(),
        total_latency_ms=145.5,
        stage_1_latency_ms=45.2,
        stage_2_latency_ms=98.3,
        fusion_latency_ms=2.0,
        total_candidates_examined=1000,
        candidates_after_stage_1=500,
        final_results_count=2,
        recall_at_k={10: 0.92, 20: 0.95},
        mrr=0.88,
        ndcg=0.91,
        fusion_strategy="weighted_sum",
        vector_weight=0.7,
        fts_weight=0.3,
        mmr_lambda=0.5,
    )

    return RetrievalResult(candidates, metadata)
