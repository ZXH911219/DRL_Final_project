"""
LanceDB 資料管理（對齊 openspec/specs/specs.md §3 與 project.md 技術棧）。

- `colpali_multi`：PyArrow 以巢狀 fixed_size_list 表示，等同
  ``fixed_size_list(fixed_size_list(float, 128), 1024)``。
- 粗檢索：對 `colpali_agg_128`（patch-mean）建立 IVF-PQ；列數不足時跳過索引並以暴力向量搜尋降級。
- 讀取多向量：支援巢狀 list、``(1024, 128)`` ndarray，以及 §3.1.1 之 **131072 展平** 自動 ``reshape``。
"""

from __future__ import annotations

import json
import logging
import re
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Mapping, Sequence

import lancedb
import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
from lancedb.db import DBConnection
from lancedb.table import Table

from ..schemas.retrieval import RetrievalCandidate

logger = logging.getLogger(__name__)

COLPALI_PATCHES: int = 1024
COLPALI_DIM: int = 128
COLPALI_FLAT_LEN: int = COLPALI_PATCHES * COLPALI_DIM  # 131072
IMAGEBIND_DIM: int = 1024
PATCH_BBOX_LEN: int = 4

# Lance IVF-PQ 訓練對 PQ 子碼本至少需要足夠樣本（實測 lance 4.x 預設約需 256 列）
_MIN_ROWS_FOR_IVF_PQ: int = 256
_FTS_STOPWORDS: frozenset[str] = frozenset(
    {
        "請",
        "找出",
        "包含",
        "的",
        "投影片",
        "投影片中",
        "頁",
        "請找出",
        "找出包含",
    }
)


def colpali_multi_value_type() -> pa.DataType:
    """ColPali 多向量欄位型別：1024 × 128 float32（巢狀 fixed_size_list）。"""
    inner = pa.list_(pa.float32(), list_size=COLPALI_DIM)
    return pa.list_(inner, list_size=COLPALI_PATCHES)


def slide_table_schema() -> pa.Schema:
    """投影片主表 Schema（§3.2 + 巢狀 colpali_multi）。"""
    return pa.schema(
        [
            pa.field("slide_id", pa.string(), nullable=False),
            pa.field("deck_id", pa.string(), nullable=False),
            pa.field("page_index", pa.int32(), nullable=False),
            pa.field("source_path", pa.string(), nullable=False),
            pa.field("created_at", pa.timestamp("us", tz="UTC"), nullable=False),
            pa.field("colpali_multi", colpali_multi_value_type(), nullable=False),
            pa.field("colpali_agg_128", pa.list_(pa.float32(), list_size=COLPALI_DIM), nullable=False),
            pa.field("imagebind_vec", pa.list_(pa.float32(), list_size=IMAGEBIND_DIM), nullable=True),
            pa.field(
                "patch_bboxes",
                pa.list_(pa.list_(pa.float32(), list_size=PATCH_BBOX_LEN), list_size=COLPALI_PATCHES),
                nullable=True,
            ),
            pa.field("fts_text", pa.string(), nullable=True),
            pa.field("quality_metrics", pa.string(), nullable=True),
        ]
    )


SLIDE_TABLE_FIELD_NAMES: frozenset[str] = frozenset(slide_table_schema().names)


def compute_colpali_agg_128(multi: np.ndarray) -> np.ndarray:
    """
    由 (1024, 128) 多向量產生第一階段粗檢索用匯總向量（patch-mean，§3.2 / §3.3）。
    """
    if multi.shape != (COLPALI_PATCHES, COLPALI_DIM):
        raise ValueError(f"預期 multi 形狀 ({COLPALI_PATCHES}, {COLPALI_DIM})，收到 {multi.shape}")
    return np.ascontiguousarray(multi, dtype=np.float32).mean(axis=0)


