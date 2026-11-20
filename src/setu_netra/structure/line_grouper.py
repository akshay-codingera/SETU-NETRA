"""
line_grouper.py: Adaptive clustering of 2D OCR detections into reading-order lines.

Why this file exists:
Raw OCR engines detect arbitrary quadrilateral text fragments whose reading order
cannot be resolved by naive y-coordinate sorting due to baseline tilt, ascender/descender
jitter, and variable font heights. This module clusters vertically overlapping tokens into
coherent horizontal lines, sorts tokens left-to-right, and sorts lines top-to-bottom.
"""

from typing import List, Sequence, Tuple
from setu_netra.core.contracts import OCRBox, ReconstructedLine
from setu_netra.structure.geometry import (
    compute_adaptive_scale,
    union_bbox,
    validate_box,
    vertical_overlap_ratio,
)


class _LineCluster:
    """Internal mutable accumulator for clustering word tokens into a single text line."""

    def __init__(self, item: Tuple[int, OCRBox]):
        idx, box = item
        self.items: List[Tuple[int, OCRBox]] = [item]
        self.ymin: float = box.ymin
        self.ymax: float = box.ymax
        self.total_center_y: float = box.center[1]

    @property
    def height(self) -> float:
        return max(1e-5, self.ymax - self.ymin)

    @property
    def mean_center_y(self) -> float:
        return self.total_center_y / max(1, len(self.items))

    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        xmin = min(b.xmin for _, b in self.items)
        xmax = max(b.xmax for _, b in self.items)
        return (xmin, self.ymin, xmax, self.ymax)

    def can_merge(
        self,
        box: OCRBox,
        median_h: float,
        overlap_threshold: float = 0.40,
    ) -> Tuple[bool, float]:
        """Check whether an OCR box geometrically belongs to this line cluster.

        Returns:
            (can_merge, overlap_score)
        """
        box_bbox = (box.xmin, box.ymin, box.xmax, box.ymax)
        cluster_bbox = self.bbox

        ratio = vertical_overlap_ratio(cluster_bbox, box_bbox)
        center_dist = abs(self.mean_center_y - box.center[1])
        ref_h = max(self.height, box.height, median_h)

        if ratio >= overlap_threshold:
            return True, ratio

        if center_dist <= 0.45 * ref_h:
            return True, max(0.1, 1.0 - (center_dist / ref_h))

        return False, 0.0

    def add(self, item: Tuple[int, OCRBox]) -> None:
        _, box = item
        self.items.append(item)
        self.ymin = min(self.ymin, box.ymin)
        self.ymax = max(self.ymax, box.ymax)
        self.total_center_y += box.center[1]


