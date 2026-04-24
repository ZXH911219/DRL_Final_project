"""
Vector Quality Checking Module
Validates feature vector quality and coverage.
"""

import numpy as np
from typing import Dict, Any, Optional


class VectorQualityChecker:
    """Check vector quality metrics."""

    def __init__(self):
        """Initialize quality checker."""
        pass

    def check_coverage(
        self, multi_vectors: np.ndarray, min_coverage: float = 0.98
    ) -> Dict[str, Any]:
        """
        Check vector coverage ratio.

        Args:
            multi_vectors: Multi-vector array (N, 128)
            min_coverage: Minimum coverage threshold

        Returns:
            Coverage metrics dictionary
        """
        # Calculate coverage: ratio of non-zero patches
        norms = np.linalg.norm(multi_vectors, axis=1)
        non_zero_count = np.sum(norms > 0.01)
        total_count = multi_vectors.shape[0]

        coverage_ratio = non_zero_count / total_count if total_count > 0 else 0.0

        return {
            "coverage_ratio": float(coverage_ratio),
            "non_zero_count": int(non_zero_count),
            "total_count": int(total_count),
            "passes_threshold": coverage_ratio >= min_coverage,
            "message": f"Coverage: {coverage_ratio:.2%} (target: {min_coverage:.2%})",
        }

    def check_geometric_completeness(
        self, multi_vectors: np.ndarray, min_variance: float = 0.5
    ) -> Dict[str, Any]:
        """
        Check geometric completeness (feature diversity).

        Args:
            multi_vectors: Multi-vector array (N, 128)
            min_variance: Minimum variance threshold

        Returns:
            Completeness metrics dictionary
        """
        # Calculate variance across dimensions
        variance = np.var(multi_vectors)

        # Calculate mean norm (should be close to 1.0 for normalized vectors)
        norms = np.linalg.norm(multi_vectors, axis=1)
        mean_norm = np.mean(norms)
        norm_std = np.std(norms)

        # Calculate condition number (numerical stability)
        U, S, Vt = np.linalg.svd(multi_vectors, full_matrices=False)
        condition_number = S[0] / (S[-1] + 1e-8)

        return {
            "variance": float(variance),
            "mean_norm": float(mean_norm),
            "norm_std": float(norm_std),
            "condition_number": float(condition_number),
            "passes_variance_threshold": variance >= min_variance,
            "message": f"Variance: {variance:.4f}, Mean norm: {mean_norm:.4f}",
        }

    def check_consistency(
        self, multi_vectors: np.ndarray, max_outlier_zscore: float = 3.0
    ) -> Dict[str, Any]:
        """
        Check for outliers and inconsistencies.

        Args:
            multi_vectors: Multi-vector array (N, 128)
            max_outlier_zscore: Z-score threshold for outliers

        Returns:
            Consistency metrics dictionary
        """
        norms = np.linalg.norm(multi_vectors, axis=1)

        # Calculate z-scores
        mean_norm = np.mean(norms)
        std_norm = np.std(norms)

        z_scores = (norms - mean_norm) / (std_norm + 1e-8)
        outlier_count = np.sum(np.abs(z_scores) > max_outlier_zscore)
        outlier_ratio = outlier_count / len(norms) if len(norms) > 0 else 0.0

        return {
            "outlier_count": int(outlier_count),
            "outlier_ratio": float(outlier_ratio),
            "outlier_percentage": float(outlier_ratio * 100),
            "has_excessive_outliers": outlier_ratio > 0.05,
            "message": f"Outliers: {outlier_ratio:.2%}",
        }

    def comprehensive_check(
        self,
        multi_vectors: np.ndarray,
        imagebind_vector: np.ndarray,
        coverage_threshold: float = 0.98,
        variance_threshold: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Comprehensive quality check.

        Args:
            multi_vectors: Multi-vector array (N, 128)
            imagebind_vector: ImageBind aligned vector
            coverage_threshold: Minimum coverage
            variance_threshold: Minimum variance

        Returns:
            Complete quality report
        """
        coverage = self.check_coverage(multi_vectors, coverage_threshold)
        completeness = self.check_geometric_completeness(multi_vectors, variance_threshold)
        consistency = self.check_consistency(multi_vectors)

        # Overall quality score (0-100)
        score = 0.0
        if coverage["passes_threshold"]:
            score += 25.0
        else:
            score += coverage["coverage_ratio"] * 25.0

        if completeness["passes_variance_threshold"]:
            score += 25.0
        else:
            score += min(completeness["variance"] / variance_threshold, 1.0) * 25.0

        if not consistency["has_excessive_outliers"]:
            score += 25.0
        else:
            score += max((1.0 - consistency["outlier_ratio"]) * 25.0, 0.0)

        # ImageBind vector quality
        imagebind_norm = np.linalg.norm(imagebind_vector)
        if 0.95 < imagebind_norm < 1.05:  # Well normalized
            score += 25.0
        else:
            score += max(20.0 - abs(imagebind_norm - 1.0) * 5.0, 0.0)

        return {
            "overall_score": float(score),  # 0-100
            "coverage": coverage,
            "geometric_completeness": completeness,
            "consistency": consistency,
            "imagebind_norm": float(imagebind_norm),
            "passed_all_checks": (
                coverage["passes_threshold"]
                and completeness["passes_variance_threshold"]
                and not consistency["has_excessive_outliers"]
                and 0.95 < imagebind_norm < 1.05
            ),
            "summary": f"Quality Score: {score:.1f}/100 - {'PASS' if score >= 85.0 else 'WARN' if score >= 70.0 else 'FAIL'}",
        }
