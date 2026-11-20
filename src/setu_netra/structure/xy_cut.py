"""
xy_cut.py: Recursive X-Y Cut algorithm for multi-column document layout analysis.

Why this file exists:
Multi-column documents (academic research papers, examination question sheets, newspapers)
have separate vertical text flows separated by whitespace gutters. Naive top-to-bottom
line grouping merges text across column gutters, scrambling sentences and destroying reading order.
Recursive X-Y Cut decomposes 2D bounding boxes hierarchically into independent column blocks
and paragraph blocks, strictly preserving left-to-right, column-by-column reading order.

Reference:
J. Ha, R. M. Haralick, and I. T. Phillips, "Recursive X-Y Cut using bounding boxes of
connected components", Proc. 3rd International Conference on Document Analysis and
Recognition (ICDAR), 1995.
"""

from typing import List, Sequence, Tuple
from setu_netra.core.contracts import OCRBox
from setu_netra.structure.geometry import compute_adaptive_scale


def _find_projection_valleys(
    intervals: List[Tuple[float, float]],
    span_min: float,
    span_max: float,
    min_gap: float,
) -> List[Tuple[float, float]]:
    """Find contiguous gaps (valleys with zero projection) wider than min_gap."""
    if span_max <= span_min or not intervals:
        return []

    # Merge overlapping intervals
    sorted_intervals = sorted(intervals, key=lambda it: it[0])
    merged: List[Tuple[float, float]] = []
    for start, end in sorted_intervals:
        if not merged:
            merged.append((start, end))
        else:
            prev_start, prev_end = merged[-1]
            if start <= prev_end:
                merged[-1] = (prev_start, max(prev_end, end))
            else:
                merged.append((start, end))

    # Gaps between merged intervals
    gaps: List[Tuple[float, float]] = []
    current_pos = span_min

    for start, end in merged:
        gap_w = start - current_pos
        if gap_w >= min_gap:
            gaps.append((current_pos, start))
        current_pos = max(current_pos, end)

    if span_max - current_pos >= min_gap:
        gaps.append((current_pos, span_max))

    return gaps


def detect_columns(
    boxes: Sequence[OCRBox],
    min_gutter_width: float = 25.0,
) -> List[List[OCRBox]]:
    """Detect independent vertical columns by finding vertical whitespace gutters.

    Args:
        boxes: Sequence of OCRBox objects on a page canvas.
        min_gutter_width: Minimum pixel width of an empty vertical band to qualify as a column gutter.

    Returns:
        List of box lists, where each inner list contains boxes belonging to one column,
        ordered left-to-right by column position.
    """
    if len(boxes) <= 1:
        return [list(boxes)]

    page_xmin = min(b.xmin for b in boxes)
    page_xmax = max(b.xmax for b in boxes)

    # Project all boxes onto X axis
    x_intervals = [(b.xmin, b.xmax) for b in boxes]
    gutters = _find_projection_valleys(x_intervals, page_xmin, page_xmax, min_gutter_width)

    # Filter out external margins (keep only internal gutters)
    internal_gutters = [g for g in gutters if g[0] > page_xmin + 20 and g[1] < page_xmax - 20]

    if not internal_gutters:
        return [list(boxes)]

    # Partition boxes into columns defined by internal gutters
    column_boundaries: List[Tuple[float, float]] = []
    left_bound = page_xmin

    for g_start, g_end in internal_gutters:
        column_boundaries.append((left_bound, g_start))
        left_bound = g_end
    column_boundaries.append((left_bound, page_xmax))

    columns: List[List[OCRBox]] = [[] for _ in column_boundaries]

    for box in boxes:
        box_center_x = box.center[0]
        # Assign to matching column
        assigned = False
        for col_idx, (c_start, c_end) in enumerate(column_boundaries):
            if c_start <= box_center_x <= c_end:
                columns[col_idx].append(box)
                assigned = True
                break
        if not assigned:
            # Fallback to nearest column center
            nearest_idx = min(
                range(len(column_boundaries)),
                key=lambda i: abs(box_center_x - (column_boundaries[i][0] + column_boundaries[i][1]) / 2.0),
            )
            columns[nearest_idx].append(box)

    # Return only non-empty columns, ordered left to right
    return [col for col in columns if col]


def recursive_xy_cut(
    boxes: Sequence[OCRBox],
    min_gutter_x: float = 25.0,
    min_gap_y: float = 20.0,
    max_depth: int = 5,
) -> List[List[OCRBox]]:
    """Hierarchically partition OCR boxes into coherent reading-order blocks using Recursive X-Y Cut.

    Algorithm:
    1. Check for vertical cut (gutters along X). If found, partition into left-to-right column slices.
    2. Check for horizontal cut (whitespace along Y). If found, partition into top-to-bottom paragraph slices.
    3. Recursively apply until no significant cuts exist or max_depth is reached.

    Returns:
        List of box groups ordered strictly according to human reading order.
    """
    if len(boxes) <= 1 or max_depth <= 0:
        return [list(boxes)]

    # 1. Attempt Vertical Cut (Column separation)
    cols = detect_columns(boxes, min_gutter_width=min_gutter_x)
    if len(cols) > 1:
        result_blocks: List[List[OCRBox]] = []
        for col_boxes in cols:
            # Recursively decompose each column
            col_blocks = recursive_xy_cut(col_boxes, min_gutter_x, min_gap_y, max_depth - 1)
            result_blocks.extend(col_blocks)
        return result_blocks

    # 2. Attempt Horizontal Cut (Paragraph / Section separation)
    ymin = min(b.ymin for b in boxes)
    ymax = max(b.ymax for b in boxes)
    y_intervals = [(b.ymin, b.ymax) for b in boxes]
    horizontal_gaps = _find_projection_valleys(y_intervals, ymin, ymax, min_gap_y)
    internal_y_gaps = [g for g in horizontal_gaps if g[0] > ymin + 5 and g[1] < ymax - 5]

    if internal_y_gaps:
        # Split into horizontal bands
        y_boundaries: List[Tuple[float, float]] = []
        top_bound = ymin
        for g_start, g_end in internal_y_gaps:
            y_boundaries.append((top_bound, g_start))
            top_bound = g_end
        y_boundaries.append((top_bound, ymax))

        bands: List[List[OCRBox]] = [[] for _ in y_boundaries]
        for box in boxes:
            box_cy = box.center[1]
            assigned = False
            for idx, (b_top, b_bot) in enumerate(y_boundaries):
                if b_top <= box_cy <= b_bot:
                    bands[idx].append(box)
                    assigned = True
                    break
            if not assigned:
                nearest_idx = min(
                    range(len(y_boundaries)),
                    key=lambda i: abs(box_cy - (y_boundaries[i][0] + y_boundaries[i][1]) / 2.0),
                )
                bands[nearest_idx].append(box)

        result_blocks = []
        for band_boxes in bands:
            if band_boxes:
                band_sub = recursive_xy_cut(band_boxes, min_gutter_x, min_gap_y, max_depth - 1)
                result_blocks.extend(band_sub)
        return result_blocks

    # Leaf node: single coherent visual block
    return [list(boxes)]
