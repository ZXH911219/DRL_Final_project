"""
Audit Logging and Monitoring for Lakehouse-Retrieval-Agent
Comprehensive logging, metrics collection, and performance tracking.
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import threading
from collections import defaultdict


@dataclass
class QueryMetrics:
    """Metrics for a single query execution."""

    query_id: str
    timestamp: str
    query_type: str  # "vector", "fts", "hybrid"
    stage_1_latency_ms: float  # Fast filtering
    stage_2_latency_ms: float  # Fine-grained matching
    total_latency_ms: float
    candidates_examined: int
    results_count: int
    fusion_strategy: Optional[str] = None
    vector_weight: Optional[float] = None
    fts_weight: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class RetrievalMetrics:
    """Metrics for retrieval quality."""

    query_id: str
    recall_at_k: Dict[int, float]  # {10: 0.92, 20: 0.95}
    mrr: float  # Mean Reciprocal Rank
    ndcg: float  # Normalized Discounted Cumulative Gain
    precision_at_1: float
    diversity_score: float
    avg_confidence: float


class JSONAuditLogger:
    """Structured JSON logging for audit trails."""

    def __init__(self, log_file: str = "retrieval_audit.jsonl"):
        """
        Initialize JSON audit logger.

        Args:
            log_file: Path to JSONL log file (one JSON per line)
        """
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Standard logger for console output
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        # Set up handlers
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

    def log_query_execution(self, metrics: QueryMetrics) -> None:
        """
        Log query execution metrics.

        Args:
            metrics: Query metrics object
        """
        log_entry = {
            "event_type": "query_execution",
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics.to_dict(),
        }

        self._write_json_log(log_entry)
        self.logger.info(
            f"Query {metrics.query_id} completed in {metrics.total_latency_ms:.1f}ms"
        )

    def log_retrieval_quality(self, metrics: RetrievalMetrics) -> None:
        """
        Log retrieval quality metrics.

        Args:
            metrics: Retrieval quality metrics
        """
        log_entry = {
            "event_type": "retrieval_quality",
            "timestamp": datetime.now().isoformat(),
            "query_id": metrics.query_id,
            "metrics": asdict(metrics),
        }

        self._write_json_log(log_entry)
        self.logger.info(
            f"Retrieval quality for {metrics.query_id}: MRR={metrics.mrr:.3f}, NDCG={metrics.ndcg:.3f}"
        )

    def log_indexing_operation(
        self,
        batch_id: str,
        slides_indexed: int,
        index_latency_ms: float,
        index_size_mb: float,
    ) -> None:
        """
        Log indexing operations.

        Args:
            batch_id: Batch identifier
            slides_indexed: Number of slides indexed
            index_latency_ms: Indexing latency
            index_size_mb: Index size in MB
        """
        log_entry = {
            "event_type": "indexing_operation",
            "timestamp": datetime.now().isoformat(),
            "batch_id": batch_id,
            "slides_indexed": slides_indexed,
            "index_latency_ms": index_latency_ms,
            "index_size_mb": index_size_mb,
            "throughput_slides_per_second": slides_indexed / (index_latency_ms / 1000)
            if index_latency_ms > 0
            else 0,
        }

        self._write_json_log(log_entry)
        self.logger.info(
            f"Indexed {slides_indexed} slides in {index_latency_ms:.1f}ms (size: {index_size_mb:.1f}MB)"
        )

    def log_error(
        self,
        error_type: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log errors.

        Args:
            error_type: Type of error
            error_message: Error message
            context: Optional context data
        """
        log_entry = {
            "event_type": "error",
            "timestamp": datetime.now().isoformat(),
            "error_type": error_type,
            "error_message": error_message,
            "context": context or {},
        }

        self._write_json_log(log_entry)
        self.logger.error(f"{error_type}: {error_message}")

    def log_cache_hit(self, query_hash: str, latency_saved_ms: float) -> None:
        """
        Log cache hits.

        Args:
            query_hash: Hash of cached query
            latency_saved_ms: Latency saved by cache
        """
        log_entry = {
            "event_type": "cache_hit",
            "timestamp": datetime.now().isoformat(),
            "query_hash": query_hash,
            "latency_saved_ms": latency_saved_ms,
        }

        self._write_json_log(log_entry)
        self.logger.debug(f"Cache hit - saved {latency_saved_ms:.1f}ms")

    def _write_json_log(self, log_entry: Dict[str, Any]) -> None:
        """
        Write log entry as JSON line.

        Args:
            log_entry: Dictionary to log
        """
        with open(self.log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")


class MetricsCollector:
    """Collect and aggregate metrics."""

    def __init__(self):
        """Initialize metrics collector."""
        self.query_metrics: List[QueryMetrics] = []
        self.retrieval_metrics: List[RetrievalMetrics] = []
        self.lock = threading.Lock()

    def collect_query_metrics(self, metrics: QueryMetrics) -> None:
        """
        Collect query metrics.

        Args:
            metrics: Query metrics
        """
        with self.lock:
            self.query_metrics.append(metrics)

    def collect_retrieval_metrics(self, metrics: RetrievalMetrics) -> None:
        """
        Collect retrieval metrics.

        Args:
            metrics: Retrieval metrics
        """
        with self.lock:
            self.retrieval_metrics.append(metrics)

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics.

        Returns:
            Dictionary with aggregated metrics
        """
        if not self.query_metrics:
            return {}

        latencies = [m.total_latency_ms for m in self.query_metrics]
        stage1_latencies = [m.stage_1_latency_ms for m in self.query_metrics]
        stage2_latencies = [m.stage_2_latency_ms for m in self.query_metrics]

        retrieval_mrrs = [m.mrr for m in self.retrieval_metrics] if self.retrieval_metrics else []
        retrieval_ndcgs = [
            m.ndcg for m in self.retrieval_metrics
        ] if self.retrieval_metrics else []

        summary = {
            "total_queries": len(self.query_metrics),
            "latency_stats": {
                "min_ms": min(latencies),
                "max_ms": max(latencies),
                "avg_ms": sum(latencies) / len(latencies),
                "p50_ms": sorted(latencies)[len(latencies) // 2],
                "p95_ms": sorted(latencies)[int(len(latencies) * 0.95)],
                "p99_ms": sorted(latencies)[int(len(latencies) * 0.99)],
            },
            "stage_1_latency_avg_ms": sum(stage1_latencies) / len(stage1_latencies)
            if stage1_latencies
            else 0,
            "stage_2_latency_avg_ms": sum(stage2_latencies) / len(stage2_latencies)
            if stage2_latencies
            else 0,
            "retrieval_quality": {
                "avg_mrr": sum(retrieval_mrrs) / len(retrieval_mrrs)
                if retrieval_mrrs
                else 0,
                "avg_ndcg": sum(retrieval_ndcgs) / len(retrieval_ndcgs)
                if retrieval_ndcgs
                else 0,
            },
        }

        return summary

    def get_query_type_stats(self) -> Dict[str, Dict[str, float]]:
        """
        Get statistics grouped by query type.

        Returns:
            Dictionary with stats per query type
        """
        type_groups = defaultdict(list)

        for metric in self.query_metrics:
            type_groups[metric.query_type].append(metric.total_latency_ms)

        stats = {}
        for query_type, latencies in type_groups.items():
            stats[query_type] = {
                "count": len(latencies),
                "avg_ms": sum(latencies) / len(latencies),
                "min_ms": min(latencies),
                "max_ms": max(latencies),
            }

        return stats


class PerformanceMonitor:
    """Real-time performance monitoring."""

    def __init__(self, alert_threshold_ms: float = 500):
        """
        Initialize performance monitor.

        Args:
            alert_threshold_ms: Latency threshold for alerts
        """
        self.alert_threshold_ms = alert_threshold_ms
        self.slow_queries = []
        self.logger = logging.getLogger(__name__)

    def check_latency(self, latency_ms: float, query_id: str) -> None:
        """
        Check if latency exceeds threshold.

        Args:
            latency_ms: Query latency
            query_id: Query identifier
        """
        if latency_ms > self.alert_threshold_ms:
            alert = {
                "query_id": query_id,
                "latency_ms": latency_ms,
                "threshold_ms": self.alert_threshold_ms,
                "excess_ms": latency_ms - self.alert_threshold_ms,
            }
            self.slow_queries.append(alert)
            self.logger.warning(
                f"SLOW QUERY ALERT: {query_id} took {latency_ms:.1f}ms (threshold: {self.alert_threshold_ms}ms)"
            )

    def get_slow_query_report(self) -> Dict[str, Any]:
        """
        Get report of slow queries.

        Returns:
            Slow queries summary
        """
        if not self.slow_queries:
            return {"total_slow_queries": 0}

        excess_times = [q["excess_ms"] for q in self.slow_queries]

        return {
            "total_slow_queries": len(self.slow_queries),
            "avg_excess_ms": sum(excess_times) / len(excess_times),
            "max_excess_ms": max(excess_times),
            "slow_queries": self.slow_queries[:10],  # Top 10
        }


class AuditTrailAnalyzer:
    """Analyze audit trail logs."""

    def __init__(self, log_file: str = "retrieval_audit.jsonl"):
        """
        Initialize analyzer.

        Args:
            log_file: Path to JSONL log file
        """
        self.log_file = Path(log_file)

    def read_logs(self) -> List[Dict[str, Any]]:
        """
        Read all audit logs.

        Returns:
            List of log entries
        """
        logs = []

        if not self.log_file.exists():
            return logs

        with open(self.log_file) as f:
            for line in f:
                if line.strip():
                    logs.append(json.loads(line))

        return logs

    def get_slowest_queries(self, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Get slowest queries from logs.

        Args:
            top_k: Number of results

        Returns:
            List of slowest query entries
        """
        logs = self.read_logs()
        query_logs = [
            l for l in logs
            if l.get("event_type") == "query_execution"
        ]

        sorted_logs = sorted(
            query_logs,
            key=lambda x: x["metrics"]["total_latency_ms"],
            reverse=True,
        )

        return sorted_logs[:top_k]

    def get_error_summary(self) -> Dict[str, int]:
        """
        Get error summary from logs.

        Returns:
            Error type counts
        """
        logs = self.read_logs()
        error_logs = [l for l in logs if l.get("event_type") == "error"]

        summary = {}
        for error_log in error_logs:
            error_type = error_log.get("error_type", "unknown")
            summary[error_type] = summary.get(error_type, 0) + 1

        return summary

    def generate_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive audit report.

        Returns:
            Audit report
        """
        logs = self.read_logs()
        event_types = defaultdict(int)

        for log in logs:
            event_types[log.get("event_type", "unknown")] += 1

        return {
            "total_log_entries": len(logs),
            "event_type_distribution": dict(event_types),
            "slowest_queries": self.get_slowest_queries(5),
            "error_summary": self.get_error_summary(),
        }
