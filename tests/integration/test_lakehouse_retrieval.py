"""Lakehouse-Retrieval-Agent Integration Test"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
from src.agents.lakehouse_retrieval import (
    HybridIndexManager,
    MaxSimMatcher,
    FTSQueryEngine,
    LakehouseRetrievalAgent,
    get_retrieval_agent,
)
from src.utils import get_logger

logger = get_logger("test_lakehouse_retrieval")


def test_vector_indexing():
    """Test vector indexing."""
    logger.info("=" * 60)
    logger.info("TEST 1: Vector Indexing")
    logger.info("=" * 60)

    try:
        # Create sample vectors
        num_vectors = 1000
        dim = 128
        vectors = np.random.randn(num_vectors, dim).astype(np.float32)

        # Build index
        index_mgr = HybridIndexManager(num_clusters=10)
        index_mgr.build(vectors)
        logger.info(f"✓ Built hybrid index for {num_vectors} vectors")

        # Test query
        query = np.random.randn(dim).astype(np.float32)
        candidates, strategy = index_mgr.query_hybrid(query, top_k=100)
        assert len(candidates) > 0, "Should return candidates"
        logger.info(f"✓ Query returned {len(candidates)} candidates ({strategy})")

        logger.info("✓ Vector Indexing Test PASSED\n")
        return True

    except Exception as e:
        logger.error(f"✗ Vector Indexing Test FAILED: {e}\n")
        return False


def test_maxsim_matching():
    """Test MaxSim matching algorithm."""
    logger.info("=" * 60)
    logger.info("TEST 2: MaxSim Matching")
    logger.info("=" * 60)

    try:
        matcher = MaxSimMatcher()

        # Create sample vectors
        query_vectors = np.random.randn(10, 128).astype(np.float32)
        doc_vectors = np.random.randn(1024, 128).astype(np.float32)

        # Compute score
        score, evidence = matcher.compute_maxsim_scores(query_vectors, doc_vectors)
        assert 0.0 <= score <= 1.0, "Score should be between 0 and 1"
        assert len(evidence) <= 5, "Should return at most 5 evidence regions"

        logger.info(f"✓ MaxSim score: {score:.4f}, evidence regions: {len(evidence)}")

        logger.info("✓ MaxSim Matching Test PASSED\n")
        return True

    except Exception as e:
        logger.error(f"✗ MaxSim Matching Test FAILED: {e}\n")
        return False


def test_fts_engine():
    """Test FTS engine."""
    logger.info("=" * 60)
    logger.info("TEST 3: FTS Engine")
    logger.info("=" * 60)

    try:
        engine = FTSQueryEngine()

        # Index some metadata
        metadata_list = [
            {"title": "Machine Learning Basics", "tags": "ML, AI, basics"},
            {"title": "Deep Learning Advanced", "tags": "DL, neural networks"},
            {"title": "Finance and Risk", "tags": "finance, risk, banking"},
        ]

        for i, meta in enumerate(metadata_list):
            engine.index_metadata(f"slide_{i}", meta)

        logger.info(f"✓ Indexed {len(metadata_list)} documents")

        # Test search
        keywords = ["machine", "learning"]
        results = engine.search(keywords, mode="OR")
        assert len(results) > 0, "Should find results"
        logger.info(f"✓ FTS search returned {len(results)} results")

        logger.info("✓ FTS Engine Test PASSED\n")
        return True

    except Exception as e:
        logger.error(f"✗ FTS Engine Test FAILED: {e}\n")
        return False


def test_retrieval_agent():
    """Test Lakehouse-Retrieval-Agent."""
    logger.info("=" * 60)
    logger.info("TEST 4: Lakehouse-Retrieval-Agent")
    logger.info("=" * 60)

    try:
        agent = get_retrieval_agent()
        logger.info(f"✓ Created agent instance")

        # Build indices
        vectors = np.random.randn(100, 128).astype(np.float32)
        agent.build_indices(vectors)
        logger.info(f"✓ Built indices for vectors")

        # Retrieve
        query = np.random.randn(128).astype(np.float32)
        result = agent.retrieve(query, query_text="machine learning", top_k2=5)

        assert result is not None, "Should return result"
        assert len(result.ranking) > 0, "Should have rankings"
        assert result.total_latency_ms > 0, "Should have latency"

        logger.info(f"✓ Retrieved {len(result.ranking)} results")
        logger.info(f"✓ Latency: {result.total_latency_ms:.2f}ms (Stage1: {result.stage_1_latency_ms:.2f}ms, Stage2: {result.stage_2_latency_ms:.2f}ms)")

        logger.info("✓ Lakehouse-Retrieval-Agent Test PASSED\n")
        return True

    except Exception as e:
        logger.error(f"✗ Lakehouse-Retrieval-Agent Test FAILED: {e}\n")
        return False


def main():
    """Run all retrieval tests."""
    logger.info("\n" + "=" * 60)
    logger.info("LAKEHOUSE-RETRIEVAL-AGENT INTEGRATION TEST SUITE")
    logger.info("=" * 60 + "\n")

    results = {
        "Vector Indexing": test_vector_indexing(),
        "MaxSim Matching": test_maxsim_matching(),
        "FTS Engine": test_fts_engine(),
        "Retrieval Agent": test_retrieval_agent(),
    }

    logger.info("=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{name}: {status}")
    logger.info(f"\nTotal: {passed}/{total} tests passed")
    logger.info("=" * 60 + "\n")

    return all(results.values())


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
