"""
block_grouper.py: Adaptive clustering of reconstructed lines into structural document blocks.

Why this file exists:
Individual lines of text belong to larger semantic structures (multiline paragraphs,
multiline questions, distinct answer options, headings, and notes). This module detects
block boundaries using adaptive vertical inter-line spacing and structural role triggers.
"""

from typing import List
from setu_netra.core.contracts import ReconstructedLine
from setu_netra.structure.classifier import (
    is_heading_candidate,
    is_sql_statement_start,
    match_list_pattern,
    match_note_pattern,
    match_option_pattern,
    RE_QUESTION_EXPLICIT,
    RE_NUMBERED_PREFIX,
)
from setu_netra.structure.geometry import vertical_gap


def group_lines_into_blocks(
    lines: List[ReconstructedLine],
) -> List[List[ReconstructedLine]]:
    """Partition a sequence of reading-order lines into coherent document blocks.

    Args:
        lines: Reconstructed text lines in top-to-bottom reading order.

    Returns:
        List of blocks, where each block is a list of lines belonging to that block.
    """
    if not lines:
        return []

    if len(lines) == 1:
        return [[lines[0]]]

    # Compute median line height across the lines
    heights = sorted(ln.height for ln in lines)
    median_h = heights[len(heights) // 2]

    # Compute vertical inter-line gaps
    gaps: List[float] = []
    for i in range(len(lines) - 1):
        g = vertical_gap(lines[i].bbox, lines[i + 1].bbox)
        if g >= 0:
            gaps.append(g)

    gaps.sort()
    median_gap = gaps[len(gaps) // 2] if gaps else 0.3 * median_h

    # Separate tight intra-line gaps (< 0.85 * median_h) from paragraph gaps
    intra_gaps = [g for g in gaps if g <= 0.85 * median_h]
    if intra_gaps:
        median_intra = intra_gaps[len(intra_gaps) // 2]
        gap_threshold = max(1.15 * median_h, 2.0 * median_intra)
    else:
        gap_threshold = 1.15 * median_h

    blocks: List[List[ReconstructedLine]] = []
    current_block: List[ReconstructedLine] = [lines[0]]

    for i in range(len(lines) - 1):
        prev_line = lines[i]
        curr_line = lines[i + 1]

        v_dist = vertical_gap(prev_line.bbox, curr_line.bbox)

        # Check terminal punctuation: incomplete sentences should not easily break
        prev_stripped = prev_line.text.strip()
        prev_has_terminator = prev_stripped.endswith((".", "?", "!", ":", ";"))
        prev_ended_with_question = (
            prev_stripped.endswith("?")
            or "?" in prev_stripped[-4:]
        )

        # Condition 1: Exceeded adaptive vertical gap threshold
        if prev_has_terminator:
            is_large_gap = v_dist > gap_threshold
        else:
            # For incomplete clauses, require a substantially larger section gap
            is_large_gap = v_dist > max(2.5 * median_h, 2.5 * gap_threshold)

        # Condition 2: Structural role boundaries
        prev_is_heading = is_heading_candidate(prev_line.text, prev_line.height, median_h)
        curr_is_heading = is_heading_candidate(curr_line.text, curr_line.height, median_h)

        curr_is_option = match_option_pattern(curr_line.text) is not None
        curr_is_sql_query = is_sql_statement_start(curr_line.text) and (prev_has_terminator or prev_stripped.endswith(";"))

        prev_is_note = match_note_pattern(prev_line.text) is not None
        curr_is_note = match_note_pattern(curr_line.text) is not None

        curr_is_list = match_list_pattern(curr_line.text) is not None

        curr_is_explicit_q = bool(RE_QUESTION_EXPLICIT.match(curr_line.text))
        curr_is_num_q = bool(RE_NUMBERED_PREFIX.match(curr_line.text))

        # If current block is an accumulating question that has not yet terminated with '?',
        # do not allow intermediate sentence fragments to be falsely broken by heading candidates.
        block_full_text = " ".join(ln.text for ln in current_block)
        is_accumulating_question = (
            any(w in block_full_text.lower().split() for w in ("which", "what", "how", "why", "who", "find", "select"))
            and not (block_full_text.endswith("?") or "?" in block_full_text[-4:])
        )
        if is_accumulating_question and not (curr_is_option or curr_is_sql_query or curr_is_explicit_q or is_large_gap):
            curr_is_heading = False

        # Low-confidence or noise lines should isolate into their own block
        is_confidence_mismatch = (
            prev_line.mean_confidence < 0.25 or curr_line.mean_confidence < 0.25
        )

        # Determine if a block boundary must be enforced
        trigger_new_block = (
            is_large_gap
            or is_confidence_mismatch
            or prev_ended_with_question
            or prev_is_heading
            or curr_is_heading
            or curr_is_option
            or curr_is_sql_query
            or prev_is_note
            or curr_is_note
            or curr_is_list
            or curr_is_explicit_q
            or curr_is_num_q
        )

        if trigger_new_block:
            blocks.append(current_block)
            current_block = [curr_line]
        else:
            current_block.append(curr_line)

    if current_block:
        blocks.append(current_block)

    return blocks
