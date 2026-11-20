"""
geometry.py: Spatial geometry and bounding-box calculations for document structure.

Why this file exists:
Document structure reconstruction depends on geometric relationships between detected
regions: vertical line alignment, horizontal adjacency, aspect ratios, and spatial gaps.
Isolating geometry into pure functions ensures deterministic, testable behavior without
side effects or external dependencies.
"""

import math
from typing import Iterable, List, Optional, Sequence, Tuple
from setu_netra.core.contracts import OCRBox


def is_valid_coord(val: object) -> bool:
    """Check if a coordinate value is a valid, finite numeric float or int."""
    if val is None:
        return False
    if not isinstance(val, (int, float)):
        return False
    if math.isnan(val) or math.isinf(val):
        return False
    return True


def validate_box(box: OCRBox) -> Tuple[bool, Optional[str]]:
    """Validate that an OCRBox has positive dimensions and valid numeric coordinates.

    Returns:
        (True, None) if valid.
        (False, error_reason) if degenerate or invalid.
    """
    if not box.polygon or len(box.polygon) < 3:
        return False, "Box polygon has fewer than 3 vertices"

    for pt in box.polygon:
        if len(pt) < 2 or not is_valid_coord(pt[0]) or not is_valid_coord(pt[1]):
            return False, f"Invalid vertex coordinate: {pt}"

    if box.width <= 0.0 or box.height <= 0.0:
        return False, f"Degenerate box dimensions: width={box.width}, height={box.height}"

    if box.xmax < box.xmin or box.ymax < box.ymin:
        return False, f"Inverted box bounds: xmin={box.xmin}, xmax={box.xmax}, ymin={box.ymin}, ymax={box.ymax}"

    return True, None


def vertical_overlap(
    b1: Tuple[float, float, float, float],
    b2: Tuple[float, float, float, float],
) -> float:
    """Compute 1D vertical overlap between two bounding boxes (xmin, ymin, xmax, ymax)."""
    _, ymin1, _, ymax1 = b1
    _, ymin2, _, ymax2 = b2
    overlap = min(ymax1, ymax2) - max(ymin1, ymin2)
    return max(0.0, overlap)


def vertical_overlap_ratio(
    b1: Tuple[float, float, float, float],
    b2: Tuple[float, float, float, float],
) -> float:
    """Compute vertical overlap normalized by the height of the shorter box."""
    h1 = max(1e-5, b1[3] - b1[1])
    h2 = max(1e-5, b2[3] - b2[1])
    overlap = vertical_overlap(b1, b2)
    return overlap / min(h1, h2)


def horizontal_gap(
    left_box: Tuple[float, float, float, float],
    right_box: Tuple[float, float, float, float],
) -> float:
    """Compute horizontal distance from the right edge of left_box to left edge of right_box.

    Returns:
        Positive distance if right_box is to the right of left_box.
        Negative overlap distance if they horizontally overlap.
    """
    return right_box[0] - left_box[2]


def vertical_gap(
    top_box: Tuple[float, float, float, float],
    bottom_box: Tuple[float, float, float, float],
) -> float:
    """Compute vertical distance from the bottom edge of top_box to top edge of bottom_box."""
    return bottom_box[1] - top_box[3]


def union_bbox(
    bboxes: Sequence[Tuple[float, float, float, float]],
) -> Tuple[float, float, float, float]:
    """Calculate the minimal enclosing bounding box covering all input boxes."""
    if not bboxes:
        return (0.0, 0.0, 0.0, 0.0)

    xmin = min(b[0] for b in bboxes)
    ymin = min(b[1] for b in bboxes)
    xmax = max(b[2] for b in bboxes)
    ymax = max(b[3] for b in bboxes)
    return (xmin, ymin, xmax, ymax)


def compute_adaptive_scale(boxes: Sequence[OCRBox]) -> Tuple[float, float]:
    """Compute median character/line height and width across a set of boxes.

    Returns:
        (median_height, median_width) in pixels.
        Falls back to (20.0, 40.0) if no valid boxes are provided.
    """
    valid_heights: List[float] = []
    valid_widths: List[float] = []

    for b in boxes:
        is_val, _ = validate_box(b)
        if is_val:
            valid_heights.append(b.height)
            valid_widths.append(b.width)

    if not valid_heights:
        return (20.0, 40.0)

    valid_heights.sort()
    valid_widths.sort()

    mid_h = len(valid_heights) // 2
    median_h = (
        valid_heights[mid_h]
        if len(valid_heights) % 2 != 0
        else (valid_heights[mid_h - 1] + valid_heights[mid_h]) / 2.0
    )

    mid_w = len(valid_widths) // 2
    median_w = (
        valid_widths[mid_w]
        if len(valid_widths) % 2 != 0
        else (valid_widths[mid_w - 1] + valid_widths[mid_w]) / 2.0
    )

    return (max(4.0, median_h), max(4.0, median_w))
