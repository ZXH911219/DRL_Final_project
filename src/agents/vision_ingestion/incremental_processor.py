"""
Incremental Batch Processing for Vision-Ingestion-Agent
Manage new PPT additions without re-indexing existing data.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


class BatchManifest:
    """Manifest for tracking batch processing state."""

    def __init__(self, manifest_path: str = "batch_manifest.json"):
        """Initialize batch manifest."""
        self.manifest_path = Path(manifest_path)
        self.manifest = self._load_manifest()

    def _load_manifest(self) -> Dict[str, Any]:
        """Load or create manifest."""
        if self.manifest_path.exists():
            with open(self.manifest_path) as f:
                return json.load(f)
        return {
            "version": "1.0",
            "created": datetime.now().isoformat(),
            "batches": {},
            "processed_ppts": {},
        }

    def save(self) -> None:
        """Save manifest to disk."""
        with open(self.manifest_path, "w") as f:
            json.dump(self.manifest, f, indent=2)

    def register_batch(
        self, batch_id: str, ppt_files: List[str], status: str = "pending"
    ) -> None:
        """
        Register a new batch.

        Args:
            batch_id: Batch identifier
            ppt_files: List of PPT file paths
            status: Batch status (pending/processing/completed/failed)
        """
        self.manifest["batches"][batch_id] = {
            "created": datetime.now().isoformat(),
            "status": status,
            "ppt_files": ppt_files,
            "total": len(ppt_files),
            "processed": 0,
            "failed": 0,
            "results": {},
        }
        self.save()

    def update_batch_status(self, batch_id: str, status: str) -> None:
        """Update batch status."""
        if batch_id in self.manifest["batches"]:
            self.manifest["batches"][batch_id]["status"] = status
            self.save()

    def register_ppt_processed(
        self,
        batch_id: str,
        ppt_path: str,
        slides_processed: int,
        success: bool = True,
    ) -> None:
        """
        Register PPT processing result.

        Args:
            batch_id: Batch ID
            ppt_path: PPT file path
            slides_processed: Number of slides processed
            success: Whether processing succeeded
        """
        if batch_id in self.manifest["batches"]:
            batch = self.manifest["batches"][batch_id]
            batch["results"][ppt_path] = {
                "timestamp": datetime.now().isoformat(),
                "slides": slides_processed,
                "success": success,
            }

            if success:
                batch["processed"] += 1
            else:
                batch["failed"] += 1

            # Register in global PPT tracking
            self.manifest["processed_ppts"][ppt_path] = {
                "batch_id": batch_id,
                "slides": slides_processed,
                "timestamp": datetime.now().isoformat(),
            }

            self.save()

    def get_processed_ppts(self) -> Dict[str, Any]:
        """Get all processed PPTs."""
        return self.manifest["processed_ppts"]

    def is_ppt_processed(self, ppt_path: str) -> bool:
        """Check if PPT was already processed."""
        return ppt_path in self.manifest["processed_ppts"]


class IncrementalBatchProcessor:
    """Process incremental batches of PPTs."""

    def __init__(self, manifest_path: str = "batch_manifest.json"):
        """Initialize processor."""
        self.manifest = BatchManifest(manifest_path)

    def identify_new_ppts(self, ppt_directory: str) -> List[str]:
        """
        Identify new PPT files not yet processed.

        Args:
            ppt_directory: Directory to scan

        Returns:
            List of new PPT file paths
        """
        ppt_dir = Path(ppt_directory)
        existing_ppts = set(self.manifest.get_processed_ppts().keys())

        new_ppts = []
        for ppt_file in ppt_dir.glob("**/*.pptx"):
            ppt_path = str(ppt_file.resolve())
            if ppt_path not in existing_ppts:
                new_ppts.append(ppt_path)

        return new_ppts

    def create_batch(self, batch_id: str, ppt_files: List[str]) -> None:
        """Create a new processing batch."""
        self.manifest.register_batch(batch_id, ppt_files, status="created")

    def start_processing(self, batch_id: str) -> None:
        """Mark batch as processing."""
        self.manifest.update_batch_status(batch_id, "processing")

    def complete_batch(self, batch_id: str) -> None:
        """Mark batch as completed."""
        self.manifest.update_batch_status(batch_id, "completed")

    def fail_batch(self, batch_id: str) -> None:
        """Mark batch as failed."""
        self.manifest.update_batch_status(batch_id, "failed")

    def record_ppt_result(
        self,
        batch_id: str,
        ppt_path: str,
        slides_processed: int,
        success: bool,
    ) -> None:
        """Record PPT processing result."""
        self.manifest.register_ppt_processed(
            batch_id, ppt_path, slides_processed, success
        )

    def get_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """Get batch processing status."""
        return self.manifest.manifest["batches"].get(batch_id, {})

    def get_statistics(self) -> Dict[str, Any]:
        """Get processing statistics."""
        batches = self.manifest.manifest["batches"]
        total_batches = len(batches)
        completed = sum(1 for b in batches.values() if b["status"] == "completed")
        total_ppts = sum(b["total"] for b in batches.values())
        total_processed = sum(b["processed"] for b in batches.values())
        total_failed = sum(b["failed"] for b in batches.values())

        return {
            "total_batches": total_batches,
            "completed_batches": completed,
            "total_ppts": total_ppts,
            "processed_ppts": total_processed,
            "failed_ppts": total_failed,
            "success_rate": (
                total_processed / total_ppts if total_ppts > 0 else 0.0
            ),
        }
