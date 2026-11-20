"""
scan.py: Instant, clean photo understanding for SETU-NETRA.

Takes an image/photo as input, reads the text via OCR, and directly tells:
1. What text was read from the photo.
2. What academic domain/topic it belongs to.
3. What it is (question type, intent, key concepts, ambiguities, and explanation).

Usage:
    python scan.py sample_data/sample_question.png
    python scan.py sample_data/sample_question2.jpeg
    python scan.py <path_to_any_image>
"""

import argparse
import sys
import time
from pathlib import Path

# Force UTF-8 encoding on Windows to prevent encoding errors
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add src to sys.path
SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.core.contracts import OCRConfig, PreprocessConfig
from setu_netra.ingestion.loader import load_image
from setu_netra.ocr.factory import get_ocr_engine
from setu_netra.preprocessing.pipeline import ImagePreprocessor
from setu_netra.semantic.embeddings.factory import get_embedding_engine
from setu_netra.semantic.engine import SemanticUnderstandingEngine
from setu_netra.structure.reconstructor import DocumentStructureReconstructor


def scan_photo(image_path: Path, use_mock: bool = False, backend: str = "auto") -> int:
    if not image_path.is_file():
        print(f"\n[ERROR] Photo not found: {image_path}")
        return 1

    print("\n" + "=" * 70)
    print("  SETU-NETRA: Instant Photo Understanding")
    print("=" * 70)
    print(f"  Photo Input:  {image_path.name}")
    print(f"  Location:     {image_path.resolve()}")
    print("  Status:       Reading photo and analyzing semantics...")

    # 1. Load and Preprocess Image
    t0 = time.perf_counter()
    image, metadata = load_image(image_path, auto_orient=True)
    prep_config = PreprocessConfig(convert_grayscale=True, contrast_factor=1.2)
    preprocessor = ImagePreprocessor(config=prep_config)
    output_dir = Path("output")
    prep_result = preprocessor.process(image, metadata, output_dir=output_dir)

    from PIL import Image as PILImage
    ocr_input = PILImage.open(prep_result.output_path) if prep_result.output_path else image

    # 2. OCR Subsystem (Reads the text)
    engine_name = "mock" if use_mock else "auto"
    ocr_config = OCRConfig(engine_name=engine_name, confidence_threshold=0.20)
    ocr_engine = get_ocr_engine(engine_name=engine_name, config=ocr_config)
    ocr_result = ocr_engine.recognize(ocr_input, config=ocr_config)

    # 3. Document Structure Reconstruction (Lines, Blocks, Questions)
    reconstructor = DocumentStructureReconstructor()
    struct_result = reconstructor.reconstruct(ocr_result)

    # 4. Semantic Understanding & Domain Classification
    embed_engine = get_embedding_engine(backend)
    sem_engine = SemanticUnderstandingEngine(embedding_engine=embed_engine)
    sem_result = sem_engine.analyze_document_structure(struct_result, document_id=image_path.stem)
    total_time = (time.perf_counter() - t0)

    # Find the main item (either the primary question or the primary block)
    primary_item = None
    if sem_result.items:
        # Prefer question items
        for it in sem_result.items:
            if "question" in it.source_id:
                primary_item = it
                break
        if not primary_item:
            primary_item = sem_result.items[0]

    # Clean transcript of detected text
    full_text = "\n".join(b.text.strip() for b in struct_result.blocks if b.text.strip())
    if not full_text:
        full_text = ocr_result.raw_text.strip() or "(No readable text detected)"

    # Format output clearly
    print("\n" + "-" * 70)
    print("  1. WHAT WAS READ FROM THE PHOTO (Extracted Text)")
    print("-" * 70)
    for line in full_text.split("\n"):
        print(f"     {line}")

    print("\n" + "-" * 70)
    print("  2. WHAT TOPIC & DOMAIN IT RESIDES TO")
    print("-" * 70)
    if primary_item and primary_item.primary_domain and primary_item.status != "UNKNOWN_DOMAIN":
        dom_score = primary_item.domains[0].similarity_score if primary_item.domains else 0.0
        print(f"  * Primary Domain:     {primary_item.primary_domain}")
        print(f"  * Confidence Match:   {dom_score * 100:.1f}%")
        if len(primary_item.domains) > 1:
            sec_domains = ", ".join(f"{d.domain_name}" for d in primary_item.domains[1:])
            print(f"  * Related / Overlap:  {sec_domains}")
        if primary_item.primary_topic:
            print(f"  * Subject Topic:      {primary_item.primary_topic}")
    else:
        print("  * Domain:             UNKNOWN / OUT-OF-DOMAIN")
        print("  * Status:             Abstained (confidence below threshold tau=0.28)")
        if primary_item and primary_item.domains:
            top_guess = primary_item.domains[0]
            print(f"  * Nearest Candidate:  {top_guess.domain_name} ({top_guess.similarity_score * 100:.1f}% - insufficient evidence)")

    print("\n" + "-" * 70)
    print("  3. WHAT IT IS (Understanding & Analysis)")
    print("-" * 70)

    # Document type
    doc_type = struct_result.metadata.get("document_type_hint", "GENERAL_TEXT")
    type_descriptions = {
        "MULTIPLE_CHOICE_ASSESSMENT": "Multiple-Choice Question (MCQ) with options",
        "QUESTION_ANSWER": "Descriptive / Academic Question",
        "REFERENCE_NOTE": "Educational Reference Note or Heading",
        "GENERAL_DOCUMENT": "General Document / Paragraph",
    }
    print(f"  * Document Type:      {type_descriptions.get(doc_type, doc_type)}")

    # Intent
    if primary_item and primary_item.question_intents:
        intents_str = ", ".join(primary_item.question_intents)
        print(f"  * Question Intent:    {intents_str}")

    # Technical depth
    if primary_item and primary_item.technical_level:
        print(f"  * Technical Level:    {primary_item.technical_level}")

    # Extracted concepts
    if primary_item and primary_item.concepts:
        concepts_str = ", ".join(c.normalized_form for c in primary_item.concepts)
        print(f"  * Key Concepts:       {concepts_str}")

    # Math entities
    if primary_item and primary_item.entities:
        entities_str = ", ".join(f"{e.text} ({e.entity_type})" for e in primary_item.entities)
        print(f"  * Math / Entities:    {entities_str}")

    # Ambiguity resolution
    if primary_item and primary_item.ambiguities:
        for amb in primary_item.ambiguities:
            print(f"  * Ambiguity Handled:  Word '{amb.term}' resolved as -> {amb.resolved_sense}")

    # Curated Knowledge citation
    if primary_item and primary_item.retrieved_knowledge:
        citation = primary_item.retrieved_knowledge[0]
        print(f"  * Reference Citation: \"{citation.title}\"")

    print("\n" + "=" * 70)
    print(f"  Analysis complete in {total_time:.2f} seconds.")
    print("=" * 70 + "\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SETU-NETRA: Scan a photo, read its text, and tell its topic and meaning."
    )
    parser.add_argument(
        "image",
        type=str,
        help="Path to the image/photo file (e.g. sample_data/sample_question.png).",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Use fast mock OCR engine for instant demonstration without neural OCR wait.",
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="auto",
        choices=["auto", "neural", "offline"],
        help="Semantic backend: 'auto' (default), 'neural', or 'offline'.",
    )
    args = parser.parse_args()

    return scan_photo(
        image_path=Path(args.image),
        use_mock=args.fast,
        backend=args.backend,
    )


if __name__ == "__main__":
    sys.exit(main())
