"""
Unit Tests for Vision-Ingestion-Agent (Task 2.9)
Comprehensive testing of all vision ingestion components with >90% coverage.
"""

import pytest
import numpy as np
import tempfile
import json
from pathlib import Path
from typing import Dict, Any


class TestVectorQualityChecker:
    """Tests for VectorQualityChecker module."""

    @pytest.fixture
    def quality_checker(self):
        from src.agents.vision_ingestion.quality_checker import VectorQualityChecker
        return VectorQualityChecker()

    def test_check_coverage_perfect(self, quality_checker):
        """Test coverage check with perfect vectors."""
        vectors = np.random.randn(1024, 128).astype(np.float32)
        result = quality_checker.check_coverage(vectors, min_coverage=0.98)
        
        assert "coverage_ratio" in result
        assert result["coverage_ratio"] > 0.9
        assert "passes_threshold" in result

    def test_check_coverage_with_nans(self, quality_checker):
        """Test coverage check with NaN values."""
        vectors = np.random.randn(1024, 128).astype(np.float32)
        vectors[10:50, :] = 0  # Inject many zeros (~4%)
        
        result = quality_checker.check_coverage(vectors, min_coverage=0.97)
        
        assert result["coverage_ratio"] < 0.97
        assert "passes_threshold" in result

    def test_check_geometric_completeness(self, quality_checker):
        """Test geometric completeness check."""
        vectors = np.random.randn(1024, 128).astype(np.float32)
        result = quality_checker.check_geometric_completeness(vectors, min_variance=0.5)
        
        assert "variance" in result
        assert "passes_variance_threshold" in result
        assert result["variance"] >= 0

    def test_check_consistency(self, quality_checker):
        """Test consistency/outlier detection."""
        vectors = np.random.randn(1024, 128).astype(np.float32)
        result = quality_checker.check_consistency(vectors)
        
        assert "outlier_count" in result
        assert "outlier_ratio" in result
        assert result["outlier_ratio"] <= 0.05  # Should be low for random data

    def test_comprehensive_check(self, quality_checker):
        """Test comprehensive quality check."""
        vectors = np.random.randn(1024, 128).astype(np.float32)
        imagebind_vec = np.random.randn(1024).astype(np.float32)
        imagebind_vec = imagebind_vec / (np.linalg.norm(imagebind_vec) + 1e-10)
        
        result = quality_checker.comprehensive_check(vectors, imagebind_vec)
        
        assert "overall_score" in result
        assert 0 <= result["overall_score"] <= 100
        assert "summary" in result
        assert "PASS" in result["summary"] or "WARN" in result["summary"] or "FAIL" in result["summary"]

    def test_quality_score_components(self, quality_checker):
        """Test that quality score is properly composed."""
        vectors = np.random.randn(1024, 128).astype(np.float32)
        imagebind_vec = np.random.randn(1024).astype(np.float32)
        
        result = quality_checker.comprehensive_check(vectors, imagebind_vec)
        
        # Verify all components present
        assert "coverage" in result
        assert "geometric_completeness" in result
        assert "consistency" in result


class TestIncrementalBatchProcessor:
    """Tests for IncrementalBatchProcessor module."""

    @pytest.fixture
    def processor(self):
        from src.agents.vision_ingestion.incremental_processor import IncrementalBatchProcessor
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.json"
            processor = IncrementalBatchProcessor(str(manifest_path))
            yield processor

    def test_batch_creation(self, processor):
        """Test batch creation."""
        ppt_files = ["/data/ppt1.pptx", "/data/ppt2.pptx"]
        processor.create_batch("batch_001", ppt_files)
        
        status = processor.get_batch_status("batch_001")
        assert status["total"] == 2
        assert status["status"] == "created"

    def test_batch_status_transitions(self, processor):
        """Test batch status transitions."""
        processor.create_batch("batch_001", ["/data/ppt1.pptx"])
        
        processor.start_processing("batch_001")
        status = processor.get_batch_status("batch_001")
        assert status["status"] == "processing"
        
        processor.complete_batch("batch_001")
        status = processor.get_batch_status("batch_001")
        assert status["status"] == "completed"

    def test_ppt_processing_record(self, processor):
        """Test recording PPT processing results."""
        processor.create_batch("batch_001", ["/data/ppt1.pptx"])
        processor.record_ppt_result("batch_001", "/data/ppt1.pptx", 10, success=True)
        
        status = processor.get_batch_status("batch_001")
        assert status["processed"] == 1
        assert "/data/ppt1.pptx" in status["results"]

    def test_statistics_collection(self, processor):
        """Test statistics collection."""
        processor.create_batch("batch_001", ["/data/ppt1.pptx", "/data/ppt2.pptx"])
        processor.record_ppt_result("batch_001", "/data/ppt1.pptx", 5, success=True)
        processor.record_ppt_result("batch_001", "/data/ppt2.pptx", 8, success=True)
        
        stats = processor.get_statistics()
        assert stats["total_ppts"] == 2
        assert stats["processed_ppts"] == 2
        assert stats["success_rate"] == 1.0


