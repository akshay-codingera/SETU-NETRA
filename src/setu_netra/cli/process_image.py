"""
process_image.py: Command-line interface for SETU-NETRA Pipeline (Milestones 1 & 2).

Why this file exists:
An engineering project must be executable and verifiable from the command line.
This script acts as the primary integration entrypoint, connecting validation,
loading, preprocessing, and OCR while providing transparent, formatted console diagnostics.
"""

import argparse
import json
import sys
from pathlib import Path

# Force UTF-8 encoding on Windows to prevent charmap encoding errors
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add src directory to sys.path if invoked directly
sys_path_root = Path(__file__).resolve().parent.parent.parent
if str(sys_path_root) not in sys.path:
    sys.path.insert(0, str(sys_path_root))

from setu_netra.core.contracts import (
    PreprocessConfig,
    OCRConfig,
    OCRBox,
    OCRResult,
    DocumentStructureResult,
    DocumentBlock,
    QuestionGroup,
    QuestionOption,
    SemanticAnalysisResult,
)
from setu_netra.ingestion.validator import validate_image_file, validate_document_file
from setu_netra.ingestion.loader import load_image
from setu_netra.preprocessing.pipeline import ImagePreprocessor
from setu_netra.ocr.factory import get_ocr_engine
from setu_netra.ocr.base import OCREngineError, OCREngineNotFoundError
from setu_netra.structure.reconstructor import DocumentStructureReconstructor
from setu_netra.semantic.engine import SemanticUnderstandingEngine
from setu_netra.semantic.embeddings.factory import get_embedding_engine
from setu_netra.store.sqlite_store import SQLiteDocumentStore
from setu_netra.retrieval.document_retriever import DocumentRetriever
from setu_netra.context.synthesizer import EvidenceContextSynthesizer
from setu_netra.pipeline.document_pipeline import DocumentIntelligencePipeline


def format_bytes(byte_count: int) -> str:
    """Format bytes into readable KB/MB string."""
    if byte_count < 1024:
        return f"{byte_count} B"
    elif byte_count < 1024 * 1024:
        return f"{byte_count / 1024:.2f} KB"
    else:
        return f"{byte_count / (1024 * 1024):.2f} MB"


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="setu-netra-process",
        description="SETU-NETRA: Image Ingestion, Validation, Preprocessing & OCR Pipeline",
    )
    # Stage 1 & 2 Ingestion & Preprocessing Arguments
    parser.add_argument(
        "-i", "--image",
        type=Path,
        default=None,
        help="Path to the input image file.",
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        default=None,
        help="Path to an existing OCR evidence JSON file to reconstruct structure directly without re-running OCR.",
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory where preprocessed images and OCR evidence will be saved (default: ./output).",
    )
    parser.add_argument(
        "--no-grayscale",
        action="store_true",
        help="Disable automatic conversion to grayscale.",
    )
    parser.add_argument(
        "--max-dim",
        type=int,
        default=1600,
        help="Maximum width or height in pixels. Larger images will be downscaled preserving aspect ratio.",
    )
    parser.add_argument(
        "--contrast",
        type=float,
        default=1.3,
        help="Contrast enhancement factor (1.0 = unchanged, >1.0 = higher contrast, default: 1.3).",
    )
    parser.add_argument(
        "--resample",
        type=str,
        default="LANCZOS",
        choices=["LANCZOS", "BICUBIC", "BILINEAR", "NEAREST"],
        help="Interpolation filter for resizing (default: LANCZOS).",
    )

    # Stage 3 OCR Arguments
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="Execute the OCR subsystem on the preprocessed image.",
    )
    parser.add_argument(
        "--ocr-engine",
        type=str,
        default="auto",
        choices=["auto", "easyocr", "mock"],
        help="OCR engine to use (default: auto).",
    )
    parser.add_argument(
        "--ocr-conf",
        type=float,
        default=0.20,
        help="Minimum confidence threshold for OCR detections (default: 0.20).",
    )
    parser.add_argument(
        "--ocr-lang",
        type=str,
        default="en",
        help="Comma-separated language codes for OCR (default: 'en').",
    )
    parser.add_argument(
        "--handwriting",
        action="store_true",
        help="Apply optimized detection and margin preset for handwritten text.",
    )
    parser.add_argument(
        "--add-margin",
        type=float,
        default=None,
        help="Margin added around detected bounding boxes (default: 0.10, handwriting: 0.20).",
    )
    parser.add_argument(
        "--mag-ratio",
        type=float,
        default=None,
        help="Image magnification factor during detection (default: 1.0, handwriting: 1.5).",
    )
    parser.add_argument(
        "--link-threshold",
        type=float,
        default=None,
        help="CRAFT affinity link threshold (default: 0.40, handwriting: 0.25).",
    )
    parser.add_argument(
        "--text-threshold",
        type=float,
        default=None,
        help="CRAFT text confidence threshold (default: 0.70, handwriting: 0.50).",
    )
    parser.add_argument(
        "--paragraph",
        action="store_true",
        help="Group nearby bounding boxes into paragraph lines.",
    )

    # Stage 5 Document Structure Reconstruction Arguments (Module 3)
    parser.add_argument(
        "--no-structure",
        action="store_true",
        help="Disable document structure reconstruction after OCR.",
    )

    # Stage 6 Semantic Understanding Arguments (Module 4)
    parser.add_argument(
        "--semantic",
        action="store_true",
        help="Execute Module 4: Semantic Understanding & Domain Classification.",
    )
    parser.add_argument(
        "--semantic-engine",
        "--semantic-backend",
        dest="semantic_engine",
        type=str,
        default="auto",
        choices=["auto", "offline", "neural"],
        help="Embedding backend for semantic classification: 'offline', 'neural', or 'auto' (default: auto).",
    )
    parser.add_argument(
        "--semantic-evidence",
        type=Path,
        default=None,
        help="Path to an existing structure evidence JSON to run semantic analysis directly.",
    )

    # Stage 7 Document Store & Grounded Context Retrieval Arguments (Module 5)
    parser.add_argument(
        "--store",
        action="store_true",
        help="Persist ingested document, pages, blocks, and embeddings into the SQLite document store.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("output/setu_netra.db"),
        help="Path to SQLite document database (default: output/setu_netra.db).",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Execute evidence-grounded semantic and lexical retrieval against stored documents.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Maximum number of context evidence passages to retrieve (default: 3).",
    )
    parser.add_argument(
        "--budget",
        type=int,
        default=1500,
        help="Maximum token budget for synthesized LLM context prompt (default: 1500).",
    )
    return parser


