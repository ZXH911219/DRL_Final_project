"""
Performance Benchmarking for Lakehouse-Retrieval-Agent
Comprehensive latency, throughput, and quality benchmarks.
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
import json
from pathlib import Path
import statistics


@dataclass
class BenchmarkResult:
    """Single benchmark run result."""

    name: str
    operation: str
    iteration: int
    latency_ms: float
    throughput_ops_per_sec: float
    success: bool
    error_msg: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "operation": self.operation,
            "iteration": self.iteration,
            "latency_ms": self.latency_ms,
            "throughput_ops_per_sec": self.throughput_ops_per_sec,
            "success": self.success,
            "error_msg": self.error_msg,
        }


class PerformanceBenchmark:
    """Run performance benchmarks."""

    # SLA targets (from specification)
    SLA_TARGETS = {
        "stage_1_retrieval_ms": 50,       # Fast filtering
        "stage_2_retrieval_ms": 100,      # MaxSim fine matching
        "total_retrieval_ms": 200,         # End-to-end
        "index_latency_ms": 500,           # Per slide
        "query_throughput_qps": 100,       # Queries per second
    }

    def __init__(self, output_dir: str = "benchmarks"):
        """Initialize benchmark."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results: List[BenchmarkResult] = []

    def benchmark_stage_1_retrieval(
        self,
        retriever,
        num_iterations: int = 100,
    ) -> Dict[str, float]:
        """
        Benchmark stage 1 (fast filtering).

        Args:
            retriever: Retriever instance with stage_1_retrieve method
            num_iterations: Number of iterations

        Returns:
            Benchmark statistics
        """
        latencies = []

        print(f"Benchmarking Stage 1 Retrieval ({num_iterations} iterations)...")

        for i in range(num_iterations):
            query_vector = np.random.randn(1024, 128).astype(np.float32)

            start = time.time()
            try:
                # Mock stage 1 operation
                results = retriever.retrieve(query_vector, top_k=500, stage=1)
                latency_ms = (time.time() - start) * 1000

                latencies.append(latency_ms)
                self.results.append(
                    BenchmarkResult(
                        name="stage_1_retrieval",
                        operation="Fast Filtering",
                        iteration=i,
                        latency_ms=latency_ms,
                        throughput_ops_per_sec=1000 / latency_ms if latency_ms > 0 else 0,
                        success=True,
                    )
                )
            except Exception as e:
                self.results.append(
                    BenchmarkResult(
                        name="stage_1_retrieval",
                        operation="Fast Filtering",
                        iteration=i,
                        latency_ms=0,
                        throughput_ops_per_sec=0,
                        success=False,
                        error_msg=str(e),
                    )
                )

        return self._compute_stats("Stage 1 Retrieval", latencies)

    def benchmark_stage_2_retrieval(
        self,
        retriever,
        num_iterations: int = 100,
    ) -> Dict[str, float]:
        """
        Benchmark stage 2 (fine-grained matching).

        Args:
            retriever: Retriever instance with stage_2_retrieve method
            num_iterations: Number of iterations

        Returns:
            Benchmark statistics
        """
        latencies = []

        print(f"Benchmarking Stage 2 Retrieval ({num_iterations} iterations)...")

        for i in range(num_iterations):
            query_vector = np.random.randn(1024, 128).astype(np.float32)
            candidates = [
                np.random.randn(1024, 128).astype(np.float32)
                for _ in range(50)
            ]

            start = time.time()
            try:
                # Mock stage 2 operation
                results = retriever.maxsim_rerank(query_vector, candidates, top_k=20)
                latency_ms = (time.time() - start) * 1000

                latencies.append(latency_ms)
                self.results.append(
                    BenchmarkResult(
                        name="stage_2_retrieval",
                        operation="MaxSim Fine Matching",
                        iteration=i,
                        latency_ms=latency_ms,
                        throughput_ops_per_sec=1000 / latency_ms if latency_ms > 0 else 0,
                        success=True,
                    )
                )
            except Exception as e:
                self.results.append(
                    BenchmarkResult(
                        name="stage_2_retrieval",
                        operation="MaxSim Fine Matching",
                        iteration=i,
                        latency_ms=0,
                        throughput_ops_per_sec=0,
                        success=False,
                        error_msg=str(e),
                    )
                )

        return self._compute_stats("Stage 2 Retrieval", latencies)

    def benchmark_e2e_retrieval(
        self,
        retriever,
        num_iterations: int = 100,
    ) -> Dict[str, float]:
        """
        Benchmark end-to-end retrieval.

        Args:
            retriever: Retriever instance
            num_iterations: Number of iterations

        Returns:
            Benchmark statistics
        """
        latencies = []

        print(f"Benchmarking E2E Retrieval ({num_iterations} iterations)...")

        for i in range(num_iterations):
            query_vector = np.random.randn(1024, 128).astype(np.float32)

            start = time.time()
            try:
                # Full retrieval pipeline
                results = retriever.retrieve(query_vector, top_k=20)
                latency_ms = (time.time() - start) * 1000

                latencies.append(latency_ms)
                self.results.append(
                    BenchmarkResult(
                        name="e2e_retrieval",
                        operation="End-to-End Retrieval",
                        iteration=i,
                        latency_ms=latency_ms,
                        throughput_ops_per_sec=1000 / latency_ms if latency_ms > 0 else 0,
                        success=True,
                    )
                )
            except Exception as e:
                self.results.append(
                    BenchmarkResult(
                        name="e2e_retrieval",
                        operation="End-to-End Retrieval",
                        iteration=i,
                        latency_ms=0,
                        throughput_ops_per_sec=0,
                        success=False,
                        error_msg=str(e),
                    )
                )

        return self._compute_stats("End-to-End Retrieval", latencies)

    def benchmark_fusion(
        self,
        fusion_engine,
        num_iterations: int = 50,
    ) -> Dict[str, float]:
        """
        Benchmark score fusion.

        Args:
            fusion_engine: Fusion engine instance
            num_iterations: Number of iterations

        Returns:
            Benchmark statistics
        """
        latencies = []

        print(f"Benchmarking Score Fusion ({num_iterations} iterations)...")

        for i in range(num_iterations):
            vector_scores = [np.random.rand() for _ in range(100)]
            fts_scores = [np.random.rand() for _ in range(100)]

            start = time.time()
            try:
                fused = fusion_engine.fuse_scores(vector_scores, fts_scores)
                latency_ms = (time.time() - start) * 1000

                latencies.append(latency_ms)
                self.results.append(
                    BenchmarkResult(
                        name="fusion",
                        operation="Score Fusion",
                        iteration=i,
                        latency_ms=latency_ms,
                        throughput_ops_per_sec=1000 / latency_ms if latency_ms > 0 else 0,
                        success=True,
                    )
                )
            except Exception as e:
                self.results.append(
                    BenchmarkResult(
                        name="fusion",
                        operation="Score Fusion",
                        iteration=i,
                        latency_ms=0,
                        throughput_ops_per_sec=0,
                        success=False,
                        error_msg=str(e),
                    )
                )

        return self._compute_stats("Score Fusion", latencies)

    def benchmark_mmr_reranking(
        self,
        ranker,
        num_iterations: int = 50,
    ) -> Dict[str, float]:
        """
        Benchmark MMR reranking.

        Args:
            ranker: MMR ranker instance
            num_iterations: Number of iterations

        Returns:
            Benchmark statistics
        """
        latencies = []

        print(f"Benchmarking MMR Reranking ({num_iterations} iterations)...")

        for i in range(num_iterations):
            candidates = [
                {
                    "slide_id": f"slide_{j}",
                    "vector": np.random.randn(1024).astype(np.float32),
                    "fused_score": np.random.rand(),
                }
                for j in range(100)
            ]

            start = time.time()
            try:
                reranked = ranker.rerank_by_mmr(candidates, top_k=20)
                latency_ms = (time.time() - start) * 1000

                latencies.append(latency_ms)
                self.results.append(
                    BenchmarkResult(
                        name="mmr_reranking",
                        operation="MMR Reranking",
                        iteration=i,
                        latency_ms=latency_ms,
                        throughput_ops_per_sec=1000 / latency_ms if latency_ms > 0 else 0,
                        success=True,
                    )
                )
            except Exception as e:
                self.results.append(
                    BenchmarkResult(
                        name="mmr_reranking",
                        operation="MMR Reranking",
                        iteration=i,
                        latency_ms=0,
                        throughput_ops_per_sec=0,
                        success=False,
                        error_msg=str(e),
                    )
                )

        return self._compute_stats("MMR Reranking", latencies)

    def _compute_stats(self, name: str, latencies: List[float]) -> Dict[str, float]:
        """
        Compute statistics.

        Args:
            name: Operation name
            latencies: List of latencies in ms

        Returns:
            Statistics dictionary
        """
        if not latencies:
            return {}

        sorted_latencies = sorted(latencies)

        stats = {
            "operation": name,
            "samples": len(latencies),
            "min_ms": min(latencies),
            "max_ms": max(latencies),
            "avg_ms": statistics.mean(latencies),
            "median_ms": statistics.median(latencies),
            "stdev_ms": statistics.stdev(latencies) if len(latencies) > 1 else 0,
            "p50_ms": sorted_latencies[int(len(latencies) * 0.50)],
            "p95_ms": sorted_latencies[int(len(latencies) * 0.95)],
            "p99_ms": sorted_latencies[int(len(latencies) * 0.99)],
        }

        # Check against SLA
        sla_key = name.lower().replace(" ", "_") + "_ms"
        if sla_key in self.SLA_TARGETS:
            target = self.SLA_TARGETS[sla_key]
            stats["sla_target_ms"] = target
            stats["meets_sla"] = stats["avg_ms"] <= target
            stats["p95_meets_sla"] = stats["p95_ms"] <= target

        print(
            f"  {name}: avg={stats['avg_ms']:.1f}ms, p95={stats['p95_ms']:.1f}ms, p99={stats['p99_ms']:.1f}ms"
        )

        return stats

    def generate_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive benchmark report.

        Returns:
            Benchmark report
        """
        stats_by_operation = {}

        for result in self.results:
            if result.operation not in stats_by_operation:
                stats_by_operation[result.operation] = {
                    "successes": 0,
                    "failures": 0,
                    "latencies": [],
                }

            if result.success:
                stats_by_operation[result.operation]["successes"] += 1
                stats_by_operation[result.operation]["latencies"].append(result.latency_ms)
            else:
                stats_by_operation[result.operation]["failures"] += 1

        # Compute final stats
        final_stats = {}
        for operation, data in stats_by_operation.items():
            if data["latencies"]:
                final_stats[operation] = self._compute_stats(operation, data["latencies"])
                final_stats[operation]["success_rate"] = (
                    data["successes"]
                    / (data["successes"] + data["failures"])
                    * 100
                )

        return {
            "timestamp": str(np.datetime64("now")),
            "sla_targets": self.SLA_TARGETS,
            "results": final_stats,
            "total_tests": len(self.results),
        }

    def save_report(self, filename: str = "benchmark_report.json") -> None:
        """Save report to file."""
        report = self.generate_report()
        report_path = self.output_dir / filename

        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        print(f"Benchmark report saved to {report_path}")

    def save_results_csv(self, filename: str = "benchmark_results.csv") -> None:
        """Save raw results to CSV."""
        import csv

        csv_path = self.output_dir / filename

        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "name",
                    "operation",
                    "iteration",
                    "latency_ms",
                    "throughput_ops_per_sec",
                    "success",
                    "error_msg",
                ],
            )
            writer.writeheader()

            for result in self.results:
                writer.writerow(result.to_dict())

        print(f"Benchmark results saved to {csv_path}")
