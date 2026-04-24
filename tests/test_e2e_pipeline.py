"""
End-to-End Integration Test for Vision-Ingestion and Lakehouse-Retrieval Pipeline
Test full retrieval flow: PPT → Vision Features → LanceDB → Hybrid Fusion → Results
"""

import pytest
import numpy as np
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple


# Mock Vision-Ingestion components
class MockVisionAgent:
    """Mock Vision-Ingestion-Agent for testing."""

    def __init__(self):
        self.processed_ppts = []

    def process_ppt(self, ppt_path: str, num_slides: int = 5) -> Dict[str, Any]:
        """Process PPT and return features."""
        features = {
            "ppt_path": ppt_path,
            "slides": [],
        }

        for slide_idx in range(num_slides):
            slide_features = {
                "slide_id": f"{Path(ppt_path).stem}_slide_{slide_idx}",
                "page_index": slide_idx,
                "multi_vectors": np.random.randn(1024, 128).astype(np.float32),
                "imagebind_vector": np.random.randn(1024).astype(np.float32),
                "patch_coordinates": [(i, i) for i in range(1024)],
                "metadata": {
                    "source": ppt_path,
                    "timestamp": "2024-01-01T00:00:00Z",
                },
                "quality_metrics": {
                    "coverage_ratio": 0.98,
                    "variance": 0.75,
                    "outlier_ratio": 0.02,
                },
            }

            features["slides"].append(slide_features)

        self.processed_ppts.append(ppt_path)
        return features


# Mock Lakehouse components
class MockMaxSimMatcher:
    """Mock MaxSim matching for testing."""

    def match(
        self,
        query_vectors: np.ndarray,
        candidate_vectors: List[np.ndarray],
    ) -> List[Tuple[int, float]]:
        """
        Mock MaxSim matching.

        Returns:
            List of (candidate_idx, score) tuples
        """
        scores = []

        for i, cand_vec in enumerate(candidate_vectors):
            # Simulate MaxSim score
            similarity = np.mean(
                np.max(np.dot(query_vectors, cand_vec.T), axis=1)
            )
            scores.append((i, similarity / (cand_vec.shape[1] + 1)))

        return sorted(scores, key=lambda x: x[1], reverse=True)