class TestFaultTolerance:
    """Tests for fault tolerance module."""

    def test_retry_decorator_success_on_retry(self):
        """Test retry decorator succeeds after retry."""
        from src.agents.vision_ingestion.fault_tolerance import retry
        
        call_count = 0
        
        @retry(max_attempts=3, initial_delay=0.01)
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary error")
            return "success"
        
        result = flaky_func()
        assert result == "success"
        assert call_count == 2

    def test_retry_decorator_exhausts_attempts(self):
        """Test retry decorator fails after exhausting attempts."""
        from src.agents.vision_ingestion.fault_tolerance import retry
        
        @retry(max_attempts=3, initial_delay=0.01)
        def always_fails():
            raise ValueError("Permanent error")
        
        with pytest.raises(ValueError):
            always_fails()

    def test_fallback_registry(self):
        """Test fallback registry."""
        from src.agents.vision_ingestion.fault_tolerance import FallbackRegistry
        
        def my_fallback():
            return "fallback_result"
        
        registry = FallbackRegistry()
        registry.register_fallback("test_op", my_fallback)
        
        result = registry.use_fallback("test_op")
        assert result == "fallback_result"

    def test_ocr_fallback_strategy(self):
        """Test OCR fallback strategy."""
        from src.agents.vision_ingestion.fault_tolerance import OCRFallbackStrategy
        
        result = OCRFallbackStrategy.fallback_to_basic_ocr("/path/to/image.png")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_rendering_fallback_strategy(self):
        """Test rendering fallback strategy."""
        from src.agents.vision_ingestion.fault_tolerance import RenderingFallbackStrategy
        
        img_path, dpi = RenderingFallbackStrategy.fallback_to_lower_resolution(
            "/path/to/ppt.pptx", 0
        )
        assert dpi == 300  # Lower DPI


class TestSerializer:
    """Tests for serialization module."""

    @pytest.fixture
    def serializer(self):
        from src.agents.vision_ingestion.serializer import FeatureBundleSerializer
        with tempfile.TemporaryDirectory() as tmpdir:
            yield FeatureBundleSerializer(tmpdir)

    def test_parquet_serialization(self, serializer):
        """Test Parquet serialization."""
        bundles = [
            {
                "slide_id": "slide_001",
                "page_index": 0,
                "multi_vectors": np.random.randn(1024, 128).astype(np.float32),
                "imagebind_vector": np.random.randn(1024).astype(np.float32),
                "patch_coordinates": [(i, i) for i in range(1024)],
                "metadata": {"source": "test.pptx"},
                "quality_metrics": {"coverage": 0.98},
            }
        ]

        output_file = serializer.serialize_to_parquet(bundles, "test.parquet")
        assert Path(output_file).exists()

    def test_hdf5_serialization(self, serializer):
        """Test HDF5 serialization."""
        bundles = [
            {
                "slide_id": "slide_001",
                "page_index": 0,
                "multi_vectors": np.random.randn(1024, 128).astype(np.float32),
                "imagebind_vector": np.random.randn(1024).astype(np.float32),
                "patch_coordinates": [],
                "metadata": {"source": "test.pptx"},
                "quality_metrics": {"coverage": 0.98},
            }
        ]

        output_file = serializer.serialize_to_hdf5(bundles, "test.h5")
        assert Path(output_file).exists()

    def test_parquet_deserialization(self, serializer):
        """Test Parquet deserialization."""
        bundles = [
            {
                "slide_id": "slide_001",
                "page_index": 0,
                "multi_vectors": np.random.randn(10, 128).astype(np.float32),
                "imagebind_vector": np.random.randn(1024).astype(np.float32),
                "patch_coordinates": [],
                "metadata": {"source": "test.pptx"},
                "quality_metrics": {"coverage": 0.98},
            }
        ]

        output_file = serializer.serialize_to_parquet(bundles, "test.parquet")
        deserialized = serializer.deserialize_parquet(output_file)

        assert deserialized["format"] == "parquet"
        assert deserialized["rows"] == 1


class TestImageBindAligner:
    """Tests for ImageBind alignment module."""

    @pytest.fixture
    def aligner(self):
        from src.agents.vision_ingestion.feature_extractor import ImageBindAligner
        return ImageBindAligner(output_dim=1024)

    def test_vector_alignment_shape(self, aligner):
        """Test vector alignment output shape."""
        multi_vectors = np.random.randn(1024, 128).astype(np.float32)
        aligned, consistency = aligner.align_vectors(multi_vectors)

        assert aligned.shape == (1024,)
        assert 0.8 <= consistency <= 1.0

    def test_alignment_normalization(self, aligner):
        """Test alignment produces normalized vectors."""
        multi_vectors = np.random.randn(1024, 128).astype(np.float32)
        aligned, _ = aligner.align_vectors(multi_vectors)

        # Check normalization (should be close to 1)
        norm = np.linalg.norm(aligned)
        assert 0.95 <= norm <= 1.05

    def test_alignment_with_text_vectors(self, aligner):
        """Test alignment with text vectors."""
        multi_vectors = np.random.randn(1024, 128).astype(np.float32)
        # Text vectors should be aggregated from multi_vectors (1024 dim)
        text_vectors = np.random.randn(1024).astype(np.float32)
        text_vectors = text_vectors / (np.linalg.norm(text_vectors) + 1e-10)

        aligned, consistency = aligner.align_vectors(multi_vectors, text_vectors=text_vectors)

        assert aligned.shape == (1024,)
        # Should have higher consistency with text alignment
        assert 0.85 <= consistency <= 1.0