def print_and_save_structure_result(
    struct_res: DocumentStructureResult,
    source_name: str,
    output_dir: Optional[Path],
    stage_num: int,
    total_stages: int,
) -> None:
    """Format and print structured document reconstruction diagnostics and persist JSON evidence."""
    print(f"\n[Stage {stage_num}/{total_stages}] Executing Document Structure Reconstruction (Module 3)...")
    print(f"  - Document Type Hint:    {struct_res.metadata.get('document_type_hint', 'UNKNOWN')}")
    print(f"  - Reconstruction Latency:{struct_res.processing_time_ms:.2f} ms (Pure geometry, CPU-only)")
    print(f"  - Total Lines Formed:    {struct_res.metadata.get('total_lines', 0)}")
    print(f"  - Total Blocks Formed:   {struct_res.metadata.get('total_blocks', 0)}")
    print(f"  - Total Questions Found: {struct_res.metadata.get('total_questions', 0)}")
    counts = struct_res.metadata.get("block_type_counts", {})
    if counts:
        counts_str = ", ".join(f"{k}: {v}" for k, v in counts.items())
        print(f"  - Block Breakdown:       {counts_str}")

    if struct_res.warnings:
        print("\n  Reconstruction Warnings:")
        for w in struct_res.warnings:
            print(f"    [!] {w}")

    if struct_res.blocks:
        print("\n  Reconstructed Document Blocks (Reading Order):")
        print(f"  {'#':<3} | {'Type':<12} | {'Conf':<6} | {'Lines':<5} | {'Box IDs':<12} | {'Text Content'}")
        print(f"  {'-'*3}-+-{'-'*12}-+-{'-'*6}-+-{'-'*5}-+-{'-'*12}-+-{'-'*30}")
        for b in struct_res.blocks:
            src_str = str(list(b.source_detection_indices))
            if len(src_str) > 12:
                src_str = src_str[:9] + "..."
            text_preview = b.text.replace("\n", " ")
            if len(text_preview) > 55:
                text_preview = text_preview[:52] + "..."
            print(
                f"  {b.block_id:<3} | {b.block_type:<12} | {b.mean_confidence*100:>5.1f}% | "
                f"{len(b.lines):<5} | {src_str:<12} | {text_preview}"
            )

    if struct_res.questions:
        print("\n  Identified Questions & Linked Answer Options:")
        for q_idx, q in enumerate(struct_res.questions, start=1):
            q_num_str = f"Q{q.question_number}" if q.question_number else f"Question #{q_idx}"
            print(f"  * [{q_num_str}] (Block {q.question_block_id}): {q.question_text}")
            if q.options:
                for opt in q.options:
                    opt_prev = opt.option_text.replace("\n", " ")
                    if len(opt_prev) > 40:
                        opt_prev = opt_prev[:37] + "..."
                    print(f"      [{opt.option_label}] {opt_prev} (Block {opt.block_id}, conf: {opt.confidence*100:.1f}%)")
            else:
                print("      (No multiple-choice options associated)")
            if q.warnings:
                for qw in q.warnings:
                    print(f"      [Warning] {qw}")

    # Persist structured document evidence
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        struct_path = output_dir / f"structure_evidence_{source_name}.json"
        struct_data = {
            "source": source_name,
            "status": struct_res.status,
            "document_type_hint": struct_res.metadata.get("document_type_hint"),
            "reconstruction_latency_ms": struct_res.processing_time_ms,
            "metadata": struct_res.metadata,
            "reading_order_box_indices": struct_res.reading_order_box_indices,
            "blocks": [
                {
                    "block_id": b.block_id,
                    "block_type": b.block_type,
                    "text": b.text,
                    "bbox_xyxy": list(b.bbox),
                    "mean_confidence": b.mean_confidence,
                    "min_confidence": b.min_confidence,
                    "source_detection_indices": list(b.source_detection_indices),
                    "role_metadata": b.role_metadata,
                    "warnings": list(b.warnings),
                }
                for b in struct_res.blocks
            ],
            "questions": [
                {
                    "question_block_id": q.question_block_id,
                    "question_number": q.question_number,
                    "question_text": q.question_text,
                    "bbox_xyxy": list(q.bbox),
                    "options": [
                        {
                            "option_label": o.option_label,
                            "option_text": o.option_text,
                            "block_id": o.block_id,
                            "confidence": o.confidence,
                            "bbox_xyxy": list(o.bbox),
                        }
                        for o in q.options
                    ],
                    "warnings": list(q.warnings),
                }
                for q in struct_res.questions
            ],
            "warnings": struct_res.warnings,
        }
        struct_path.write_text(json.dumps(struct_data, indent=2), encoding="utf-8")
        print(f"\n  [OK] Document Structure Evidence JSON saved to: {struct_path.resolve()}")


