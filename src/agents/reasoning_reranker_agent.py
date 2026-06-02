"""Reasoning-Reranker-Agent（對齊 openspec/specs/specs.md §3.1 與 §5.1）。"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ..schemas import QueryPayload, RankedCandidate, ReasoningBundle, ReasoningStep, RetrievalContext
from .vision_ingestion_agent import build_slide_fts_text, extract_slide_text_sections

logger = logging.getLogger(__name__)

_DEFAULT_WEIGHTS: tuple[float, float, float] = (0.4, 0.4, 0.2)
_QUERY_NOISE_PHRASES: tuple[str, ...] = (
    "請找出",
    "請",
    "找出",
    "包含",
    "相關",
    "有關",
    "的投影片",
    "投影片",
    "簡報",
    "頁面",
    "圖中的",
    "圖片中的",
    "文字",
)


def _clip01(value: float) -> float:
    return float(max(0.0, min(1.0, value)))


def _confidence_level(score: float) -> Literal["high", "medium", "low"]:
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def _risk_level(risk: float) -> Literal["low", "medium", "high"]:
    if risk < 0.15:
        return "low"
    if risk < 0.45:
        return "medium"
    return "high"


def _compact_text(text: str | None) -> str:
    if not text:
        return ""
    compact = re.sub(r"\s+", "", str(text)).lower()
    for phrase in _QUERY_NOISE_PHRASES:
        compact = compact.replace(phrase.lower(), "")
    return compact


def _split_structured_slide_text(text: str | None) -> dict[str, str]:
    if not text:
        return {}
    sections: dict[str, list[str]] = {"標題": [], "內文": [], "備註": []}
    current_key: str | None = None
    for raw_line in str(text).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("標題:"):
            current_key = "標題"
            sections[current_key].append(line.split(":", 1)[1].strip())
            continue
        if line.startswith("內文:"):
            current_key = "內文"
            sections[current_key].append(line.split(":", 1)[1].strip())
            continue
        if line.startswith("備註:"):
            current_key = "備註"
            sections[current_key].append(line.split(":", 1)[1].strip())
            continue
        if current_key is not None:
            sections[current_key].append(line)
    return {key: " ".join(value).strip() for key, value in sections.items() if any(value)}


def _text_signal_score(query_text: str | None, candidate_text: str | None) -> float:
    query = _compact_text(query_text)
    candidate = _compact_text(candidate_text)
    if not query or not candidate:
        return 0.0
    if query in candidate:
        return 1.0

    query_len = len(query)
    candidate_len = len(candidate)
    if query_len == 0 or candidate_len == 0:
        return 0.0

    ngrams: set[str] = set()
    max_n = min(6, query_len)
    for n in range(2, max_n + 1):
        for idx in range(0, query_len - n + 1):
            piece = query[idx : idx + n]
            if len(piece) >= 2:
                ngrams.add(piece)

    if not ngrams:
        return 0.0

    matches = sum(1 for gram in ngrams if gram in candidate)
    return _clip01(matches / max(1, min(len(ngrams), 24)))


def _text_alignment_score(query_text: str | None, candidate: dict[str, Any]) -> float:
    structured = _split_structured_slide_text(candidate.get("fts_text"))
    if not structured:
        source_path = candidate.get("source_path")
        page_index = candidate.get("page_index")
        if source_path is not None and page_index is not None:
            try:
                from pptx import Presentation

                prs = Presentation(str(Path(source_path)))
                slide = prs.slides[int(page_index)]
                title_text, body_text, notes_text = extract_slide_text_sections(slide)
                fallback_text = build_slide_fts_text(title_text, body_text, notes_text)
                structured = _split_structured_slide_text(fallback_text)
            except Exception:
                structured = {}
    title_score = _text_signal_score(query_text, structured.get("標題"))
    body_score = _text_signal_score(query_text, structured.get("內文"))
    notes_score = _text_signal_score(query_text, structured.get("備註"))

    if not structured:
        flat_score = _text_signal_score(query_text, candidate.get("fts_text") or candidate.get("slide_caption") or "")
        return flat_score

    return _clip01(0.60 * title_score + 0.30 * body_score + 0.10 * notes_score)


def _estimate_claim_counts(inference_text: str, key_phrases: list[str]) -> tuple[int, int]:
    lines = [line.strip(" -•\t") for line in inference_text.splitlines() if line.strip()]
    claims = [line for line in lines if re.match(r"^(step\s*\d+|visual|query|semantic|deep|confidence|結論|推理|step)", line, re.I)]
    total = max(len(claims), len(key_phrases), 1)
    unreferenced = 0
    for claim in claims:
        if not any(phrase and phrase.lower() in claim.lower() for phrase in key_phrases):
            unreferenced += 1
    return total, min(unreferenced, total)


def _hallucination_risk(
    evidence_coverage_ratio: float,
    semantic_consistency: float,
    inference_text: str,
    key_phrases: list[str],
) -> tuple[float, Literal["low", "medium", "high"], dict[str, Any]]:
    total_claims, unreferenced_claims = _estimate_claim_counts(inference_text, key_phrases)
    unreferenced_ratio = 0.0 if total_claims == 0 else unreferenced_claims / total_claims
    risk = 0.4 * (1.0 - evidence_coverage_ratio) + 0.35 * (1.0 - semantic_consistency) + 0.25 * unreferenced_ratio
    risk = _clip01(risk)
    level = _risk_level(risk)
    audit = {
        "evidence_coverage_ratio": evidence_coverage_ratio,
        "semantic_consistency": semantic_consistency,
        "total_claims": total_claims,
        "unreferenced_claims": unreferenced_claims,
        "unreferenced_ratio": unreferenced_ratio,
        "hallucination_risk": risk,
        "hallucination_risk_level": level,
    }
    return risk, level, audit


def _final_score(
    retrieval_score: float,
    reasoning_score: float,
    completeness_score: float,
    weights: tuple[float, float, float] = _DEFAULT_WEIGHTS,
) -> float:
    lambda_1, lambda_2, lambda_3 = weights
    total = lambda_1 + lambda_2 + lambda_3
    if total <= 0:
        return _clip01(retrieval_score)
    weighted = (
        lambda_1 * retrieval_score
        + lambda_2 * reasoning_score
        + lambda_3 * completeness_score
    ) / total
    return _clip01(weighted)


def _parse_final_json(inference_text: str) -> dict[str, Any]:
    """從 MM-R5 輸出中穩健抽取最後一個 JSON object。"""
    candidates = list(re.finditer(r"\{", inference_text))
    for match in reversed(candidates):
        start = match.start()
        depth = 0
        for end in range(start, len(inference_text)):
            ch = inference_text[end]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    raw = inference_text[start : end + 1]
                    try:
                        return json.loads(raw)
                    except Exception:
                        break
    raise ValueError("無法從推理輸出中解析最後一個 JSON object")


class MultimodalReasoningModel:
    """可配置的多模態 LLM 介面；若未載入實模組則使用 deterministic stub。"""

    def __init__(
        self,
        model_id: str = "mm-r5",
        *,
        device: str | None = None,
        backend: str = "stub",
        max_new_tokens: int = 256,
    ) -> None:
        self.model_id = model_id
        self.device = device
        self.backend = backend.lower().strip()
        self.max_new_tokens = int(max_new_tokens)
        self._loaded = False
        self._pipe: Any = None

        if self.backend == "stub":
            return

        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoProcessor
        except ImportError:
            logger.warning("未安裝 torch/transformers，Reasoning 模型退回 stub。")
            self.backend = "stub"
            return

        self._torch = torch
        if self.device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"

        try:
            self._processor = AutoProcessor.from_pretrained(model_id)
            self._model = AutoModelForCausalLM.from_pretrained(model_id, device_map="auto")
            self._model.eval()
            self._loaded = True
        except Exception:
            logger.warning("無法載入推理模型 %s，退回 stub。", model_id, exc_info=True)
            self.backend = "stub"
            self._loaded = False

    def generate(self, prompt: str, *, candidate: dict[str, Any]) -> str:
        if self.backend == "stub" or not self._loaded:
            return self._generate_stub(prompt, candidate=candidate)

        try:
            import torch
        except ImportError:
            return self._generate_stub(prompt, candidate=candidate)

        inputs = self._processor(text=prompt, return_tensors="pt")
        inputs = {k: v.to(next(self._model.parameters()).device) for k, v in inputs.items()}
        with torch.inference_mode():
            output = self._model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
            )
        text = self._processor.decode(output[0], skip_special_tokens=True)
        return text

    def _generate_stub(self, prompt: str, *, candidate: dict[str, Any]) -> str:
        slide_id = candidate.get("slide_id", "unknown")
        score = float(candidate.get("maxsim_score", candidate.get("retrieval_score", 0.0)))
        completeness = float(candidate.get("completeness_score", 0.7))
        text_signal = _text_alignment_score(candidate.get("_query_text"), candidate)
        
        # To avoid flattening the score variance in stub mode, rely primarily on the retrieval score
        reasoning_score = _clip01(0.85 * score + 0.15 * text_signal)
        steps = [
            "Visual Perception: 從 slide_id 與 evidence_patches 推測視覺內容已對齊。",
            "Query Understanding: 查詢與候選 slide 的主題存在語義交集。",
            "Semantic Alignment: 與檢索分數、證據區塊資訊一致。",
            "Deep Reasoning: 以可見證據支持候選投影片的相關性。",
            f"Confidence Assessment: reason_score={reasoning_score:.4f}, completeness={completeness:.4f}.",
        ]
        payload = {
            "reasoning_score": reasoning_score,
            "completeness_score": completeness,
            "confidence_level": _confidence_level(reasoning_score),
        }
        return "\n".join(steps + [json.dumps(payload, ensure_ascii=False)])


def _default_dynamic_weights(query: QueryPayload) -> tuple[float, float, float]:
    text = (query.query_text or "").strip()
    concept_count = len(re.findall(r"[A-Za-z0-9_\u4e00-\u9fff]+", text))
    if concept_count >= 8:
        return 0.3, 0.5, 0.2
    if query.user_preferences.get("prefer_explainability"):
        return 0.35, 0.35, 0.3
    if query.user_preferences.get("precision_first"):
        return 0.5, 0.35, 0.15
    return _DEFAULT_WEIGHTS


@dataclass(frozen=True)
class _ReasoningResult:
    slide_id: str
    original_rank: int
    reranked_score: float
    retrieval_score: float
    reasoning_score: float
    completeness_score: float
    inference_text: str
    reasoning_steps: list[ReasoningStep]
    confidence_level: Literal["high", "medium", "low"]
    key_evidence_phrases: list[str]
    fallback_retrieval_only: bool
    audit: dict[str, Any]


class ReasoningRerankerAgent:
    """Reasoning-Reranker-Agent：MM-R5 推理 + 重新排序 + 降級。"""

    def __init__(
        self,
        *,
        model: MultimodalReasoningModel | None = None,
        top_k: int = 20,
        per_candidate_timeout_s: float | None = None,
        batch_timeout_s: float | None = None,
        weights: tuple[float, float, float] | None = None,
        max_workers: int = 4,
    ) -> None:
        self._model = model or MultimodalReasoningModel(
            model_id=os.environ.get("MMR5_MODEL", "mm-r5"),
            device=os.environ.get("MMR5_DEVICE"),
            backend=os.environ.get("MMR5_BACKEND", "stub"),
            max_new_tokens=int(os.environ.get("MMR5_MAX_NEW_TOKENS", "256")),
        )
        self._top_k = max(1, int(top_k))
        self._per_candidate_timeout_s = per_candidate_timeout_s if per_candidate_timeout_s is not None else float(os.environ.get("MMR5_PER_CANDIDATE_TIMEOUT_S", "8"))
        self._batch_timeout_s = batch_timeout_s if batch_timeout_s is not None else float(os.environ.get("MMR5_BATCH_TIMEOUT_S", "120"))
        self._weights = weights or _DEFAULT_WEIGHTS
        self._max_workers = max(1, int(max_workers))

    @property
    def model_revision(self) -> str:
        return f"{self._model.model_id}:{self._model.backend}"

    def _build_prompt(self, query: QueryPayload, candidate: dict[str, Any]) -> str:
        evidence = candidate.get("evidence_patches", [])
        evidence_text = ", ".join(
            f"patch={p.get('patch_index')} bbox={p.get('bbox_norm')} score={p.get('score'):.4f}"
            for p in evidence
        ) or "無"
        query_text = query.query_text or ""
        slide_id = candidate.get("slide_id", "unknown")
        page_index = candidate.get("page_index", -1)
        retrieval_score = float(candidate.get("maxsim_score", candidate.get("retrieval_score", 0.0)))
        structured_text = _split_structured_slide_text(candidate.get("fts_text"))
        title_text = structured_text.get("標題") or "無"
        body_text = structured_text.get("內文") or candidate.get("fts_text") or candidate.get("slide_caption") or evidence_text or "無"
        notes_text = structured_text.get("備註") or "無"
        prompt = f"""你是企業簡報檢索系統的「多模態視覺推理專家」。你的任務是像人類一樣直接「觀看」投影片圖片，並判斷它是否符合使用者的查詢。
