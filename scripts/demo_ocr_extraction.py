"""
demo_ocr_extraction.py: Demonstrates image OCR, CRAFT bounding boxes, and reading-order reconstruction.
"""
import sys
import os
from pathlib import Path
from PIL import Image

sys.path.insert(0, "src")

from setu_netra.ocr.easyocr_engine import EasyOCREngine
from setu_netra.structure.reconstructor import DocumentStructureReconstructor

def run_demo():
    print("=" * 68)
    print("  SETU-NETRA: IMAGE OCR EXTRACTION & SPATIAL LAYOUT PIPELINE")
    print("=" * 68)

    img_path = Path("sample_data/sample_question.png")
    if not img_path.exists():
        img_path = Path("output/uploads/462cfeeb/quest6.png")

    with Image.open(img_path) as img:
        w, h = img.size
        mode = img.mode
        pil_copy = img.copy()

    print(f"\n[1] IMAGE INGESTION & GEOMETRY:")
    print(f"    • File Path:   {img_path}")
    print(f"    • Dimensions:  {w} x {h} px")
    print(f"    • Color Mode:  {mode}")

    print(f"\n[2] RUNNING CRAFT DETECTOR & RESNET-BILSTM-CTC RECOGNIZER...")
    ocr = EasyOCREngine()
    result = ocr.recognize(pil_copy)

    avg_conf = (sum(b.confidence for b in result.boxes) / len(result.boxes)) if result.boxes else 0.0
    print(f"    • OCR Engine:         {result.engine_name} v{result.engine_version}")
    print(f"    • Processing Time:    {result.processing_time_ms:.1f} ms")
    print(f"    • Overall Confidence: {avg_conf:.2%}")
    print(f"    • Detections Found:   {len(result.boxes)} text regions")
    print(f"\n    Sample Spatial Detections (Bounding Box & CTC Confidence):")
    for i, b in enumerate(result.boxes[:5]):
        coords = f"[{int(b.xmin)},{int(b.ymin)} to {int(b.xmax)},{int(b.ymax)}]"
        print(f"       [{i+1}] {coords:<20} | Conf: {b.confidence:>5.1%} | \"{b.text}\"")

    print(f"\n[3] 2D SPATIAL READING-ORDER & BLOCK RECONSTRUCTION:")
    reconstructor = DocumentStructureReconstructor()
    struct = reconstructor.reconstruct(result.boxes)

    print(f"    • Logical Blocks Identified: {len(struct.blocks)}")
    for i, blk in enumerate(struct.blocks[:4]):
        btype = getattr(blk.block_type, 'value', str(blk.block_type))
        print(f"       [{btype}] \"{blk.text}\" (block_id={blk.block_id}, conf={blk.mean_confidence:.1%})")

    print(f"\n[4] RECONSTRUCTED FULL TRANSCRIPT:")
    print("    " + "-" * 55)
    for line in struct.raw_transcript.splitlines()[:6]:
        if line.strip():
            print(f"    {line}")
    print("    " + "-" * 55)

    print("\n" + "=" * 68)
    print("  EXTRACTION COMPLETE: Spatial structure ready for Question Answering.")
    print("=" * 68)

if __name__ == "__main__":
    run_demo()
