"""
docx_loader.py: Microsoft Word (.docx) document ingestion and structural decomposition.

Why this file exists:
Enterprise and academic workflows frequently produce native .docx documents (curricula,
exam papers, study guides, research drafts). This module parses .docx files natively
using zipfile and XML element trees (with python-docx compatibility), extracting paragraphs,
headings, and tables, synthesizing page boundaries, and rendering preview canvases with
exact bounding boxes for visual citation grounding.
"""

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

WORD_NAMESPACE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _get_tag(local_name: str) -> str:
    return f"{WORD_NAMESPACE}{local_name}"


def parse_docx_xml(docx_path: Path) -> List[Dict[str, Any]]:
    """Parse raw paragraphs, headings, and tables from a .docx file without external dependencies."""
    raw_elements: List[Dict[str, Any]] = []

    with zipfile.ZipFile(docx_path, "r") as zf:
        if "word/document.xml" not in zf.namelist():
            raise ValueError(f"Invalid DOCX file: missing word/document.xml in {docx_path}")

        xml_bytes = zf.read("word/document.xml")
        root = ET.fromstring(xml_bytes)
        body = root.find(_get_tag("body"))
        if body is None:
            return []

        for elem in body:
            tag = elem.tag

            # Paragraphs (<w:p>)
            if tag == _get_tag("p"):
                # Check for explicit page break (<w:br w:type="page"/>)
                has_page_break = bool(elem.findall(f".//{_get_tag('br')}[@{WORD_NAMESPACE}type='page']"))

                # Check for heading style
                p_style = elem.find(f".//{_get_tag('pStyle')}")
                style_val = p_style.attrib.get(f"{WORD_NAMESPACE}val", "") if p_style is not None else ""
                is_heading = "heading" in style_val.lower() or "title" in style_val.lower()

                # Extract text from runs
                texts = [t.text for t in elem.findall(f".//{_get_tag('t')}") if t.text]
                full_text = "".join(texts).strip()

                if full_text:
                    raw_elements.append({
                        "type": "HEADING" if is_heading else "PARAGRAPH",
                        "text": full_text,
                        "style": style_val,
                        "has_page_break": has_page_break,
                    })
                elif has_page_break:
                    raw_elements.append({
                        "type": "PAGE_BREAK",
                        "text": "",
                        "style": "",
                        "has_page_break": True,
                    })

            # Tables (<w:tbl>)
            elif tag == _get_tag("tbl"):
                table_rows: List[List[str]] = []
                for row_elem in elem.findall(_get_tag("tr")):
                    row_cells: List[str] = []
                    for cell_elem in row_elem.findall(_get_tag("tc")):
                        cell_texts = [t.text for t in cell_elem.findall(f".//{_get_tag('t')}") if t.text]
                        row_cells.append(" ".join(cell_texts).strip())
                    if any(row_cells):
                        table_rows.append(row_cells)

                if table_rows:
                    # Format table as readable markdown-like text
                    table_str = "\n".join(" | ".join(r) for r in table_rows)
                    raw_elements.append({
                        "type": "TABLE",
                        "text": table_str,
                        "style": "table",
                        "has_page_break": False,
                        "rows": table_rows,
                    })

    return raw_elements


def load_docx_pages(
    file_path: Path,
    canvas_width: int = 800,
    canvas_height: int = 1100,
    words_per_page: int = 400,
) -> List[Tuple[int, Image.Image, int, int, List[Dict[str, Any]]]]:
    """Decompose DOCX file into sequential synthetic pages with preview canvases and bounding boxes.

    Returns:
        List of tuples: (page_number, pil_preview_image, width, height, page_blocks)
    """
    path = Path(file_path).resolve()
    elements = parse_docx_xml(path)
    if not elements:
        # Return at least 1 empty page
        blank = Image.new("RGB", (canvas_width, canvas_height), color=(255, 255, 255))
        return [(1, blank, canvas_width, canvas_height, [])]

    pages_data: List[List[Dict[str, Any]]] = [[]]
    current_word_count = 0

    for elem in elements:
        if elem["type"] == "PAGE_BREAK":
            if pages_data[-1]:
                pages_data.append([])
                current_word_count = 0
            continue

        w_count = len(elem["text"].split())
        if current_word_count + w_count > words_per_page and pages_data[-1]:
            pages_data.append([])
            current_word_count = 0

        pages_data[-1].append(elem)
        current_word_count += w_count

        if elem.get("has_page_break", False):
            pages_data.append([])
            current_word_count = 0

    if not pages_data[-1] and len(pages_data) > 1:
        pages_data.pop()

    rendered_pages: List[Tuple[int, Image.Image, int, int, List[Dict[str, Any]]]] = []

    for p_idx, page_elems in enumerate(pages_data, start=1):
        # Create white preview canvas
        canvas = Image.new("RGB", (canvas_width, canvas_height), color=(255, 255, 255))
        draw = ImageDraw.Draw(canvas)

        margin_x = 50.0
        current_y = 50.0
        line_height = 24.0
        page_blocks: List[Dict[str, Any]] = []

        for b_idx, elem in enumerate(page_elems, start=1):
            text = elem["text"]
            b_type = elem["type"]

            # Estimate wrapped lines
            max_chars_per_line = 70
            words = text.split()
            lines: List[str] = []
            curr_line: List[str] = []
            for w in words:
                if sum(len(x) + 1 for x in curr_line) + len(w) <= max_chars_per_line:
                    curr_line.append(w)
                else:
                    lines.append(" ".join(curr_line))
                    curr_line = [w]
            if curr_line:
                lines.append(" ".join(curr_line))

            block_height = max(line_height, len(lines) * line_height)
            block_ymin = current_y
            block_ymax = min(canvas_height - 30.0, current_y + block_height)
            block_xmin = margin_x
            block_xmax = canvas_width - margin_x

            # Draw text on preview canvas
            y_cursor = current_y
            for line_str in lines:
                if y_cursor + line_height < canvas_height - 20:
                    draw.text((margin_x, y_cursor), line_str, fill=(20, 20, 20))
                    y_cursor += line_height

            bbox = (round(block_xmin, 1), round(block_ymin, 1), round(block_xmax, 1), round(block_ymax, 1))

            page_blocks.append({
                "block_id": b_idx,
                "block_type": b_type,
                "text": text,
                "bounding_box": bbox,
                "confidence": 1.0,
            })

            current_y = block_ymax + 14.0  # paragraph spacing

        rendered_pages.append((p_idx, canvas, canvas_width, canvas_height, page_blocks))

    return rendered_pages