def print_and_save_semantic_result(
    semantic_res: SemanticAnalysisResult,
    source_name: str,
    output_dir: Optional[Path],
    stage_num: int,
    total_stages: int,
) -> None:
    """Format and print structured semantic analysis diagnostics and persist JSON evidence."""
    print(f"\n[Stage {stage_num}/{total_stages}] Executing Semantic Understanding & Domain Classification (Module 4)...")
    print(f"  - Active Embedding Engine: {semantic_res.embedding_engine}")
    print(f"  - Semantic Latency:        {semantic_res.processing_time_ms:.2f} ms")
    print(f"  - Primary Document Domains:{', '.join(semantic_res.document_domains) or 'None'}")
    print(f"  - Items Analyzed:          {len(semantic_res.items)}")

    if semantic_res.warnings:
        print("\n  Semantic Warnings:")
        for w in semantic_res.warnings:
            print(f"    [!] {w}")

    print("\n  Detailed Semantic Breakdown per Item:")
    for it in semantic_res.items:
        print(f"\n  * Item [{it.source_id}] (Status: {it.status}, Tech Level: {it.technical_level}):")
        text_prev = it.original_text.replace("\n", " ")
        if len(text_prev) > 70:
            text_prev = text_prev[:67] + "..."
        print(f"    Text:        \"{text_prev}\"")
        if it.primary_domain:
            dom_score = it.domains[0].similarity_score if it.domains else 0.0
            print(f"    Domain:      {it.primary_domain} (Score: {dom_score:.4f}, Method: {it.classification_method})")
            if len(it.domains) > 1:
                sec_doms = ", ".join(f"{d.domain_name} ({d.similarity_score:.3f})" for d in it.domains[1:])
                print(f"    Secondary:   {sec_doms}")
        else:
            print("    Domain:      UNKNOWN / INSUFFICIENT EVIDENCE")

        if it.question_intents:
            print(f"    Intents:     {', '.join(it.question_intents)}")

        if it.concepts:
            concept_strs = [f"{c.normalized_form} [{c.concept_type}]" for c in it.concepts]
            print(f"    Concepts:    {', '.join(concept_strs)}")

        if it.entities:
            entity_strs = [f"{e.text} ({e.entity_type})" for e in it.entities]
            print(f"    Entities:    {', '.join(entity_strs)}")

        if it.relationships:
            rel_strs = [f"({r.source} -> {r.relation} -> {r.target})" for r in it.relationships]
            print(f"    Relations:   {', '.join(rel_strs)}")

        if it.ambiguities:
            for amb in it.ambiguities:
                cues_str = f"cues: {list(amb.context_cues)}" if amb.context_cues else "no resolving cues"
                print(f"    Disambig:    Term '{amb.term}' -> {amb.resolved_sense} ({cues_str})")

        if it.retrieved_knowledge:
            for rk in it.retrieved_knowledge:
                print(f"    Grounding:   \"{rk.title}\" (Sim: {rk.similarity_score:.3f})")

    # Persist JSON
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        sem_path = output_dir / f"semantic_evidence_{source_name}.json"
        sem_data = {
            "source": source_name,
            "status": semantic_res.status,
            "embedding_engine": semantic_res.embedding_engine,
            "processing_time_ms": semantic_res.processing_time_ms,
            "document_domains": semantic_res.document_domains,
            "metadata": semantic_res.metadata,
            "items": [
                {
                    "source_id": it.source_id,
                    "original_text": it.original_text,
                    "normalized_text": it.normalized_text,
                    "primary_domain": it.primary_domain,
                    "domains": [
                        {
                            "domain_id": d.domain_id,
                            "domain_name": d.domain_name,
                            "hierarchy_path": list(d.hierarchy_path),
                            "similarity_score": d.similarity_score,
                            "is_primary": d.is_primary,
                            "evidence_terms": list(d.evidence_terms),
                        }
                        for d in it.domains
                    ],
                    "primary_topic": it.primary_topic,
                    "secondary_topics": list(it.secondary_topics),
                    "concepts": [
                        {
                            "text": c.text,
                            "normalized_form": c.normalized_form,
                            "concept_type": c.concept_type,
                            "span": list(c.span) if c.span else None,
                            "confidence": c.confidence,
                        }
                        for c in it.concepts
                    ],
                    "entities": [
                        {
                            "text": e.text,
                            "entity_type": e.entity_type,
                            "attributes": e.attributes,
                        }
                        for e in it.entities
                    ],
                    "relationships": [
                        {
                            "source": r.source,
                            "relation": r.relation,
                            "target": r.target,
                        }
                        for r in it.relationships
                    ],
                    "question_intents": list(it.question_intents),
                    "technical_level": it.technical_level,
                    "ambiguities": [
                        {
                            "term": a.term,
                            "resolved_sense": a.resolved_sense,
                            "confidence": a.confidence,
                            "candidate_senses": list(a.candidate_senses),
                            "context_cues": list(a.context_cues),
                        }
                        for a in it.ambiguities
                    ],
                    "warnings": list(it.warnings),
                    "retrieved_knowledge": [
                        {
                            "source_id": rk.source_id,
                            "title": rk.title,
                            "passage": rk.passage,
                            "similarity_score": rk.similarity_score,
                        }
                        for rk in it.retrieved_knowledge
                    ],
                    "classification_method": it.classification_method,
                    "status": it.status,
                }
                for it in semantic_res.items
            ],
            "warnings": semantic_res.warnings,
        }
        sem_path.write_text(json.dumps(sem_data, indent=2), encoding="utf-8")
        print(f"\n  [OK] Semantic Evidence JSON saved to: {sem_path.resolve()}")