def group_detections_into_lines(
    boxes: Sequence[OCRBox],
) -> Tuple[List[ReconstructedLine], List[int], List[str]]:
    """Group 2D OCR boxes into horizontally ordered lines and global reading order.

    Uses a neighbor-chain baseline tracking algorithm designed specifically to handle:
    - Baseline tilt and handwritten ascender/descender jitter.
    - Strict prevention of vertical line collapse (prevents tokens in separate lines from
      interleaving horizontally).
    - Preservation of left-to-right reading order across multi-word spans.

    Args:
        boxes: Sequence of detected OCR boxes from an OCR engine.

    Returns:
        (reconstructed_lines, reading_order_indices, warnings)
    """
    warnings: List[str] = []
    valid_items: List[Tuple[int, OCRBox]] = []

    for idx, box in enumerate(boxes):
        is_val, reason = validate_box(box)
        if not is_val:
            warnings.append(f"Ignored degenerate box at index {idx}: {reason}")
            continue
        valid_items.append((idx, box))

    if not valid_items:
        return [], [], warnings

    valid_boxes = [b for _, b in valid_items]
    median_h, _ = compute_adaptive_scale(valid_boxes)

    # 1. Neighbor-Chain Linking:
    # For each box_a, find the optimal rightward word successor box_b on the same line
    successors: dict[int, int] = {}
    predecessors: dict[int, int] = {}

    for i, (_, box_a) in enumerate(valid_items):
        best_j = None
        best_cost = 999999.0

        for j, (_, box_b) in enumerate(valid_items):
            if i == j:
                continue

            # box_b must be to the right of box_a
            dx = box_b.xmin - box_a.xmax
            # Allow slight ligature overlap (e.g. cursive writing down to -0.35 * median_h)
            if dx < -0.35 * median_h:
                continue
            # Maximum word gap on the same line
            if dx > 4.5 * median_h:
                continue

            dy = abs(box_b.center[1] - box_a.center[1])
            if dy > 0.65 * median_h:
                continue

            span_dx = box_b.center[0] - box_a.center[0]
            if span_dx <= 5:
                continue

            # Slope constraint: prevent linking vertically stacked tokens
            slope = dy / span_dx
            if slope > 0.45:
                continue

            cost = max(0.0, dx) + 2.8 * dy
            if cost < best_cost:
                best_cost = cost
                best_j = j

        if best_j is not None:
            # If best_j already has a predecessor, keep the one with lower cost
            if best_j in predecessors:
                prev_i = predecessors[best_j]
                _, prev_box = valid_items[prev_i]
                _, target_box = valid_items[best_j]
                prev_dx = target_box.xmin - prev_box.xmax
                prev_dy = abs(target_box.center[1] - prev_box.center[1])
                prev_cost = max(0.0, prev_dx) + 2.8 * prev_dy
                if best_cost < prev_cost:
                    del successors[prev_i]
                    successors[i] = best_j
                    predecessors[best_j] = i
            else:
                successors[i] = best_j
                predecessors[best_j] = i

    # 2. Extract Chain Heads (nodes with no incoming left predecessor)
    heads = [i for i in range(len(valid_items)) if i not in predecessors]

    # 3. Traverse chains from heads
    raw_chains: List[List[Tuple[int, OCRBox]]] = []
    visited = set()
    for h in heads:
        curr = h
        chain: List[Tuple[int, OCRBox]] = []
        while curr is not None and curr not in visited:
            visited.add(curr)
            chain.append(valid_items[curr])
            curr = successors.get(curr)
        if chain:
            raw_chains.append(chain)

    # Collect any unvisited tokens as isolated single-item lines
    for i in range(len(valid_items)):
        if i not in visited:
            raw_chains.append([valid_items[i]])
            visited.add(i)

    # 4. Sort chains top-to-bottom in true document reading order
    # Sort key: vertical baseline of the line start, with tolerance for horizontal alignment
    def _chain_sort_key(c: List[Tuple[int, OCRBox]]) -> Tuple[float, float]:
        first_box = c[0][1]
        mean_center_y = sum(b.center[1] for _, b in c) / len(c)
        # Quantize Y slightly by 0.35 * median_h to stabilize lines that start slightly jittered
        quantized_y = round(first_box.ymin / (0.45 * median_h)) * (0.45 * median_h)
        return (first_box.ymin, first_box.xmin)

    raw_chains.sort(key=_chain_sort_key)

    # 5. Convert chains into ReconstructedLine instances
    reconstructed_lines: List[ReconstructedLine] = []

    for chain in raw_chains:
        # Guarantee strict left-to-right token ordering within the line
        chain.sort(key=lambda it: it[1].xmin)

        box_indices = tuple(idx for idx, _ in chain)
        words = tuple(b.text.strip() for _, b in chain if b.text.strip())
        confidences = tuple(b.confidence for _, b in chain)
        line_text = " ".join(words)

        all_bboxes = [(b.xmin, b.ymin, b.xmax, b.ymax) for _, b in chain]
        line_bbox = union_bbox(all_bboxes)

        mean_conf = (
            sum(confidences) / len(confidences) if confidences else 0.0
        )
        min_conf = min(confidences) if confidences else 0.0

        reconstructed_lines.append(
            ReconstructedLine(
                text=line_text,
                box_indices=box_indices,
                bbox=line_bbox,
                mean_confidence=round(mean_conf, 4),
                min_confidence=round(min_conf, 4),
                words=words,
                confidences=confidences,
            )
        )

    # Flatten reading-order detection indices
    reading_order_indices: List[int] = []
    for line in reconstructed_lines:
        reading_order_indices.extend(line.box_indices)

    return reconstructed_lines, reading_order_indices, warnings
