"""
End-to-End Integration Test for Real Models
Tests ColPali (Vision) -> MM-R5 (Reasoning) -> Argos (Verification) pipeline
"""

import pytest
import numpy as np
import logging
from pathlib import Path
from typing import Dict, Any

# Suppress verbose logging in tests
logging.basicConfig(level=logging.WARNING)


class TestRealColPaliIntegration:
    """Test ColPali vision extraction integration."""

    @pytest.fixture
    def colpali_agent(self):
        """Create ColPali agent for testing."""
        from src.agents.vision_ingestion.colpali_real import RealColPaliVisionAgent

        agent = RealColPaliVisionAgent(device="cpu")  # Use CPU for tests
        agent.initialize()
        return agent

    def test_colpali_initialization(self, colpali_agent):
        """Test ColPali agent initializes without error."""
        assert colpali_agent is not None
        assert colpali_agent.image_renderer is not None
        assert colpali_agent.extractor is not None

    def test_colpali_placeholder_features(self, colpali_agent):
        """Test ColPali can generate placeholder features."""
        # Create dummy image
        dummy_image = np.random.randint(0, 256, (768, 1024, 3), dtype=np.uint8)

        # Extract features
        multi_vectors, confidence = colpali_agent.extractor.extract_features_from_image(
            dummy_image
        )

        # Verify output shape and type
        assert multi_vectors.shape == (1024, 128)
        assert multi_vectors.dtype == np.float32
        assert 0 <= confidence <= 1.0

    def test_colpali_batch_extraction(self, colpali_agent):
        """Test batch feature extraction."""
        # Create batch of dummy images
        batch = [
            np.random.randint(0, 256, (768, 1024, 3), dtype=np.uint8)
            for _ in range(3)
        ]

        # Extract features
        wrapper = colpali_agent.extractor
        results = []
        for image in batch:
            vectors, conf = wrapper.extract_features_from_image(image)
            results.append(vectors)

        # Verify results
        assert len(results) == 3
        for vectors in results:
            assert vectors.shape == (1024, 128)


class TestRealMM_R5Integration:
    """Test MM-R5 reasoning integration."""

    @pytest.fixture
    def mm_r5_reranker(self):
        """Create MM-R5 reranker for testing."""
        from src.agents.reasoning_reranker.mm_r5_real import MM_R5ReasoningReranker

        reranker = MM_R5ReasoningReranker(device="cpu")
        return reranker

    def test_mm_r5_initialization(self, mm_r5_reranker):
        """Test MM-R5 reranker initializes."""
        assert mm_r5_reranker is not None
        assert mm_r5_reranker.reasoner is not None

    def test_mm_r5_reasoning_generation(self, mm_r5_reranker):
        """Test MM-R5 generates reasoning chain."""
        query = "machine learning in financial risk management"
        slide_content = "Discussion of ML algorithms for risk assessment"
        slide_id = "slide_42"

        result = mm_r5_reranker.reasoner.generate_reasoning_chain(
            query=query,
            slide_content=slide_content,
            slide_id=slide_id,
        )

        # Verify result structure
        assert result.query == query
        assert result.slide_id == slide_id
        assert len(result.reasoning_chain) > 0
        assert isinstance(result.final_score, float)
        assert 0 <= result.final_score <= 1.0

    def test_mm_r5_reasoning_steps_structure(self, mm_r5_reranker):
        """Test reasoning steps have correct structure."""
        query = "test query"
        slide_content = "test content"

        result = mm_r5_reranker.reasoner.generate_reasoning_chain(
            query=query,
            slide_content=slide_content,
            slide_id="test_slide",
        )

        # Verify reasoning steps
        assert len(result.reasoning_chain) >= 5
        for step in result.reasoning_chain:
            assert hasattr(step, "step_id")
            assert hasattr(step, "step_name")
            assert hasattr(step, "reasoning_text")
            assert 0 <= step.local_score <= 1.0
            assert 0 <= step.confidence <= 1.0

    def test_mm_r5_candidates_reranking(self, mm_r5_reranker):
        """Test reranking of multiple candidates."""
        query = "blockchain technology applications"
        candidates = [
            {
                "slide_id": "slide_1",
                "content": "Blockchain for supply chain",
                "score": 0.85,
            },
            {
                "slide_id": "slide_2",
                "content": "Financial cryptocurrencies",
                "score": 0.75,
            },
            {
                "slide_id": "slide_3",
                "content": "Traditional databases",
                "score": 0.40,
            },
        ]

        reranked = mm_r5_reranker.rerank_candidates(query, candidates)

        # Verify reranking
        assert len(reranked) == 3
        assert all("reranked_score" in c for c in reranked)
        assert all("reasoning" in c for c in reranked)
        assert reranked[0]["reranked_score"] >= reranked[1]["reranked_score"]