def run_semantic_evidence_mode(evidence_path: Path, output_dir: Optional[Path], engine_name: str) -> int:
    """Run semantic understanding directly from an existing structure evidence JSON file."""
    print("=" * 70)
    print("  SETU-NETRA: Semantic Understanding (Evidence Mode)")
    print("=" * 70)
    print(f"Target Structure Evidence: {evidence_path}")

    if not evidence_path.is_file():
        print(f"  [ERROR] Structure evidence file not found: {evidence_path}")
        return 1

    try:
        data = json.loads(evidence_path.read_text(encoding="utf-8"))
        stem = evidence_path.stem.replace("structure_evidence_", "")

        # Reconstruct QuestionGroup dataclasses
        questions: List[QuestionGroup] = []
        for q in data.get("questions", []):
            opts: List[QuestionOption] = []
            for opt in q.get("options", []):
                opts.append(
                    QuestionOption(
                        option_label=opt["option_label"],
                        option_text=opt["option_text"],
                        block_id=opt["block_id"],
                        confidence=opt["confidence"],
                        bbox=tuple(opt["bbox_xyxy"]),
                    )
                )
            questions.append(
                QuestionGroup(
                    question_block_id=q["question_block_id"],
                    question_text=q["question_text"],
                    question_number=q.get("question_number"),
                    options=tuple(opts),
                    bbox=tuple(q["bbox_xyxy"]),
                    warnings=tuple(q.get("warnings", [])),
                )
            )

        # Reconstruct DocumentBlock dataclasses
        blocks: List[DocumentBlock] = []
        for b in data.get("blocks", []):
            blocks.append(
                DocumentBlock(
                    block_id=b["block_id"],
                    block_type=b["block_type"],
                    text=b["text"],
                    lines=(),
                    bbox=tuple(b["bbox_xyxy"]),
                    mean_confidence=b["mean_confidence"],
                    min_confidence=b["min_confidence"],
                    source_detection_indices=tuple(b.get("source_detection_indices", [])),
                    role_metadata=b.get("role_metadata", {}),
                    warnings=tuple(b.get("warnings", [])),
                )
            )

        struct_res = DocumentStructureResult(
            blocks=blocks,
            questions=questions,
            raw_transcript="\n\n".join(b.text for b in blocks),
            status=data.get("status", "SUCCESS"),
            warnings=data.get("warnings", []),
            metadata=data.get("metadata", {}),
        )

        embed_engine = get_embedding_engine(engine_name)
        if engine_name == "auto":
            print(f"  [Auto-Backend] Selected '{embed_engine.engine_name}' (dim={embed_engine.dimension})")
        sem_engine = SemanticUnderstandingEngine(embedding_engine=embed_engine)
        sem_res = sem_engine.analyze_document_structure(struct_res, document_id=stem)

        print_and_save_semantic_result(
            semantic_res=sem_res,
            source_name=stem,
            output_dir=output_dir,
            stage_num=1,
            total_stages=1,
        )
        print("\n" + "=" * 70)
        print("  Semantic Understanding Completed Successfully.")
        print("=" * 70)
        return 0

    except Exception as err:
        print(f"  [ERROR] Failed to run semantic understanding from evidence: {err}")
        return 1


