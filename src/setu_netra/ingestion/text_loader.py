"""
text_loader.py: Plain text (.txt) document ingestion and structural pagination.

Why this file exists:
Provides clean, reliable ingestion for unformatted and formatted plain text files
(exam question banks, lecture notes, code docs, transcripts). Partitions text into
sequential pages, identifies structural roles (headings, questions, paragraphs), and
synthesizes rendered visual page canvases with exact spatial bounding boxes for uniform
provenance tracking and UI highlighting.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple
from PIL import Image, ImageDraw


def load_text_pages(
    file_path: Path,
    canvas_width: int = 800,
    canvas_height: int = 1100,
    lines_per_page: int = 40,
) -> List[Tuple[int, Image.Image, int, int, List[Dict[str, Any]]]]:
    """Decompose a plain text document into sequential pages with visual preview canvases.

    Returns:
        List of tuples: (page_number, pil_preview_image, width, height, page_blocks)
    """
    path = Path(file_path).resolve()
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_content = f.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="latin-1", errors="replace") as f:
            raw_content = f.read()

    # Split into logical paragraphs separated by blank lines
    raw_paragraphs = [p.strip() for p in raw_content.split("\n\n") if p.strip()]
    if not raw_paragraphs:
        blank = Image.new("RGB", (canvas_width, canvas_height), color=(255, 255, 255))
        return [(1, blank, canvas_width, canvas_height, [])]

    # Cluster paragraphs into pages
    pages_paragraphs: List[List[str]] = [[]]
    current_line_count = 0

    for para in raw_paragraphs:
        lines = para.split("\n")
        para_lines = max(1, len(lines))
        if current_line_count + para_lines > lines_per_page and pages_paragraphs[-1]:
            pages_paragraphs.append([])
            current_line_count = 0

        pages_paragraphs[-1].append(para)
        current_line_count += para_lines

    rendered_pages: List[Tuple[int, Image.Image, int, int, List[Dict[str, Any]]]] = []

    for p_idx, page_paras in enumerate(pages_paragraphs, start=1):
        canvas = Image.new("RGB", (canvas_width, canvas_height), color=(255, 255, 255))
        draw = ImageDraw.Draw(canvas)

        margin_x = 50.0
        current_y = 50.0
        line_height = 22.0
        page_blocks: List[Dict[str, Any]] = []

        for b_idx, para_text in enumerate(page_paras, start=1):
            # Classify role
            b_type = "PARAGRAPH"
            first_line = para_text.split("\n")[0].strip()
            if first_line.isupper() and len(first_line) < 80:
                b_type = "HEADING"
            elif first_line.startswith("#") or first_line.startswith("SECTION") or first_line.startswith("CHAPTER"):
                b_type = "HEADING"
            elif "?" in para_text or first_line.lower().startswith(("q", "question", "what", "explain", "how", "why")):
                b_type = "QUESTION"

            lines = para_text.split("\n")
            block_h = max(line_height, len(lines) * line_height)
            block_ymin = current_y
            block_ymax = min(canvas_height - 30.0, current_y + block_h)
            block_xmin = margin_x
            block_xmax = canvas_width - margin_x

            # Draw lines
            y_cursor = current_y
            for line_str in lines:
                if y_cursor + line_height < canvas_height - 20:
                    draw.text((margin_x, y_cursor), line_str[:85], fill=(20, 20, 20))
                    y_cursor += line_height

            bbox = (round(block_xmin, 1), round(block_ymin, 1), round(block_xmax, 1), round(block_ymax, 1))

            page_blocks.append({
                "block_id": b_idx,
                "block_type": b_type,
                "text": para_text,
                "bounding_box": bbox,
                "confidence": 1.0,
            })

            current_y = block_ymax + 12.0

        rendered_pages.append((p_idx, canvas, canvas_width, canvas_height, page_blocks))

    return rendered_pages
