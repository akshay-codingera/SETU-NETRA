# Root-Cause Investigation: Handwritten Document Structure Reconstruction Failure

**Document Version:** 1.0.0  
**Target Ingestion:** `quest7.png` (Handwritten SQL Multiple-Choice Problem)  
**System Component:** `setu_netra.structure.line_grouper`, `block_grouper`, `classifier`, `reconstructor`  
**Date:** November 12, 2026  

---

## 1. Executive Summary

During ingestion testing with handwritten document `quest7.png`, SETU-NETRA successfully localized ink strokes using EasyOCR but produced a severely corrupted reading order. Words from adjacent lines and different multiple-choice options were interleaved horizontally into a nonsensical transcript:
```text
uestion which students result groubed by of whose age is greater than 10 _ and shous the theix Groub (i.e., number of students in each Groub) ? the following SQL query Correctly selects the
```
This failure prevented question recognition and caused multiple-choice code block segmentation to collapse.

This investigation diagnosed the exact mathematical and algorithmic mechanisms responsible for line interleaving, premature block fragmentation, and missed option delimiters.

---

## 2. Root-Cause Diagnosis

### 2.1 The Dynamic Bounding Box Expansion Defect (Line Interleaving)
In `src/setu_netra/structure/line_grouper.py`, line clustering originally used an accumulator `_LineCluster` with dynamic bounding box expansion:
```python
# DEFECTIVE CODE:
def add(self, item: Tuple[int, OCRBox]) -> None:
    _, box = item
    self.items.append(item)
    self.ymin = min(self.ymin, box.ymin)  # DYNAMIC DRIFT
    self.ymax = max(self.ymax, box.ymax)  # DYNAMIC DRIFT
```
**Mechanism of Failure:**
1. Handwritten text exhibits baseline tilt, ascenders (e.g. `h`, `l`, `d`), and descenders (e.g. `y`, `g`, `p`).
2. In `quest7.png`, an ascender on the right side of Line 1 (`d` in `students`) had a high `ymax`.
3. When added to the cluster, `_LineCluster.ymax` expanded downward by 25 pixels.
4. On subsequent iterations, words from Line 2 (`whose`, `age`, `is`) fell within the expanded `[ymin, ymax]` boundary and were absorbed into the Line 1 cluster.
5. In Step 3, the cluster sorted all absorbed words strictly by `xmin` (horizontal position).
6. Because words on Line 2 occurred at various horizontal positions, sorting by `xmin` interleaved words from Line 1 and Line 2 into a single scrambled sentence:
   `which (L1) students (L2) result (L3) groubed (L3) by (L3) of (L1) whose (L2)...`

### 2.2 Global Bounding Box Overlap Failure on Sloped Baselines
Handwritten notes contain a natural 1.5° to 3° downward or upward tilt. Over an image width of 1600px, a 2° tilt produces a vertical displacement of:
$$\Delta y = 1600 \times \tan(2^\circ) \approx 55.8\text{ px}$$
Because the median line height of handwritten text in `quest7.png` was 42px, the rightmost word of Line $N$ sat lower than the leftmost word of Line $N+1$. Any purely global vertical overlap metric (`vertical_overlap_ratio > 0.40`) inevitably linked the end of line $N$ to the beginning of line $N+1$.

### 2.3 Premature Heading Misclassification
In `src/setu_netra/structure/classifier.py`, line heights exceeding $1.35 \times \text{median\_line\_height}$ were classified as `BlockType.HEADING`. Handwritten lines naturally fluctuate in bounding box height due to tall cursive strokes. As a result, clauses within the middle of a continuous question statement:
- `students whose age is greater than 10 _ and shous the`
- `result groubed by theix Groub (i.e., number of students in`
were erroneously marked as `HEADING` blocks, triggering premature block splits before the terminal question mark `?`.

### 2.4 Bare Option Letter Rejection
The option regex in `classifier.py` and `question_extractor.py` strictly expected delimited formats:
`A.`, `B)`, `[A]`, `(A)`
In `quest7.png`, the handwritten options were penned as bare capital letters:
`A SELECT...`, `B SELECT...`, `D SELECT...`
Because these lacked trailing periods or parentheses, they failed regex matching and were grouped into a generic paragraph block rather than four distinct multiple-choice option code blocks.

---

## 3. Corrective Architecture

To permanently resolve these defects without black-box ML or hardcoded heuristics, the following architecture was deployed:

1. **Neighbor-Chain Baseline Tracking (`line_grouper.py`):**
   Replaced global bounding-box clustering with local horizontal forward-linking. Words link strictly to their immediate rightward neighbor within a bounded vertical threshold ($|\Delta y| \le 0.65 \times \text{median\_height}$). Line baselines are tracked incrementally across words, preventing vertical drift.

2. **Accumulating Question Protection (`block_grouper.py`):**
   Question blocks that have opened with interrogative terminology (`which`, `what`, `select`) and have not reached a terminal question mark `?` are protected from premature heading splits.

3. **Bare Option & SQL Query Segmentation (`classifier.py`, `block_grouper.py`):**
   Added `RE_OPTION_BARE` matching `A-E` followed by uppercase keywords (`SELECT`, `Some`, `All`), and enabled multiline regex matching with `re.DOTALL`. Distinct SQL statements are isolated into separate code blocks.

4. **Sequential Missing Option Inference (`question_extractor.py`):**
   When faint handwriting causes OCR to drop an option label (e.g. Option C between B and D in `quest7.png`), the sequential reconstructor infers the missing letter from query syntax and block order.
