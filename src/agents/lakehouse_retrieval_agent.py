"""Lakehouse-Retrieval-Agent（對齊 openspec/specs/specs.md §2.4）。"""

from __future__ import annotations

import io
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
from PIL import Image

from ..schemas import EvidencePatch, QueryPayload, RetrievalCandidate, RetrievalContext, RetrievalMetrics
from ..schemas.enums import Modality
from ..storage import COLPALI_DIM, COLPALI_PATCHES, LanceDBManager, colpali_multi_to_numpy

logger = logging.getLogger(__name__)


def _default_patch_bbox_norm(patch_index: int) -> tuple[float, float, float, float]:
    if patch_index < 0 or patch_index >= COLPALI_PATCHES:
        raise ValueError(f"patch_index 必須介於 0..{COLPALI_PATCHES - 1}")
    grid = 32
    y, x = divmod(int(patch_index), grid)
    x0 = x / grid
    y0 = y / grid
    x1 = (x + 1) / grid
    y1 = (y + 1) / grid
    return float(x0), float(y0), float(x1), float(y1)


def _align_embeddings_to_colpali_dim(embeddings: np.ndarray) -> np.ndarray:
    """將模型輸出對齊到 (Q, 128)；若 hidden dimension 不符則截斷或補零。"""
    if embeddings.ndim != 2:
        raise ValueError(f"預期 2D embeddings，收到 shape={embeddings.shape}")
    _, hidden = embeddings.shape
    aligned = np.ascontiguousarray(embeddings, dtype=np.float32)
    if hidden > COLPALI_DIM:
        aligned = aligned[:, :COLPALI_DIM]
    elif hidden < COLPALI_DIM:
        pad = np.zeros((aligned.shape[0], COLPALI_DIM - hidden), dtype=np.float32)
        aligned = np.concatenate([aligned, pad], axis=1)
    return aligned


