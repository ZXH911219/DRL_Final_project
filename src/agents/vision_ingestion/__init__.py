"""Vision-Ingestion-Agent for visual feature extraction."""

from .ppt_parser import PPTParser, parse_ppt
from .image_renderer import ImageRenderer, render_ppt
from .feature_extractor import ColPaliExtractor, ImageBindAligner, VisualFeatureBundle
from .agent import VisionIngestionAgent, get_vision_agent

__all__ = [
    "PPTParser",
    "parse_ppt",
    "ImageRenderer",
    "render_ppt",
    "ColPaliExtractor",
    "ImageBindAligner",
    "VisualFeatureBundle",
    "VisionIngestionAgent",
    "get_vision_agent",
]