def run_evidence_mode(evidence_path: Path, output_dir: Optional[Path]) -> int:
    """Reconstruct document structure directly from an existing OCR evidence JSON file."""
    print("=" * 70)
    print("  SETU-NETRA: Document Structure Reconstruction (Evidence Mode)")
    print("=" * 70)
    print(f"Target Evidence: {evidence_path}")

    if not evidence_path.is_file():
        print(f"  [ERROR] Evidence file not found: {evidence_path}")
        return 1

    try:
        data = json.loads(evidence_path.read_text(encoding="utf-8"))
        detections = data.get("detections", [])
        boxes: List[OCRBox] = []
        for d in detections:
            poly = tuple(tuple(float(c) for c in pt) for pt in d.get("polygon", []))
            boxes.append(
                OCRBox(
                    polygon=poly,
                    text=str(d.get("text", "")),
                    confidence=float(d.get("confidence", 0.0)),
                )
            )

        print(f"  - Loaded Detections:     {len(boxes)}")
        stem = evidence_path.stem.replace("ocr_evidence_", "")
        reconstructor = DocumentStructureReconstructor()
        struct_res = reconstructor.reconstruct(boxes)
        print_and_save_structure_result(
            struct_res=struct_res,
            source_name=stem,
            output_dir=output_dir,
            stage_num=1,
            total_stages=1,
        )
        print("\n" + "=" * 70)
        print("  Structure Reconstruction Completed Successfully.")
        print("=" * 70)
        return 0

    except Exception as err:
        print(f"  [ERROR] Failed to reconstruct from evidence: {err}")
        return 1