class ColPaliQueryEncoder:
    """ColPali 查詢編碼器：文字／圖像查詢都回傳 (Q, 128) 多向量。"""

    def __init__(
        self,
        model_id: str = "vidore/colpali-v1.3-hf",
        *,
        device: str | None = None,
        dtype: Literal["auto", "float16", "bfloat16", "float32"] = "auto",
        fallback_tokens: int = 32,
        fallback_seed: int = 42,
        load_hf: bool = True,
    ) -> None:
        self._model_id = model_id
        self._fallback_tokens = int(fallback_tokens)
        self._fallback_seed = int(fallback_seed)
        self._backend = "stub"
        self._torch = None
        self._model = None
        self._processor = None

        if not load_hf:
            return

        try:
            import torch
            from transformers import ColPaliForRetrieval, ColPaliProcessor
        except ImportError:
            logger.warning("未安裝 torch / transformers，ColPaliQueryEncoder 將使用 stub fallback。")
            return

        self._torch = torch
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self._device = device

        torch_dtype: Any = None
        if dtype == "float16":
            torch_dtype = torch.float16
        elif dtype == "bfloat16":
            torch_dtype = torch.bfloat16
        elif dtype == "float32":
            torch_dtype = torch.float32
        elif dtype == "auto":
            torch_dtype = "auto"

        self._processor = ColPaliProcessor.from_pretrained(model_id)
        if device == "cpu":
            kw: dict[str, Any] = {}
            if isinstance(torch_dtype, str):
                kw["torch_dtype"] = torch.float32
            elif torch_dtype is not None:
                kw["torch_dtype"] = torch_dtype
            self._model = ColPaliForRetrieval.from_pretrained(model_id, **kw)
            self._model.to("cpu")
        else:
            kw = {"device_map": "auto"}
            if torch_dtype is not None:
                kw["torch_dtype"] = torch_dtype
            self._model = ColPaliForRetrieval.from_pretrained(model_id, **kw)
        self._model.eval()
        self._backend = "hf_colpali"

    @property
    def backend(self) -> str:
        return self._backend

    def _encode_with_stub(self, payload: bytes | str) -> np.ndarray:
        seed = self._fallback_seed
        if isinstance(payload, str):
            seed ^= hash(payload) & 0xFFFFFFFF
        else:
            seed ^= hash(payload) & 0xFFFFFFFF
        rng = np.random.default_rng(seed)
        emb = rng.standard_normal((self._fallback_tokens, COLPALI_DIM), dtype=np.float32)
        norms = np.maximum(np.linalg.norm(emb, axis=1, keepdims=True), 1e-8)
        return np.ascontiguousarray(emb / norms, dtype=np.float32)

    def _encode_with_hf(self, *, text: str | None = None, image: Image.Image | None = None) -> tuple[np.ndarray, dict[str, Any]]:
        assert self._torch is not None
        assert self._processor is not None
        assert self._model is not None

        if text is None and image is None:
            raise ValueError("text 與 image 至少需提供一項")

        if text is not None and image is not None:
            inputs = self._processor(text=[text], images=[image], return_tensors="pt")
        elif text is not None:
            inputs = self._processor(text=[text], return_tensors="pt")
        else:
            inputs = self._processor(images=[image], return_tensors="pt")

        device = next(self._model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}

        t0 = time.perf_counter()
        with self._torch.inference_mode():
            out = self._model(**inputs)
            emb_tensor = getattr(out, "embeddings", None)
            if emb_tensor is None:
                raise RuntimeError("ColPali 模型輸出缺少 embeddings 欄位")
            emb = emb_tensor[0].detach().float().cpu().numpy()
        elapsed_ms = (time.perf_counter() - t0) * 1000

        aligned = _align_embeddings_to_colpali_dim(emb)
        info = {
            "backend": "hf_colpali",
            "model_id": self._model_id,
            "encode_ms": elapsed_ms,
            "source_tokens": int(emb.shape[0]),
            "source_hidden": int(emb.shape[1]),
        }
        return aligned, info

    def encode_text(self, text: str) -> tuple[np.ndarray, dict[str, Any]]:
        text = text.strip()
        if not text:
            raise ValueError("query_text 不可為空")
        if self._backend == "hf_colpali":
            try:
                return self._encode_with_hf(text=text)
            except Exception:
                logger.warning("HF ColPali 文字編碼失敗，改用 stub fallback", exc_info=True)
        return self._encode_with_stub(text), {"backend": "stub", "modality": "text"}

    def encode_image(self, image: Image.Image) -> tuple[np.ndarray, dict[str, Any]]:
        if self._backend == "hf_colpali":
            try:
                return self._encode_with_hf(image=image)
            except Exception:
                logger.warning("HF ColPali 圖像編碼失敗，改用 stub fallback", exc_info=True)
        return self._encode_with_stub(image.tobytes()), {"backend": "stub", "modality": "image"}


def build_query_encoder_from_env() -> ColPaliQueryEncoder:
    """從環境變數建立查詢編碼器。"""
    backend = os.environ.get("COLPALI_BACKEND", "stub").strip().lower()
    model = os.environ.get("COLPALI_MODEL", "vidore/colpali-v1.3-hf")
    device = os.environ.get("COLPALI_DEVICE")
    dtype = os.environ.get("COLPALI_DTYPE", "auto")
    fallback_tokens = int(os.environ.get("COLPALI_QUERY_FALLBACK_TOKENS", "32"))
    fallback_seed = int(os.environ.get("COLPALI_STUB_SEED", "42"))

    if backend in {"stub", "fake", "dummy"}:
        return ColPaliQueryEncoder(
            model_id=model,
            device=device,
            dtype=dtype,  # type: ignore[arg-type]
            fallback_tokens=fallback_tokens,
            fallback_seed=fallback_seed,
            load_hf=False,
        )
    if backend in {"hf", "huggingface", "transformers"}:
        return ColPaliQueryEncoder(
            model_id=model,
            device=device,
            dtype=dtype,  # type: ignore[arg-type]
            fallback_tokens=fallback_tokens,
            fallback_seed=fallback_seed,
            load_hf=True,
        )
    raise ValueError(f"未知 COLPALI_BACKEND={backend!r}（stub / hf）")


