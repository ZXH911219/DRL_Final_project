#!/usr/bin/env python3
"""Lakehouse-Retrieval-Agent 查詢 CLI。"""

from __future__ import annotations

import argparse
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
    if isinstance(value, Path):
        return str(value)
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

    parser = argparse.ArgumentParser(description="使用 Lakehouse-Retrieval-Agent 進行投影片檢索")
    parser.add_argument("--lancedb", type=Path, default=Path("./data/lancedb"), help="LanceDB 資料目錄")
    parser.add_argument("--table", type=str, default="slides", help="資料表名稱")
    parser.add_argument("--request-id", type=str, required=True, help="查詢追蹤 ID")
    parser.add_argument("--modality", type=str, choices=("text", "image", "multimodal"), required=True)
    parser.add_argument("--query-text", type=str, default=None, help="文字查詢")
    parser.add_argument("--query-image", type=Path, default=None, help="圖像查詢檔案")
    parser.add_argument("--top-k-filter", type=int, default=500, help="粗檢索候選數")
    parser.add_argument("--top-k-maxsim", type=int, default=20, help="MaxSim 精排輸出數")
    parser.add_argument("--evidence-top-n", type=int, default=5, help="每張投影片保留的證據 patch 數")
    parser.add_argument("--batch-size", type=int, default=32, help="MaxSim 批次大小")
    parser.add_argument(
        "--colpali-backend",
        choices=("stub", "hf", "env"),
        default="env",
        help="stub=假向量；hf=Transformers ColPali；env=讀取 COLPALI_BACKEND 環境變數",
    )
    parser.add_argument("--colpali-model", type=str, default="vidore/colpali-v1.3-hf", help="ColPali 模型 ID")
    parser.add_argument("--colpali-device", type=str, default=None, help="ColPali 裝置，例如 cuda / cpu")
    parser.add_argument("--verbose", action="store_true", help="輸出 DEBUG 日誌")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.colpali_backend == "stub":
        os.environ["COLPALI_BACKEND"] = "stub"
    elif args.colpali_backend == "hf":
        os.environ["COLPALI_BACKEND"] = "hf"
    os.environ["COLPALI_MODEL"] = args.colpali_model
    if args.colpali_device:
        os.environ["COLPALI_DEVICE"] = args.colpali_device

    from src.agents.lakehouse_retrieval_agent import LakehouseRetrievalAgent
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

    lance = LanceDBManager(str(args.lancedb.resolve()), args.table)
    agent = LakehouseRetrievalAgent(
        lance,
        evidence_top_n=int(args.evidence_top_n),
        batch_size=int(args.batch_size),
    )

    context = agent.search(payload)
    print(json.dumps(_json_safe(context.model_dump(mode="python")), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())