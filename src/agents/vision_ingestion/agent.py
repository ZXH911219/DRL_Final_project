"""
Vision-Ingestion-Agent
Main orchestrator for PPT ingestion pipeline.
Coordinates parsing, rendering, feature extraction, and storage.
"""

import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...utils import get_logger, get_lancedb_manager


class VisionIngestionAgent:
    """Main Vision-Ingestion-Agent implementation."""

    def __init__(self):
        """Initialize agent."""
        self.logger = get_logger("VisionIngestionAgent")
        self.lancedb = get_lancedb_manager()

        # Import components
        from .ppt_parser import parse_ppt
        from .image_renderer import ImageRenderer
        from .feature_extractor import extract_visual_features

        self.parse_ppt = parse_ppt
        self.ImageRenderer = ImageRenderer
        self.extract_visual_features = extract_visual_features

    def ingest_ppt(
        self,
        ppt_path: str,
        batch_id: Optional[str] = None,
        store_images: bool = False,
    ) -> Dict[str, Any]:
        """
        Complete PPT ingestion pipeline.

        Args:
            ppt_path: Path to PPT file
            batch_id: Batch identifier for tracking
            store_images: Whether to store rendered images

        Returns:
            Ingestion result dictionary
        """
        self.logger.info(f"Starting PPT ingestion: {ppt_path}")
        result = {
            "success": False,
            "ppt_path": ppt_path,
            "batch_id": batch_id,
            "slides_processed": 0,
            "errors": [],
            "warnings": [],
        }

        try:
            # Step 1: Parse PPT structure
            self.logger.info("Step 1: Parsing PPT structure...")
            parser = self.parse_ppt(ppt_path)
            if not parser:
                result["errors"].append("Failed to parse PPT")
                return result

            total_slides = parser.get_slide_count()
            self.logger.info(f"Total slides: {total_slides}")

            # Step 2: Create temporary directory for images
            temp_dir = tempfile.mkdtemp(prefix="drl_vision_")
            self.logger.info(f"Created temporary directory: {temp_dir}")

            # Step 3: Render images
            self.logger.info("Step 2: Rendering PPT to images...")
            renderer = self.ImageRenderer()
            image_paths = renderer.render_ppt_to_images(ppt_path, temp_dir)
            self.logger.info(f"Rendered {len(image_paths)} images")

            # Step 4: Extract features for each slide
            self.logger.info("Step 3: Extracting visual features...")
            features_list = []

            for slide_idx in range(total_slides):
                try:
                    # Load image
                    image_path = image_paths[slide_idx] if slide_idx < len(image_paths) else None
                    if not image_path or not Path(image_path).exists():
                        self.logger.warning(f"Image not found for slide {slide_idx}")
                        result["warnings"].append(f"Missing image for slide {slide_idx}")
                        continue

                    import numpy as np

                    img_array = renderer.load_image_as_array(image_path)
                    if img_array is None:
                        self.logger.warning(f"Failed to load image for slide {slide_idx}")
                        continue

                    # Get slide metadata
                    metadata = parser.get_slide_metadata(slide_idx)

                    # Extract visual features
                    features = self.extract_visual_features(
                        img_array,
                        slide_id=f"slide_{slide_idx}",
                        page_index=slide_idx,
                        metadata=metadata,
                    )

                    if features:
                        features_list.append(features)
                        self.logger.info(f"Extracted features for slide {slide_idx}")
                    else:
                        self.logger.warning(f"Failed to extract features for slide {slide_idx}")
                        result["warnings"].append(f"Feature extraction failed for slide {slide_idx}")

                except Exception as e:
                    self.logger.error(f"Error processing slide {slide_idx}: {e}")
                    result["errors"].append(f"Error processing slide {slide_idx}: {str(e)}")

            # Step 5: Store features in vector database
            self.logger.info("Step 4: Storing features in vector database...")
            if features_list and self.lancedb.is_connected():
                try:
                    # Create table for this batch
                    table_name = f"slides_{batch_id}" if batch_id else "slides"

                    # Prepare data for storage
                    data = []
                    for features in features_list:
                        data.append({
                            "slide_id": features.slide_id,
                            "page_index": features.page_index,
                            "multi_vectors": features.multi_vectors,
                            "imagebind_vector": features.imagebind_vector,
                            "metadata": features.metadata,
                        })

                    # Store in database
                    self.lancedb.add_vectors(table_name, [f.imagebind_vector for f in features_list])
                    self.logger.info(f"Stored {len(features_list)} feature vectors")
                    result["slides_processed"] = len(features_list)

                except Exception as e:
                    self.logger.error(f"Error storing features: {e}")
                    result["errors"].append(f"Storage error: {str(e)}")
            else:
                result["warnings"].append("LanceDB not connected, skipping storage")

            # Cleanup
            if not store_images:
                shutil.rmtree(temp_dir)
                self.logger.info(f"Cleaned up temporary directory")

            result["success"] = len(result["errors"]) == 0
            self.logger.info(f"PPT ingestion completed: {result['slides_processed']} slides processed")

            return result

        except Exception as e:
            self.logger.error(f"Fatal error during ingestion: {e}")
            result["errors"].append(f"Fatal error: {str(e)}")
            return result


# Global agent instance
_agent: Optional[VisionIngestionAgent] = None


def get_vision_agent() -> VisionIngestionAgent:
    """Get or create global Vision-Ingestion-Agent."""
    global _agent
    if _agent is None:
        _agent = VisionIngestionAgent()
    return _agent
