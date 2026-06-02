"""ReasoningBundle（對齊 openspec/specs/specs.md §2.5）。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ReasoningStep(BaseModel):
    step_id: int
    step_name: str
    reasoning_text: str
    local_score: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)


class RankedCandidate(BaseModel):
    slide_id: str
    original_rank: int
    reranked_score: float = Field(..., ge=0.0, le=1.0)
    retrieval_score: float
    reasoning_score: float
    completeness_score: float = Field(0.0, ge=0.0, le=1.0)
    inference_text: str
    reasoning_steps: list[ReasoningStep]
    confidence_level: Literal["high", "medium", "low"]
    key_evidence_phrases: list[str]
    fallback_retrieval_only: bool = False


class ReasoningBundle(BaseModel):
    request_id: str
    ranking: list[RankedCandidate]
    reasoning_model_revision: str
    audit: dict[str, Any] = Field(default_factory=dict)
