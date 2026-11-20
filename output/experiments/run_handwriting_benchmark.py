"""
run_handwriting_benchmark.py: Systematic evaluation of preprocessing and OCR parameters
on handwritten multiple-choice question image (sample_question2.jpeg).
"""

import json
import time
import sys
from pathlib import Path
import numpy as np
from PIL import Image

# Ensure src is on sys.path
SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.preprocessing.operations import adjust_contrast, to_grayscale
import easyocr


def edit_distance(ref, hyp):
    """Compute standard Levenshtein distance."""
    d = [[0] * (len(hyp) + 1) for _ in range(len(ref) + 1)]
    for i in range(len(ref) + 1):
        d[i][0] = i
    for j in range(len(hyp) + 1):
        d[0][j] = j
    for i in range(1, len(ref) + 1):
        for j in range(1, len(hyp) + 1):
            if ref[i - 1] == hyp[j - 1]:
                d[i][j] = d[i - 1][j - 1]
            else:
                d[i][j] = 1 + min(d[i - 1][j], d[i][j - 1], d[i - 1][j - 1])
    return d[len(ref)][len(hyp)]


def compute_cer(ref_str, hyp_str):
    """Character Error Rate (CER)."""
    ref_norm = " ".join(ref_str.strip().split())
    hyp_norm = " ".join(hyp_str.strip().split())
    dist = edit_distance(list(ref_norm), list(hyp_norm))
    return dist / max(len(ref_norm), 1)


def compute_wer(ref_str, hyp_str):
    """Word Error Rate (WER)."""
    ref_words = ref_str.strip().split()
    hyp_words = hyp_str.strip().split()
    dist = edit_distance(ref_words, hyp_words)
    return dist / max(len(ref_words), 1)


# Ground truth reference text
GROUND_TRUTH_TRANSCRIPT = (
    "Who is the Prime Minister of India? "
    "a) Rahul Gandhi "
    "b) Narendra Modi "
    "c) Droupadi Murmu "
    "d) Shahrukh Patel"
)

TARGET_ENTITIES = [
    "Rahul Gandhi",
    "Narendra Modi",
    "Droupadi Murmu",
    "Shahrukh Patel",
]


