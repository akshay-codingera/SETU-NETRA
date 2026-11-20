"""
run_real_world_failure_tests.py: Empirical test suite executing SETU-NETRA on 10 edge and failure cases.
"""

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from setu_netra.ingestion.validator import validate_document_file
from setu_netra.ingestion.pdf_loader import is_pdfium_available, load_pdf_pages
from setu_netra.ocr.mock_engine import MockOCREngine
from setu_netra.ocr.easyocr_engine import EasyOCREngine
from setu_netra.pipeline.document_pipeline import DocumentIntelligencePipeline
from setu_netra.semantic.embeddings.offline_engine import OfflineSemanticEngine
from setu_netra.store.sqlite_store import SQLiteDocumentStore
from setu_netra.structure.reconstructor import DocumentStructureReconstructor


def run_tests():
    temp_dir = Path(tempfile.mkdtemp(prefix="setu_real_world_"))
    db_path = temp_dir / "real_world.db"
    store = SQLiteDocumentStore(db_path)
    embed_engine = OfflineSemanticEngine(dimension=512)
    ocr_engine = EasyOCREngine()

    pipeline = DocumentIntelligencePipeline(
        store=store,
        ocr_engine=ocr_engine,
        embedding_engine=embed_engine,
    )

    results = {}
    print("=" * 80)
    print("  SETU-NETRA: REAL-WORLD FAILURE AND LIMITATION TESTS")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # CASE 1: Empty Page
    # --------------------------------------------------------------------------
    print("\n--- CASE 1: Empty Page (Blank White Image) ---")
    img_empty = Image.new("RGB", (800, 1000), color="white")
    empty_path = temp_dir / "case1_empty.png"
    img_empty.save(empty_path)

    try:
        doc = pipeline.ingest_document(empty_path)
        blocks = store.get_blocks(doc.doc_id)
        print(f"  Result: Ingested as {doc.doc_id}, total blocks: {len(blocks)}")
        results["case1_empty_page"] = {
            "status": "PASS",
            "block_count": len(blocks),
            "notes": "Handles cleanly without crashing; produces 0 blocks",
        }
    except Exception as e:
        print(f"  [FAIL] Crashed: {e}")
        results["case1_empty_page"] = {"status": "FAIL", "error": str(e)}

    # --------------------------------------------------------------------------
    # CASE 2: Corrupted PDF (Bad header / partial file)
    # --------------------------------------------------------------------------
    print("\n--- CASE 2: Corrupted PDF ---")
    corrupt_pdf_path = temp_dir / "case2_corrupt.pdf"
    corrupt_pdf_path.write_bytes(b"%PDF-1.4\n%Fake truncated header without xref")

    try:
        doc = pipeline.ingest_document(corrupt_pdf_path)
        print(f"  [UNEXPECTED] Ingestion succeeded: {doc.doc_id}")
        results["case2_corrupt_pdf"] = {"status": "UNEXPECTED_PASS", "notes": "PDF parser did not fail on truncated PDF"}
    except Exception as e:
        print(f"  Result: Safely rejected with error: {e}")
        results["case2_corrupt_pdf"] = {
            "status": "EXPECTED_FAILURE",
            "error_type": type(e).__name__,
            "error_message": str(e),
            "notes": "Defensively rejected before corrupted execution",
        }

    # --------------------------------------------------------------------------
    # CASE 3: Rotated Page (90 degrees clockwise)
    # --------------------------------------------------------------------------
    print("\n--- CASE 3: Rotated Page (90 deg Clockwise) ---")
    img_rot = Image.new("RGB", (800, 400), color="white")
    draw = ImageDraw.Draw(img_rot)
    draw.text((50, 150), "What is the time complexity of binary search?", fill="black")
    img_rot_90 = img_rot.rotate(90, expand=True)
    rot_path = temp_dir / "case3_rotated90.png"
    img_rot_90.save(rot_path)

    try:
        doc = pipeline.ingest_document(rot_path)
        blocks = store.get_blocks(doc.doc_id)
        detected_text = " ".join(b["text"] for b in blocks)
        print(f"  Result: Blocks: {len(blocks)}, Detected Text: '{detected_text}'")
        # Check if text was recognized or scrambled
        recognized = "binary" in detected_text.lower() or "search" in detected_text.lower()
        results["case3_rotated_page"] = {
            "status": "PASS" if recognized else "DEGRADED",
            "recognized": recognized,
            "detected_text": detected_text,
            "notes": "Without orientation normalization, sideways text causes OCR failure or word scrambling",
        }
    except Exception as e:
        print(f"  [FAIL] Crashed: {e}")
        results["case3_rotated_page"] = {"status": "FAIL", "error": str(e)}

    # --------------------------------------------------------------------------
    # CASE 4: Low-Resolution / Heavily Blurred Image
    # --------------------------------------------------------------------------
    print("\n--- CASE 4: Low-Resolution Image (150x80 px) ---")
    img_low = Image.new("RGB", (150, 80), color="white")
    draw = ImageDraw.Draw(img_low)
    draw.text((10, 20), "Low Res Text", fill="black")
    low_path = temp_dir / "case4_lowres.png"
    img_low.save(low_path)

    try:
        doc = pipeline.ingest_document(low_path)
        blocks = store.get_blocks(doc.doc_id)
        detected_text = " ".join(b["text"] for b in blocks)
        print(f"  Result: Blocks: {len(blocks)}, Detected Text: '{detected_text}'")
        results["case4_low_resolution"] = {
            "status": "DEGRADED" if not detected_text else "PASS",
            "block_count": len(blocks),
            "detected_text": detected_text,
            "notes": "Tiny fonts / low resolution result in near-zero character recognition",
        }
    except Exception as e:
        print(f"  [FAIL] Crashed: {e}")
        results["case4_low_resolution"] = {"status": "FAIL", "error": str(e)}

    # --------------------------------------------------------------------------
    # CASE 5: Multi-Column Document (2 Columns)
    # --------------------------------------------------------------------------
    print("\n--- CASE 5: Multi-Column Layout (2 Columns) ---")
    img_col = Image.new("RGB", (1000, 600), color="white")
    draw = ImageDraw.Draw(img_col)
    # Column 1
    draw.text((50, 50), "Column 1 Heading", fill="black")
    draw.text((50, 100), "This is paragraph in column one.", fill="black")
    draw.text((50, 150), "It continues on column one line two.", fill="black")
    # Column 2
    draw.text((550, 50), "Column 2 Heading", fill="black")
    draw.text((550, 100), "This is paragraph in column two.", fill="black")
    draw.text((550, 150), "It continues on column two line two.", fill="black")
    col_path = temp_dir / "case5_multicol.png"
    img_col.save(col_path)

    try:
        doc = pipeline.ingest_document(col_path)
        blocks = store.get_blocks(doc.doc_id)
        print(f"  Result: Blocks: {len(blocks)}")
        for idx, b in enumerate(blocks, 1):
            print(f"    Block {idx} ({b['block_type']}): '{b['text']}'")
        
        # Check if line grouper merged across columns (e.g. 'Column 1 Heading Column 2 Heading' in one line)
        merged_columns = any("column 1" in b["text"].lower() and "column 2" in b["text"].lower() for b in blocks)
        print(f"  Merged across column gutter: {merged_columns}")
        results["case5_multi_column"] = {
            "status": "LIMITATION_IDENTIFIED" if merged_columns else "PASS",
            "merged_columns": merged_columns,
            "block_count": len(blocks),
            "notes": "Pure horizontal projection / line grouping merges lines horizontally across column gutters if vertical coordinates overlap",
        }
    except Exception as e:
        print(f"  [FAIL] Crashed: {e}")
        results["case5_multi_column"] = {"status": "FAIL", "error": str(e)}

    # --------------------------------------------------------------------------
    # CASE 6: Tabular Data (Grid / Table)
    # --------------------------------------------------------------------------
    print("\n--- CASE 6: Table Layout ---")
    img_tbl = Image.new("RGB", (900, 400), color="white")
    draw = ImageDraw.Draw(img_tbl)
    # Header
    draw.text((50, 50), "ID", fill="black")
    draw.text((250, 50), "Algorithm", fill="black")
    draw.text((550, 50), "Complexity", fill="black")
    # Row 1
    draw.text((50, 100), "1", fill="black")
    draw.text((250, 100), "Merge Sort", fill="black")
    draw.text((550, 100), "O(N log N)", fill="black")
    # Row 2
    draw.text((50, 150), "2", fill="black")
    draw.text((250, 150), "Quick Sort", fill="black")
    draw.text((550, 150), "O(N^2)", fill="black")
    tbl_path = temp_dir / "case6_table.png"
    img_tbl.save(tbl_path)

    try:
        doc = pipeline.ingest_document(tbl_path)
        blocks = store.get_blocks(doc.doc_id)
        print(f"  Result: Blocks: {len(blocks)}")
        for idx, b in enumerate(blocks, 1):
            print(f"    Block {idx} ({b['block_type']}): '{b['text']}'")
        results["case6_table"] = {
            "status": "LIMITATION_IDENTIFIED",
            "block_count": len(blocks),
            "notes": "Tables are linearized into standard paragraph blocks rather than structured grid/cells",
        }
    except Exception as e:
        print(f"  [FAIL] Crashed: {e}")
        results["case6_table"] = {"status": "FAIL", "error": str(e)}

    # --------------------------------------------------------------------------
    # CASE 7: Multi-Language Document (English + Hindi / Devanagari)
    # --------------------------------------------------------------------------
    print("\n--- CASE 7: Multi-Language Document (Hindi / Devanagari) ---")
    img_lang = Image.new("RGB", (800, 300), color="white")
    draw = ImageDraw.Draw(img_lang)
    draw.text((50, 50), "English Header: Setu-Netra", fill="black")
    draw.text((50, 120), "सेतु-नेत्र बहुभाषी परीक्षण", fill="black")
    lang_path = temp_dir / "case7_multilang.png"
    img_lang.save(lang_path)

    try:
        doc = pipeline.ingest_document(lang_path)
        blocks = store.get_blocks(doc.doc_id)
        detected_text = " ".join(b["text"] for b in blocks)
        print(f"  Result: Blocks: {len(blocks)}, Detected: '{detected_text}'")
        hindi_detected = "सेतु" in detected_text or "नेत्र" in detected_text
        results["case7_multilingual"] = {
            "status": "PASS" if hindi_detected else "LIMITATION_IDENTIFIED",
            "hindi_detected": hindi_detected,
            "detected_text": detected_text,
            "notes": "EasyOCR initialized with ['en'] only. Non-Latin scripts (Devanagari) are dropped or rendered as gibberish without explicit language config",
        }
    except Exception as e:
        print(f"  [FAIL] Crashed: {e}")
        results["case7_multilingual"] = {"status": "FAIL", "error": str(e)}

    # --------------------------------------------------------------------------
    # CASE 8: Digitally Generated Multi-Page PDF
    # --------------------------------------------------------------------------
    print("\n--- CASE 8: Clean Digitally Generated 3-Page PDF ---")
    pdf_clean = temp_dir / "case8_digital.pdf"
    imgs = []
    for p in range(1, 4):
        im = Image.new("RGB", (600, 400), color="white")
        dr = ImageDraw.Draw(im)
        dr.text((40, 40), f"Digital PDF Page {p}: Section {p}.1", fill="black")
        dr.text((40, 100), f"Detailed content for page {p} in digital format.", fill="black")
        imgs.append(im)
    imgs[0].save(pdf_clean, save_all=True, append_images=imgs[1:])

    try:
        t0 = time.perf_counter()
        doc = pipeline.ingest_document(pdf_clean)
        elapsed = time.perf_counter() - t0
        pages = store.get_pages(doc.doc_id)
        blocks = store.get_blocks(doc.doc_id)
        print(f"  Result: Ingested {len(pages)} pages, {len(blocks)} blocks in {elapsed:.2f}s")
        results["case8_digital_pdf"] = {
            "status": "PASS",
            "pages": len(pages),
            "blocks": len(blocks),
            "latency_s": round(elapsed, 2),
        }
    except Exception as e:
        print(f"  [FAIL] Crashed: {e}")
        results["case8_digital_pdf"] = {"status": "FAIL", "error": str(e)}

    # --------------------------------------------------------------------------
    # CASE 9: Scanned PDF with Noise and Grain
    # --------------------------------------------------------------------------
    print("\n--- CASE 9: Scanned PDF with Artifacts and Contrast Variation ---")
    pdf_scan = temp_dir / "case9_scanned.pdf"
    img_scan = Image.new("RGB", (800, 600), color=(235, 230, 220)) # yellowish paper
    dr = ImageDraw.Draw(img_scan)
    dr.text((60, 60), "SCANNED EXAM DOCUMENT", fill=(50, 50, 50))
    dr.text((60, 140), "Q.1 What is the primary memory component?", fill=(60, 60, 60))
    dr.text((60, 200), "[A] Cache Memory", fill=(60, 60, 60))
    dr.text((60, 250), "[B] Hard Disk Drive", fill=(60, 60, 60))
    
    # Add noise / gaussian blur to simulate scan
    img_noisy = img_scan.filter(ImageFilter.GaussianBlur(radius=0.7))
    img_noisy.save(pdf_scan)

    try:
        t0 = time.perf_counter()
        doc = pipeline.ingest_document(pdf_scan)
        elapsed = time.perf_counter() - t0
        blocks = store.get_blocks(doc.doc_id)
        detected_text = " ".join(b["text"] for b in blocks)
        print(f"  Result: Ingested in {elapsed:.2f}s, Blocks: {len(blocks)}")
        print(f"  Detected: '{detected_text}'")
        has_question = any(b["block_type"] == "QUESTION" for b in blocks)
        has_options = any(b["block_type"] == "OPTION" for b in blocks)
        results["case9_scanned_pdf"] = {
            "status": "PASS" if (has_question or has_options) else "DEGRADED",
            "blocks": len(blocks),
            "has_question": has_question,
            "has_options": has_options,
            "latency_s": round(elapsed, 2),
            "detected_text": detected_text,
        }
    except Exception as e:
        print(f"  [FAIL] Crashed: {e}")
        results["case9_scanned_pdf"] = {"status": "FAIL", "error": str(e)}

    # --------------------------------------------------------------------------
    # CASE 10: Very Large Document (10-Page PDF)
    # --------------------------------------------------------------------------
    print("\n--- CASE 10: Multi-Page Document Scaling (10-Page PDF) ---")
    pdf_large = temp_dir / "case10_large.pdf"
    large_imgs = []
    for p in range(1, 11):
        im = Image.new("RGB", (500, 350), color="white")
        dr = ImageDraw.Draw(im)
        dr.text((30, 30), f"Doc 10 Page {p}", fill="black")
        dr.text((30, 80), f"Question on Page {p}: Explain topic {p}", fill="black")
        large_imgs.append(im)
    large_imgs[0].save(pdf_large, save_all=True, append_images=large_imgs[1:])

    try:
        t0 = time.perf_counter()
        doc = pipeline.ingest_document(pdf_large)
        elapsed = time.perf_counter() - t0
        pages = store.get_pages(doc.doc_id)
        blocks = store.get_blocks(doc.doc_id)
        print(f"  Result: Ingested {len(pages)} pages, {len(blocks)} blocks in {elapsed:.2f}s ({elapsed/10:.2f}s/page)")
        results["case10_large_doc"] = {
            "status": "PASS",
            "page_count": len(pages),
            "total_blocks": len(blocks),
            "total_time_s": round(elapsed, 2),
            "time_per_page_s": round(elapsed / len(pages), 2),
            "notes": "CPU-bound sequential OCR scales linearly with page count (~2-4s per page on CPU)",
        }
    except Exception as e:
        print(f"  [FAIL] Crashed: {e}")
        results["case10_large_doc"] = {"status": "FAIL", "error": str(e)}

    # Write empirical results to JSON
    report_file = Path("scratch/real_world_test_results.json")
    report_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nEmpirical results saved to: {report_file}")

    store.close()
    shutil.rmtree(temp_dir, ignore_errors=True)
    return results


if __name__ == "__main__":
    run_tests()
