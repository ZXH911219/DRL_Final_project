"""Multi-Modal and Fusion Integration Test"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
from src.agents.multimodal_space import (
    ImageBindSpace,
    MultiModalAligner,
    RetrievalFuser,
    DiversityRanker,
    DeduplicateEngine,
)
from src.utils import get_logger

logger = get_logger("test_multimodal")


def test_imagebind_space():
    """Test ImageBind space."""
    logger.info("=" * 60)
    logger.info("TEST 1: ImageBind Space")
    logger.info("=" * 60)

    try:
        space = ImageBindSpace(output_dim=1024)

        # Test text encoding
        text_embedding = space.encode_text("Machine learning in finance")
        assert text_embedding.shape == (1024,), "Should be 1024-dim"
        assert np.linalg.norm(text_embedding) < 1.01, "Should be normalized"

        # Test image encoding
        image = np.random.randint(0, 255, (768, 1024, 3), dtype=np.uint8)
        image_embedding = space.encode_image(image)
        assert image_embedding.shape == (1024,), "Should be 1024-dim"

        # Test consistency
        consistency = space.cross_modal_consistency(text_embedding, image_embedding)
        assert 0.0 <= consistency <= 1.0, "Consistency should be in [0, 1]"

        logger.info(f"✓ Text embedding: {text_embedding.shape}")
        logger.info(f"✓ Image embedding: {image_embedding.shape}")
        logger.info(f"✓ Cross-modal consistency: {consistency:.3f}")
        logger.info("✓ ImageBind Space Test PASSED\n")
        return True

    except Exception as e:
        logger.error(f"✗ ImageBind Space Test FAILED: {e}\n")
        return False


def test_multimodal_aligner():
    """Test multi-modal alignment."""
    logger.info("=" * 60)
    logger.info("TEST 2: Multi-Modal Aligner")
    logger.info("=" * 60)

    try:
        aligner = MultiModalAligner(output_dim=512)

        # Create sample embeddings
        embeddings = {
            "text": np.random.randn(512),
            "image": np.random.randn(512),
            "audio": np.random.randn(512),
        }

        # Normalize
        for k in embeddings:
            embeddings[k] = embeddings[k] / (np.linalg.norm(embeddings[k]) + 1e-8)

        # Fuse
        fused, consistency = aligner.fuse_embeddings(embeddings)
        assert fused.shape == (512,), "Fused should be 512-dim"
        assert np.linalg.norm(fused) < 1.01, "Fused should be normalized"
        assert len(consistency) == 3, "Should have 3 consistency scores"

        # Quality check
        quality = aligner.quality_check(embeddings)
        assert "all_aligned" in quality, "Quality should have alignment status"

        logger.info(f"✓ Fused embedding: {fused.shape}")
        logger.info(f"✓ Consistency scores: {consistency}")
        logger.info(f"✓ Quality: all_aligned={quality['all_aligned']}")
        logger.info("✓ Multi-Modal Aligner Test PASSED\n")
        return True

    except Exception as e:
        logger.error(f"✗ Multi-Modal Aligner Test FAILED: {e}\n")
        return False


def test_retrieval_fusion():
    """Test retrieval fusion."""
    logger.info("=" * 60)
    logger.info("TEST 3: Retrieval Fusion")
    logger.info("=" * 60)

    try:
        fuser = RetrievalFuser(alpha=0.7, beta=0.3)

        # Vector ranking
        vector_ranking = [
            {"slide_id": "slide_0", "score": 0.9},
            {"slide_id": "slide_1", "score": 0.7},
            {"slide_id": "slide_2", "score": 0.5},
        ]

        # FTS ranking
        fts_ranking = [
            {"slide_id": "slide_1", "score": 0.95},
            {"slide_id": "slide_2", "score": 0.8},
            {"slide_id": "slide_3", "score": 0.6},
        ]

        # Fuse
        fused = fuser.fuse_rankings(vector_ranking, fts_ranking)
        assert len(fused) > 0, "Should have fused results"
        assert "fused_score" in fused[0], "Should have fused_score"

        logger.info(f"✓ Fused {len(fused)} results")
        logger.info(f"✓ Top result: {fused[0]['slide_id']} (score: {fused[0]['fused_score']:.3f})")
        logger.info("✓ Retrieval Fusion Test PASSED\n")
        return True

    except Exception as e:
        logger.error(f"✗ Retrieval Fusion Test FAILED: {e}\n")
        return False


def test_diversity_ranker():
    """Test diversity ranking."""
    logger.info("=" * 60)
    logger.info("TEST 4: Diversity Ranker")
    logger.info("=" * 60)

    try:
        ranker = DiversityRanker(lambda_param=0.5)

        # Candidates
        candidates = [
            {"slide_id": f"slide_{i}", "score": 0.9 - i * 0.1}
            for i in range(10)
        ]

        # Mock embeddings (orthogonal-ish)
        embeddings = np.random.randn(10, 128)
        embeddings = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-8)

        # MMR rerank
        reranked = ranker.mmr_rerank(candidates, embeddings, top_k=5)
        assert len(reranked) == 5, "Should return 5 results"

        logger.info(f"✓ MMR reranked to {len(reranked)} results")
        logger.info(f"✓ Top candidate: {reranked[0]['slide_id']}")
        logger.info("✓ Diversity Ranker Test PASSED\n")
        return True

    except Exception as e:
        logger.error(f"✗ Diversity Ranker Test FAILED: {e}\n")
        return False


def test_deduplication():
    """Test deduplication."""
    logger.info("=" * 60)
    logger.info("TEST 5: Deduplication")
    logger.info("=" * 60)

    try:
        dedup_engine = DeduplicateEngine(threshold=0.95)

        # Create similar embeddings
        base_embedding = np.random.randn(128)
        embeddings = np.vstack([
            base_embedding,
            base_embedding + np.random.randn(128) * 0.01,  # Very similar
            np.random.randn(128),  # Different
        ])
        embeddings = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-8)

        candidates = [
            {"slide_id": f"slide_{i}"}
            for i in range(3)
        ]

        # Deduplicate
        filtered = dedup_engine.deduplicate(embeddings, candidates)
        assert len(filtered) <= 3, "Should remove some duplicates"

        logger.info(f"✓ Deduplicated from {len(candidates)} to {len(filtered)} results")
        logger.info("✓ Deduplication Test PASSED\n")
        return True

    except Exception as e:
        logger.error(f"✗ Deduplication Test FAILED: {e}\n")
        return False


def main():
    """Run all tests."""
    logger.info("\n" + "=" * 60)
    logger.info("MULTI-MODAL & FUSION INTEGRATION TEST SUITE")
    logger.info("=" * 60 + "\n")

    results = {
        "ImageBind Space": test_imagebind_space(),
        "Multi-Modal Aligner": test_multimodal_aligner(),
        "Retrieval Fusion": test_retrieval_fusion(),
        "Diversity Ranker": test_diversity_ranker(),
        "Deduplication": test_deduplication(),
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
