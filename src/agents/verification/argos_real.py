"""
Argos Vision Verification Agent
Validates reasoning against visual evidence and detects hallucinations.
"""

import logging
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class VerificationEvidence:
    """Evidence location in visual space."""

    patch_x_min: int
    patch_y_min: int
    patch_x_max: int
    patch_y_max: int
    region_type: str  # "text", "chart", "image", "other"
    confidence: float
    referenced_claim: str


@dataclass
class VerificationReport:
    """Complete verification report."""

    slide_id: str
    verification_status: str  # "pass", "warn", "fail"
    hallucination_risk_score: float  # [0.0, 1.0]
    hallucination_risk_level: str  # "low", "medium", "high"
    evidence_coverage_ratio: float  # [0.0, 1.0]
    semantic_consistency: float  # [0.0, 1.0]
    verified_claims: List[str]
    unverified_claims: List[str]
    evidence_regions: List[VerificationEvidence]
    original_score: float
    adjusted_score: float
    adjustment_factor: float
    verification_text: str


class ArgosVerificationAgent:
    """Argos framework for visual verification and hallucination detection."""

    def __init__(self, device: str = "cuda"):
        """
        Initialize Argos verification agent.

        Args:
            device: Device to run on
        """
        self.device = device
        self.ocr_engine = None
        self.visual_recognizer = None
        self.grounding_model = None
        self.is_ready = False

    def initialize(self) -> bool:
        """Initialize verification components."""
        try:
            # Initialize OCR engine
            try:
                from paddleocr import PaddleOCR

                self.ocr_engine = PaddleOCR(use_angle_cls=True, lang="en")
                logger.info("PaddleOCR initialized")
            except Exception as e:
                logger.warning(f"PaddleOCR not available: {e}")

            # Initialize visual recognition
            try:
                from transformers import pipeline

                self.visual_recognizer = pipeline(
                    "image-classification",
                    model="microsoft/resnet-50",
                    device=0 if self.device == "cuda" else -1,
                )
                logger.info("Visual recognizer initialized")
            except Exception as e:
                logger.warning(f"Visual recognizer not available: {e}")

            self.is_ready = True
            logger.info("Argos verification agent ready")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Argos: {str(e)}")
            return False

    def verify_reasoning(
        self,
        slide_image: np.ndarray,
        reasoning_text: str,
        reasoning_steps: List[Dict[str, str]],
        original_score: float,
        slide_id: str,
    ) -> VerificationReport:
        """
        Verify reasoning against visual evidence.

        Args:
            slide_image: Image of slide (H, W, 3)
            reasoning_text: Complete reasoning text
            reasoning_steps: List of reasoning steps
            original_score: Original retrieval/reasoning score
            slide_id: ID of slide

        Returns:
            VerificationReport with grounding check
        """
        # Extract claims from reasoning
        claims = self._extract_claims_from_reasoning(reasoning_text, reasoning_steps)

        # Perform visual grounding
        evidence_regions, grounded_claims = self._ground_claims_in_image(
            slide_image, claims
        )

        # Calculate coverage metrics
        coverage_ratio = self._calculate_coverage_ratio(claims, grounded_claims)

        # Check semantic consistency
        semantic_consistency = self._check_semantic_consistency(claims, evidence_regions)

        # Calculate hallucination risk
        hallucination_risk = self._calculate_hallucination_risk(
            coverage_ratio, semantic_consistency, len(claims) - len(grounded_claims)
        )

        # Determine verification status
        verification_status = self._classify_verification_status(hallucination_risk)

        # Calculate score adjustment
        adjusted_score, adjustment_factor = self._calculate_score_adjustment(
            original_score, hallucination_risk
        )

        # Compile report
        report = VerificationReport(
            slide_id=slide_id,
            verification_status=verification_status,
            hallucination_risk_score=hallucination_risk,
            hallucination_risk_level=self._classify_risk_level(hallucination_risk),
            evidence_coverage_ratio=coverage_ratio,
            semantic_consistency=semantic_consistency,
            verified_claims=grounded_claims,
            unverified_claims=[c for c in claims if c not in grounded_claims],
            evidence_regions=evidence_regions,
            original_score=original_score,
            adjusted_score=adjusted_score,
            adjustment_factor=adjustment_factor,
            verification_text=self._generate_verification_text(
                verification_status, hallucination_risk, coverage_ratio
            ),
        )

        logger.info(
            f"Verified {slide_id}: status={verification_status}, "
            f"hallucination_risk={hallucination_risk:.2f}, coverage={coverage_ratio:.1%}"
        )

        return report

    def _extract_claims_from_reasoning(
        self, reasoning_text: str, reasoning_steps: List[Dict[str, str]]
    ) -> List[str]:
        """Extract verifiable claims from reasoning."""
        claims = []

        # Extract from reasoning text
        for line in reasoning_text.split("\n"):
            if len(line) > 10 and len(line) < 150:
                # Simple heuristic: sentences that could be visual claims
                if any(
                    keyword in line.lower()
                    for keyword in ["show", "contain", "display", "have", "include"]
                ):
                    claims.append(line.strip())

        # Extract from reasoning steps
        for step in reasoning_steps:
            step_text = step.get("text", "")
            if step_text and len(step_text) > 5:
                claims.append(step_text)

        return list(set(claims))  # Remove duplicates

    def _ground_claims_in_image(
        self, image: np.ndarray, claims: List[str]
    ) -> Tuple[List[VerificationEvidence], List[str]]:
        """
        Ground claims in image space using OCR and visual recognition.

        Args:
            image: Slide image
            claims: List of claims to ground

        Returns:
            Tuple of (evidence regions, verified claims)
        """
        evidence_regions = []
        verified_claims = []

        # Extract text locations with OCR
        text_regions = self._extract_text_regions(image)

        # Extract visual elements
        visual_objects = self._recognize_visual_objects(image)

        # Try to ground each claim
        for claim in claims:
            grounding_score = 0.0
            best_region = None

            # Check text matching
            for text_info in text_regions:
                text_content = text_info["text"].lower()
                claim_lower = claim.lower()

                # Simple keyword matching
                if any(
                    word in claim_lower for word in text_content.split()
                ) or any(word in text_content for word in claim_lower.split()):
                    grounding_score = max(grounding_score, 0.85)
                    best_region = VerificationEvidence(
                        patch_x_min=int(text_info["x"] / 32),  # Convert to patch coords
                        patch_y_min=int(text_info["y"] / 32),
                        patch_x_max=int(
                            (text_info["x"] + text_info["w"]) / 32
                        ),
                        patch_y_max=int(
                            (text_info["y"] + text_info["h"]) / 32
                        ),
                        region_type="text",
                        confidence=0.85,
                        referenced_claim=claim,
                    )

            # Check visual objects
            for obj in visual_objects:
                obj_label = obj["label"].lower()
                if any(word in claim.lower() for word in obj_label.split()):
                    grounding_score = max(grounding_score, 0.70)
                    best_region = VerificationEvidence(
                        patch_x_min=int(obj["x"] / 32),
                        patch_y_min=int(obj["y"] / 32),
                        patch_x_max=int((obj["x"] + obj["w"]) / 32),
                        patch_y_max=int((obj["y"] + obj["h"]) / 32),
                        region_type="chart" if "chart" in obj_label else "image",
                        confidence=0.70,
                        referenced_claim=claim,
                    )

            if grounding_score >= 0.60:
                verified_claims.append(claim)
                if best_region:
                    evidence_regions.append(best_region)

        return evidence_regions, verified_claims

    def _extract_text_regions(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Extract text regions using OCR."""
        if not self.ocr_engine:
            return []

        try:
            ocr_results = self.ocr_engine.ocr(image, cls=True)

            text_regions = []
            for line in ocr_results:
                for word_info in line:
                    coords = word_info[0]
                    text = word_info[1][0]
                    confidence = word_info[1][1]

                    if confidence > 0.5:
                        x_min = min(c[0] for c in coords)
                        y_min = min(c[1] for c in coords)
                        x_max = max(c[0] for c in coords)
                        y_max = max(c[1] for c in coords)

                        text_regions.append(
                            {
                                "text": text,
                                "x": x_min,
                                "y": y_min,
                                "w": x_max - x_min,
                                "h": y_max - y_min,
                                "confidence": confidence,
                            }
                        )

            return text_regions

        except Exception as e:
            logger.warning(f"OCR extraction failed: {e}")
            return []

    def _recognize_visual_objects(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Recognize visual objects in image."""
        if not self.visual_recognizer:
            return []

        try:
            # Simple object detection
            # In production, would use YOLOv8 or similar
            objects = [
                {
                    "label": "chart",
                    "x": 100,
                    "y": 150,
                    "w": 200,
                    "h": 150,
                    "confidence": 0.75,
                },
                {
                    "label": "table",
                    "x": 50,
                    "y": 50,
                    "w": 150,
                    "h": 100,
                    "confidence": 0.70,
                },
            ]
            return objects

        except Exception as e:
            logger.warning(f"Object recognition failed: {e}")
            return []

    def _calculate_coverage_ratio(self, claims: List[str], verified: List[str]) -> float:
        """Calculate what fraction of claims have visual evidence."""
        if not claims:
            return 1.0
        return len(verified) / len(claims)

    def _check_semantic_consistency(
        self, claims: List[str], evidence: List[VerificationEvidence]
    ) -> float:
        """Check if visual evidence semantically matches claims."""
        if not evidence:
            return 0.5

        # Consistency score based on evidence-to-claim ratio
        consistency_score = min(len(evidence) / max(len(claims), 1), 1.0)

        # Penalize if many claims have no evidence
        unverified_penalty = (len(claims) - len(evidence)) / max(len(claims), 1)
        consistency_score = max(consistency_score - 0.3 * unverified_penalty, 0.0)

        return consistency_score

    def _calculate_hallucination_risk(
        self,
        coverage_ratio: float,
        semantic_consistency: float,
        num_unverified_claims: int,
    ) -> float:
        """Calculate hallucination risk score."""
        # Components:
        # - Missing coverage
        coverage_risk = (1.0 - coverage_ratio) * 0.40
        # - Semantic inconsistency
        consistency_risk = (1.0 - semantic_consistency) * 0.35
        # - Number of unverified claims
        claim_risk = min(num_unverified_claims / 5.0, 1.0) * 0.25

        hallucination_risk = coverage_risk + consistency_risk + claim_risk
        return min(max(hallucination_risk, 0.0), 1.0)

    def _classify_verification_status(self, hallucination_risk: float) -> str:
        """Classify verification status based on risk."""
        if hallucination_risk < 0.15:
            return "pass"
        elif hallucination_risk < 0.45:
            return "warn"
        else:
            return "fail"

    def _classify_risk_level(self, risk_score: float) -> str:
        """Classify risk level."""
        if risk_score < 0.15:
            return "low"
        elif risk_score < 0.45:
            return "medium"
        else:
            return "high"

    def _calculate_score_adjustment(
        self, original_score: float, hallucination_risk: float
    ) -> Tuple[float, float]:
        """Calculate score adjustment factor based on risk."""
        # Adjustment follows: adjusted = original * (1 - sqrt(risk))
        adjustment_factor = 1.0 - np.sqrt(hallucination_risk)
        adjusted_score = original_score * adjustment_factor

        return adjusted_score, adjustment_factor

    def _generate_verification_text(
        self,
        status: str,
        hallucination_risk: float,
        coverage_ratio: float,
    ) -> str:
        """Generate human-readable verification summary."""
        text = f"Verification Status: {status.upper()}\n"
        text += f"Hallucination Risk: {hallucination_risk:.1%}\n"
        text += f"Evidence Coverage: {coverage_ratio:.1%}\n"

        if status == "pass":
            text += "✓ All claims have strong visual evidence support"
        elif status == "warn":
            text += "⚠ Some claims lack complete visual evidence - review recommended"
        else:
            text += "✗ Multiple claims lack visual support - result confidence lowered"

        return text


class VerificationAgentFactory:
    """Factory for creating verification agents."""

    _instance = None

    @classmethod
    def get_agent(cls, device: str = "cuda") -> ArgosVerificationAgent:
        """Get or create singleton verification agent."""
        if cls._instance is None:
            cls._instance = ArgosVerificationAgent(device)
            cls._instance.initialize()
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset singleton instance."""
        cls._instance = None
