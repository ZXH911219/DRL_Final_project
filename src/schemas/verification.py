"""VerificationReport、VerifiedOutput（對齊 openspec/specs/specs.md §2.6）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .enums import RiskLevel, VerificationStatus
from .query import QueryPayload
from .reasoning import ReasoningBundle
from .retrieval import RetrievalContext


class EvidenceRegion(BaseModel):
    patch_coords: tuple[int, int, int, int] = Field(
        ...,
        description="patch 網格 tl_x, tl_y, br_x, br_y（含邊界約定）",
    )
    bbox_norm: tuple[float, float, float, float]
    region_type: Literal["text", "chart", "image", "other"]
    referenced_claim: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class VerifiedCandidate(BaseModel):
    slide_id: str
    original_reranked_score: float
    adjusted_score: float = Field(..., ge=0.0, le=1.0)
    verification_status: VerificationStatus
    hallucination_risk_score: float = Field(..., ge=0.0, le=1.0)
    hallucination_risk_level: RiskLevel
    evidence_coverage_ratio: float = Field(..., ge=0.0, le=1.0)
    semantic_consistency: float = Field(..., ge=0.0, le=1.0)
    verified_claims: list[str] = Field(default_factory=list)
    unverified_claims: list[str] = Field(default_factory=list)
    evidence_regions: list[EvidenceRegion] = Field(default_factory=list)
    evidence_map_asset_id: str | None = None
    inference_text: str | None = Field(
        None,
        description="模型推理產生的原始文本內容",
    )


class VerificationReport(BaseModel):
    verification_id: str
    request_id: str
    generated_at: datetime
    per_slide: list[VerifiedCandidate]
    audit_trail: dict[str, Any]
    summary: dict[str, Any] = Field(
        default_factory=dict,
        description="如 pass/warn/fail 計數、平均風險",
    )


class VerifiedOutput(BaseModel):
    """對使用者／Streamlit 的最終契約。"""

    request_id: str
    query: QueryPayload
    retrieval: RetrievalContext
    reasoning: ReasoningBundle
    verification: VerificationReport
    total_latency_ms: float
    degradation_flags: list[str] = Field(
        default_factory=list,
        description="例如 reasoning_timeout, verification_timeout",
    )

    @model_validator(mode="after")
    def aligned_request_ids(self) -> VerifiedOutput:
        ids = {
            self.request_id,
            self.query.request_id,
            self.retrieval.request_id,
            self.reasoning.request_id,
            self.verification.request_id,
        }
        if len(ids) != 1:
            raise ValueError(
                "VerifiedOutput 內 request_id 與子物件 request_id 必須完全一致",
            )
        return self