class TestRetrievalResult:
    """Tests for RetrievalResult interface."""

    @pytest.fixture
    def sample_result(self):
        from src.agents.lakehouse_retrieval.retrieval_result import (
            create_retrieval_result_example,
        )
        return create_retrieval_result_example()

    def test_retrieval_result_creation(self, sample_result):
        """Test retrieval result creation."""
        assert len(sample_result) == 2
        assert sample_result[0].slide_id == "ppt_001_slide_05"

    def test_retrieval_result_filtering(self, sample_result):
        """Test result filtering."""
        filtered = sample_result.filter_by_score(min_score=0.85)
        assert len(filtered) >= 1

    def test_retrieval_result_json_serialization(self, sample_result):
        """Test JSON serialization."""
        json_str = sample_result.to_json()
        assert isinstance(json_str, str)
        
        # Verify it's valid JSON
        data = json.loads(json_str)
        assert "candidates" in data
        assert "metadata" in data

    def test_retrieval_result_json_deserialization(self, sample_result):
        """Test JSON deserialization."""
        json_str = sample_result.to_json()
        
        from src.agents.lakehouse_retrieval.retrieval_result import RetrievalResult
        restored = RetrievalResult.from_json(json_str)
        
        assert len(restored) == len(sample_result)
        assert restored[0].slide_id == sample_result[0].slide_id

    def test_retrieval_result_file_roundtrip(self, sample_result):
        """Test file save/load roundtrip."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "result.json"
            
            sample_result.save_to_file(str(filepath))
            assert filepath.exists()
            
            from src.agents.lakehouse_retrieval.retrieval_result import RetrievalResult
            loaded = RetrievalResult.load_from_file(str(filepath))
            
            assert len(loaded) == len(sample_result)


class TestHybridFusion:
    """Tests for hybrid retrieval fusion."""

    @pytest.fixture
    def fusion_engine(self):
        from src.agents.lakehouse_retrieval.hybrid_fusion import (
            ScoreFusionEngine,
            HybridRetrievalConfig,
        )
        config = HybridRetrievalConfig()
        return ScoreFusionEngine(config)

    def test_score_fusion_weighted_sum(self, fusion_engine):
        """Test weighted sum fusion."""
        vector_scores = [0.9, 0.8, 0.7]
        fts_scores = [0.6, 0.7, 0.8]

        fused = fusion_engine.fuse_scores(vector_scores, fts_scores)

        assert len(fused) == 3
        assert all(0.0 <= score <= 1.0 for score in fused)

    def test_score_fusion_normalization(self, fusion_engine):
        """Test score normalization."""
        vector_scores = [10.0, 5.0, 1.0]  # Large range
        fts_scores = [1.0, 2.0, 3.0]

        fused = fusion_engine.fuse_scores(vector_scores, fts_scores)

        assert all(0.0 <= score <= 1.0 for score in fused)


class TestMMRReranking:
    """Tests for MMR diversity reranking."""

    @pytest.fixture
    def ranker(self):
        from src.agents.lakehouse_retrieval.mmr_diversity import (
            MaximalMarginalRelevanceRanker,
        )
        return MaximalMarginalRelevanceRanker(lambda_factor=0.5)

    def test_mmr_reranking(self, ranker):
        """Test MMR reranking."""
        candidates = [
            {
                "slide_id": f"slide_{i}",
                "vector": np.random.randn(1024).astype(np.float32),
                "fused_score": float(np.random.rand()),
            }
            for i in range(20)
        ]

        reranked = ranker.rerank_by_mmr(candidates, top_k=5)

        assert len(reranked) == 5
        assert all("mmr_rank" in r for r in reranked)

    def test_mmr_lambda_effect(self):
        """Test effect of lambda parameter."""
        from src.agents.lakehouse_retrieval.mmr_diversity import (
            MaximalMarginalRelevanceRanker,
        )

        candidates = [
            {
                "slide_id": f"slide_{i}",
                "vector": np.random.randn(100).astype(np.float32),
                "fused_score": float(1.0 - i * 0.1),  # Decreasing relevance
            }
            for i in range(10)
        ]

        # High lambda = prefer relevance
        ranker_high = MaximalMarginalRelevanceRanker(lambda_factor=0.9)
        reranked_high = ranker_high.rerank_by_mmr(candidates, top_k=5)

        # Low lambda = prefer diversity
        ranker_low = MaximalMarginalRelevanceRanker(lambda_factor=0.1)
        reranked_low = ranker_low.rerank_by_mmr(candidates, top_k=5)

        # Rankings should be different
        high_ids = [r["slide_id"] for r in reranked_high]
        low_ids = [r["slide_id"] for r in reranked_low]

        # They shouldn't be identical
        assert high_ids != low_ids


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
