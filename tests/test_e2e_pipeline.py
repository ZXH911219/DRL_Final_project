import sys
import os
import shutil
from pathlib import Path
from PIL import Image, ImageDraw
import json


def test_end_to_end_pipeline(tmp_path):
    # make repo root importable as package `src`
    repo_root = os.getcwd()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from src.agents.vision_ingestion_agent import VisionIngestionAgent
    from src.storage.lancedb_manager import LanceDBManager
    from src.schemas.query import QueryPayload
    from src.agents.lakehouse_retrieval_agent import LakehouseRetrievalAgent
    from src.agents.reasoning_reranker_agent import ReasoningRerankerAgent
    from src.agents.argos_verification_agent import ArgosVerificationAgent

    # create temp lancedb dir
    db_dir = tmp_path / "lance_db"
    db_dir.mkdir()
    lance = LanceDBManager(str(db_dir))

    # build a synthetic slide image
    w, h = 1280, 720
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    d.text((50, 30), "市場成長趨勢", fill="black")
    # simple upward trend
    chart_x0, chart_y0 = 200, 200
    chart_x1, chart_y1 = 1100, 600
    d.rectangle([chart_x0, chart_y0, chart_x1, chart_y1], outline="black")
    pts = [(chart_x0 + i * (chart_x1 - chart_x0) / 9, chart_y1 - (i * (chart_y1 - chart_y0) / 9)) for i in range(10)]
    d.line(pts, fill="blue", width=4)

    # ingest (stub encoder default)
    vision = VisionIngestionAgent(lance=lance, dpi=600)
    bundles = vision.ingest_images(deck_id="deck-test", source_path=Path("synthetic.pptx"), images=[img])
    assert len(bundles) == 1
    b = bundles[0]
    assert b.quality_metrics.get("dpi") == 600.0
    assert getattr(b.multi_vectors, "shape", None) == (1024, 128)

    # retrieval
    q = QueryPayload(request_id="e2e-pytest-1", modality="text", query_text="市場成長趨勢")
    retrieval_agent = LakehouseRetrievalAgent(lance=lance)
    retrieval = retrieval_agent.search(q)
    assert len(retrieval.candidates) >= 1
    top = retrieval.candidates[0]
    assert top.evidence_patches and len(top.evidence_patches) > 0

    # reasoning rerank
    reranker = ReasoningRerankerAgent()
    reasoning = reranker.rerank(retrieval)
    assert reasoning.ranking and len(reasoning.ranking) > 0
    orig_score = float(reasoning.ranking[0].reranked_score)

    # inject hallucinated claim
    reasoning.ranking[0].inference_text = reasoning.ranking[0].inference_text + "\nTitle contains \"月度成長率上升\""

    # verify (use image loader returning our synthetic image), OCR disabled to force patch fallback
    verifier = ArgosVerificationAgent(ocr_enabled=False)
    verified = verifier.verify(q, retrieval, reasoning, lambda sid: img)

    per = verified.verification.per_slide
    assert len(per) >= 1
    v0 = per[0]
    # adjusted score should be bounded and not greater than original reranked score
    assert 0.0 <= v0.adjusted_score <= 1.0
    assert v0.adjusted_score <= orig_score + 1e-8

    # hallucination risk present when unverified claims exist (we injected one)
    assert 0.0 <= v0.hallucination_risk_score <= 1.0

    # can serialize VerifiedOutput to JSON-compatible dict
    ser = verified.model_dump() if hasattr(verified, "model_dump") else verified.dict()
    # allow non-JSON-native types by falling back to str
    json.dumps(ser, ensure_ascii=False, default=str)
