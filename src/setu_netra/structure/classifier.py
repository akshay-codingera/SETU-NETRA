"""
classifier.py: Rule-based classification of lines and blocks into structural document roles.

Why this file exists:
In academic and real-world documents, structural components (headings, questions, options,
lists, notes, and continuous paragraphs) exhibit recognizable linguistic markers, punctuation,
and geometry. We classify these using deterministic, lightweight pattern rules without
black-box AI or LLMs.
"""

import re
from typing import Optional, Tuple
from setu_netra.core.contracts import BlockType


# ------------------------------------------------------------------------------
# Pattern Definitions
# ------------------------------------------------------------------------------

# Bracketed option: [A], [B], (A), (b), [1], (1)
RE_OPTION_BRACKET = re.compile(
    r"^\s*(?:\[(?P<lbl1>[A-Da-d0-9])\]|\((?P<lbl2>[A-Da-d0-9])\))\s*(?P<rest>.*)$",
    re.DOTALL,
)

# Delimited letter option: A., B), c-, D:
RE_OPTION_DELIMITED = re.compile(
    r"^\s*(?P<lbl>[A-Ea-e])[\.\)\-:]\s*(?P<rest>.*)$",
    re.DOTALL,
)

# Bare letter option: A SELECT..., B SELECT..., A Some..., D All...
RE_OPTION_BARE = re.compile(
    r"^\s*(?P<lbl>[A-Ea-e])\s+(?P<rest>(?:SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|Some|All|No|None|[A-Z0-9\"'\(]).*)$",
    re.DOTALL | re.IGNORECASE,
)

# SQL statement start keywords
RE_SQL_STATEMENT_START = re.compile(
    r"^\s*(?:[A-Ea-e][\.\)\s]\s*)?(?:SELECT|INSERT\s+INTO|UPDATE|DELETE\s+FROM|CREATE\s+TABLE|ALTER\s+TABLE|DROP\s+TABLE|WITH)\b",
    re.IGNORECASE | re.DOTALL,
)

# Common OCR noise patterns for option labels:
# e.g., 'IDJ' or '1DJ' -> [D]
RE_OPTION_OCR_IDJ = re.compile(
    r"^\s*(?:ID[Jj]|1D[Jj]|\[DJ|ID\])\s*(?P<rest>.*)$",
    re.DOTALL,
)
# e.g., 'd2' or 'd)' -> d)
RE_OPTION_OCR_D2 = re.compile(
    r"^\s*d[2\)]\s*(?P<rest>.*)$",
    re.DOTALL,
)
# e.g., '()' or '0)' or 'C)' -> c)
RE_OPTION_OCR_PAREN_EMPTY = re.compile(
    r"^\s*(?:\(\)|0\)|O\))\s*(?P<rest>.*)$",
    re.DOTALL,
)

# Explicit question prefix: Q.1), Question 2:, Q1:
RE_QUESTION_EXPLICIT = re.compile(
    r"^\s*(?:Q(?:uestion)?\.?\s*(?P<num>\d+)?[:\.\)]\s*)(?P<rest>.*)$",
    re.IGNORECASE,
)

# Numbered prefix: 1., 2), 3:
RE_NUMBERED_PREFIX = re.compile(
    r"^\s*(?P<num>\d+)[\.\)\-:]\s+(?P<rest>.*)$"
)

# Bullet list prefix: -, *, •, +, >, ~
RE_BULLET_PREFIX = re.compile(
    r"^\s*[\u2022\u25E6\u2023\u25AA\-\*\+\>\~]\s+(?P<rest>.*)$"
)

# Note prefix: Note:, NOTE:, NB:, Remark:, Remarks:, Assume:
RE_NOTE_PREFIX = re.compile(
    r"^\s*(?:Note|NOTE|NB|Notice|Remark|Remarks|Assume|Disclaimer)[:\.\-]\s*(?P<rest>.*)$",
    re.IGNORECASE,
)

# Interrogative starter words
QUESTION_STARTER_WORDS = (
    "what",
    "who",
    "which",
    "where",
    "when",
    "why",
    "how",
    "explain",
    "find",
    "compute",
    "calculate",
    "solve",
    "determine",
    "define",
    "state",
    "choose",
    "select",
    "identify",
    "koh",  # Frequent OCR misread for 'Who'
    "wh0",
)

