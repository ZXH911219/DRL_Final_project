"""Argos Verification Agent

Implements claim extraction, visual grounding (OCR fallback to evidence patches),
hallucination risk scoring, and VerifiedOutput construction.

Designed to be conservative and stub-friendly (optional pytesseract).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, List, Optional, Tuple
import re
import time

from PIL import Image
from pydantic import BaseModel

try:
    import pytesseract
    _HAS_TESSERACT = True
except Exception:
    _HAS_TESSERACT = False
try:
    import easyocr
    _HAS_EASYOCR = True
except Exception:
    _HAS_EASYOCR = False

from ..schemas.verification import (
    EvidenceRegion,
    VerifiedCandidate,
    VerificationReport,
    VerifiedOutput,
)
from ..schemas.reasoning import ReasoningBundle, RankedCandidate
from ..schemas.retrieval import RetrievalContext, EvidencePatch
from ..schemas.query import QueryPayload
from ..schemas.enums import RiskLevel, VerificationStatus

from difflib import SequenceMatcher


def extract_claims(inference_text: str) -> list[str]:
    """Lightweight claim extraction using heuristic regexes.

    Returns a list of short claim strings.
    """
    if not inference_text:
        return []

    claims: list[str] = []

    patterns = [
        r"Title (?:contains|is|has)[:\s]+\"?([^\"\.\n]+)\"?",
        r"Chart (?:shows|indicates|displays)[:\s]+\"?([^\"\.\n]+)\"?",
        r"Figure (?:shows|indicates)[:\s]+\"?([^\"\.\n]+)\"?",
        r"Slide \d+ (?:contains|has)[:\s]+\"?([^\"\.\n]+)\"?",
    ]

    for pat in patterns:
        for m in re.finditer(pat, inference_text, flags=re.IGNORECASE):
            claims.append(m.group(1).strip())

    # fallback: quoted segments
    for q in re.findall(r'\"([^\"]{5,200})\"', inference_text):
        if q not in claims:
            claims.append(q.strip())

    # as final fallback, split sentences and take nouny phrases
    if not claims:
        sents = re.split(r"[\.\n]", inference_text)
        for s in sents:
            s = s.strip()
            if not s:
                continue
            if len(s) < 200 and len(s) > 10:
                claims.append(s)

    # dedupe
    out: list[str] = []
    for c in claims:
        if c not in out:
            out.append(c)
    return out


def patch_grid_to_pixel_bbox(
    bbox_norm: Tuple[float, float, float, float],
    image_size: Tuple[int, int],
) -> Tuple[int, int, int, int]:
    """Convert normalized bbox (x0,y0,x1,y1) to integer pixel bbox.

    Also useful for mapping patch-space boxes to pixels when needed.
    """
    w, h = image_size
    x0, y0, x1, y1 = bbox_norm
    return (int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h))


def pixel_bbox_to_patch_coords(
    pixel_bbox: Tuple[int, int, int, int], image_size: Tuple[int, int], grid_size: int = 32
) -> Tuple[int, int, int, int]:
    """Map pixel bbox to patch-grid coords (tl_x, tl_y, br_x, br_y) inclusive.

    Grid is 32x32 by default.
    """
    w, h = image_size
    patch_w = w / grid_size
    patch_h = h / grid_size
    x0, y0, x1, y1 = pixel_bbox
    tl_x = max(0, int(x0 // patch_w))
    tl_y = max(0, int(y0 // patch_h))
    br_x = min(grid_size - 1, int((x1 - 1) // patch_w))
    br_y = min(grid_size - 1, int((y1 - 1) // patch_h))
    return (tl_x, tl_y, br_x, br_y)


def _text_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    a_lower = a.lower().strip()
    b_lower = b.lower().strip()
    if not a_lower or not b_lower:
        return 0.0
    if a_lower == b_lower:
        return 1.0
    # claim is inside the text
    if len(a_lower) >= 2 and a_lower in b_lower:
        return 1.0
    # text is inside the claim (only valid if text is substantive)
    if len(b_lower) >= 4 and b_lower in a_lower:
        return 1.0
    return SequenceMatcher(None, a_lower, b_lower).ratio()


@dataclass
class ArgosConfig:
    verification_timeout_ms: int = 1500
    w1: float = 0.4
    w2: float = 0.4
    w3: float = 0.2
    # Exponent applied to risk when down-weighting original score (default sqrt)
    risk_exponent: float = 0.5
    # Scale applied to the risk term before subtracting (1.0 preserves previous behavior)
    risk_alpha: float = 1.0


class ArgosVerificationAgent:
    def __init__(self, config: ArgosConfig | None = None, ocr_enabled: bool = True):
        self.config = config or ArgosConfig()
        # choose OCR backend: prefer pytesseract, fallback to easyocr
        self._ocr_requested = bool(ocr_enabled)
        if ocr_enabled and _HAS_TESSERACT:
            self.ocr_backend = "pytesseract"
            self.ocr_enabled = True
        elif ocr_enabled and _HAS_EASYOCR:
            self.ocr_backend = "easyocr"
            self.ocr_enabled = True
        else:
            self.ocr_backend = None
            self.ocr_enabled = False

    def verify(
        self,
        query: QueryPayload,
        retrieval: RetrievalContext,
        reasoning: ReasoningBundle,
        slide_image_loader: Any,
    ) -> VerifiedOutput:
        """Main entrypoint.

        slide_image_loader(slide_id) -> PIL.Image
        """
        start = time.time()
        request_id = query.request_id

        # collect per-slide verification results
        per_slide: list[VerifiedCandidate] = []

        if not reasoning.ranking:
            raise ValueError("ReasoningBundle.ranking empty")

        top = reasoning.ranking[0]
        
        # 判斷是否為 Stub 模式
        is_stub = "Visual Perception:" in top.inference_text
        if is_stub:
            # Split by whitespace to preserve Chinese characters and numbers
            words = [w.strip() for w in (query.query_text or "").split() if len(w.strip()) >= 2]
            claims = list(set(words)) if words else [query.query_text]
        else:
            claims = extract_claims(top.inference_text)

        for cand in reasoning.ranking:
            slide_id = cand.slide_id
            img = None
            try:
                img = slide_image_loader(slide_id)
            except Exception:
                img = None

            image_size = img.size if img is not None else (1024, 768)

            verified_claims: list[str] = []
            unverified_claims: list[str] = []
            evidence_regions: list[EvidenceRegion] = []
            semantic_scores: list[float] = []

            # per-claim grounding
            for claim in claims:
                found = False
                best_conf = 0.0
                best_bbox_norm = None

                # OCR path
                if self.ocr_enabled and img is not None:
                    try:
                        if self.ocr_backend == "pytesseract":
                            ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                            texts = ocr_data.get("text", [])
                            for i, txt in enumerate(texts):
                                if not txt or txt.strip() == "":
                                    continue
                                sim = _text_similarity(claim, txt)
                                if sim > best_conf and sim > 0.5:
                                    # build norm bbox
                                    x = int(ocr_data["left"][i])
                                    y = int(ocr_data["top"][i])
                                    w = int(ocr_data["width"][i])
                                    h = int(ocr_data["height"][i])
                                    bbox_px = (x, y, x + w, y + h)
                                    bbox_norm = (
                                        bbox_px[0] / image_size[0],
                                        bbox_px[1] / image_size[1],
                                        bbox_px[2] / image_size[0],
                                        bbox_px[3] / image_size[1],
                                    )
                                    best_conf = sim
                                    best_bbox_norm = bbox_norm
                                    found = True
                        elif self.ocr_backend == "easyocr":
                            # easyocr returns list of (bbox, text, conf)
                            import numpy as np

                            reader = easyocr.Reader(["ch_sim", "en"], gpu=False)  # type: ignore
                            results = reader.readtext(np.array(img))
                            for bbox, txt, conf in results:
                                if not txt or not txt.strip():
                                    continue
                                sim = _text_similarity(claim, txt)
                                if sim > best_conf and sim > 0.5:
                                    xs = [p[0] for p in bbox]
                                    ys = [p[1] for p in bbox]
                                    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
                                    bbox_px = (int(x0), int(y0), int(x1), int(y1))
                                    bbox_norm = (
                                        bbox_px[0] / image_size[0],
                                        bbox_px[1] / image_size[1],
                                        bbox_px[2] / image_size[0],
                                        bbox_px[3] / image_size[1],
                                    )
                                    best_conf = float(conf)
                                    best_bbox_norm = bbox_norm
                                    found = True
                    except Exception:
                        # OCR failed; will fallback to evidence patches
                        found = False

                # fallback: use evidence_patches from retrieval ONLY IF we didn't just use stub keywords
                # if is_stub is True, we want strict OCR verification to differentiate slides!
                if not found and retrieval is not None:
                    r_cand = next((r for r in retrieval.candidates if r.slide_id == slide_id), None)
                    
                    # 1. Very fast text-based fallback (using python-pptx extracted text)
                    if not found and is_stub and r_cand:
                        fts_text = getattr(r_cand, "fts_text", "")
                        if not fts_text and hasattr(r_cand, "metadata"):
                            fts_text = r_cand.metadata.get("fts_text", "")
                        if fts_text and _text_similarity(claim, str(fts_text)) >= 1.0:
                            found = True
                            best_conf = 1.0
                            best_bbox_norm = (0.0, 0.0, 1.0, 1.0) # Full slide fake bbox
                    
                    # 2. Original patch fallback
                    if not found and not is_stub:
                        if r_cand and r_cand.evidence_patches:
                            # take top scoring patch as evidence
                            ep = sorted(r_cand.evidence_patches, key=lambda e: -e.score)[0]
                            best_conf = ep.score
                            best_bbox_norm = ep.bbox_norm
                            found = True

                if found and best_bbox_norm is not None:
                    # compute patch coords
                    pixel_bbox = patch_grid_to_pixel_bbox(best_bbox_norm, image_size)
                    patch_coords = pixel_bbox_to_patch_coords(pixel_bbox, image_size, grid_size=32)
                    sim_score = best_conf
                    semantic_scores.append(sim_score)

                    evidence_regions.append(
                        EvidenceRegion(
                            patch_coords=patch_coords,
                            bbox_norm=best_bbox_norm,
                            region_type="text",
                            referenced_claim=claim,
                            confidence=sim_score,
                        )
                    )
                    verified_claims.append(claim)
                else:
                    unverified_claims.append(claim)

            # compute metrics
            n_claims = max(1, len(claims))
            u = len(unverified_claims)
            c = float(cand.completeness_score if hasattr(cand, "completeness_score") else 0.0)
            # semantic consistency: average of semantic_scores
            s = float(sum(semantic_scores) / len(semantic_scores)) if semantic_scores else 0.0

            w1 = self.config.w1
            w2 = self.config.w2
            w3 = self.config.w3
            r = w1 * (1 - c) + w2 * (1 - s) + w3 * (u / n_claims)
            r = max(0.0, min(1.0, r))

            # down-weight original reranked score by a power-law on risk
            s_adj = cand.reranked_score * (1 - (self.config.risk_alpha * (r ** self.config.risk_exponent)))
            s_adj = max(0.0, min(1.0, s_adj))

            # map risk to level
            if r < 0.33:
                level = RiskLevel.LOW
            elif r < 0.66:
                level = RiskLevel.MEDIUM
            else:
                level = RiskLevel.HIGH

            # evidence coverage ratio = verified claims / n_claims
            evidence_coverage_ratio = (n_claims - u) / n_claims

            # verification status heuristic
            if evidence_coverage_ratio > 0.66 and s > 0.5:
                status = VerificationStatus.PASS
            elif evidence_coverage_ratio > 0.33:
                status = VerificationStatus.WARN
            else:
                status = VerificationStatus.FAIL

            semantic_consistency = s

            verified_candidate = VerifiedCandidate(
                slide_id=slide_id,
                original_reranked_score=cand.reranked_score,
                adjusted_score=s_adj,
                verification_status=status,
                hallucination_risk_score=r,
                hallucination_risk_level=level,
                evidence_coverage_ratio=evidence_coverage_ratio,
                semantic_consistency=semantic_consistency,
                verified_claims=verified_claims,
                unverified_claims=unverified_claims,
                evidence_regions=evidence_regions,
                evidence_map_asset_id=None,
                inference_text=top.inference_text,
            )

            per_slide.append(verified_candidate)

        # Sort per_slide by adjusted_score descending so the best verified slides come first
        per_slide.sort(key=lambda x: x.adjusted_score, reverse=True)

        total_latency_ms = (time.time() - start) * 1000.0

        report = VerificationReport(
            verification_id=f"ver-{request_id}",
            request_id=request_id,
            generated_at=datetime.utcnow(),
            per_slide=per_slide,
            audit_trail={
                "ocr_enabled": self.ocr_enabled,
                "claims_extracted": len(claims),
            },
            summary={
                "verified_count": sum(1 for p in per_slide if p.verification_status == VerificationStatus.PASS),
                "warn_count": sum(1 for p in per_slide if p.verification_status == VerificationStatus.WARN),
                "fail_count": sum(1 for p in per_slide if p.verification_status == VerificationStatus.FAIL),
                "avg_risk": sum(p.hallucination_risk_score for p in per_slide) / max(1, len(per_slide)),
            },
        )

        verified_output = VerifiedOutput(
            request_id=request_id,
            query=query,
            retrieval=retrieval,
            reasoning=reasoning,
            verification=report,
            total_latency_ms=total_latency_ms,
            degradation_flags=[],
        )

        return verified_output
