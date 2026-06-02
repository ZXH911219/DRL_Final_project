"""
Pydantic 綱要模組（對齊 openspec/specs/specs.md §2）。

Python 3.10+；建議搭配 Pydantic v2。
"""

from __future__ import annotations

from .enums import Modality, RiskLevel, VerificationStatus
from .query import QueryPayload
from .reasoning import RankedCandidate, ReasoningBundle, ReasoningStep
from .retrieval import (
    EvidencePatch,
    IMAGEBIND_DIM,
    RetrievalCandidate,
    RetrievalContext,
    RetrievalMetrics,
)
from .verification import (
    EvidenceRegion,
    VerifiedCandidate,
    VerifiedOutput,
    VerificationReport,
)

__all__ = [
    "IMAGEBIND_DIM",
    "EvidencePatch",
    "EvidenceRegion",
    "Modality",
    "QueryPayload",
    "RankedCandidate",
    "ReasoningBundle",
    "ReasoningStep",
    "RetrievalCandidate",
    "RetrievalContext",
    "RetrievalMetrics",
    "RiskLevel",
    "VerifiedCandidate",
    "VerifiedOutput",
    "VerificationReport",
    "VerificationStatus",
]