def run_benchmark():
    input_path = Path("sample_data/sample_question2.jpeg")
    raw_img = Image.open(input_path)

    exp_dir = Path("output/experiments")
    exp_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("SETU-NETRA: HANDWRITING BENCHMARK & EXPERIMENTAL INVESTIGATION")
    print(f"Target Image: {input_path} (Size: {raw_img.size}, Mode: {raw_img.mode})")
    print("=" * 80)

    # 1. Initialize Reader
    reader = easyocr.Reader(["en"], gpu=False)

    # 2. Define Preprocessing Variants
    # Variant P1: Raw RGB
    p1_img = raw_img.copy()
    p1_img.save(exp_dir / "p1_raw_rgb.png")

    # Variant P2: Grayscale (mode 'L') without contrast enhancement
    p2_img = to_grayscale(raw_img)
    p2_img.save(exp_dir / "p2_grayscale_no_contrast.png")

    # Variant P3: Grayscale with mild contrast (1.15)
    p3_img = adjust_contrast(p2_img, 1.15)
    p3_img.save(exp_dir / "p3_grayscale_contrast_1_15.png")

    # Variant P4: Grayscale with baseline contrast (1.30)
    p4_img = adjust_contrast(p2_img, 1.30)
    p4_img.save(exp_dir / "p4_grayscale_contrast_1_30.png")

    # Variant P5: Grayscale with high contrast (1.50)
    p5_img = adjust_contrast(p2_img, 1.50)
    p5_img.save(exp_dir / "p5_grayscale_contrast_1_50.png")

    experiments = [
        # (ID, Label, Image, OCR Params)
        (
            "EXP_0_BASELINE",
            "Existing Baseline (Grayscale + Contrast 1.30, Default OCR)",
            p4_img,
            {},
        ),
        (
            "EXP_1_RAW_RGB",
            "Raw RGB (No Grayscale, Contrast 1.0, Default OCR)",
            p1_img,
            {},
        ),
        (
            "EXP_2_GRAY_NO_CONTRAST",
            "Grayscale Only (Contrast 1.0, Default OCR)",
            p2_img,
            {},
        ),
        (
            "EXP_3_MILD_CONTRAST",
            "Grayscale + Mild Contrast (1.15, Default OCR)",
            p3_img,
            {},
        ),
        (
            "EXP_4_HIGH_CONTRAST",
            "Grayscale + High Contrast (1.50, Default OCR)",
            p5_img,
            {},
        ),
        (
            "EXP_5_OCR_MARGIN_0_20",
            "Grayscale Only + add_margin=0.20",
            p2_img,
            {"add_margin": 0.20},
        ),
        (
            "EXP_6_OCR_MAG_RATIO_1_5",
            "Grayscale Only + mag_ratio=1.5",
            p2_img,
            {"mag_ratio": 1.5},
        ),
        (
            "EXP_7_OCR_LOW_LINK_THS",
            "Grayscale Only + link_threshold=0.25",
            p2_img,
            {"link_threshold": 0.25},
        ),
        (
            "EXP_8_OCR_LOW_TEXT_THS",
            "Grayscale Only + text_threshold=0.50, low_text=0.30",
            p2_img,
            {"text_threshold": 0.50, "low_text": 0.30},
        ),
        (
            "EXP_9_OCR_PARAGRAPH",
            "Grayscale Only + paragraph=True",
            p2_img,
            {"paragraph": True},
        ),
        (
            "EXP_10_OPTIMIZED_COMBINED",
            "Optimized: Gray(1.0) + mag_ratio=1.5 + add_margin=0.20 + link_ths=0.25",
            p2_img,
            {"mag_ratio": 1.5, "add_margin": 0.20, "link_threshold": 0.25},
        ),
    ]

    results_table = []

    for exp_id, label, img_pil, ocr_kwargs in experiments:
        print(f"\nRunning {exp_id}: {label}...")
        img_np = np.array(img_pil.convert("RGB"))

        t0 = time.perf_counter()
        raw_res = reader.readtext(img_np, **ocr_kwargs)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        detected_tokens = []
        confidences = []
        for item in raw_res:
            if len(item) == 3:
                poly, text, conf = item
                detected_tokens.append(str(text).strip())
                confidences.append(float(conf))
            elif len(item) == 2:
                # If paragraph=True, item is (poly, text)
                poly, text = item
                detected_tokens.append(str(text).strip())
                confidences.append(1.0)

        hyp_transcript = " ".join(detected_tokens)
        cer = compute_cer(GROUND_TRUTH_TRANSCRIPT, hyp_transcript)
        wer = compute_wer(GROUND_TRUTH_TRANSCRIPT, hyp_transcript)
        mean_conf = float(np.mean(confidences)) if confidences else 0.0

        # Check entity recognition
        entity_matches = {}
        for entity in TARGET_ENTITIES:
            # Check for substring or closest match
            words_in_hyp = hyp_transcript.lower()
            entity_words = entity.lower().split()
            present = all(w in words_in_hyp for w in entity_words)
            entity_matches[entity] = present

        record = {
            "exp_id": exp_id,
            "label": label,
            "ocr_kwargs": ocr_kwargs,
            "latency_ms": round(latency_ms, 1),
            "boxes_count": len(detected_tokens),
            "mean_conf": round(mean_conf, 4),
            "cer": round(cer, 4),
            "wer": round(wer, 4),
            "entities": entity_matches,
            "transcript": hyp_transcript,
        }
        results_table.append(record)

        print(f"  Latency: {latency_ms:.1f}ms | Boxes: {len(detected_tokens)} | CER: {cer*100:.1f}% | WER: {wer*100:.1f}%")
        print(f"  Recognized: \"{hyp_transcript}\"")

    # Save complete benchmark record
    benchmark_json = exp_dir / "handwriting_benchmark_results.json"
    benchmark_json.write_text(json.dumps(results_table, indent=2), encoding="utf-8")
    print("\n" + "=" * 80)
    print(f"Benchmark completed. Results written to: {benchmark_json.resolve()}")
    print("=" * 80)


if __name__ == "__main__":
    run_benchmark()