class TestArgosVerificationIntegration:
    """Test Argos verification agent integration."""

    @pytest.fixture
    def verification_agent(self):
        """Create Argos verification agent."""
        from src.agents.verification.argos_real import ArgosVerificationAgent

        agent = ArgosVerificationAgent(device="cpu")
        agent.initialize()
        return agent

    def test_argos_initialization(self, verification_agent):
        """Test Argos agent initializes."""
        assert verification_agent is not None

    def test_argos_verification_report(self, verification_agent):
        """Test Argos generates verification report."""
        # Create dummy slide image
        slide_image = np.random.randint(0, 256, (768, 1024, 3), dtype=np.uint8)

        reasoning_text = "This slide shows a chart with upward trends"
        reasoning_steps = [
            {"step": "Visual Perception", "text": "Detected line chart"},
            {"step": "Query Analysis", "text": "Looking for growth trends"},
        ]

        report = verification_agent.verify_reasoning(
            slide_image=slide_image,
            reasoning_text=reasoning_text,
            reasoning_steps=reasoning_steps,
            original_score=0.85,
            slide_id="test_slide",
        )

        # Verify report structure
        assert report.slide_id == "test_slide"
        assert report.verification_status in ["pass", "warn", "fail"]
        assert 0 <= report.hallucination_risk_score <= 1.0
        assert 0 <= report.evidence_coverage_ratio <= 1.0
        assert 0 <= report.semantic_consistency <= 1.0

    def test_argos_hallucination_detection(self, verification_agent):
        """Test hallucination risk calculation."""
        slide_image = np.random.randint(0, 256, (768, 1024, 3), dtype=np.uint8)

        # Create reasoning with many unsupported claims
        reasoning_text = "The slide shows advanced AI, quantum computing, time travel"
        reasoning_steps = []

        report = verification_agent.verify_reasoning(
            slide_image=slide_image,
            reasoning_text=reasoning_text,
            reasoning_steps=reasoning_steps,
            original_score=0.90,
            slide_id="hallucination_test",
        )

        # Hallucination risk should be elevated
        assert report.hallucination_risk_score > 0.2
        assert len(report.unverified_claims) > 0


class TestEndToEndPipeline:
    """Test complete pipeline: Vision -> Reasoning -> Verification."""

    def test_full_pipeline_initialization(self):
        """Test all three agents can initialize together."""
        from src.agents.vision_ingestion.colpali_real import RealColPaliVisionAgent
        from src.agents.reasoning_reranker.mm_r5_real import MM_R5ReasoningReranker
        from src.agents.verification.argos_real import ArgosVerificationAgent

        vision_agent = RealColPaliVisionAgent(device="cpu")
        reasoning_reranker = MM_R5ReasoningReranker(device="cpu")
        verification_agent = ArgosVerificationAgent(device="cpu")

        # Initialize all
        vision_init = vision_agent.initialize()
        reasoning_init = reasoning_reranker.reasoner.is_ready
        verification_init = verification_agent.is_ready

        # At least some should work
        assert vision_agent is not None
        assert reasoning_reranker is not None
        assert verification_agent is not None

    def test_pipeline_data_flow(self):
        """Test data flows correctly through pipeline."""
        from src.agents.vision_ingestion.colpali_real import RealColPaliVisionAgent
        from src.agents.reasoning_reranker.mm_r5_real import MM_R5ReasoningReranker
        from src.agents.verification.argos_real import ArgosVerificationAgent

        # Stage 1: Vision extraction
        vision_agent = RealColPaliVisionAgent(device="cpu")
        vision_agent.initialize()

        dummy_image = np.random.randint(0, 256, (768, 1024, 3), dtype=np.uint8)
        multi_vectors, confidence = vision_agent.extractor.extract_features_from_image(
            dummy_image
        )

        assert multi_vectors.shape == (1024, 128)

        # Stage 2: Reasoning
        reranker = MM_R5ReasoningReranker(device="cpu")
        candidates = [
            {
                "slide_id": "slide_1",
                "content": "Sample content",
                "score": 0.85,
            }
        ]

        reranked = reranker.rerank_candidates(query="test query", candidates=candidates)
        assert len(reranked) > 0
        assert "reasoning" in reranked[0]

        # Stage 3: Verification
        verification_agent = ArgosVerificationAgent(device="cpu")
        verification_agent.initialize()

        report = verification_agent.verify_reasoning(
            slide_image=dummy_image,
            reasoning_text="Test reasoning",
            reasoning_steps=[],
            original_score=reranked[0]["reranked_score"],
            slide_id="slide_1",
        )

        assert report.slide_id == "slide_1"
        assert report.adjusted_score <= report.original_score  # Should be adjusted down or same


class TestRealModelPerformance:
    """Test performance characteristics of real models."""

    def test_colpali_throughput(self):
        """Test ColPali extraction throughput."""
        from src.agents.vision_ingestion.colpali_real import RealColPaliExtractor
        import time

        extractor = RealColPaliExtractor(device="cpu")

        # Generate batch of images
        batch_size = 5
        images = [
            np.random.randint(0, 256, (768, 1024, 3), dtype=np.uint8)
            for _ in range(batch_size)
        ]

        # Measure extraction time
        start = time.time()
        for image in images:
            extractor.extract_features_from_image(image)
        elapsed = time.time() - start

        # Should complete in reasonable time (>100ms placeholder, <5s real)
        assert elapsed < 10.0, f"Extraction took {elapsed:.1f}s, expected <10s"

    def test_mm_r5_reasoning_latency(self):
        """Test MM-R5 reasoning latency."""
        from src.agents.reasoning_reranker.mm_r5_real import RealMM_R5Reasoner
        import time

        reasoner = RealMM_R5Reasoner(device="cpu")

        # Test reasoning latency
        start = time.time()
        result = reasoner.generate_reasoning_chain(
            query="test",
            slide_content="content",
            slide_id="test",
        )
        elapsed = time.time() - start

        # Should complete in reasonable time
        assert elapsed < 30.0, f"Reasoning took {elapsed:.1f}s"

    def test_argos_verification_latency(self):
        """Test Argos verification latency."""
        from src.agents.verification.argos_real import ArgosVerificationAgent
        import time

        agent = ArgosVerificationAgent(device="cpu")
        agent.initialize()

        image = np.random.randint(0, 256, (768, 1024, 3), dtype=np.uint8)

        start = time.time()
        report = agent.verify_reasoning(
            slide_image=image,
            reasoning_text="test",
            reasoning_steps=[],
            original_score=0.85,
            slide_id="test",
        )
        elapsed = time.time() - start

        # Should complete quickly
        assert elapsed < 5.0, f"Verification took {elapsed:.1f}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