def numpy_multi_to_nested_list(multi: np.ndarray) -> list[list[float]]:
    """將 (1024, 128) float32 轉成可寫入 Lance 的巢狀 Python list（外層 1024 列、每列 128）。"""
    if multi.shape != (COLPALI_PATCHES, COLPALI_DIM):
        raise ValueError(f"預期 multi 形狀 ({COLPALI_PATCHES}, {COLPALI_DIM})，收到 {multi.shape}")
    m = np.ascontiguousarray(multi, dtype=np.float32)
    return [m[i].tolist() for i in range(COLPALI_PATCHES)]


def colpali_multi_to_numpy(raw: Any) -> np.ndarray:
    """
    將從 Lance／Pandas 讀出的 `colpali_multi` 還原為 float32 ndarray，形狀 (1024, 128)。

    支援：
    - 巢狀 list / tuple（1024×128）
    - ndarray 形狀 (1024, 128)
    - **展平** list／ndarray 長度 131072（§3.1.1 C contiguous flatten）
    - pyarrow FixedSizeListScalar：轉為 numpy 後再判斷
    """
    if raw is None:
        raise ValueError("colpali_multi 不可為 None")

    if hasattr(raw, "as_py"):
        raw = raw.as_py()

    arr = np.asarray(raw, dtype=np.float32)

    if arr.shape == (COLPALI_PATCHES, COLPALI_DIM):
        return np.ascontiguousarray(arr, dtype=np.float32)

    if arr.ndim == 1 and arr.shape[0] == COLPALI_FLAT_LEN:
        return arr.reshape(COLPALI_PATCHES, COLPALI_DIM)

    if arr.ndim == 1 and arr.shape[0] != COLPALI_FLAT_LEN:
        raise ValueError(
            f"展平向量長度必須為 {COLPALI_FLAT_LEN}，收到 {arr.shape[0]}",
        )

    raise ValueError(
        f"無法將 colpali_multi 還原為 ({COLPALI_PATCHES}, {COLPALI_DIM})，收到 shape={arr.shape}",
    )


def coarse_distance_to_similarity_score(distance: float) -> float:
    """
    將 LanceDB `metric='cosine'` 回傳的距離映射到 [0, 1] 相似度，供 `RetrievalCandidate.maxsim_score` 粗排階段使用。

    文件慣例：cosine 距離約在 [0, 2]，相同向量距離 0 → 分數 1。
    """
    d = float(distance)
    sim = 1.0 - d / 2.0
    if sim < 0.0:
        return 0.0
    if sim > 1.0:
        return 1.0
    return sim


def _extract_keyword_terms(query_text: str) -> list[str]:
    raw = (query_text or "").strip().lower()
    if not raw:
        return []

    tokens = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", raw)
    terms: list[str] = []
    for token in tokens:
        if token in _FTS_STOPWORDS:
            continue
        if token not in terms:
            terms.append(token)

    if terms:
        return terms
    return [raw]


@dataclass(frozen=True)
class CoarseSearchHit:
    slide_id: str
    distance: float
    row: dict[str, Any]