這是一個支援純視覺搜尋的系統！如果使用者搜尋的具體視覺特徵（例如「綠色障礙物」、「圓餅圖」、「紅色番茄」、「藍色線條」）真實出現在圖片畫面中，請務必給予極高的 reasoning_score (0.8~1.0)，**即使這些詞彙完全沒有寫在投影片的文字中**！

請依序輸出五個段落，對應步驟：視覺感知（描述你看到的畫面）、查詢解析、語義對齊、深層推理、信度評估。
最後給出一行 JSON：{{"reasoning_score":0-1,"completeness_score":0-1,"confidence_level":"high|medium|low"}}。

【使用者查詢】
{query_text}

【候選投影片】
slide_id: {slide_id}
page_index: {page_index}
MaxSim 檢索分數: {retrieval_score:.4f}

【投影片內容摘要】
{candidate.get('fts_text') or candidate.get('slide_caption') or evidence_text or '無'}

【標題文字】
{title_text}

【內文文字】
{body_text}

【備註文字】
{notes_text}

【證據區塊】
{evidence_text}

請依照系統指示完成五步驟推理，並嚴格標註每一步所依據的視覺證據（例如：畫面的正中央有一個綠色的巨大方塊，這符合綠色障礙物的描述）。如果視覺上高度吻合，請直接在 JSON 中給予高分。"""
        return prompt

    def _generate_with_gemini(self, api_key: str, prompt: str, query: QueryPayload, candidate: dict[str, Any], image_loader: Any) -> str:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        contents = [prompt]
        if image_loader is not None:
            slide_id = candidate.get("slide_id")
            if slide_id:
                try:
                    img = image_loader(slide_id)
                    if img:
                        contents.insert(0, img)
                except Exception as e:
                    logger.warning(f"Gemini image load failed for {slide_id}: {e}")
                    
        try:
            response = model.generate_content(contents)
            return response.text
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            return self._model.generate(prompt, candidate=candidate)

    def _candidate_to_result(self, query: QueryPayload, rank: int, candidate: Any) -> _ReasoningResult:
        candidate_dict = candidate.model_dump(mode="python") if hasattr(candidate, "model_dump") else dict(candidate)
        retrieval_score = float(candidate_dict.get("maxsim_score", 0.0))
        candidate_dict["_query_text"] = query.query_text or ""
        text_alignment_score = _text_alignment_score(query.query_text, candidate_dict)
        prompt = self._build_prompt(query, candidate_dict)
        
        # Check if Gemini API key is provided
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key and api_key.strip():
            inference_text = self._generate_with_gemini(api_key, prompt, query, candidate_dict, getattr(self, "_current_image_loader", None))
        else:
            inference_text = self._model.generate(prompt, candidate=candidate_dict)

        try:
            final_json = _parse_final_json(inference_text)
            reasoning_score = _clip01(float(final_json.get("reasoning_score", 0.0)))
            completeness_score = _clip01(float(final_json.get("completeness_score", candidate_dict.get("completeness_score", 0.7))))
            confidence_level = str(final_json.get("confidence_level", _confidence_level(reasoning_score)))
            if confidence_level not in {"high", "medium", "low"}:
                confidence_level = _confidence_level(reasoning_score)
        except Exception:
            reasoning_score = _clip01(0.5 * retrieval_score)
            completeness_score = _clip01(float(candidate_dict.get("completeness_score", 0.5)))
            confidence_level = _confidence_level(reasoning_score)

        if text_alignment_score > 0:
            completeness_score = _clip01(max(completeness_score, text_alignment_score))
            reasoning_score = _clip01(0.7 * reasoning_score + 0.3 * text_alignment_score)

        steps = [
            ReasoningStep(step_id=1, step_name="Visual Perception", reasoning_text="從候選投影片與證據區塊確認視覺線索。", local_score=_clip01(reasoning_score * 0.9), confidence=_clip01(reasoning_score)),
            ReasoningStep(step_id=2, step_name="Query Understanding", reasoning_text="將查詢拆解為核心概念並對照候選主題。", local_score=_clip01(reasoning_score * 0.95), confidence=_clip01(reasoning_score)),
            ReasoningStep(step_id=3, step_name="Semantic Alignment", reasoning_text="比對檢索得分、文字摘要與證據區塊的一致性。", local_score=_clip01(reasoning_score), confidence=_clip01(reasoning_score)),
            ReasoningStep(step_id=4, step_name="Deep Reasoning", reasoning_text="推論候選投影片是否足以支持查詢意圖。", local_score=_clip01((reasoning_score + completeness_score) / 2), confidence=_clip01(reasoning_score)),
            ReasoningStep(step_id=5, step_name="Confidence Assessment", reasoning_text="輸出信度與最終推理分數。", local_score=_clip01(reasoning_score), confidence=_clip01(reasoning_score)),
        ]

        evidence_phrases = []
        for item in candidate_dict.get("evidence_patches", []):
            patch_index = item.get("patch_index")
            if patch_index is not None:
                evidence_phrases.append(f"patch_{patch_index}")
        if not evidence_phrases:
            evidence_phrases = [candidate_dict.get("slide_id", "unknown")]

        risk_score, risk_level, risk_audit = _hallucination_risk(
            evidence_coverage_ratio=float(candidate_dict.get("evidence_coverage_ratio", 1.0)),
            semantic_consistency=float(candidate_dict.get("semantic_consistency", reasoning_score)),
            inference_text=inference_text,
            key_phrases=evidence_phrases,
        )
        adjusted_reasoning = _clip01(reasoning_score * (1.0 - risk_score**0.5))
        final_score = _final_score(
            retrieval_score=retrieval_score,
            reasoning_score=adjusted_reasoning,
            completeness_score=completeness_score,
            weights=self._weights,
        )
        fallback = False
        if risk_level == "high" and adjusted_reasoning < 0.2:
            fallback = False

        audit = {
            "prompt": prompt,
            "risk": risk_audit,
            "parsed_json": final_json if "final_json" in locals() else None,
            "adjusted_reasoning_score": adjusted_reasoning,
            "final_score": final_score,
        }
        return _ReasoningResult(
            slide_id=str(candidate_dict.get("slide_id", "unknown")),
            original_rank=rank,
            reranked_score=final_score,
            retrieval_score=retrieval_score,
            reasoning_score=adjusted_reasoning,
            completeness_score=completeness_score,
            inference_text=inference_text,
            reasoning_steps=steps,
            confidence_level=confidence_level,
            key_evidence_phrases=evidence_phrases,
            fallback_retrieval_only=fallback,
            audit=audit,
        )

    def rerank(self, retrieval: RetrievalContext, image_loader: Any = None) -> ReasoningBundle:
        """執行 RetrievalContext → ReasoningBundle 的重排流程。"""
        query = retrieval.query
        selected = list(retrieval.candidates[: self._top_k])
        t0 = time.perf_counter()

        futures = []
        results: list[_ReasoningResult] = []
        timeout_occurred = False
        
        self._current_image_loader = image_loader
        
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            for rank, candidate in enumerate(selected, start=1):
                futures.append((rank, candidate, executor.submit(self._candidate_to_result, query, rank, candidate)))

            for rank, candidate, future in futures:
                per_candidate_timeout = self._per_candidate_timeout_s
                if time.perf_counter() - t0 > self._batch_timeout_s:
                    timeout_occurred = True
                    break
                try:
                    results.append(future.result(timeout=per_candidate_timeout))
                except FuturesTimeoutError:
                    timeout_occurred = True
                    future.cancel()
                    candidate_dict = candidate.model_dump(mode="python") if hasattr(candidate, "model_dump") else dict(candidate)
                    retrieval_score = float(candidate_dict.get("maxsim_score", 0.0))
                    results.append(
                        _ReasoningResult(
                            slide_id=str(candidate_dict.get("slide_id", "unknown")),
                            original_rank=rank,
                            reranked_score=retrieval_score,
                            retrieval_score=retrieval_score,
                            reasoning_score=0.0,
                            completeness_score=0.0,
                            inference_text="推理逾時，已降級為檢索分排序。",
                            reasoning_steps=[],
                            confidence_level="low",
                            key_evidence_phrases=[],
                            fallback_retrieval_only=True,
                            audit={"reasoning_timeout": True, "original_rank": rank},
                        )
                    )
                except Exception as exc:
                    timeout_occurred = True
                    logger.warning("候選推理失敗，降級為檢索分數：%s", exc, exc_info=True)
                    candidate_dict = candidate.model_dump(mode="python") if hasattr(candidate, "model_dump") else dict(candidate)
                    retrieval_score = float(candidate_dict.get("maxsim_score", 0.0))
                    results.append(
                        _ReasoningResult(
                            slide_id=str(candidate_dict.get("slide_id", "unknown")),
                            original_rank=rank,
                            reranked_score=retrieval_score,
                            retrieval_score=retrieval_score,
                            reasoning_score=0.0,
                            completeness_score=0.0,
                            inference_text="推理失敗，已降級為檢索分排序。",
                            reasoning_steps=[],
                            confidence_level="low",
                            key_evidence_phrases=[],
                            fallback_retrieval_only=True,
                            audit={"reasoning_failure": str(exc), "original_rank": rank},
                        )
                    )

        if timeout_occurred and len(results) < len(selected):
            for rank, candidate in enumerate(selected[len(results) :], start=len(results) + 1):
                candidate_dict = candidate.model_dump(mode="python") if hasattr(candidate, "model_dump") else dict(candidate)
                retrieval_score = float(candidate_dict.get("maxsim_score", 0.0))
                results.append(
                    _ReasoningResult(
                        slide_id=str(candidate_dict.get("slide_id", "unknown")),
                        original_rank=rank,
                        reranked_score=retrieval_score,
                        retrieval_score=retrieval_score,
                        reasoning_score=0.0,
                        completeness_score=0.0,
                        inference_text="批次推理逾時，已降級為檢索分排序。",
                        reasoning_steps=[],
                        confidence_level="low",
                        key_evidence_phrases=[],
                        fallback_retrieval_only=True,
                        audit={"reasoning_timeout": True, "original_rank": rank},
                    )
                )

        results.sort(key=lambda item: item.reranked_score, reverse=True)

        ranking = [
            RankedCandidate(
                slide_id=item.slide_id,
                original_rank=item.original_rank,
                reranked_score=_clip01(item.reranked_score),
                retrieval_score=item.retrieval_score,
                reasoning_score=item.reasoning_score,
                completeness_score=item.completeness_score,
                inference_text=item.inference_text,
                reasoning_steps=item.reasoning_steps,
                confidence_level=item.confidence_level,
                key_evidence_phrases=item.key_evidence_phrases,
                fallback_retrieval_only=item.fallback_retrieval_only,
            )
            for item in results
        ]

        audit = {
            "model_revision": self.model_revision,
            "timeout_occurred": timeout_occurred,
            "top_k": self._top_k,
            "weights": self._weights,
        }
        if timeout_occurred:
            audit["degradation"] = "reasoning_timeout_or_failure"

        return ReasoningBundle(
            request_id=retrieval.request_id,
            ranking=ranking,
            reasoning_model_revision=self.model_revision,
            audit=audit,
        )


__all__ = [
    "MultimodalReasoningModel",
    "ReasoningRerankerAgent",
]