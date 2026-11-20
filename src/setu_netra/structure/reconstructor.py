"""
reconstructor.py: Document structure reconstruction engine for SETU-NETRA (Module 3).

Why this file exists:
Raw OCR detections are unordered, fragmented 2D bounding boxes. This engine orchestrates
reading-order reconstruction, horizontal line synthesis, vertical block clustering,
rule-based semantic classification, and question-option relationship mapping into a
deterministic, generic document structure.
"""

import time
from typing import Dict, List, Optional, Sequence, Tuple
from setu_netra.core.contracts import (
    BlockType,
    DocumentBlock,
    DocumentStructureResult,
    OCRBox,
    OCRResult,
    QuestionGroup,
    QuestionOption,
    ReconstructedLine,
)
from setu_netra.structure.block_grouper import group_lines_into_blocks
from setu_netra.structure.classifier import classify_line_or_block
from setu_netra.structure.geometry import compute_adaptive_scale, union_bbox
from setu_netra.structure.line_grouper import group_detections_into_lines
from setu_netra.structure.xy_cut import detect_columns, recursive_xy_cut


class DocumentStructureReconstructor:
    """Lightweight, geometry-driven document structure reconstruction engine."""

    def reconstruct(
        self,
        ocr_input: OCRResult | Sequence[OCRBox],
    ) -> DocumentStructureResult:
        """Reconstruct document structure from raw OCR detections.

        Args:
            ocr_input: Either an OCRResult instance or a sequence of OCRBox objects.

        Returns:
            DocumentStructureResult containing ordered blocks, questions, and metadata.
        """
        start_time = time.perf_counter()
        all_warnings: List[str] = []

        # Extract boxes from container if necessary
        if isinstance(ocr_input, OCRResult):
            boxes = ocr_input.boxes
            if ocr_input.status != "SUCCESS" and not boxes:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return DocumentStructureResult(
                    blocks=[],
                    questions=[],
                    raw_transcript="",
                    reading_order_box_indices=[],
                    processing_time_ms=round(elapsed_ms, 2),
                    status="EMPTY",
                    warnings=["Empty input OCRResult with status: " + ocr_input.status],
                    metadata={"total_blocks": 0},
                )
        else:
            boxes = list(ocr_input)

        if not boxes:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return DocumentStructureResult(
                blocks=[],
                questions=[],
                raw_transcript="",
                reading_order_box_indices=[],
                processing_time_ms=round(elapsed_ms, 2),
                status="EMPTY",
                warnings=["No OCR detections provided to reconstructor."],
                metadata={"total_blocks": 0},
            )

        # Stage 1 & 2: Multi-Column Layout Analysis & Line/Block Grouping
        columns = detect_columns(boxes)
        lines: List[ReconstructedLine] = []
        reading_order_indices: List[int] = []
        line_clusters: List[List[ReconstructedLine]] = []

        if len(columns) > 1:
            all_warnings.append(f"Multi-column layout detected: {len(columns)} columns separated by vertical gutters.")
            for col_boxes in columns:
                col_lines, col_order, col_warn = group_detections_into_lines(col_boxes)
                lines.extend(col_lines)
                reading_order_indices.extend(col_order)
                all_warnings.extend(col_warn)
                if col_lines:
                    col_clusters = group_lines_into_blocks(col_lines)
                    line_clusters.extend(col_clusters)
        else:
            lines, reading_order_indices, line_warnings = group_detections_into_lines(boxes)
            all_warnings.extend(line_warnings)
            if lines:
                line_clusters = group_lines_into_blocks(lines)

        if not lines:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return DocumentStructureResult(
                blocks=[],
                questions=[],
                raw_transcript="",
                reading_order_box_indices=[],
                processing_time_ms=round(elapsed_ms, 2),
                status="EMPTY",
                warnings=all_warnings or ["No valid lines could be formed from input boxes."],
                metadata={"total_blocks": 0},
            )

        # Calculate document-wide median line height for adaptive scaling
        median_line_h, _ = compute_adaptive_scale(boxes)

        # Stage 3: Block Role Classification
        blocks: List[DocumentBlock] = []
        has_active_question = False

        for block_idx, cluster_lines in enumerate(line_clusters, start=1):
            block_text = "\n".join(ln.text for ln in cluster_lines)
            block_bbox = union_bbox([ln.bbox for ln in cluster_lines])
            block_h = max(1e-5, block_bbox[3] - block_bbox[1])

            mean_c = sum(ln.mean_confidence for ln in cluster_lines) / len(cluster_lines)
            min_c = min(ln.min_confidence for ln in cluster_lines)

            # Flatten source detection indices
            src_indices: List[int] = []
            for ln in cluster_lines:
                src_indices.extend(ln.box_indices)

            b_type, role_meta, b_warnings = classify_line_or_block(
                text=block_text,
                line_height=block_h,
                median_line_height=median_line_h,
                mean_confidence=mean_c,
                has_preceding_question=has_active_question,
            )

            if b_type == BlockType.QUESTION:
                has_active_question = True

            doc_block = DocumentBlock(
                block_id=block_idx,
                block_type=b_type,
                text=block_text,
                lines=tuple(cluster_lines),
                bbox=block_bbox,
                mean_confidence=round(mean_c, 4),
                min_confidence=round(min_c, 4),
                source_detection_indices=tuple(src_indices),
                role_metadata=role_meta,
                warnings=tuple(b_warnings),
            )
            blocks.append(doc_block)

        # Stage 4: Question & Option Association
        questions: List[QuestionGroup] = []
        current_q_block: Optional[DocumentBlock] = None
        current_options: List[QuestionOption] = []

        for blk in blocks:
            if blk.block_type == BlockType.QUESTION:
                # If a previous question was open, commit it
                if current_q_block is not None:
                    q_group = self._finalize_question_group(current_q_block, current_options)
                    questions.append(q_group)
                    current_options = []

                current_q_block = blk

            elif blk.block_type == BlockType.OPTION:
                lbl = blk.role_metadata.get("option_label", "?")
                opt_text = blk.role_metadata.get("option_text", blk.text)
                opt = QuestionOption(
                    option_label=lbl,
                    option_text=opt_text,
                    block_id=blk.block_id,
                    confidence=blk.mean_confidence,
                    bbox=blk.bbox,
                )

                if current_q_block is not None:
                    current_options.append(opt)
                    blk.role_metadata["parent_question_id"] = current_q_block.block_id
                else:
                    all_warnings.append(
                        f"Orphaned option label '{lbl}' in block {blk.block_id} with no preceding question."
                    )

            elif blk.block_type in (BlockType.HEADING, BlockType.NOTE, BlockType.LIST_ITEM):
                # A structural break finishes the current question group if options were collected
                if current_q_block is not None and current_options:
                    q_group = self._finalize_question_group(current_q_block, current_options)
                    questions.append(q_group)
                    current_q_block = None
                    current_options = []

        # Commit trailing question group
        if current_q_block is not None:
            q_group = self._finalize_question_group(current_q_block, current_options)
            questions.append(q_group)

        # Stage 5: Assemble Full Document Result
        block_counts: Dict[str, int] = {}
        for b in blocks:
            block_counts[b.block_type] = block_counts.get(b.block_type, 0) + 1

        # Determine document type hint
        if len(questions) > 0 and block_counts.get(BlockType.OPTION, 0) > 0:
            doc_hint = "MULTIPLE_CHOICE_ASSESSMENT"
        elif len(questions) > 0:
            doc_hint = "QUESTION_DOCUMENT"
        elif block_counts.get(BlockType.LIST_ITEM, 0) > 0:
            doc_hint = "LIST_OR_INSTRUCTION_DOCUMENT"
        else:
            doc_hint = "GENERAL_TEXT_DOCUMENT"

        raw_transcript = "\n\n".join(b.text for b in blocks)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        metadata = {
            "document_type_hint": doc_hint,
            "total_blocks": len(blocks),
            "total_lines": len(lines),
            "total_questions": len(questions),
            "block_type_counts": block_counts,
        }

        return DocumentStructureResult(
            blocks=blocks,
            questions=questions,
            raw_transcript=raw_transcript,
            reading_order_box_indices=reading_order_indices,
            processing_time_ms=round(elapsed_ms, 2),
            status="SUCCESS",
            warnings=all_warnings,
            metadata=metadata,
        )

    def _finalize_question_group(
        self,
        q_block: DocumentBlock,
        options: List[QuestionOption],
    ) -> QuestionGroup:
        """Create a validated QuestionGroup and check option sequence consistency."""
        q_num = q_block.role_metadata.get("question_number")
        q_warnings: List[str] = []

        # Option sequence validation (e.g. check for missing options like B in A, C, D)
        labels = [o.option_label for o in options]
        if labels:
            ascii_vals = [ord(l) for l in labels if len(l) == 1 and l.isalpha()]
            if len(ascii_vals) == len(labels) and len(ascii_vals) > 1:
                min_v, max_v = min(ascii_vals), max(ascii_vals)
                expected_set = set(range(min_v, max_v + 1))
                missing = [chr(v) for v in sorted(expected_set - set(ascii_vals))]
                if missing:
                    q_warnings.append(f"Non-consecutive options: missing label(s) {missing}")

        all_bboxes = [q_block.bbox] + [o.bbox for o in options]
        group_bbox = union_bbox(all_bboxes)

        return QuestionGroup(
            question_block_id=q_block.block_id,
            question_text=q_block.text,
            question_number=q_num,
            options=tuple(options),
            bbox=group_bbox,
            warnings=tuple(q_warnings),
        )
