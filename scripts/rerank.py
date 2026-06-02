#!/usr/bin/env python3
"""Reasoning-Reranker-Agent 查詢 CLI。"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import os
import sys
from pathlib import Path

import numpy as np


def _bootstrap_path() -> None:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def _json_safe(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if hasattr(value, "as_py"):
        try:
            return _json_safe(value.as_py())
        except Exception:
            pass
    if hasattr(value, "to_pydatetime"):
        try:
            return value.to_pydatetime().isoformat()
        except Exception:
            pass
    if hasattr(value, "isoformat") and callable(value.isoformat):
        try:
            return value.isoformat()
        except Exception:
            pass
    if isinstance(value, dict):
        return {str(key): _json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    return value


def main() -> int:
    _bootstrap_path()

    parser = argparse.ArgumentParser(description="使用 Reasoning-Reranker-Agent 進行推理重排")
    parser.add_argument("--lancedb", type=Path, default=Path("./data/lancedb"), help="LanceDB 資料目錄")
    parser.add_argument("--table", type=str, default="slides", help="資料表名稱")
    parser.add_argument("--request-id", type=str, required=True, help="查詢追蹤 ID")
    parser.add_argument("--modality", type=str, choices=("text", "image", "multimodal"), required=True)
    parser.add_argument("--query-text", type=str, default=None, help="文字查詢")
    parser.add_argument("--query-image", type=Path, default=None, help="圖像查詢檔案")
    parser.add_argument("--top-k-filter", type=int, default=500, help="粗檢索候選數")
    parser.add_argument("--top-k-maxsim", type=int, default=20, help="MaxSim 精排輸出數")
    parser.add_argument("--top-k-rerank", type=int, default=20, help="推理重排候選數，預設 20")
    parser.add_argument("--per-candidate-timeout-s", type=float, default=None, help="單候選推理 timeout（秒）")
    parser.add_argument("--batch-timeout-s", type=float, default=None, help="整批推理 timeout（秒）")
    parser.add_argument("--max-workers", type=int, default=4, help="批次並行工作數")
    parser.add_argument("--weights", type=str, default=None, help="重排權重，格式 λ1,λ2,λ3")
    parser.add_argument("--mmr5-backend", choices=("stub", "hf", "env"), default="env", help="stub=假推理；hf=Transformers；env=讀環境變數")
    parser.add_argument("--mmr5-model", type=str, default="mm-r5", help="推理模型 ID")
    parser.add_argument("--mmr5-device", type=str, default=None, help="推理裝置，例如 cuda / cpu")
    parser.add_argument("--verbose", action="store_true", help="輸出 DEBUG 日誌")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.mmr5_backend == "stub":
        os.environ["MMR5_BACKEND"] = "stub"
    elif args.mmr5_backend == "hf":
        os.environ["MMR5_BACKEND"] = "hf"
    os.environ["MMR5_MODEL"] = args.mmr5_model
    if args.mmr5_device:
        os.environ["MMR5_DEVICE"] = args.mmr5_device

    from src.agents.lakehouse_retrieval_agent import LakehouseRetrievalAgent
    from src.agents.reasoning_reranker_agent import ReasoningRerankerAgent
    from src.schemas import Modality, QueryPayload
    from src.storage import LanceDBManager

    query_text = args.query_text.strip() if args.query_text else None
    query_image_bytes = None
    query_image_mime = None
    if args.query_image is not None:
        if not args.query_image.is_file():
            logging.error("找不到圖像檔：%s", args.query_image)
            return 2
        query_image_bytes = args.query_image.read_bytes()
        query_image_mime = "image/png"

    payload = QueryPayload(
        request_id=args.request_id,
        modality=Modality(args.modality),
        query_text=query_text,
        query_image_bytes=query_image_bytes,
        query_image_mime=query_image_mime,
        top_k_filter=int(args.top_k_filter),
        top_k_maxsim=int(args.top_k_maxsim),
    )

    if args.weights:
        parts = [float(item.strip()) for item in args.weights.split(",")]
        if len(parts) != 3:
            raise ValueError("--weights 必須提供三個權重，例如 0.4,0.4,0.2")
        weights = (parts[0], parts[1], parts[2])
    else:
        weights = None

    lance = LanceDBManager(str(args.lancedb.resolve()), args.table)
    retrieval_agent = LakehouseRetrievalAgent(lance)
    reasoning_agent = ReasoningRerankerAgent(
        top_k=int(args.top_k_rerank),
        per_candidate_timeout_s=args.per_candidate_timeout_s,
        batch_timeout_s=args.batch_timeout_s,
        weights=weights,
        max_workers=int(args.max_workers),
    )

    retrieval_context = retrieval_agent.search(payload)
    bundle = reasoning_agent.rerank(retrieval_context)
    print(json.dumps(_json_safe(bundle.model_dump(mode="python")), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())