class MockLakehouseRetriever:
    """Mock Lakehouse-Retrieval-Agent for testing."""

    def __init__(self):
        self.indexed_slides = {}
        self.maxsim_matcher = MockMaxSimMatcher()

    def index_slides(self, slides: List[Dict[str, Any]]) -> None:
        """Index slides in mock LanceDB."""
        for slide in slides:
            slide_id = slide["slide_id"]
            self.indexed_slides[slide_id] = {
                "vectors": slide["multi_vectors"],
                "imagebind": slide["imagebind_vector"],
                "metadata": slide["metadata"],
            }

    def retrieve(
        self,
        query_vector: np.ndarray,
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        """Retrieve top-k slides."""
        if not self.indexed_slides:
            return []

        candidates = []

        for slide_id, data in self.indexed_slides.items():
            vec = data["vectors"]
            score = np.mean(np.max(np.dot(query_vector, vec.T), axis=1))
            candidates.append(
                {
                    "slide_id": slide_id,
                    "vector_score": score,
                    "vector": data["imagebind"],
                    "metadata": data["metadata"],
                }
            )

        # Sort by score descending
        candidates.sort(key=lambda x: x["vector_score"], reverse=True)
        return candidates[:top_k]


# Test fixtures
@pytest.fixture
def vision_agent():
    """Create mock vision agent."""
    return MockVisionAgent()


@pytest.fixture
def lakehouse_retriever():
    """Create mock lakehouse retriever."""
    return MockLakehouseRetriever()


@pytest.fixture
def sample_ppt_paths():
    """Create sample PPT paths."""
    return [
        "/data/ppts/finance_report.pptx",
        "/data/ppts/ml_applications.pptx",
        "/data/ppts/risk_management.pptx",
    ]


# Integration Tests
class TestVisionLakehouseIntegration:
    """Test complete Vision → Lakehouse pipeline."""

    def test_e2e_ppt_processing_and_indexing(
        self,
        vision_agent,
        lakehouse_retriever,
        sample_ppt_paths,
    ):
        """Test end-to-end PPT processing and indexing."""
        all_slides = []

        # Step 1: Process PPTs with Vision agent
        for ppt_path in sample_ppt_paths:
            features = vision_agent.process_ppt(ppt_path, num_slides=5)
            all_slides.extend(features["slides"])

        # Verify vision processing
        assert len(all_slides) == len(sample_ppt_paths) * 5
        assert all("multi_vectors" in s for s in all_slides)
        assert all("imagebind_vector" in s for s in all_slides)

        # Step 2: Index slides in LanceDB
        lakehouse_retriever.index_slides(all_slides)

        # Verify indexing
        assert len(lakehouse_retriever.indexed_slides) == len(all_slides)

    def test_hybrid_retrieval_with_vector_and_fts(
        self,
        vision_agent,
        lakehouse_retriever,
        sample_ppt_paths,
    ):
        """Test hybrid retrieval combining vector and FTS."""
        from src.agents.lakehouse_retrieval.hybrid_fusion import (
            HybridRetriever,
            HybridRetrievalConfig,
        )

        # Process and index
        all_slides = []
        for ppt_path in sample_ppt_paths:
            features = vision_agent.process_ppt(ppt_path, num_slides=3)
            all_slides.extend(features["slides"])

        lakehouse_retriever.index_slides(all_slides)

        # Create query vector
        query_vector = np.random.randn(1024, 128).astype(np.float32)

        # Retrieve with vector
        vector_results = lakehouse_retriever.retrieve(query_vector, top_k=10)

        # Mock FTS results
        fts_results = [
            {
                "slide_id": r["slide_id"],
                "score": np.random.rand() * 0.5,  # Lower FTS scores
            }
            for r in vector_results[:5]
        ]

        # Hybrid fusion
        config = HybridRetrievalConfig(
            vector_weight=0.7,
            fts_weight=0.3,
            fusion_strategy="weighted_sum",
        )
        hybrid_retriever = HybridRetriever(config)

        combined = hybrid_retriever.combine_results(
            vector_results,
            fts_results,
            top_k=5,
        )

        # Verify fusion
        assert len(combined) <= 5
        assert all("fused_score" in c for c in combined)
        assert all(0.0 <= c["fused_score"] <= 1.0 for c in combined)

        # Verify descending order
        scores = [c["fused_score"] for c in combined]
        assert scores == sorted(scores, reverse=True)

    def test_mmr_diversity_reranking(
        self,
        vision_agent,
        lakehouse_retriever,
        sample_ppt_paths,
    ):
        """Test MMR diversity reranking."""
        from src.agents.lakehouse_retrieval.mmr_diversity import (
            MaximalMarginalRelevanceRanker,
        )

        # Process and index
        all_slides = []
        for ppt_path in sample_ppt_paths:
            features = vision_agent.process_ppt(ppt_path, num_slides=2)
            all_slides.extend(features["slides"])

        lakehouse_retriever.index_slides(all_slides)

        # Retrieve results
        query_vector = np.random.randn(1024, 128).astype(np.float32)
        vector_results = lakehouse_retriever.retrieve(query_vector, top_k=10)

        # Add vectors to results
        for result in vector_results:
            result["vector"] = lakehouse_retriever.indexed_slides[
                result["slide_id"]
            ]["imagebind"]

        # Apply MMR reranking
        ranker = MaximalMarginalRelevanceRanker(lambda_factor=0.5)
        reranked = ranker.rerank_by_mmr(vector_results, top_k=5)

        # Verify reranking
        assert len(reranked) <= 5
        assert all("mmr_rank" in r for r in reranked)
        assert all("mmr_score" in r for r in reranked)

    def test_quality_checking_integration(
        self,
        vision_agent,
        sample_ppt_paths,
    ):
        """Test vector quality checking in pipeline."""
        from src.agents.vision_ingestion.quality_checker import (
            VectorQualityChecker,
        )

        # Process PPT
        ppt_path = sample_ppt_paths[0]
        features = vision_agent.process_ppt(ppt_path, num_slides=2)

        # Check quality
        checker = VectorQualityChecker()

        for slide in features["slides"]:
            quality_report = checker.comprehensive_check(
                multi_vectors=slide["multi_vectors"],
                imagebind_vector=slide["imagebind_vector"],
            )

            # Verify quality report
            assert "overall_score" in quality_report
            assert "coverage" in quality_report
            assert "geometric_completeness" in quality_report
            assert "consistency" in quality_report
            assert "summary" in quality_report
            assert quality_report["overall_score"] >= 0
            assert quality_report["overall_score"] <= 100

    def test_incremental_batch_processing(
        self,
        vision_agent,
        sample_ppt_paths,
    ):
        """Test incremental batch processing."""
        from src.agents.vision_ingestion.incremental_processor import (
            IncrementalBatchProcessor,
        )

        processor = IncrementalBatchProcessor()

        # Create first batch
        batch_id = "batch_001"
        ppt_files = sample_ppt_paths[:2]
        processor.create_batch(batch_id, ppt_files)

        # Verify batch creation
        batch_status = processor.get_batch_status(batch_id)
        assert batch_status["status"] == "created"
        assert batch_status["total"] == 2

        # Process batch
        processor.start_processing(batch_id)

        for ppt in ppt_files:
            features = vision_agent.process_ppt(ppt)
            processor.record_ppt_result(
                batch_id,
                ppt,
                len(features["slides"]),
                success=True,
            )

        processor.complete_batch(batch_id)

        # Verify batch completion
        final_status = processor.get_batch_status(batch_id)
        assert final_status["status"] == "completed"
        assert final_status["processed"] == 2

    def test_fault_tolerance_retry(self):
        """Test fault tolerance retry decorator."""
        from src.agents.vision_ingestion.fault_tolerance import retry

        call_count = 0

        @retry(max_attempts=3, initial_delay=0.1, backoff_factor=2.0)
        def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary failure")
            return "success"

        result = flaky_operation()
        assert result == "success"
        assert call_count == 2

    def test_serialization_roundtrip(
        self,
        vision_agent,
        sample_ppt_paths,
    ):
        """Test serialization and deserialization."""
        from src.agents.vision_ingestion.serializer import (
            FeatureBundleSerializer,
        )

        # Process PPT
        ppt_path = sample_ppt_paths[0]
        features = vision_agent.process_ppt(ppt_path, num_slides=2)

        # Serialize to Parquet
        serializer = FeatureBundleSerializer()
        parquet_file = serializer.serialize_to_parquet(
            features["slides"],
            "test_batch.parquet",
        )

        # Deserialize
        deserialized = serializer.deserialize_parquet(parquet_file)

        # Verify
        assert deserialized["format"] == "parquet"
        assert deserialized["rows"] == 2

    def test_pipeline_latency(
        self,
        vision_agent,
        lakehouse_retriever,
        sample_ppt_paths,
    ):
        """Test pipeline latency."""
        import time

        # Time vision processing
        vision_start = time.time()
        all_slides = []
        for ppt_path in sample_ppt_paths:
            features = vision_agent.process_ppt(ppt_path, num_slides=3)
            all_slides.extend(features["slides"])
        vision_time = time.time() - vision_start

        # Time indexing
        index_start = time.time()
        lakehouse_retriever.index_slides(all_slides)
        index_time = time.time() - index_start

        # Time retrieval
        query_vector = np.random.randn(1024, 128).astype(np.float32)
        retrieval_start = time.time()
        results = lakehouse_retriever.retrieve(query_vector, top_k=10)
        retrieval_time = time.time() - retrieval_start

        # Report latencies
        latencies = {
            "vision_processing_ms": vision_time * 1000,
            "indexing_ms": index_time * 1000,
            "retrieval_ms": retrieval_time * 1000,
            "total_ms": (vision_time + index_time + retrieval_time) * 1000,
        }

        # Verify reasonable latencies
        assert latencies["vision_processing_ms"] < 5000
        assert latencies["indexing_ms"] < 1000
        assert latencies["retrieval_ms"] < 500

        return latencies


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
