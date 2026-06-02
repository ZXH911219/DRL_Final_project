"""QueryPayload（對齊 openspec/specs/specs.md §2.2）。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from .enums import Modality

_DEFAULT_TIMEOUT_MS: dict[str, int] = {
    "retrieval_total": 200,
    "reasoning_per_candidate": 8000,
    "reasoning_batch": 120000,
    "verification_per_slide": 1500,
}


class QueryPayload(BaseModel):
    """使用者查詢標準載荷（API / 代理間第一棒）。"""

    request_id: str = Field(..., description="全鏈路追蹤 ID")
    modality: Modality = Field(..., description="查詢模態；影響文字／圖像欄位必填與互斥規則")
    query_text: str | None = None
    query_image_bytes: bytes | None = None
    query_image_mime: str | None = Field(default=None, description="例如 image/png")
    top_k_filter: int = Field(500, ge=10, le=2000, description="K₁ 粗檢索")
    top_k_maxsim: int = Field(20, ge=1, le=50, description="K₂ 精排輸出")
    locale: str = Field("zh-TW", description="提示詞與 UI 語系提示")
    user_preferences: dict[str, Any] = Field(default_factory=dict)
    timeout_ms: dict[str, int] = Field(default_factory=lambda: dict(_DEFAULT_TIMEOUT_MS))

    @field_validator("query_text")
    @classmethod
    def strip_optional_text(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s if s else None

    @model_validator(mode="after")
    def modality_payload_consistency(self) -> QueryPayload:
        """文字與圖像依模態互斥且必填（規格書 §2.2；MULTIMODAL 為合理延伸）。"""
        text = self.query_text
        img = self.query_image_bytes

        if self.modality is Modality.TEXT:
            if not text:
                raise ValueError("TEXT 模式需提供 query_text")
            if img is not None:
                raise ValueError("TEXT 模式不得提供 query_image_bytes（互斥）")
            return self

        if self.modality is Modality.IMAGE:
            if not img:
                raise ValueError("IMAGE 模式需提供 query_image_bytes")
            if text is not None:
                raise ValueError("IMAGE 模式不得提供 query_text（互斥）")
            return self

        if self.modality is Modality.MULTIMODAL:
            if not text:
                raise ValueError("MULTIMODAL 模式需提供 query_text")
            if not img:
                raise ValueError("MULTIMODAL 模式需提供 query_image_bytes")
            return self

        raise ValueError(f"不支援的模態: {self.modality!r}")