class LanceDBManager:
    """
    LanceDB 連線與投影片表維護：寫入巢狀 colpali_multi、agg 向量、IVF-PQ 粗檢索索引。
    """

    def __init__(
        self,
        uri: str,
        table_name: str = "slides",
        *,
        connect: DBConnection | None = None,
    ) -> None:
        self._uri = uri
        self._table_name = table_name
        self._db: DBConnection = connect if connect is not None else lancedb.connect(uri)

    @property
    def db(self) -> DBConnection:
        return self._db

    @property
    def table_name(self) -> str:
        return self._table_name

    def open_table(self) -> Table:
        return self._db.open_table(self._table_name)

    def table_exists(self) -> bool:
        try:
            self._db.open_table(self._table_name)
            return True
        except Exception:
            return False

    def create_table(
        self,
        mode: str = "create",
        schema: pa.Schema | None = None,
    ) -> Table:
        """
        建立空表或覆寫。`mode`: ``create`` | ``overwrite``。
        """
        sch = schema or slide_table_schema()
        if mode == "overwrite":
            return self._db.create_table(self._table_name, schema=sch, mode="overwrite")
        if mode == "create":
            return self._db.create_table(self._table_name, schema=sch, mode="create")
        raise ValueError("mode 必須為 'create' 或 'overwrite'")

    def normalize_slide_record(self, rec: Mapping[str, Any]) -> dict[str, Any]:
        """
        正規化寫入列：若缺 `colpali_agg_128` 則由 `colpali_multi` 計算；
        若 `colpali_multi` 為 ndarray 則轉巢狀 list；補上 `created_at`。
        """
        out = dict(rec)
        if "created_at" not in out:
            out["created_at"] = datetime.now(timezone.utc)

        cm = out.get("colpali_multi")
        if cm is None:
            raise ValueError("記錄必須包含 colpali_multi")

        multi = colpali_multi_to_numpy(cm)
        out["colpali_multi"] = numpy_multi_to_nested_list(multi)

        if out.get("colpali_agg_128") is None:
            agg = compute_colpali_agg_128(multi)
            out["colpali_agg_128"] = agg.tolist()
        elif isinstance(out["colpali_agg_128"], np.ndarray):
            agg = np.ascontiguousarray(out["colpali_agg_128"], dtype=np.float32)
            if agg.shape != (COLPALI_DIM,):
                raise ValueError(f"colpali_agg_128 形狀須為 ({COLPALI_DIM},)，收到 {agg.shape}")
            out["colpali_agg_128"] = agg.tolist()

        if out.get("quality_metrics") is not None and not isinstance(out["quality_metrics"], str):
            out["quality_metrics"] = json.dumps(out["quality_metrics"], ensure_ascii=False)

        for key in ("imagebind_vec", "patch_bboxes"):
            val = out.get(key)
            if isinstance(val, np.ndarray):
                out[key] = val.tolist()

        unknown = set(out) - SLIDE_TABLE_FIELD_NAMES
        if unknown:
            logger.debug("略過非 Schema 欄位: %s", sorted(unknown))
        return {k: out[k] for k in out if k in SLIDE_TABLE_FIELD_NAMES}

    def add(self, records: Sequence[Mapping[str, Any]], *, mode: str = "append") -> Table:
        """批次寫入；自動正規化向量與欄位。"""
        rows = [self.normalize_slide_record(r) for r in records]
        if not self.table_exists():
            tbl = self.create_table(mode="create")
            tbl.add(rows)
            return tbl
        tbl = self.open_table()
        tbl.add(rows, mode=mode)
        return tbl

    def count_rows(self) -> int:
        return int(self.open_table().count_rows())

    def build_ivf_pq_index_on_agg(
        self,
        *,
        metric: str = "cosine",
        num_partitions: int | None = None,
        num_sub_vectors: int | None = None,
        vector_column_name: str = "colpali_agg_128",
        replace: bool = True,
        wait_timeout_s: float | None = None,
    ) -> bool:
        """
        於 `colpali_agg_128` 上建立 IVF-PQ（§3.3）。

        若列數 < `_MIN_ROWS_FOR_IVF_PQ`，跳過建索引並回傳 False（粗檢索仍可用無索引 `search`）。
        """
        tbl = self.open_table()
        n = int(tbl.count_rows())
        if n < _MIN_ROWS_FOR_IVF_PQ:
            warnings.warn(
                f"列數 {n} < {_MIN_ROWS_FOR_IVF_PQ}，Lance PQ 訓練不足；已跳過 IVF-PQ。"
                " 粗檢索將使用無索引向量掃描。",
                stacklevel=2,
            )
            return False

        if num_sub_vectors is None:
            num_sub_vectors = max(8, COLPALI_DIM // 8)

        if num_partitions is None:
            num_partitions = max(2, min(256, n // 4096))
            if num_partitions >= n:
                num_partitions = max(1, n // 2)

        kwargs: dict[str, Any] = {
            "metric": metric,
            "vector_column_name": vector_column_name,
            "num_partitions": num_partitions,
            "num_sub_vectors": num_sub_vectors,
            "replace": replace,
            "index_type": "IVF_PQ",
        }
        if wait_timeout_s is not None:
            from datetime import timedelta

            kwargs["wait_timeout"] = timedelta(seconds=wait_timeout_s)

        tbl.create_index(**kwargs)
        logger.info(
            "IVF-PQ 已建立：column=%s partitions=%s sub_vectors=%s rows=%s",
            vector_column_name,
            num_partitions,
            num_sub_vectors,
            n,
        )
        return True

    def coarse_search(
        self,
        query_agg_128: np.ndarray,
        *,
        k: int,
        vector_column_name: str = "colpali_agg_128",
        metric: str = "cosine",
        nprobes: int | None = None,
    ) -> list[CoarseSearchHit]:
        """第一階段粗檢索：以匯總向量查詢 Top-K。"""
        q = np.ascontiguousarray(query_agg_128, dtype=np.float32).reshape(COLPALI_DIM)
        tbl = self.open_table()
        builder = tbl.search(q, vector_column_name=vector_column_name).metric(metric).limit(k)
        if nprobes is not None:
            builder = builder.nprobes(nprobes)
        df = builder.to_pandas()
        hits: list[CoarseSearchHit] = []
        for _, row in df.iterrows():
            dist = float(row["_distance"])
            sid = str(row["slide_id"])
            hits.append(CoarseSearchHit(slide_id=sid, distance=dist, row=row.to_dict()))
        return hits

    def keyword_search(
        self,
        query_text: str,
        *,
        k: int,
        text_column: str = "fts_text",
    ) -> list[CoarseSearchHit]:
        """Keyword/FTS-like coarse search over the `fts_text` column."""
        query_text = (query_text or "").strip()
        if not query_text:
            return []

        tbl = self.open_table()
        df = tbl.to_pandas()
        if text_column not in df.columns:
            return []

        terms = _extract_keyword_terms(query_text)
        if not terms:
            return []

        query_compact = re.sub(r"\s+", "", query_text.lower())
        scored_rows: list[tuple[float, dict[str, Any]]] = []

        for _, row in df.iterrows():
            text = row.get(text_column)
            if text is None:
                continue
            text_l = str(text).lower()
            text_compact = re.sub(r"\s+", "", text_l)

            term_weight_total = 0.0
            matched_weight = 0.0
            for term in terms:
                weight = 2.0 if re.search(r"[a-z0-9]", term) else 1.0
                term_weight_total += weight
                if term in text_l:
                    matched_weight += weight

            if term_weight_total <= 0:
                continue

            score = matched_weight / term_weight_total
            if query_compact and query_compact in text_compact:
                score = min(1.0, score + 0.25)

            if score <= 0:
                continue

            row_dict = row.to_dict()
            row_dict["match_type"] = "fts"
            row_dict["keyword_score"] = float(score)
            row_dict["retrieval_source"] = "fts"
            scored_rows.append((float(score), row_dict))

        scored_rows.sort(key=lambda item: (-item[0], str(item[1].get("slide_id", ""))))
        hits: list[CoarseSearchHit] = []
        for score, row_dict in scored_rows[: max(0, k) if k else None]:
            sid = str(row_dict.get("slide_id"))
            hits.append(CoarseSearchHit(slide_id=sid, distance=float(1.0 - score), row=row_dict))
        return hits

    def hybrid_coarse_search(
        self,
        query_agg_128: np.ndarray,
        query_text: str,
        *,
        k: int,
        vector_column_name: str = "colpali_agg_128",
        text_column: str = "fts_text",
        metric: str = "cosine",
        nprobes: int | None = None,
    ) -> tuple[list[CoarseSearchHit], dict[str, int]]:
        """Run vector search and keyword search in parallel, then merge by slide_id."""
        with ThreadPoolExecutor(max_workers=2) as executor:
            vector_future = executor.submit(
                self.coarse_search,
                query_agg_128,
                k=k,
                vector_column_name=vector_column_name,
                metric=metric,
                nprobes=nprobes,
            )
            keyword_future = executor.submit(
                self.keyword_search,
                query_text,
                k=k,
                text_column=text_column,
            )
            vector_hits = vector_future.result()
            keyword_hits = keyword_future.result()

        merged: dict[str, dict[str, Any]] = {}

        def _merge_hit(hit: CoarseSearchHit, source: str) -> None:
            entry = merged.setdefault(
                hit.slide_id,
                {
                    "slide_id": hit.slide_id,
                    "distance": float(hit.distance),
                    "row": dict(hit.row),
                    "sources": set(),
                },
            )
            entry["sources"].add(source)
            entry["distance"] = min(float(entry["distance"]), float(hit.distance))
            row = entry["row"]
            row.update(hit.row)
            row["retrieval_source"] = source
            if source == "vector":
                row["vector_distance"] = float(hit.distance)
            elif source == "fts":
                row["keyword_distance"] = float(hit.distance)
                row["keyword_score"] = float(hit.row.get("keyword_score", max(0.0, 1.0 - float(hit.distance))))

        for hit in vector_hits:
            _merge_hit(hit, "vector")
        for hit in keyword_hits:
            _merge_hit(hit, "fts")

        merged_hits: list[CoarseSearchHit] = []
        for item in merged.values():
            sources = item["sources"]
            row = dict(item["row"])
            if sources == {"fts"}:
                row["match_type"] = "title-hit"
            elif sources == {"vector"}:
                row["match_type"] = "vector-hit"
            else:
                row["match_type"] = "hybrid-title-hit"
            row["retrieval_sources"] = sorted(sources)
            merged_hits.append(
                CoarseSearchHit(
                    slide_id=str(item["slide_id"]),
                    distance=float(item["distance"]),
                    row=row,
                )
            )

        def _sort_key(hit: CoarseSearchHit) -> tuple[int, float, str]:
            sources = hit.row.get("retrieval_sources", [])
            is_fts = 0 if "fts" in sources else 1
            return (is_fts, float(hit.distance), str(hit.slide_id))

        merged_hits.sort(key=_sort_key)

        stats = {
            "vector_candidates": len(vector_hits),
            "fts_candidates": len(keyword_hits),
            "union_candidates": len(merged_hits),
        }
        logger.info(
            "Hybrid coarse search completed: vector=%s fts=%s union=%s",
            stats["vector_candidates"],
            stats["fts_candidates"],
            stats["union_candidates"],
        )
        return merged_hits, stats

    def get_colpali_multi(self, slide_id: str) -> np.ndarray:
        """依 slide_id 讀取多向量並還原為 (1024, 128)。"""
        tbl = self.open_table()
        at = tbl.to_arrow()
        mask = pc.equal(at["slide_id"], pa.scalar(slide_id, type=pa.string()))
        filtered = at.filter(mask)
        if filtered.num_rows == 0:
            raise KeyError(f"找不到 slide_id={slide_id!r}")
        raw = filtered.column("colpali_multi")[0].as_py()
        return colpali_multi_to_numpy(raw)

    def coarse_hits_to_retrieval_candidates(
        self,
        hits: Sequence[CoarseSearchHit],
    ) -> list[RetrievalCandidate]:
        """
        將粗檢索命中轉成 `RetrievalCandidate`（`retrieval_stage='filtering'`）。

        `evidence_patches` 於第一階段為空；MaxSim 後由 Lakehouse-Agent 填入。
        """
        out: list[RetrievalCandidate] = []
        for h in hits:
            row = h.row
            score = coarse_distance_to_similarity_score(h.distance)
            page_index = int(row.get("page_index", 0))
            meta = {
                "deck_id": row.get("deck_id"),
                "source_path": row.get("source_path"),
                "coarse_distance": h.distance,
            }
            out.append(
                RetrievalCandidate(
                    slide_id=h.slide_id,
                    page_index=page_index,
                    maxsim_score=score,
                    evidence_patches=[],
                    retrieval_stage="filtering",
                    metadata={k: v for k, v in meta.items() if v is not None},
                )
            )
        return out

    def fetch_colpali_tensors(
        self,
        slide_ids: Sequence[str],
    ) -> dict[str, np.ndarray]:
        """批次讀取多向量，供第二階段 MaxSim（形狀皆為 (1024, 128)）。"""
        result: dict[str, np.ndarray] = {}
        for sid in slide_ids:
            result[sid] = self.get_colpali_multi(str(sid))
        return result
