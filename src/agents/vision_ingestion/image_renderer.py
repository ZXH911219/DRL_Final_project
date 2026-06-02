"""
Image Rendering Module
Convert PPT slides to high-quality images using LibreOffice.
"""

import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Optional

import numpy as np
from PIL import Image


class ImageRenderer:
    """Render PPT slides to high-quality images."""

    def __init__(
        self,
        output_format: str = "png",
        dpi: int = 600,
        resolution: tuple = (1024, 768),
        quality: int = 95,
    ):
        """
        Initialize image renderer.

        Args:
            output_format: Output image format (png, jpg, etc.)
            dpi: DPI for rendering
            resolution: Output resolution (width, height)
            quality: Image quality (for JPG)
        """
        self.output_format = output_format
        self.dpi = dpi
        self.resolution = resolution
        self.quality = quality

    def _detect_libreoffice(self) -> Optional[str]:
        """Detect LibreOffice installation."""
        possible_paths = [
            "soffice",
            "/usr/bin/soffice",
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
            "C:\\Program Files\\LibreOffice\\program\\soffice.exe",
            "C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe",
        ]

        for path in possible_paths:
            try:
                if path == "soffice":
                    resolved = shutil.which(path)
                    if resolved:
                        return resolved
                elif Path(path).exists():
                    return path
            except Exception:
                continue

        return None

    def render_ppt_to_images(
        self,
        ppt_path: str,
        output_dir: Optional[str] = None,
    ) -> List[str]:
        """
        Render PPT to images using LibreOffice headless.

        Args:
            ppt_path: Path to PPT file
            output_dir: Output directory for images

        Returns:
            List of output image paths
        """
        if output_dir is None:
            output_dir = tempfile.mkdtemp()

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        libreoffice = self._detect_libreoffice()
        if not libreoffice:
            print(
                "ERROR: LibreOffice not found. Install LibreOffice to enable PPT rendering.",
            )
            return []

        try:
            # Convert PPT to PDF first (intermediate format)
            cmd = [
                libreoffice,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(output_path),
                ppt_path,
            ]

            subprocess.run(cmd, capture_output=True, timeout=300)

            # LibreOffice writes a PDF with the same base name into outdir.
            # Detect the real PDF file produced instead of relying on a hardcoded name.
            pdf_files = list(output_path.glob("*.pdf"))
            if not pdf_files:
                print("ERROR rendering PPT: no PDF produced by LibreOffice")
                return []

            # Prefer a PDF that matches the PPT base name
            ppt_stem = Path(ppt_path).stem
            matched = [p for p in pdf_files if p.stem == ppt_stem]
            pdf_output = matched[0] if matched else pdf_files[0]

            # Then convert PDF to images
            return self._pdf_to_images(str(pdf_output), output_dir)

        except Exception as e:
            print(f"ERROR rendering PPT: {e}")
            return []

    def _pdf_to_images(self, pdf_path: str, output_dir: str) -> List[str]:
        """Convert PDF to images."""
        try:
            from pdf2image import convert_from_path

            output_path = Path(output_dir)
            images = convert_from_path(
                pdf_path,
                dpi=self.dpi,
                size=self.resolution,
            )

            output_files = []
            for i, image in enumerate(images):
                # Normalize to standard resolution
                image = image.resize(self.resolution, Image.Resampling.LANCZOS)

                output_file = output_path / f"slide_{i:03d}.{self.output_format}"
                image.save(str(output_file), quality=self.quality)
                output_files.append(str(output_file))

            return output_files

        except ImportError:
            print("ERROR: pdf2image not installed. Run: pip install pdf2image")
            return []

    def load_image_as_array(self, image_path: str) -> Optional[np.ndarray]:
        """Load image and convert to numpy array."""
        try:
            image = Image.open(image_path)
            # Normalize to standard resolution
            if image.size != self.resolution:
                image = image.resize(self.resolution, Image.Resampling.LANCZOS)

            return np.array(image)
        except Exception as e:
            print(f"ERROR loading image: {e}")
            return None


def render_ppt(ppt_path: str, output_dir: str) -> List[str]:
    """
    Render PPT to images.

    Args:
        ppt_path: Path to PPT file
        output_dir: Output directory

    Returns:
        List of image file paths
    """
    renderer = ImageRenderer()
    return renderer.render_ppt_to_images(ppt_path, output_dir)