# Header keyword indicators
HEADING_KEYWORDS = (
    "test bench",
    "sample question",
    "examination",
    "section",
    "chapter",
    "instructions",
    "header",
    "title",
    "setu-netra",
)


def match_option_pattern(text: str) -> Optional[Tuple[str, str]]:
    """Check if the text begins with a multiple-choice option marker.

    Returns:
        (normalized_label, remainder_text) or None if not an option.
    """
    cleaned = text.strip()
    if not cleaned:
        return None

    # Check bracketed [A] or (A)
    m = RE_OPTION_BRACKET.match(cleaned)
    if m:
        lbl = m.group("lbl1") or m.group("lbl2")
        return (lbl.upper(), m.group("rest").strip())

    # Check delimited letter A. or B)
    m = RE_OPTION_DELIMITED.match(cleaned)
    if m:
        return (m.group("lbl").upper(), m.group("rest").strip())

    # Check bare letter option: A SELECT..., B SELECT..., A Some...
    m_bare = RE_OPTION_BARE.match(cleaned)
    if m_bare:
        return (m_bare.group("lbl").upper(), m_bare.group("rest").strip())

    # Check OCR noise for [D]
    m = RE_OPTION_OCR_IDJ.match(cleaned)
    if m:
        return ("D", m.group("rest").strip())

    # Check OCR noise for d) / d2
    m = RE_OPTION_OCR_D2.match(cleaned)
    if m:
        return ("D", m.group("rest").strip())

    # Check OCR noise for c) -> '()' or '0)'
    m = RE_OPTION_OCR_PAREN_EMPTY.match(cleaned)
    if m:
        return ("C", m.group("rest").strip())

    return None


def match_note_pattern(text: str) -> Optional[str]:
    """Check if text begins with a note/remark indicator."""
    m = RE_NOTE_PREFIX.match(text.strip())
    if m:
        return m.group("rest").strip()
    return None


def match_list_pattern(text: str) -> Optional[Tuple[str, str]]:
    """Check if text begins with a bullet or numbered list marker.

    Returns:
        (bullet_or_number, remainder_text) or None
    """
    cleaned = text.strip()
    # Check bullet list
    m_bullet = RE_BULLET_PREFIX.match(cleaned)
    if m_bullet:
        return ("•", m_bullet.group("rest").strip())

    # Check numbered list
    m_num = RE_NUMBERED_PREFIX.match(cleaned)
    if m_num:
        return (m_num.group("num"), m_num.group("rest").strip())

    return None


def is_interrogative_sentence(text: str) -> bool:
    """Check if text contains question-asking terminology or ends with a question mark."""
    cleaned = text.strip()
    if not cleaned:
        return False

    # Check terminal question mark
    if cleaned.endswith("?") or "?" in cleaned[-4:]:
        return True

    # Check starter words
    first_word = cleaned.split()[0].lower().rstrip(":,.-") if cleaned.split() else ""
    if first_word in QUESTION_STARTER_WORDS:
        return True

    return False


def is_sql_statement_start(text: str) -> bool:
    """Check if the text represents the beginning of an SQL statement."""
    cleaned = text.strip()
    if not cleaned:
        return False
    return bool(RE_SQL_STATEMENT_START.search(cleaned))


def is_heading_candidate(text: str, line_height: float, median_line_height: float) -> bool:
    """Determine whether a line resembles a document title or section heading."""
    cleaned = text.strip()
    if not cleaned:
        return False

    # Questions ending with '?' or containing question marks are NOT headings
    if cleaned.endswith("?") or "?" in cleaned[-4:]:
        return False

    # SQL statements or clauses are NEVER headings
    if is_sql_statement_start(cleaned):
        return False
    words_upper = [w.strip("(),;._") for w in cleaned.upper().split()]
    if any(k in words_upper for k in ("SELECT", "FROM", "WHERE", "GROUP", "HAVING", "ORDER", "COUNT", "STUDENT", "STUDENTS")):
        return False

    # Lowercase starts are continuation clauses, not headings
    if cleaned[0].islower() and not cleaned.startswith(("q", "a")):
        return False

    lower_text = cleaned.lower()

    # Contains prominent header keywords
    for kw in HEADING_KEYWORDS:
        if kw in lower_text:
            return True

    # Significantly larger font than body text
    if line_height >= 1.35 * median_line_height and len(cleaned) < 80:
        return True

    # All-caps line with multiple words (e.g., "GENERAL INSTRUCTIONS")
    words = [w for w in cleaned.split() if w.isalpha()]
    if len(words) >= 2 and all(w.isupper() for w in words) and len(cleaned) < 60:
        if not cleaned.endswith((".", ":", ";")):
            return True

    return False


