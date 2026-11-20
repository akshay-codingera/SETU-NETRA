"""
Image & document ingestion package: validation, safe loading, and PDF decomposition.
"""

from setu_netra.ingestion.validator import validate_image_file, validate_document_file
from setu_netra.ingestion.loader import load_image, extract_metadata
from setu_netra.ingestion.pdf_loader import (
    load_pdf_pages,
    is_pdfium_available,
    get_pdf_page_count,
)

__all__ = [
    "validate_image_file",
    "validate_document_file",
    "load_image",
    "extract_metadata",
    "load_pdf_pages",
    "is_pdfium_available",
    "get_pdf_page_count",
]