def run_query_mode(
    query_text: str,
    db_path: Path,
    top_k: int = 3,
    budget: int = 1500,
    engine_name: str = "auto",
) -> int:
    """Execute evidence-grounded semantic and lexical retrieval against stored documents."""
    print("=" * 70)
    print("  SETU-NETRA: Evidence-Grounded Context Retrieval (Module 5)")
    print("=" * 70)
    print(f"Target Database: {db_path}")
    print(f"User Query:      '{query_text}'")

    if not Path(db_path).exists():
        print(f"\n  [ERROR] Document database not found at: {db_path}")
        print("  Please ingest documents into the store first using '--store' or DocumentIntelligencePipeline.")
        return 1

    try:
        store = SQLiteDocumentStore(db_path)
        engine = get_embedding_engine(engine_name)
        retriever = DocumentRetriever(store, engine)
        synthesizer = EvidenceContextSynthesizer()

        passages = retriever.retrieve(query=query_text, top_k=top_k, threshold=0.15)
        ctx = synthesizer.synthesize(query=query_text, passages=passages, max_budget_tokens=budget)

        print(f"\n[Retrieval Diagnostics]")
        print(f"  - Active Embedding Engine: {engine.engine_name}")
        print(f"  - Candidate Blocks Found:  {len(passages)}")
        print(f"  - Blocks Packaged:         {len(ctx.passages)}")
        print(f"  - Estimated Token Count:   {ctx.token_count_estimate} / {budget} tokens")
        print(f"  - Budget Truncated:        {ctx.truncated}")

        if passages:
            print("\n" + "-" * 70)
            print("  RANKED RETRIEVED PASSAGES (PROVENANCE)")
            print("-" * 70)
            for idx, p in enumerate(passages, start=1):
                print(f"  #{idx} [Sim: {p.similarity_score:.4f} | Method: {p.retrieval_method}]")
                print(f"     Source: {p.document_name} (Page {p.page_number}, Block {p.block_id})")
                print(f"     Type:   {p.block_type} | Conf: {p.confidence * 100:.1f}%")
                print(f"     Box:    {p.bounding_box}")
                preview = p.text.replace("\n", " ")
                if len(preview) > 70:
                    preview = preview[:67] + "..."
                print(f"     Text:   \"{preview}\"\n")

        print("=" * 70)
        print("  SYNTHESIZED CONTEXT PAYLOAD FOR DOWNSTREAM LLM")
        print("=" * 70)
        print(ctx.formatted_context)
        return 0
    except Exception as err:
        print(f"\n  [ERROR] Context retrieval failed: {err}")
        return 1


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Direct query retrieval mode (Module 5)
    if args.query:
        return run_query_mode(
            query_text=args.query,
            db_path=args.db_path,
            top_k=args.top_k,
            budget=args.budget,
            engine_name=args.semantic_engine,
        )

    # Direct semantic evidence mode
    if args.semantic_evidence:
        return run_semantic_evidence_mode(args.semantic_evidence, args.output_dir, args.semantic_engine)

    # Direct evidence reconstruction mode
    if args.evidence:
        return run_evidence_mode(args.evidence, args.output_dir)

    input_path = args.image
    if not input_path:
        print("[ERROR] Please specify an image/PDF with -i / --image, a search with --query, an OCR evidence with --evidence, or structure evidence with --semantic-evidence.")
        parser.print_help()
        return 1

    # Multi-page PDF or SQLite Store Ingestion mode
    if input_path.suffix.lower() == ".pdf" or args.store:
        print("=" * 70)
        print("  SETU-NETRA: Document Intelligence Pipeline & Persistence (Module 5)")
        print("=" * 70)
        print(f"Target Document: {input_path}")
        print(f"Target Database: {args.db_path}")

        try:
            store = SQLiteDocumentStore(args.db_path)
            ocr_eng = get_ocr_engine(args.ocr_engine)
            embed_eng = get_embedding_engine(args.semantic_engine)
            pipeline = DocumentIntelligencePipeline(
                store=store,
                ocr_engine=ocr_eng,
                embedding_engine=embed_eng,
            )
            print("\n[Ingestion & Pipeline Execution]")
            print(f"  - Active OCR Engine:       {ocr_eng.engine_name}")
            print(f"  - Active Embedding Engine: {embed_eng.engine_name}")
            stored = pipeline.ingest_document(input_path)
            print(f"  [OK] Document successfully stored:")
            print(f"       Document ID:   {stored.doc_id}")
            print(f"       Filename:      {stored.file_name}")
            print(f"       Page Count:    {stored.page_count}")
            print(f"       File Hash:     {stored.file_hash[:16]}...")
            print(f"       Status:        {stored.status}")

            pages = store.get_pages(stored.doc_id)
            blocks = store.get_blocks(stored.doc_id)
            print(f"       Total Pages:   {len(pages)}")
            print(f"       Total Blocks:  {len(blocks)}")
            print("\n" + "=" * 70)
            print("  Ingestion Completed Successfully.")
            print("=" * 70)
            return 0
        except Exception as err:
            print(f"\n  [ERROR] Ingestion failed: {err}")
            return 1

    run_structure = args.ocr and not args.no_structure
    run_semantic = run_structure and args.semantic
    if run_semantic:
        total_stages = 6
    elif run_structure:
        total_stages = 5
    elif args.ocr:
        total_stages = 4
    else:
        total_stages = 3
    print("=" * 70)
    print("  SETU-NETRA: Pipeline Execution")
    print("=" * 70)
    print(f"Target Input: {input_path}")

    # Stage 1: Validation
    print(f"\n[Stage 1/{total_stages}] Validating input file...")
    validation = validate_image_file(input_path)
    if not validation.is_valid:
        print(f"  [ERROR] Validation failed: {validation.error_message}")
        print("  Pipeline aborted safely before attempting image decoding.")
        return 1
    print("  [OK] File exists, within size limits, and image headers are intact.")

    # Stage 2: Ingestion & Loading
    print(f"\n[Stage 2/{total_stages}] Loading image into memory and reading metadata...")
    try:
        image, original_meta = load_image(input_path, auto_orient=True)
    except Exception as err:
        print(f"  [ERROR] Failed to load image: {err}")
        return 1

    print(f"  - Filename:            {original_meta.file_name}")
    print(f"  - Format:              {original_meta.format}")
    print(f"  - Color Mode:          {original_meta.color_mode} ({original_meta.channels} channel(s))")
    print(f"  - Dimensions:          {original_meta.width} x {original_meta.height} px")
    print(f"  - Resolution:          {original_meta.resolution_mp} Megapixels")
    print(f"  - Aspect Ratio:        {original_meta.aspect_ratio} (W/H)")
    print(f"  - File Size on Disk:   {format_bytes(original_meta.file_size_bytes)}")
    print(f"  - Uncompressed RAM:    {format_bytes(original_meta.estimated_memory_bytes)}")
    if original_meta.exif_orientation:
        print(f"  - EXIF Orientation:    Tag {original_meta.exif_orientation} (normalized upright)")

    # Stage 3: Preprocessing
    print(f"\n[Stage 3/{total_stages}] Executing preprocessing pipeline...")
    # Handwriting preset adjusts contrast to 1.0 if not explicitly overridden
    contrast_val = args.contrast
    if args.handwriting and abs(args.contrast - 1.3) < 1e-4:
        contrast_val = 1.0
        print("  - [Preset: Handwriting] Using neutral contrast (1.0) to preserve cursive stroke continuity.")

    config = PreprocessConfig(
        convert_grayscale=not args.no_grayscale,
        max_dimension=args.max_dim,
        resample_filter=args.resample,
        contrast_factor=contrast_val,
    )
    preprocessor = ImagePreprocessor(config=config)
    result = preprocessor.process(
        image=image,
        original_metadata=original_meta,
        output_dir=args.output_dir,
    )

    print("\nTransformations applied:")
    for step in result.steps_applied:
        print(f"  * {step}")

    print("\nResult Comparison:")
    orig = result.original_metadata
    proc = result.processed_metadata
    print(f"  {'Metric':<22} | {'Original':<20} | {'Processed':<20}")
    print(f"  {'-'*22}-+-{'-'*20}-+-{'-'*20}")
    print(f"  {'Dimensions (WxH)':<22} | {f'{orig.width}x{orig.height}':<20} | {f'{proc.width}x{proc.height}':<20}")
    print(f"  {'Color Mode':<22} | {orig.color_mode:<20} | {proc.color_mode:<20}")
    print(f"  {'Channels':<22} | {orig.channels:<20} | {proc.channels:<20}")
    print(f"  {'RAM Buffer Est.':<22} | {format_bytes(orig.estimated_memory_bytes):<20} | {format_bytes(proc.estimated_memory_bytes):<20}")

    print("\nPreservation Verification:")
    print(f"  [OK] Original file remains untouched at: {orig.file_path}")
    if result.output_path:
        print(f"  [OK] Processed copy saved separately at: {result.output_path}")

    # Stage 4: OCR (Optional flag)
    if args.ocr:
        print(f"\n[Stage 4/{total_stages}] Executing OCR Subsystem...")
        languages = tuple(l.strip() for l in args.ocr_lang.split(",") if l.strip())
        # Resolve OCR parameters based on preset and flags
        if args.handwriting:
            add_margin = args.add_margin if args.add_margin is not None else 0.20
            mag_ratio = args.mag_ratio if args.mag_ratio is not None else 1.5
            link_ths = args.link_threshold if args.link_threshold is not None else 0.25
            text_ths = args.text_threshold if args.text_threshold is not None else 0.50
            low_text = 0.30
            print("  - [Preset: Handwriting] Detection parameters: mag_ratio=1.5, add_margin=0.20, link_threshold=0.25")
        else:
            add_margin = args.add_margin if args.add_margin is not None else 0.10
            mag_ratio = args.mag_ratio if args.mag_ratio is not None else 1.0
            link_ths = args.link_threshold if args.link_threshold is not None else 0.40
            text_ths = args.text_threshold if args.text_threshold is not None else 0.70
            low_text = 0.40

        ocr_config = OCRConfig(
            engine_name=args.ocr_engine,
            languages=languages,
            confidence_threshold=args.ocr_conf,
            use_gpu=False,
            add_margin=add_margin,
            mag_ratio=mag_ratio,
            link_threshold=link_ths,
            text_threshold=text_ths,
            low_text=low_text,
            paragraph=args.paragraph,
        )

        try:
            engine = get_ocr_engine(args.ocr_engine, config=ocr_config)
            print(f"  - Active Engine:       {engine.engine_name} (v{engine.engine_version})")
            print(f"  - Target Languages:    {ocr_config.languages}")
            print(f"  - Execution Device:    CPU")
            print(f"  - Confidence Filter:   >= {ocr_config.confidence_threshold:.2f}")

            # Run inference on the in-memory preprocessed image
            from PIL import Image as PILImage
            ocr_input_img = PILImage.open(result.output_path) if result.output_path else image
            ocr_res = engine.recognize(ocr_input_img, config=ocr_config)

            print(f"  - Status:              {ocr_res.status}")
            print(f"  - Inference Latency:   {ocr_res.processing_time_ms:.1f} ms")
            print(f"  - Detections Found:    {len(ocr_res.boxes)}")

            if ocr_res.error_message:
                print(f"  - Message:             {ocr_res.error_message}")

            if ocr_res.boxes:
                print("\n  Extracted OCR Evidence (Top Detections):")
                print(f"  {'#':<4} | {'Conf':<6} | {'Bounding Box (xmin, ymin, xmax, ymax)':<38} | {'Recognized Text'}")
                print(f"  {'-'*4}-+-{'-'*6}-+-{'-'*38}-+-{'-'*25}")
                for idx, box in enumerate(ocr_res.boxes, start=1):
                    bbox_str = f"[{box.xmin:.1f}, {box.ymin:.1f}, {box.xmax:.1f}, {box.ymax:.1f}]"
                    print(f"  {idx:<4} | {box.confidence*100:>5.1f}% | {bbox_str:<38} | {box.text}")

                # Save OCR evidence to structured JSON file
                if args.output_dir:
                    stem = original_meta.file_path.stem
                    evidence_path = args.output_dir / f"ocr_evidence_{stem}.json"
                    evidence_data = {
                        "source_file": str(original_meta.file_path),
                        "engine": ocr_res.engine_name,
                        "engine_version": ocr_res.engine_version,
                        "processing_time_ms": ocr_res.processing_time_ms,
                        "status": ocr_res.status,
                        "detections": [
                            {
                                "text": b.text,
                                "confidence": b.confidence,
                                "polygon": b.polygon,
                                "bbox_xyxy": [b.xmin, b.ymin, b.xmax, b.ymax],
                            }
                            for b in ocr_res.boxes
                        ],
                        "raw_transcript": ocr_res.raw_text,
                    }
                    evidence_path.write_text(json.dumps(evidence_data, indent=2), encoding="utf-8")
                    print(f"\n  [OK] OCR Evidence JSON saved to: {evidence_path.resolve()}")

                # Stage 5: Document Structure Reconstruction (Module 3)
                if run_structure:
                    reconstructor = DocumentStructureReconstructor()
                    struct_res = reconstructor.reconstruct(ocr_res)
                    stem = original_meta.file_path.stem
                    print_and_save_structure_result(
                        struct_res=struct_res,
                        source_name=stem,
                        output_dir=args.output_dir,
                        stage_num=5,
                        total_stages=total_stages,
                    )

                    # Stage 6: Semantic Understanding & Domain Classification (Module 4)
                    if run_semantic:
                        embed_engine = get_embedding_engine(args.semantic_engine)
                        if args.semantic_engine == "auto":
                            print(f"\n  [Auto-Backend] Selected '{embed_engine.engine_name}' (dim={embed_engine.dimension})")
                        sem_engine = SemanticUnderstandingEngine(embedding_engine=embed_engine)
                        sem_res = sem_engine.analyze_document_structure(struct_res, document_id=stem)
                        print_and_save_semantic_result(
                            semantic_res=sem_res,
                            source_name=stem,
                            output_dir=args.output_dir,
                            stage_num=6,
                            total_stages=total_stages,
                        )

        except (OCREngineNotFoundError, OCREngineError) as err:
            print(f"\n  [ERROR] OCR execution halted: {err}")
            return 1
        except Exception as err:
            print(f"\n  [ERROR] Unexpected error in OCR pipeline: {err}")
            return 1

    print("\n" + "=" * 70)
    print("  Execution Completed Successfully.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