@dataclass(frozen=True)
class _LoadedCandidate:
    slide_id: str
    page_index: int
    row: dict[str, Any]
    colpali_multi: np.ndarray


class LakehouseRetrievalAgent:
    """Lakehouse-Retrieval-Agent：粗檢索 + MaxSim 精排 + 證據區塊標註。"""

    def __init__(
        self,
        lance: LanceDBManager,
        *,
        query_encoder: ColPaliQueryEncoder | None = None,
        evidence_top_n: int = 5,
        batch_size: int = 32,
        use_gpu: bool | None = None,
    ) -> None:
        self._lance = lance
        self._query_encoder = query_encoder or build_query_encoder_from_env()
        self._evidence_top_n = max(1, int(evidence_top_n))
        self._batch_size = max(1, int(batch_size))
        self._use_gpu = use_gpu

    @property
    def lance(self) -> LanceDBManager:
        return self._lance

    @property
    def query_encoder(self) -> ColPaliQueryEncoder:
        return self._query_encoder

    def _load_query_vectors(self, query: QueryPayload) -> tuple[np.ndarray, dict[str, Any]]:
        query_vectors: list[np.ndarray] = []
        encoder_meta: dict[str, Any] = {"query_backend": self._query_encoder.backend, "raw_query_text": query.query_text}

        if query.modality in (Modality.TEXT, Modality.MULTIMODAL):
            if not query.query_text:
                raise ValueError("TEXT / MULTIMODAL 查詢需提供 query_text")
            text_vec, text_meta = self._query_encoder.encode_text(query.query_text)
            query_vectors.append(text_vec)
            encoder_meta["text"] = text_meta

        if query.modality in (Modality.IMAGE, Modality.MULTIMODAL):
            if not query.query_image_bytes:
                raise ValueError("IMAGE / MULTIMODAL 查詢需提供 query_image_bytes")
            image = Image.open(io.BytesIO(query.query_image_bytes)).convert("RGB")
            image_vec, image_meta = self._query_encoder.encode_image(image)
            query_vectors.append(image_vec)
            encoder_meta["image"] = image_meta

        if not query_vectors:
            raise ValueError("查詢至少需包含文字或圖像其中一種模態")

        query_multi = np.ascontiguousarray(np.concatenate(query_vectors, axis=0), dtype=np.float32)
        if query_multi.ndim != 2 or query_multi.shape[1] != COLPALI_DIM:
            raise ValueError(f"query multi-vector 形狀必須為 (Q, {COLPALI_DIM})，收到 {query_multi.shape}")
        encoder_meta["query_tokens"] = int(query_multi.shape[0])
        return query_multi, encoder_meta

    def _query_aggregate(self, query_multi: np.ndarray) -> np.ndarray:
        return np.ascontiguousarray(query_multi, dtype=np.float32).mean(axis=0)

    def _load_candidate(self, hit: Any) -> _LoadedCandidate:
        row = dict(hit.row)
        slide_id = str(hit.slide_id)
        page_index = int(row.get("page_index", 0))

        colpali_multi = self._lance.get_colpali_multi(slide_id)
        row["colpali_multi"] = colpali_multi

        return _LoadedCandidate(
            slide_id=slide_id,
            page_index=page_index,
            row=row,
            colpali_multi=colpali_multi,
        )

    def _load_patch_bboxes(self, row: dict[str, Any], patch_count: int) -> list[tuple[float, float, float, float]]:
        raw = row.get("patch_bboxes")
        if raw is None:
            return [_default_patch_bbox_norm(i) for i in range(patch_count)]
        try:
            if hasattr(raw, "as_py"):
                raw = raw.as_py()
            out: list[tuple[float, float, float, float]] = []
            for i, item in enumerate(raw):
                if item is None:
                    out.append(_default_patch_bbox_norm(i))
                else:
                    x0, y0, x1, y1 = item
                    out.append((float(x0), float(y0), float(x1), float(y1)))
            if len(out) < patch_count:
                out.extend(_default_patch_bbox_norm(i) for i in range(len(out), patch_count))
            return out[:patch_count]
        except Exception:
            logger.debug("patch_bboxes 解析失敗，改用預設 32x32 網格", exc_info=True)
            return [_default_patch_bbox_norm(i) for i in range(patch_count)]

    def _maxsim_scores(
        self,
        query_multi: np.ndarray,
        docs: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """回傳 (candidate_scores, patch_scores)；候選內的 patch_scores 取 max over query tokens。"""
        try:
            import torch
            import torch.nn.functional as F
        except ImportError:
            q = np.ascontiguousarray(query_multi, dtype=np.float32)
            q = q / np.maximum(np.linalg.norm(q, axis=1, keepdims=True), 1e-8)
            score_chunks: list[np.ndarray] = []
            patch_chunks: list[np.ndarray] = []
            for start in range(0, docs.shape[0], self._batch_size):
                chunk = np.ascontiguousarray(docs[start : start + self._batch_size], dtype=np.float32)
                chunk = chunk / np.maximum(np.linalg.norm(chunk, axis=2, keepdims=True), 1e-8)
                sim = np.einsum("qd,bnd->bqn", q, chunk)
                patch_scores = sim.max(axis=1)
                score_chunks.append(patch_scores.mean(axis=1))
                patch_chunks.append(patch_scores)
            return np.concatenate(score_chunks, axis=0), np.concatenate(patch_chunks, axis=0)

        use_cuda = self._use_gpu if self._use_gpu is not None else torch.cuda.is_available()
        device = torch.device("cuda" if use_cuda and torch.cuda.is_available() else "cpu")

        q = torch.as_tensor(query_multi, dtype=torch.float32, device=device)
        q = F.normalize(q, p=2, dim=-1)

        score_chunks: list[np.ndarray] = []
        patch_chunks: list[np.ndarray] = []
        for start in range(0, docs.shape[0], self._batch_size):
            chunk = torch.as_tensor(docs[start : start + self._batch_size], dtype=torch.float32, device=device)
            chunk = F.normalize(chunk, p=2, dim=-1)
            sim = torch.einsum("qd,bnd->bqn", q, chunk)
            patch_scores = sim.max(dim=1).values
            score_chunks.append(patch_scores.mean(dim=1).detach().cpu().numpy())
            patch_chunks.append(patch_scores.detach().cpu().numpy())

        return np.concatenate(score_chunks, axis=0), np.concatenate(patch_chunks, axis=0)

    def search(self, query: QueryPayload) -> RetrievalContext:
        """執行 QueryPayload → RetrievalContext 的完整湖倉檢索流程。"""
        t0 = time.perf_counter()
        query_multi, encoder_meta = self._load_query_vectors(query)
        query_agg = self._query_aggregate(query_multi)

        t_filter0 = time.perf_counter()
        coarse_hits, coarse_stats = self._lance.hybrid_coarse_search(
            query_agg,
            query.query_text,
            k=query.top_k_filter,
        )
        logger.info(
            "Retrieval coarse stats: vector=%s fts=%s union=%s query=%r",
            coarse_stats.get("vector_candidates", 0),
            coarse_stats.get("fts_candidates", 0),
            coarse_stats.get("union_candidates", 0),
            query.query_text,
        )
        filter_stage_latency_ms = (time.perf_counter() - t_filter0) * 1000

        if not coarse_hits:
            metrics = RetrievalMetrics(
                total_latency_ms=(time.perf_counter() - t0) * 1000,
                filter_stage_latency_ms=filter_stage_latency_ms,
                maxsim_stage_latency_ms=0.0,
                candidates_examined=0,
                recall_at_10=None,
                mrr=None,
            )
            return RetrievalContext(
                request_id=query.request_id,
                query=query,
                candidates=[],
                metrics=metrics,
                query_colpali=query_multi.tolist(),
                query_imagebind=None,
            )

        loaded_candidates = [self._load_candidate(hit) for hit in coarse_hits]
        docs = np.stack([candidate.colpali_multi for candidate in loaded_candidates], axis=0)

        t_max0 = time.perf_counter()
        candidate_scores, patch_scores = self._maxsim_scores(query_multi, docs)
        maxsim_stage_latency_ms = (time.perf_counter() - t_max0) * 1000

        # Apply a base-score premium before Top-N filtering so keyword hits survive reranking.
        try:
            for i, cand in enumerate(loaded_candidates):
                sources = cand.row.get("retrieval_sources", [])
                match_type = str(cand.row.get("match_type", "vector-hit"))
                keyword_score = float(cand.row.get("keyword_score", 0.0) or 0.0)
                if "fts" in sources or match_type.startswith("title"):
                    premium = 0.05 + (keyword_score * 0.01)
                    if "vector" in sources:
                        premium += 0.02
                    candidate_scores[i] = float(candidate_scores[i]) + premium
                    cand.row["match_type"] = match_type if match_type != "vector-hit" else "title-hit"
                else:
                    cand.row["match_type"] = "vector-hit"
        except Exception:
            logger.debug("title premium application failed", exc_info=True)

        ranked_indices = np.argsort(-candidate_scores)
        top_indices = ranked_indices[: min(query.top_k_maxsim, len(loaded_candidates))]

        candidates: list[RetrievalCandidate] = []
        for rank_position, idx in enumerate(top_indices, start=1):
            candidate = loaded_candidates[int(idx)]
            raw_score = float(candidate_scores[int(idx)])
            maxsim_score = float(np.clip((raw_score + 1.0) / 2.0, 0.0, 1.0))
            candidate_patch_scores = patch_scores[int(idx)]
            top_patch_indices = np.argsort(-candidate_patch_scores)[: self._evidence_top_n]
            bboxes = self._load_patch_bboxes(candidate.row, patch_count=int(candidate.colpali_multi.shape[0]))

            evidence_patches = [
                EvidencePatch(
                    patch_index=int(patch_index),
                    score=float(np.clip((float(candidate_patch_scores[int(patch_index)]) + 1.0) / 2.0, 0.0, 1.0)),
                    bbox_norm=bboxes[int(patch_index)],
                )
                for patch_index in top_patch_indices
            ]

            metadata = {
                k: v
                for k, v in candidate.row.items()
                if k not in {"colpali_multi", "patch_bboxes"} and v is not None
            }
            metadata.update(
                {
                    "raw_maxsim_score": raw_score,
                    "rank_position": rank_position,
                    "query_tokens": int(query_multi.shape[0]),
                    "encoder_backend": encoder_meta.get("query_backend"),
                    "match_type": candidate.row.get("match_type", "vector-hit"),
                    "retrieval_sources": candidate.row.get("retrieval_sources", []),
                }
            )
            candidates.append(
                RetrievalCandidate(
                    slide_id=candidate.slide_id,
                    page_index=candidate.page_index,
                    maxsim_score=maxsim_score,
                    evidence_patches=evidence_patches,
                    retrieval_stage="hybrid" if "fts" in candidate.row.get("retrieval_sources", []) else "maxsim",
                    metadata=metadata,
                )
            )

        metrics = RetrievalMetrics(
            total_latency_ms=(time.perf_counter() - t0) * 1000,
            filter_stage_latency_ms=filter_stage_latency_ms,
            maxsim_stage_latency_ms=maxsim_stage_latency_ms,
            candidates_examined=len(loaded_candidates),
            recall_at_10=None,
            mrr=None,
        )
        return RetrievalContext(
            request_id=query.request_id,
            query=query,
            candidates=candidates,
            metrics=metrics,
            query_colpali=query_multi.tolist(),
            query_imagebind=None,
        )


__all__ = [
    "ColPaliQueryEncoder",
    "LakehouseRetrievalAgent",
    "build_query_encoder_from_env",
]