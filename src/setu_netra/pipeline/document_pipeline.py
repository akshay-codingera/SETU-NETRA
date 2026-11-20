"""
document_pipeline.py: Unified multi-page document intelligence pipeline and persistence coordinator.

Why this file exists:
Coordinates image and multi-page PDF ingestion, preprocessing, OCR, geometric structure
reconstruction, embedding extraction, SQLite persistence, and grounded context synthesis
into a single, high-level, production-grade interface.
"""

from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
from PIL import Image

from setu_netra.context.synthesizer import EvidenceContextSynthesizer
from setu_netra.core.contracts import (
    DocumentStructureResult,
    OCRResult,
    PreprocessConfig,
    RetrievedPassage,
    StoredDocument,
    SynthesizedContext,
)
from setu_netra.ingestion.docx_loader import load_docx_pages
from setu_netra.ingestion.loader import load_image
from setu_netra.ingestion.pdf_loader import is_pdfium_available, load_pdf_pages
from setu_netra.ingestion.text_loader import load_text_pages
from setu_netra.ingestion.validator import validate_document_file
from setu_netra.ocr.base import BaseOCREngine
from setu_netra.ocr.factory import get_ocr_engine
from setu_netra.preprocessing.operations import (
    adjust_contrast,
    map_bbox_to_original,
    normalize_exif_orientation,
    resize_keep_aspect_ratio,
    safe_composite_on_white,
    to_grayscale,
)
from setu_netra.preprocessing.pipeline import ImagePreprocessor
from setu_netra.retrieval.document_retriever import DocumentRetriever
from setu_netra.semantic.embeddings.base import BaseEmbeddingEngine
from setu_netra.semantic.embeddings.factory import get_embedding_engine
from setu_netra.store.sqlite_store import SQLiteDocumentStore, compute_file_sha256
from setu_netra.structure.reconstructor import DocumentStructureReconstructor


