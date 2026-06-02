#!/usr/bin/env python3
"""
簡易 PPT 攝取 CLI：Vision-Ingestion-Agent → LanceDB。

前置需求：
  - LibreOffice（soffice）於 PATH，或 Windows 預設安裝路徑。
  - Poppler（pdf2image 依賴）已安裝並可在 PATH 找到。
  - 專案根目錄設定 PYTHONPATH=.（或已安裝本套件）。

範例：
  set PYTHONPATH=.
  python scripts/ingest_pptx.py --pptx ./deck.pptx --lancedb ./data/lancedb --deck-id mydeck --dpi 600
  set COLPALI_BACKEND=hf && python scripts/ingest_pptx.py ...
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path


def _bootstrap_path() -> None:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def main() -> int:
    _bootstrap_path()

    parser = argparse.ArgumentParser(description="將 .pptx 攝取至 LanceDB（Vision-Ingestion-Agent）")
    parser.add_argument("--pptx", type=Path, required=True, help="輸入 .pptx 路徑")
    parser.add_argument("--lancedb", type=Path, default=Path("./data/lancedb"), help="LanceDB 資料目錄")
    parser.add_argument("--table", type=str, default="slides", help="資料表名稱")
    parser.add_argument("--deck-id", type=str, default="", help="語料庫／簡報 ID（預設為檔名 stem）")
    parser.add_argument("--dpi", type=int, default=600, help="PDF 點陣化 DPI（agents.md：600）")
    parser.add_argument(
        "--colpali-backend",
        choices=("stub", "hf", "env"),
        default="env",
        help="stub=假向量；hf=Transformers ColPali；env=讀取 COLPALI_BACKEND 環境變數",
    )
    parser.add_argument("--imagebind-placeholder", action="store_true", help="寫入占位 imagebind_vec（零向量）")
    parser.add_argument("--keep-artifacts", action="store_true", help="保留 LibreOffice/pdf 暫存目錄")
    parser.add_argument("--workdir", type=Path, default=None, help="指定暫存目錄（不指定則自動建立）")
    parser.add_argument("--build-ivf-pq", action="store_true", help="攝取後嘗試建立 colpali_agg_128 之 IVF-PQ")
    parser.add_argument("-v", "--verbose", action="store_true", help="DEBUG 日誌")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    pptx_path: Path = args.pptx
    if not pptx_path.is_file():
        logging.error("找不到檔案：%s", pptx_path)
        return 2

    deck_id = args.deck_id.strip() or pptx_path.stem

    if args.colpali_backend == "stub":
        os.environ["COLPALI_BACKEND"] = "stub"
    elif args.colpali_backend == "hf":
        os.environ["COLPALI_BACKEND"] = "hf"
    # env: 不覆寫

    from src.agents.vision_ingestion_agent import (
        ImageBindEncoderPlaceholder,
        VisionIngestionAgent,
        build_colpali_encoder_from_env,
    )
    from src.storage import LanceDBManager, slide_table_schema

    lance = LanceDBManager(str(args.lancedb.resolve()), args.table)
    if not lance.table_exists():
        lance.create_table(mode="create", schema=slide_table_schema())
        logging.info("已建立新表：%s / %s", args.lancedb, args.table)

    colpali = build_colpali_encoder_from_env()
    ib = ImageBindEncoderPlaceholder(enabled=bool(args.imagebind_placeholder))
    agent = VisionIngestionAgent(lance, colpali=colpali, imagebind=ib, dpi=int(args.dpi))

    bundles = agent.ingest_pptx(
        pptx_path,
        deck_id,
        workdir=args.workdir,
        keep_artifacts=bool(args.keep_artifacts),
    )
    logging.info("已攝取 %s 頁，寫入 LanceDB。", len(bundles))

    if args.build_ivf_pq:
        ok = lance.build_ivf_pq_index_on_agg()
        logging.info("IVF-PQ 建立結果：%s", ok)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