def classify_line_or_block(
    text: str,
    line_height: float,
    median_line_height: float,
    mean_confidence: float,
    has_preceding_question: bool = False,
) -> Tuple[str, dict, list[str]]:
    """Classify the structural role of a line or block of text.

    Args:
        text: Reconstructed text string.
        line_height: Height of the line/block in pixels.
        median_line_height: Median line height across the document.
        mean_confidence: Normalized OCR confidence [0.0, 1.0].
        has_preceding_question: True if an unresolved question was encountered above.

    Returns:
        (block_type, role_metadata, warnings)
    """
    cleaned = text.strip()
    warnings: list[str] = []
    metadata: dict = {}

    # Degenerate or low confidence detection
    if not cleaned or mean_confidence < 0.25:
        warnings.append("low_confidence_detection")
        return BlockType.UNCLASSIFIED, metadata, warnings

    # 1. Note / Disclaimer
    note_content = match_note_pattern(cleaned)
    if note_content is not None:
        metadata["note_body"] = note_content
        return BlockType.NOTE, metadata, warnings

    # 2. Answer Option
    option_match = match_option_pattern(cleaned)
    if option_match is not None:
        lbl, opt_text = option_match
        metadata["option_label"] = lbl
        metadata["option_text"] = opt_text
        return BlockType.OPTION, metadata, warnings

    # 2B. SQL Code Statement (unlabelled query)
    if is_sql_statement_start(cleaned):
        metadata["language"] = "sql"
        return BlockType.CODE, metadata, warnings

    # 3. Explicit Question (e.g., Q1: or Question 2.)
    m_q_explicit = RE_QUESTION_EXPLICIT.match(cleaned)
    if m_q_explicit:
        num = m_q_explicit.group("num")
        if num:
            metadata["question_number"] = num
        return BlockType.QUESTION, metadata, warnings

    # 4. Numbered Prefix (e.g., 1. or 2))
    # Distinguish between numbered question vs. numbered list item!
    m_num = RE_NUMBERED_PREFIX.match(cleaned)
    if m_num:
        num = m_num.group("num")
        rest = m_num.group("rest")
        if is_interrogative_sentence(rest) or is_interrogative_sentence(cleaned):
            metadata["question_number"] = num
            return BlockType.QUESTION, metadata, warnings
        else:
            # Declarative numbered item
            metadata["list_index"] = num
            return BlockType.LIST_ITEM, metadata, warnings

    # 5. Bullet List
    m_bullet = RE_BULLET_PREFIX.match(cleaned)
    if m_bullet:
        metadata["bullet_type"] = "•"
        return BlockType.LIST_ITEM, metadata, warnings

    # 6. Unnumbered Question (checked before Heading so interrogatives are never treated as titles)
    if is_interrogative_sentence(cleaned):
        return BlockType.QUESTION, metadata, warnings

    # 7. Heading / Title
    if is_heading_candidate(cleaned, line_height, median_line_height):
        return BlockType.HEADING, metadata, warnings

    # 8. Implicit option under an active question (e.g. unlabelled option list or entity name)
    # If the user has a question followed by options, but an option label was dropped by OCR
    # (e.g., "Rahul Gandhi" immediately under a question without 'a)' label)
    if has_preceding_question and len(cleaned.split()) <= 4 and not cleaned.endswith((".", ":", ";")):
        # Mark as candidate option or paragraph with warning
        metadata["possible_unlabelled_option"] = True

    # 9. Default: Continuous Paragraph
    return BlockType.PARAGRAPH, metadata, warnings
