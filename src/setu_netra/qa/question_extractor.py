"""
question_extractor.py: Question segmentation, option parsing, and intent classification for SETU-NETRA.

Why this file exists:
Uploaded study documents and exams contain single questions, multiple questions,
MCQs with options, and follow-up inquiries. This module extracts, segments, and
classifies questions into well-defined cognitive intents without assuming every
document is an MCQ or single query.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple
from setu_netra.core.contracts import DocumentBlock, DocumentStructureResult, QuestionGroup


@dataclass
class ExtractedQuestion:
    """Standardized representation of an extracted question."""
    question_id: int
    prompt: str
    intent: str                        # 'DEFINITION', 'COMPARISON', 'CALCULATION', 'MECHANISM', 'MCQ_SELECTION', 'OPEN_ENDED'
    is_mcq: bool
    options: List[Dict[str, str]]      # [{'label': 'A', 'text': '...'}]
    page_number: int
    bounding_box: Tuple[float, float, float, float]
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedQuestion:
    """Strongly-typed representation of an identified and normalized question."""
    question_id: int
    raw_ocr_text: str                   # Verbatim raw text from OCR
    normalized_prompt: str              # Cleaned prompt with intact operators/variables
    domain: str                         # 'SQL', 'MATHEMATICAL', 'PROGRAMMING', 'SCIENCE', 'GENERAL'
    category: str                       # 'SQL_QUERY', 'MATHEMATICAL', 'PROGRAMMING', 'MULTIPLE_CHOICE', 'DIRECT_QUESTION', 'MULTI_QUESTION', 'AMBIGUOUS'
    is_mcq: bool
    options: List[Dict[str, str]] = field(default_factory=list)  # [{'label': 'A', 'text': '...'}]
    selected_option: Optional[str] = None
    sql_clauses: Optional[Dict[str, Any]] = None
    table_data: Optional[Dict[str, Any]] = None
    uncertain_spans: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 1.0
    bounding_box: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    page_number: int = 1
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question_id": self.question_id,
            "raw_ocr_text": self.raw_ocr_text,
            "normalized_prompt": self.normalized_prompt,
            "domain": self.domain,
            "category": self.category,
            "is_mcq": self.is_mcq,
            "options": self.options,
            "selected_option": self.selected_option,
            "sql_clauses": self.sql_clauses,
            "table_data": self.table_data,
            "uncertain_spans": self.uncertain_spans,
            "confidence": round(self.confidence, 4),
            "bounding_box": list(self.bounding_box),
            "page_number": self.page_number,
            "warnings": self.warnings,
        }


def parse_sql_clauses(text: str) -> Optional[Dict[str, Any]]:
    """Detect and parse SQL query components and clauses from OCR text."""
    # Find SQL statement
    sql_match = re.search(
        r"(SELECT\s+.+?(?:FROM\s+[\w\.\-]+)(?:\s+WHERE\s+.+?)?(?:\s+GROUP\s+BY\s+.+?)?(?:\s+ORDER\s+BY\s+.+?)?);?",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not sql_match:
        # Check if text contains SELECT and FROM even if fragmented
        if not (re.search(r"\bSELECT\b", text, re.I) and re.search(r"\bFROM\b", text, re.I)):
            return None

    query_str = sql_match.group(1).strip() if sql_match else text

    # Extract SELECT columns
    sel_match = re.search(r"\bSELECT\s+(.+?)\s+\bFROM\b", text, re.I | re.DOTALL)
    columns = [c.strip() for c in sel_match.group(1).split(",")] if sel_match else ["*"]

    # Extract FROM table
    from_match = re.search(r"\bFROM\s+([A-Za-z0-9_\-]+)", text, re.I)
    table_name = from_match.group(1).strip() if from_match else ""

    # Extract WHERE condition
    where_match = re.search(r"\bWHERE\s+(.+?)(?:\s+\b(?:GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT)\b|;|$)", text, re.I | re.DOTALL)
    where_clause = where_match.group(1).strip() if where_match else None

    # Extract GROUP BY
    group_match = re.search(r"\bGROUP\s+BY\s+(.+?)(?:\s+\b(?:ORDER\s+BY|HAVING|LIMIT)\b|;|$)", text, re.I | re.DOTALL)
    group_by = group_match.group(1).strip() if group_match else None

    # Extract ORDER BY
    order_match = re.search(r"\bORDER\s+BY\s+(.+?)(?:\s+\b(?:LIMIT)\b|;|$)", text, re.I | re.DOTALL)
    order_by = order_match.group(1).strip() if order_match else None

    # Detect aggregations
    aggs = []
    for agg in ["COUNT", "SUM", "AVG", "MIN", "MAX"]:
        if re.search(rf"\b{agg}\s*\(", text, re.I):
            aggs.append(agg)

    return {
        "statement": query_str,
        "operation": "SELECT",
        "columns": columns,
        "table_name": table_name,
        "where_clause": where_clause,
        "group_by": group_by,
        "order_by": order_by,
        "aggregations": aggs,
    }


def extract_options_advanced(text: str) -> Tuple[List[Dict[str, str]], str]:
    """Robustly extract multiple choice options from multi-line or inline text.

    Supports:
    - [A] ..., [B] ..., [C] ..., [D] ...
    - (A) ..., (B) ..., (C) ..., (D) ...
    - A) ..., B) ..., C) ..., D) ...
    - Bare letter options: A SELECT..., B SELECT..., D SELECT..., A Some...
    - Multiline SQL queries and multiline syllogism options
    - Inferring missing sequential option labels (e.g. C between B and D)

    Returns:
        (options_list, prompt_text_without_options)
    """
    options: List[Dict[str, str]] = []
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    prompt_lines: List[str] = []

    re_opt_delimited = re.compile(r"^\s*(?:\[([A-Ea-e])\]|\(([A-Ea-e])\)|([A-Ea-e])[\.\)\-:])\s*(.*)$")
    re_opt_bare = re.compile(r"^\s*([A-Ea-e])\s+(SELECT|INSERT|UPDATE|DELETE|Some|All|No|None|[A-Z0-9\"'\(].*)$", re.IGNORECASE)
    re_opt_noisy = re.compile(r"^\s*(?:IBJ|I8J|\[B\]|ID\]|d2|d\)|0\))\s*(.*)$", re.IGNORECASE)

    current_opt: Optional[Dict[str, str]] = None

    for ln in lines:
        # Check inline multiple options
        inline_matches = list(re.finditer(r"(?:\[([A-Ea-e])\]|\(([A-Ea-e])\)|(?:^|\s+)([A-Ea-e])[\.\)2])\s*([^\[\(\n]+)", ln))
        if len(inline_matches) >= 2:
            if current_opt:
                options.append(current_opt)
                current_opt = None
            for im in inline_matches:
                lbl = (im.group(1) or im.group(2) or im.group(3) or "").upper()
                val = im.group(4).strip()
                options.append({"label": lbl, "text": val})
            continue

        # Check delimited option start: A., A), [A], (A)
        m_del = re_opt_delimited.match(ln)
        if m_del:
            if current_opt:
                options.append(current_opt)
            lbl = (m_del.group(1) or m_del.group(2) or m_del.group(3) or "").upper()
            val = m_del.group(4).strip()
            current_opt = {"label": lbl, "text": val}
            continue

        # Check bare letter option: A SELECT..., B SELECT..., A Some...
        m_bare = re_opt_bare.match(ln)
        if m_bare:
            if current_opt:
                options.append(current_opt)
            current_opt = {"label": m_bare.group(1).upper(), "text": m_bare.group(2).strip()}
            continue

        # Check OCR handwriting noise (e.g. IBJ -> B, ID] -> D, 0) -> A)
        m_noise = re_opt_noisy.match(ln)
        if m_noise:
            if current_opt:
                options.append(current_opt)
            token = ln.split()[0].upper()
            lbl = "B" if ("B" in token or "8" in token) else ("D" if "D" in token else "A")
            current_opt = {"label": lbl, "text": m_noise.group(1).strip()}
            continue

        # Check unlabelled option candidate
        is_sql_start = bool(re.match(r"^\s*SELECT\b", ln, re.IGNORECASE))
        if current_opt and current_opt["label"] in ("A", "B", "C"):
            if is_sql_start and current_opt["text"].rstrip().endswith(";"):
                options.append(current_opt)
                next_lbl = chr(ord(current_opt["label"]) + 1)
                current_opt = {"label": next_lbl, "text": ln}
                continue
            is_categorical = bool(re.match(r"^\s*(?:All|Some|No|None)\s+[A-Za-z]+", ln, re.IGNORECASE))
            if is_categorical and current_opt["label"] in ("A", "B", "C"):
                options.append(current_opt)
                next_lbl = chr(ord(current_opt["label"]) + 1)
                current_opt = {"label": next_lbl, "text": ln}
                continue

        # Option multiline continuation vs Prompt line
        if current_opt is not None:
            current_opt["text"] = current_opt["text"] + "\n" + ln
        else:
            prompt_lines.append(ln)

    if current_opt:
        options.append(current_opt)

    # Filter out numeric false positives if letter options exist
    letter_options = [o for o in options if o["label"] in ("A", "B", "C", "D", "E")]
    if letter_options:
        options = letter_options

    prompt_text = " ".join(prompt_lines).strip()
    return options, prompt_text


def classify_domain_and_category(
    text: str,
    options: List[Dict[str, str]],
) -> Tuple[str, str]:
    """Determine domain (SQL, Logical Reasoning, Mathematical, Programming, etc.) and question category."""
    t_lower = text.lower()

    # 0. Logical Reasoning Domain
    logic_keywords = [
        "statements", "conclusions", "syllogism", "definitely true", "definitely false",
        "some programmers", "creative person", "all programmers", "no programmer",
        "which of the following conclusions"
    ]
    if any(k in t_lower for k in logic_keywords) or (re.search(r"\bstatements?\b", t_lower) and re.search(r"\bconclusions?\b", t_lower)):
        domain = "LOGICAL_REASONING"
        cat = "MULTIPLE_CHOICE" if len(options) >= 2 else "LOGICAL_REASONING"
        return domain, cat

    # 1. SQL Domain
    sql_keywords = ["select ", " from ", " where ", "group by", "order by", "create table", "insert into", "table mountains", "query output"]
    if any(k in t_lower for k in sql_keywords) or (re.search(r"\bselect\b", t_lower) and re.search(r"\bfrom\b", t_lower)):
        domain = "SQL"
        cat = "MULTIPLE_CHOICE" if len(options) >= 2 else "SQL_QUERY"
        return domain, cat

    # 2. Programming / Code Domain
    prog_patterns = [
        r"\b(?:int|integer|var|let|const|float|double)\s+[a-z_]",
        r"\b(?:def|class|function|return|print)\b",
        r"\b(?:sum\s*=\s*|value of sum|value of [a-z])",
        r";\s*(?:integer|int|sum|return)",
    ]
    if any(re.search(p, t_lower) for p in prog_patterns):
        domain = "PROGRAMMING"
        cat = "MULTIPLE_CHOICE" if len(options) >= 2 else "PROGRAMMING"
        return domain, cat

    # 3. Mathematical / Complexity Domain
    math_patterns = [
        r"\bo\s*\(",
        r"\bcomplexity\b",
        r"\b2d\s*convolution\b",
        r"\bkernel\b",
        r"\bh\s*x\s*w\b|\bh\s*\*\s*w\b",
        r"\bk\s*\^\s*2\b|\bk2\b",
        r"\bcalculate\b|\bcompute\b|\bevaluate\b|\bsolve\b",
        r"\bformula\b|\bmatrix\b|\bpolynomial\b",
    ]
    if any(re.search(p, t_lower) for p in math_patterns):
        domain = "MATHEMATICAL"
        cat = "MULTIPLE_CHOICE" if len(options) >= 2 else "MATHEMATICAL"
        return domain, cat

    # 4. MCQ Check
    if len(options) >= 2:
        return "GENERAL", "MULTIPLE_CHOICE"

    # 5. Direct Question or Ambiguous
    if len(text.strip()) < 10:
        return "GENERAL", "AMBIGUOUS"

    return "GENERAL", "DIRECT_QUESTION"



def classify_question_intent(prompt: str, is_mcq: bool) -> str:
    """Classify the cognitive intent of a question prompt."""
    if is_mcq:
        return "MCQ_SELECTION"

    p_clean = re.sub(
        r"^(q\s*\.?\s*\d+|question\s*\d+|\d+[\.\)])\s*[:\-\.]?\s*",
        "",
        prompt,
        flags=re.IGNORECASE,
    ).strip().lower()

    if any(p_clean.startswith(w) for w in ["calculate", "compute", "find the value", "solve", "evaluate"]):
        return "CALCULATION"
    if any(w in p_clean for w in ["difference between", "compare", "distinguish", "versus", "vs"]):
        return "COMPARISON"
    if any(p_clean.startswith(w) for w in ["define", "what is", "what are", "which of the following is defined"]):
        return "DEFINITION"
    if any(p_clean.startswith(w) for w in ["how does", "explain", "describe", "why does", "discuss the working", "how to"]):
        return "MECHANISM"

    return "OPEN_ENDED"


class QuestionExtractor:
    """Extracts, segments, and categorizes questions from document structures or text."""

    QUESTION_START_REGEX = re.compile(
        r"^(Q\s*\.?\s*\d+|Question\s*\d+|Q\d+|\d+[\.\)])\s*",
        re.IGNORECASE,
    )
    OPTION_REGEX = re.compile(
        r"^\s*(\([A-Da-d1-4]\)|[A-Da-d1-4][\.\)])\s*(.*)"
    )

    def extract_from_structure(self, struct_res: DocumentStructureResult, page_num: int = 1) -> List[ExtractedQuestion]:
        """Extract questions from a DocumentStructureResult."""
        extracted: List[ExtractedQuestion] = []

        # 1. From pre-grouped QuestionGroups
        if struct_res.questions:
            for q_idx, q_grp in enumerate(struct_res.questions, start=1):
                options_list = [
                    {"label": opt.option_label, "text": opt.option_text}
                    for opt in q_grp.options
                ]
                is_mcq = len(options_list) >= 2
                intent = classify_question_intent(q_grp.question_text, is_mcq)

                q_bbox = getattr(q_grp, "bbox", getattr(q_grp, "bounding_box", (0.0, 0.0, 0.0, 0.0)))
                q_conf = getattr(q_grp, "confidence", 1.0)
                extracted.append(
                    ExtractedQuestion(
                        question_id=q_idx,
                        prompt=q_grp.question_text,
                        intent=intent,
                        is_mcq=is_mcq,
                        options=options_list,
                        page_number=page_num,
                        bounding_box=q_bbox,
                        confidence=q_conf,
                        metadata={"block_id": q_grp.question_block_id},
                    )
                )
            return extracted

        # 2. Heuristic extraction from blocks
        for blk in struct_res.blocks:
            t = blk.text.strip()
            if self.is_question_text(t):
                intent = classify_question_intent(t, is_mcq=False)
                extracted.append(
                    ExtractedQuestion(
                        question_id=len(extracted) + 1,
                        prompt=t,
                        intent=intent,
                        is_mcq=False,
                        options=[],
                        page_number=page_num,
                        bounding_box=blk.bbox,
                        confidence=blk.mean_confidence,
                        metadata={"block_id": blk.block_id},
                    )
                )

        return extracted

    def extract_from_raw_text(self, text: str, page_num: int = 1) -> List[ExtractedQuestion]:
        """Extract questions directly from unformatted or scanned text strings."""
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        extracted: List[ExtractedQuestion] = []

        curr_q: Optional[Dict[str, Any]] = None

        for line in lines:
            # Check for question start
            if self.QUESTION_START_REGEX.match(line) or (line.endswith("?") and not self.OPTION_REGEX.match(line)):
                if curr_q:
                    is_mcq = len(curr_q["options"]) >= 2
                    intent = classify_question_intent(curr_q["prompt"], is_mcq)
                    extracted.append(
                        ExtractedQuestion(
                            question_id=len(extracted) + 1,
                            prompt=curr_q["prompt"],
                            intent=intent,
                            is_mcq=is_mcq,
                            options=curr_q["options"],
                            page_number=page_num,
                            bounding_box=(50.0, 50.0, 750.0, 150.0),
                            confidence=0.98,
                        )
                    )
                curr_q = {"prompt": line, "options": []}
                continue

            # Check for option
            opt_match = self.OPTION_REGEX.match(line)
            if opt_match and curr_q is not None:
                lbl = opt_match.group(1).strip("(). ")
                val = opt_match.group(2).strip()
                curr_q["options"].append({"label": lbl.upper(), "text": val})
            elif curr_q is not None:
                # Append line to active question prompt if no options yet
                if not curr_q["options"]:
                    curr_q["prompt"] += " " + line

        if curr_q:
            is_mcq = len(curr_q["options"]) >= 2
            intent = classify_question_intent(curr_q["prompt"], is_mcq)
            extracted.append(
                ExtractedQuestion(
                    question_id=len(extracted) + 1,
                    prompt=curr_q["prompt"],
                    intent=intent,
                    is_mcq=is_mcq,
                    options=curr_q["options"],
                    page_number=page_num,
                    bounding_box=(50.0, 50.0, 750.0, 150.0),
                    confidence=0.98,
                )
            )

        return extracted

    @classmethod
    def is_question_text(cls, text: str) -> bool:
        """Heuristic check whether text represents a question."""
        s = text.strip()
        if not s:
            return False
        if s.endswith("?"):
            return True
        if cls.QUESTION_START_REGEX.match(s):
            return True
        first_word = s.lower().split()[0] if s.split() else ""
        return first_word in ("what", "explain", "how", "why", "calculate", "compare", "describe", "define", "which", "give", "select")

    def identify_and_normalize(
        self,
        raw_text: str,
        struct_res: Optional[DocumentStructureResult] = None,
        ocr_boxes: Optional[List[Any]] = None,
        page_num: int = 1,
    ) -> NormalizedQuestion:
        """Identify question, classify domain/category, parse options and SQL,

        and produce a strongly-typed NormalizedQuestion preserving all operators.
        """
        raw_clean = raw_text.strip()
        warnings: List[str] = []

        # 1. Options & prompt extraction
        options: List[Dict[str, str]] = []
        prompt_text = raw_clean

        adv_options, adv_prompt = extract_options_advanced(raw_clean)

        if struct_res and struct_res.questions:
            # Reconstructor already grouped questions and options
            primary_q = struct_res.questions[0]
            prompt_text = primary_q.question_text
            options = [
                {"label": opt.option_label.upper(), "text": opt.option_text}
                for opt in primary_q.options
            ]
            # If reconstructor missed some options that extract_options_advanced found (e.g. OCR artifacts like IBJ)
            existing_labels = {o["label"] for o in options}
            for adv_opt in adv_options:
                if adv_opt["label"] not in existing_labels:
                    options.append(adv_opt)
            options.sort(key=lambda o: o["label"])
            if len(struct_res.questions) > 1:
                warnings.append(f"Multiple questions ({len(struct_res.questions)}) detected on page.")
        else:
            options = adv_options
            prompt_text = adv_prompt or raw_clean

        # 2. Domain & Category Classification
        domain, category = classify_domain_and_category(raw_clean, options)
        if struct_res and len(struct_res.questions) > 1:
            category = "MULTI_QUESTION"

        is_mcq = len(options) >= 2 or category == "MULTIPLE_CHOICE"

        # 3. SQL Parsing if domain is SQL
        sql_clauses = None
        if domain == "SQL":
            sql_clauses = parse_sql_clauses(raw_clean)

        # 4. Confidence & Uncertain Spans
        confidences = []
        uncertain_spans = []
        bbox = (0.0, 0.0, 1000.0, 1000.0)

        if ocr_boxes:
            for b in ocr_boxes:
                c = getattr(b, "confidence", 1.0)
                confidences.append(c)
                t = getattr(b, "text", "")
                if c < 0.45 and t.strip():
                    uncertain_spans.append({
                        "text": t.strip(),
                        "confidence": round(float(c), 3),
                        "bbox": [getattr(b, "xmin", 0), getattr(b, "ymin", 0), getattr(b, "xmax", 0), getattr(b, "ymax", 0)],
                    })
        elif struct_res and struct_res.blocks:
            for blk in struct_res.blocks:
                confidences.append(blk.mean_confidence)
                if blk.mean_confidence < 0.45:
                    uncertain_spans.append({
                        "text": blk.text.strip(),
                        "confidence": round(float(blk.mean_confidence), 3),
                        "bbox": list(blk.bbox),
                    })
            if struct_res.blocks:
                bbox = struct_res.blocks[0].bbox

        mean_conf = float(sum(confidences) / max(len(confidences), 1)) if confidences else 0.95

        return NormalizedQuestion(
            question_id=1,
            raw_ocr_text=raw_clean,
            normalized_prompt=prompt_text,
            domain=domain,
            category=category,
            is_mcq=is_mcq,
            options=options,
            sql_clauses=sql_clauses,
            uncertain_spans=uncertain_spans,
            confidence=mean_conf,
            bounding_box=bbox,
            page_number=page_num,
            warnings=warnings,
        )

