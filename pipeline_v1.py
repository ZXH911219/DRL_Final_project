"""Pipeline v1: run Lakehouse Retrieval -> Reasoning Reranker -> Argos Verification

Usage examples:
  python pipeline_v1.py --lance-uri lanedb://path/to/db --query-text "市場成長"

If `--lance-uri` is omitted the script will exit with instructions.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from uuid import uuid4

from PIL import Image

# ensure project root is importable so `src.*` absolute imports work
ROOT = os.path.dirname(__file__)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.agents import ArgosVerificationAgent, LakehouseRetrievalAgent, ReasoningRerankerAgent
from src.agents.argos_verification_agent import ArgosConfig
from src.schemas.query import QueryPayload
from src.storage.lancedb_manager import LanceDBManager


def slide_image_loader_from_artifacts(slide_id: str) -> Image.Image:
    # try couple common locations
    candidates = [
        os.path.join("artifacts", f"{slide_id}.png"),
        os.path.join("artifacts", f"{slide_id}.jpg"),
        os.path.join("artifacts", slide_id),
    ]
    for p in candidates:
        if os.path.exists(p):
            return Image.open(p).convert("RGB")
    # fallback: blank image
    return Image.new("RGB", (1280, 720), color=(255, 255, 255))


def run_pipeline(lance_uri: str, query_text: str, request_id: str | None = None, risk_alpha: float = 1.0, progress_callback=None, image_loader=None) -> dict:
    request_id = request_id or str(uuid4())
    q = QueryPayload(request_id=request_id, modality="text", query_text=query_text)
    loader_func = image_loader or slide_image_loader_from_artifacts

    if progress_callback: progress_callback(0, 3, "第一階段：正在從資料庫撈取最相關的候選名單 (Retrieval)...")
    lance = LanceDBManager(lance_uri)
    retrieval_agent = LakehouseRetrievalAgent(lance=lance)
    retrieval = retrieval_agent.search(q)

    if progress_callback: progress_callback(1, 3, "第二階段：正在進行語意重排與推理 (Reranking)...")
    reranker = ReasoningRerankerAgent()
    reasoning = reranker.rerank(retrieval, image_loader=loader_func)

    if progress_callback: progress_callback(2, 3, "第三階段：正在進行事實查核與涵蓋率驗證 (Verification)...")
    # Allow configurable risk downweighting
    config = ArgosConfig(risk_alpha=risk_alpha)
    verifier = ArgosVerificationAgent(config=config)
    verified = verifier.verify(q, retrieval, reasoning, loader_func)

    if progress_callback: progress_callback(3, 3, "處理完成！準備顯示結果...")
    out = verified.model_dump() if hasattr(verified, "model_dump") else verified.dict()
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--lance-uri", required=True, help="LanceDB URI for slide table")
    p.add_argument("--query-text", required=True)
    p.add_argument("--request-id", default=None)
    args = p.parse_args()

    result = run_pipeline(args.lance_uri, args.query_text, request_id=args.request_id)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
