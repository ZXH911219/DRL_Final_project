"""RetrievalContext 與候選結構（對齊 openspec/specs/specs.md §2.4）。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .query import QueryPayload

IMAGEBIND_DIM: int = 1024


class EvidencePatch(BaseModel):
    patch_index: int = Field(..., ge=0, le=1023)
    score: float
    bbox_norm: tuple[float, float, float, float] = Field(
        ...,
        description="x0,y0,x1,y1 相對原圖 0–1",
    )


class RetrievalCandidate(BaseModel):
    slide_id: str
    page_index: int
    maxsim_score: float = Field(..., ge=0.0, le=1.0)
    evidence_patches: list[EvidencePatch]
    retrieval_stage: Literal["filtering", "maxsim", "hybrid"] = "maxsim"
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalMetrics(BaseModel):
    total_latency_ms: float
    filter_stage_latency_ms: float
    maxsim_stage_latency_ms: float
    candidates_examined: int
    recall_at_10: float | None = None
    mrr: float | None = None


class RetrievalContext(BaseModel):
    """Lakehouse-Retrieval-Agent 輸出；Reasoning-Reranker 輸入。"""

    request_id: str
    query: QueryPayload
    candidates: list[RetrievalCandidate]
    metrics: RetrievalMetrics
    query_colpali: list[list[float]] | None = Field(
        None,
        description="序列化 (Q,128)，可選避免重算",
    )
    query_imagebind: list[float] | None = Field(
        None,
        description="長度 1024；與索引欄位一致",
    )

    @model_validator(mode="after")
    def request_id_matches_query(self) -> RetrievalContext:
        if self.request_id != self.query.request_id:
            raise ValueError(
                "RetrievalContext.request_id 必須與 query.request_id 一致",
            )
        return self

    @model_validator(mode="after")
    def query_imagebind_dim(self) -> RetrievalContext:
        if self.query_imagebind is not None and len(self.query_imagebind) != IMAGEBIND_DIM:
            raise ValueError(
                f"query_imagebind 長度必須為 {IMAGEBIND_DIM}，收到 {len(self.query_imagebind)}",
            )
        return self

    @model_validator(mode="after")
    def query_colpali_row_dim(self) -> RetrievalContext:
        if self.query_colpali is None:
            return self
        for i, row in enumerate(self.query_colpali):
            if len(row) != 128:
                raise ValueError(
                    f"query_colpali[{i}] 每列須為長度 128（ColPali 維度），收到 {len(row)}",
                )
        return self