class DocumentIntelligencePipeline:
    """Production document intelligence pipeline coordinating ingestion, persistence, and retrieval."""

    def __init__(
        self,
        store: Optional[SQLiteDocumentStore] = None,
        ocr_engine: Optional[BaseOCREngine] = None,
        embedding_engine: Optional[BaseEmbeddingEngine] = None,
        preprocess_config: Optional[PreprocessConfig] = None,
        db_path: Union[str, Path] = "output/setu_netra.db",
    ):
        self.store = store or SQLiteDocumentStore(db_path=db_path)
        self.ocr_engine = ocr_engine or get_ocr_engine("easyocr")
        self.embedding_engine = embedding_engine or get_embedding_engine("auto")
        self.preprocessor = ImagePreprocessor(config=preprocess_config or PreprocessConfig())
        self.reconstructor = DocumentStructureReconstructor()
        self.retriever = DocumentRetriever(self.store, self.embedding_engine)
        self.synthesizer = EvidenceContextSynthesizer()

    def ingest_document(
        self,
        file_path: Union[str, Path],
        force_reprocess: bool = False,
        dpi: int = 150,
        workspace_id: str = "default",
    ) -> StoredDocument:
        """Ingest a multi-page PDF or image document, execute OCR and structure, and persist in the store.

        Args:
            file_path: Path to the target image or PDF document.
            force_reprocess: If False, returns existing cached record if SHA-256 matches.
            dpi: Rendering resolution for PDF pages (default: 150 DPI).
            workspace_id: Workspace scope for multi-tenant isolation (default: 'default').

        Returns:
            StoredDocument representing the persisted record.
        """
        path = Path(file_path).resolve()

        # 1. Defensive Validation
        validation = validate_document_file(path)
        if not validation.is_valid:
            raise ValueError(f"Document validation failed: {validation.error_message}")

        # 2. Content Deduplication Check
        file_hash = compute_file_sha256(path)
        if not force_reprocess:
            existing = self.store.get_document_by_hash(file_hash, workspace_id=workspace_id)
            if existing:
                return existing

        ext = path.suffix.lower()
        is_pdf = (ext == ".pdf")
        is_docx = (ext == ".docx")
        is_txt = (ext == ".txt")

        # 3. Page Decomposition
        pages_to_process: List[Tuple[int, Image.Image, int, int]] = []
        structured_doc_pages: Optional[List[Tuple[int, Image.Image, int, int, List[Dict[str, Any]]]]] = None

        if is_pdf:
            if not is_pdfium_available():
                raise ImportError("pypdfium2 is required for PDF ingestion. Run: pip install pypdfium2")
            pages_to_process = load_pdf_pages(path, dpi=dpi)
            doc_type = "PDF"
        elif is_docx:
            structured_doc_pages = load_docx_pages(path)
            doc_type = "DOCX"
        elif is_txt:
            structured_doc_pages = load_text_pages(path)
            doc_type = "TXT"
        else:
            img, meta = load_image(path, auto_orient=True)
            pages_to_process = [(1, img, meta.width, meta.height)]
            doc_type = "IMAGE"

        doc_id = f"doc_{path.stem}_{file_hash[:8]}" if workspace_id == "default" else f"doc_{path.stem}_{file_hash[:8]}_{workspace_id[:8]}"
        page_count = len(structured_doc_pages) if structured_doc_pages is not None else len(pages_to_process)

        # 4. Save Parent Document Record First (Satisfies Foreign Key Constraints)
        stored_doc = self.store.save_document(
            doc_id=doc_id,
            file_path=path,
            file_hash=file_hash,
            file_type=doc_type,
            page_count=page_count,
            status="PROCESSING",
            metadata={
                "original_filename": path.name,
                "embedding_engine": self.embedding_engine.engine_name,
            },
            workspace_id=workspace_id,
        )

        # 5. Process Each Page
        if structured_doc_pages is not None:
            # Native digital structured ingestion (DOCX / TXT)
            for page_num, raw_image, w, h, pre_blocks in structured_doc_pages:
                page_id = f"{doc_id}_p{page_num}"
                block_records: List[Dict] = []
                if pre_blocks:
                    block_texts = [b["text"].strip() for b in pre_blocks]
                    vectors = self.embedding_engine.embed_texts(block_texts)
                    for b_idx, blk in enumerate(pre_blocks):
                        block_records.append({
                            "block_id": blk["block_id"],
                            "block_type": blk["block_type"],
                            "text": blk["text"],
                            "confidence": blk.get("confidence", 1.0),
                            "bounding_box": blk["bounding_box"],
                            "source_detection_indices": [],
                            "embedding": vectors[b_idx],
                            "embedding_dim": len(vectors[b_idx]),
                            "embedding_engine": self.embedding_engine.engine_name,
                            "primary_domain": "",
                            "concepts": [],
                        })

                self.store.save_page(
                    page_id=page_id,
                    doc_id=doc_id,
                    page_number=page_num,
                    width=w,
                    height=h,
                    metadata={"block_count": len(block_records)},
                )
                self.store.save_blocks(
                    doc_id=doc_id,
                    page_number=page_num,
                    blocks_data=block_records,
                    workspace_id=workspace_id,
                )

        else:
            # Raster & PDF Vision OCR Pipeline
            for page_num, raw_image, w, h in pages_to_process:
                page_id = f"{doc_id}_p{page_num}"

                # Ensure orientation is normalized and transparent channels are composited over white
                normalized_raw = safe_composite_on_white(normalize_exif_orientation(raw_image))
                w, h = normalized_raw.size

                # Preprocess page image non-destructively in-memory
                proc_img = normalized_raw.copy()
                cfg = self.preprocessor.config
                if cfg.convert_grayscale and proc_img.mode != "L":
                    proc_img = to_grayscale(proc_img)
                if cfg.max_dimension is not None:
                    resized_img, was_resized = resize_keep_aspect_ratio(
                        proc_img,
                        max_dimension=cfg.max_dimension,
                        resample_filter=cfg.resample_filter,
                    )
                    if was_resized:
                        proc_img = resized_img
                if abs(cfg.contrast_factor - 1.0) > 1e-4:
                    proc_img = adjust_contrast(proc_img, cfg.contrast_factor)

                proc_w, proc_h = proc_img.size

                # Run OCR recognition
                ocr_res: OCRResult = self.ocr_engine.recognize(proc_img)

                # Reconstruct reading order, lines, and blocks
                struct_res: DocumentStructureResult = self.reconstructor.reconstruct(ocr_res)

                # Extract embeddings for all reconstructed blocks
                block_records = []
                if struct_res.blocks:
                    block_texts = [b.text.strip() for b in struct_res.blocks]
                    # Embed all block texts in a single batch
                    vectors = self.embedding_engine.embed_texts(block_texts)

                    for b_idx, blk in enumerate(struct_res.blocks):
                        # Rescale bounding box from processed space back to original image space
                        orig_bbox = map_bbox_to_original(
                            blk.bbox,
                            orig_size=(w, h),
                            proc_size=(proc_w, proc_h),
                        )
                        block_records.append({
                            "block_id": blk.block_id,
                            "block_type": blk.block_type.value if hasattr(blk.block_type, "value") else str(blk.block_type),
                            "text": blk.text,
                            "confidence": blk.mean_confidence,
                            "bounding_box": orig_bbox,
                            "source_detection_indices": blk.source_detection_indices,
                            "embedding": vectors[b_idx],
                            "embedding_dim": len(vectors[b_idx]),
                            "embedding_engine": self.embedding_engine.engine_name,
                            "primary_domain": "",
                            "concepts": [],
                        })

                # Format questions and page metadata
                detected_questions_data = [
                    {
                        "question_block_id": q.question_block_id,
                        "question_text": q.question_text,
                        "question_number": q.question_number,
                        "options": [{"label": opt.option_label, "text": opt.option_text} for opt in q.options],
                        "bbox": map_bbox_to_original(q.bbox, orig_size=(w, h), proc_size=(proc_w, proc_h)),
                        "warnings": list(q.warnings),
                    }
                    for q in struct_res.questions
                ]

                page_meta = {
                    "block_count": len(block_records),
                    "full_text": struct_res.raw_transcript,
                    "raw_transcript": struct_res.raw_transcript,
                    "ocr_boxes_count": len(ocr_res.boxes),
                    "ocr_status": ocr_res.status,
                    "detected_questions": detected_questions_data,
                    "warnings": list(struct_res.warnings),
                }

                # Save page record and block records in SQLite store
                self.store.save_page(
                    page_id=page_id,
                    doc_id=doc_id,
                    page_number=page_num,
                    width=w,
                    height=h,
                    metadata=page_meta,
                )
                self.store.save_blocks(
                    doc_id=doc_id,
                    page_number=page_num,
                    blocks_data=block_records,
                    workspace_id=workspace_id,
                )

        # Mark document status as fully PROCESSED
        stored_doc = self.store.save_document(
            doc_id=doc_id,
            file_path=path,
            file_hash=file_hash,
            file_type=doc_type,
            page_count=page_count,
            status="PROCESSED",
            metadata={
                "original_filename": path.name,
                "embedding_engine": self.embedding_engine.engine_name,
            },
            workspace_id=workspace_id,
        )

        return stored_doc

    def reindex_document(self, doc_id: str, dpi: int = 150) -> StoredDocument:
        """Re-index an existing document without duplicating records or changing its doc_id.

        Clears existing pages, blocks, and vector embeddings for this doc_id, and re-executes
        layout reconstruction and vector embedding from the source file.
        """
        doc = self.store.get_document_by_id(doc_id)
        if not doc:
            raise KeyError(f"Document with ID '{doc_id}' not found.")

        path = Path(doc.file_path)
        if not path.exists():
            raise FileNotFoundError(f"Underlying file not found on disk at: {path}")

        # Clear existing blocks and pages
        self.store.clear_document_blocks(doc_id)

        # Force re-ingestion of the file
        return self.ingest_document(file_path=path, force_reprocess=True, dpi=dpi)

    def query(
        self,
        query_text: str,
        top_k: int = 3,
        threshold: float = 0.20,
        max_budget_tokens: int = 1500,
        doc_id: Optional[str] = None,
        alpha: float = 0.70,
    ) -> SynthesizedContext:
        """Retrieve relevant passages from stored documents and package into an evidence-backed prompt.

        Args:
            query_text: User or system search query.
            top_k: Maximum number of candidate passages to retrieve.
            threshold: Minimum similarity threshold.
            max_budget_tokens: Token ceiling for synthesized prompt context.
            doc_id: Optional filter for a specific document.
            alpha: Weight for dense cosine vs lexical overlap (default: 0.70).

        Returns:
            SynthesizedContext containing formatted prompt and provenance tags.
        """
        passages: List[RetrievedPassage] = self.retriever.retrieve(
            query=query_text,
            top_k=top_k,
            threshold=threshold,
            doc_id=doc_id,
            alpha=alpha,
        )

        return self.synthesizer.synthesize(
            query=query_text,
            passages=passages,
            max_budget_tokens=max_budget_tokens,
        )
