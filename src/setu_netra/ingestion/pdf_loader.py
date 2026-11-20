"""
pdf_loader.py: Multi-page PDF ingestion and page rasterization for SETU-NETRA.

Why this file exists:
Organizations operate primarily on PDF documents (scanned forms, multi-page exam
papers, contracts, and research reports). This module decomposes multi-page PDFs
into sequential, high-resolution PIL Image buffers for downstream OCR and structure
reconstruction while preserving document-level and page-level provenance.
"""

from pathlib import Path
from typing import List, Tuple
from PIL import Image

try:
    import pypdfium2 as pdfium
    PYPDFIUM2_AVAILABLE = True
except ImportError:
    PYPDFIUM2_AVAILABLE = False


def is_pdfium_available() -> bool:
    """Check whether pypdfium2 is installed and ready."""
    return PYPDFIUM2_AVAILABLE


def get_pdf_page_count(file_path: Path) -> int:
    """Fast inspection of the total page count in a PDF file without full rasterization."""
    if not PYPDFIUM2_AVAILABLE:
        raise ImportError(
            "pypdfium2 is required for PDF ingestion. Please install it with: pip install pypdfium2"
        )
    path = Path(file_path)
    doc = pdfium.PdfDocument(path)
    try:
        return len(doc)
    finally:
        doc.close()


def load_pdf_pages(
    file_path: Path,
    dpi: int = 150,
) -> List[Tuple[int, Image.Image, int, int]]:
    """Decompose and render a multi-page PDF document into sequential PIL Image pages.

    Args:
        file_path: Path to the target PDF file.
        dpi: Target rendering resolution in dots per inch (default: 150 DPI).
             150 DPI provides an optimal balance between OCR character definition
             and memory usage (~1.5-2.5 MB per rendered page).

    Returns:
        List of tuples: (page_number, pil_image, pixel_width, pixel_height).
        Note: page_number is 1-based (page 1, page 2, ...).

    Raises:
        ImportError: If pypdfium2 is not installed.
        FileNotFoundError: If the specified file does not exist.
        ValueError: If the PDF contains zero pages or is corrupted.
    """
    if not PYPDFIUM2_AVAILABLE:
        raise ImportError(
            "pypdfium2 is required for PDF ingestion. Please install it with: pip install pypdfium2"
        )

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file does not exist: {path}")

    doc = pdfium.PdfDocument(path)
    rendered_pages: List[Tuple[int, Image.Image, int, int]] = []

    try:
        total_pages = len(doc)
        if total_pages == 0:
            raise ValueError(f"PDF document contains zero pages: {path}")

        # PDF standard coordinate space is 72 points per inch
        scale = float(dpi) / 72.0

        for page_idx in range(total_pages):
            page_num = page_idx + 1
            page = doc[page_idx]
            # Render page via PDFium native renderer directly to PIL Image
            rendered_image = page.render(scale=scale).to_pil()
            w, h = rendered_image.size
            rendered_pages.append((page_num, rendered_image, w, h))

        return rendered_pages
    finally:
        doc.close()
