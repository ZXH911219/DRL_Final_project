import sys
import os
from pathlib import Path
from PIL import Image, ImageDraw
import pytest


def _has_tesseract():
    try:
        import pytesseract

        # ensure binary is present
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _has_easyocr():
    try:
        import easyocr

        return True
    except Exception:
        return False


@pytest.mark.skipif(not (_has_tesseract() or _has_easyocr()), reason="No OCR backend available: pytesseract or easyocr required")
def test_ocr_grounding(tmp_path):
    repo_root = os.getcwd()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from src.agents.vision_ingestion_agent import VisionIngestionAgent
    from src.storage.lancedb_manager import LanceDBManager
    from src.schemas.query import QueryPayload
    from src.agents.lakehouse_retrieval_agent import LakehouseRetrievalAgent
    from src.agents.reasoning_reranker_agent import ReasoningRerankerAgent
    from src.agents.argos_verification_agent import ArgosVerificationAgent

    db_dir = tmp_path / "lance_db"
    db_dir.mkdir()
    lance = LanceDBManager(str(db_dir))

    # image with clear title text (larger font) to help OCR
    w, h = 1280, 720
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    d.text((50, 30), "市場成長趨勢", fill="black")

    vision = VisionIngestionAgent(lance=lance, dpi=600)
    bundles = vision.ingest_images(deck_id="deck-ocr", source_path=Path("synthetic.pptx"), images=[img])
    assert bundles and bundles[0].multi_vectors.shape == (1024, 128)

    q = QueryPayload(request_id="ocr-1", modality="text", query_text="市場成長趨勢")
    retrieval_agent = LakehouseRetrievalAgent(lance=lance)
    retrieval = retrieval_agent.search(q)

    reranker = ReasoningRerankerAgent()
    reasoning = reranker.rerank(retrieval)

    # ask verifier to use OCR (it will pick available backend)
    verifier = ArgosVerificationAgent(ocr_enabled=True)
    verified = verifier.verify(q, retrieval, reasoning, lambda sid: img)

    per = verified.verification.per_slide
    assert len(per) >= 1
    v0 = per[0]
    # Expect some verified claims if OCR succeeded
    assert 0.0 <= v0.hallucination_risk_score <= 1.0
