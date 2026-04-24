"""Unit tests for core models."""

import pytest
import numpy as np
from datetime import datetime
from src.core.models import (
    VisualFeatureBundle,
    RetrievalCandidate,
    VerificationStatus,
    ConfidenceLevel,
)


class TestVisualFeatureBundle:
    """Test VisualFeatureBundle data model."""
    
    def test_create_bundle(self):
        """Test creating a visual feature bundle."""
        vectors = np.random.randn(1024, 128).astype(np.float32)
        imagebind_vec = np.random.randn(1024).astype(np.float32)
        
        bundle = VisualFeatureBundle(
            slide_id="slide_001",
            page_index=0,
            multi_vectors=vectors,
            patch_coordinates=[(i, i) for i in range(1024)],
            imagebind_vector=imagebind_vec,
        )
        
        assert bundle.slide_id == "slide_001"
        assert bundle.multi_vectors.shape == (1024, 128)
        assert bundle.imagebind_vector.shape == (1024,)
        assert len(bundle.patch_coordinates) == 1024


class TestRetrievalCandidate:
    """Test RetrievalCandidate data model."""
    
    def test_create_candidate(self):
        """Test creating a retrieval candidate."""
        candidate = RetrievalCandidate(
            slide_id="slide_042",
            page_index=41,
            maxsim_score=0.92,
            evidence_regions=[(10, 15, 30, 40)],
            retrieval_stage="reranking",
        )
        
        assert candidate.slide_id == "slide_042"
        assert candidate.maxsim_score == 0.92
        assert candidate.retrieval_stage == "reranking"


class TestEnums:
    """Test enum classes."""
    
    def test_verification_status(self):
        """Test VerificationStatus enum."""
        assert VerificationStatus.PASS.value == "pass"
        assert VerificationStatus.WARN.value == "warn"
        assert VerificationStatus.FAIL.value == "fail"
    
    def test_confidence_level(self):
        """Test ConfidenceLevel enum."""
        assert ConfidenceLevel.HIGH.value == "high"
        assert ConfidenceLevel.MEDIUM.value == "medium"
        assert ConfidenceLevel.LOW.value == "low"


if __name__ == "__main__":
    pytest.main([__file__])
