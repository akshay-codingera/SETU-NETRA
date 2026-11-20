"""
Document structure reconstruction subsystem for SETU-NETRA (Module 3).
"""

from setu_netra.structure.geometry import (
    validate_box,
    vertical_overlap,
    vertical_overlap_ratio,
    horizontal_gap,
    vertical_gap,
    union_bbox,
    compute_adaptive_scale,
)
from setu_netra.structure.line_grouper import group_detections_into_lines
from setu_netra.structure.block_grouper import group_lines_into_blocks
from setu_netra.structure.classifier import (
    classify_line_or_block,
    match_option_pattern,
    match_note_pattern,
    match_list_pattern,
    is_heading_candidate,
    is_interrogative_sentence,
)
from setu_netra.structure.reconstructor import DocumentStructureReconstructor

__all__ = [
    "validate_box",
    "vertical_overlap",
    "vertical_overlap_ratio",
    "horizontal_gap",
    "vertical_gap",
    "union_bbox",
    "compute_adaptive_scale",
    "group_detections_into_lines",
    "group_lines_into_blocks",
    "classify_line_or_block",
    "match_option_pattern",
    "match_note_pattern",
    "match_list_pattern",
    "is_heading_candidate",
    "is_interrogative_sentence",
    "DocumentStructureReconstructor",
]
