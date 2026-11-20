"""
contracts.py: Explicit data models (contracts) for SETU-NETRA.

Why this file exists:
In a modular architecture, components must communicate through well-defined,
strongly-typed data structures rather than ad-hoc dictionaries or global variables.
This prevents subtle runtime errors and decouples the modules.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class ImageMetadata:
    """Immutable metadata describing an ingested image."""

    file_path: Path
    file_name: str
    file_size_bytes: int
    format: str            # e.g., 'JPEG', 'PNG', 'WEBP'
    color_mode: str        # e.g., 'RGB', 'RGBA', 'L' (Grayscale), 'CMYK'
    width: int             # in pixels
    height: int            # in pixels
    channels: int          # 1 for grayscale, 3 for RGB, 4 for RGBA
    estimated_memory_bytes: int  # Uncompressed raster buffer size in RAM
    exif_orientation: Optional[int] = None  # EXIF Orientation Tag (1-8) if present

    @property
    def resolution_mp(self) -> float:
        """Resolution in megapixels."""
        return round((self.width * self.height) / 1_000_000, 2)

    @property
    def aspect_ratio(self) -> float:
        """Aspect ratio (width / height)."""
        return round(self.width / max(self.height, 1), 3)


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of validating an input file before opening or processing."""

    is_valid: bool
    error_message: Optional[str] = None
    file_path: Optional[Path] = None


@dataclass(frozen=True)
class PreprocessConfig:
    """Configuration options for image preprocessing.

    Keeping parameters in a dedicated configuration class allows easy
    experimentation without modifying pipeline logic.
    """

    convert_grayscale: bool = True
    max_dimension: Optional[int] = 1600  # Downscale if width or height exceeds this
    resample_filter: str = "LANCZOS"     # LANCZOS, BICUBIC, BILINEAR, NEAREST
    contrast_factor: float = 1.3         # 1.0 is original, >1.0 increases contrast
    auto_orient: bool = True             # Correct EXIF rotation


@dataclass
class ProcessedImageResult:
    """Container for the output of the preprocessing pipeline."""

    original_metadata: ImageMetadata
    processed_metadata: ImageMetadata
    steps_applied: List[str] = field(default_factory=list)
    output_path: Optional[Path] = None


# ==============================================================================
# Milestone 2: OCR Contracts & Data Structures
# ==============================================================================

@dataclass(frozen=True)
class OCRBox:
    """Represents a single detected and recognized text region.

    Attributes:
        polygon: Quadrilateral vertices [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
                 ordered clockwise: top-left, top-right, bottom-right, bottom-left.
        text: Decoded unicode string recognized within this region.
        confidence: Normalized confidence probability in range [0.0, 1.0].
    """

    polygon: Tuple[Tuple[float, float], ...]
    text: str
    confidence: float

    @property
    def xmin(self) -> float:
        return min(p[0] for p in self.polygon) if self.polygon else 0.0

    @property
    def ymin(self) -> float:
        return min(p[1] for p in self.polygon) if self.polygon else 0.0

    @property
    def xmax(self) -> float:
        return max(p[0] for p in self.polygon) if self.polygon else 0.0

    @property
    def ymax(self) -> float:
        return max(p[1] for p in self.polygon) if self.polygon else 0.0

    @property
    def width(self) -> float:
        return max(0.0, self.xmax - self.xmin)

    @property
    def height(self) -> float:
        return max(0.0, self.ymax - self.ymin)

    @property
    def center(self) -> Tuple[float, float]:
        return (self.xmin + self.width / 2.0, self.ymin + self.height / 2.0)


@dataclass(frozen=True)
class OCRConfig:
    """Configuration options for OCR inference."""

    engine_name: str = "easyocr"         # 'easyocr', 'mock', 'paddleocr'
    languages: Tuple[str, ...] = ("en",)  # Language codes
    use_gpu: bool = False                # Forced CPU execution for laptop compatibility
    confidence_threshold: float = 0.20   # Ignore detections below this confidence
    detail: int = 1                      # 1: returns boxes and confidences; 0: text only
    add_margin: float = 0.10             # Margin added around detected bounding boxes
    mag_ratio: float = 1.0               # Image magnification factor during detection
    text_threshold: float = 0.70         # CRAFT text confidence threshold
    low_text: float = 0.40               # CRAFT low-bound text score
    link_threshold: float = 0.40         # CRAFT character affinity link threshold
    paragraph: bool = False              # Group nearby bounding boxes into paragraph lines


@dataclass
class OCRResult:
    """Structured result returned by an OCR engine."""

    engine_name: str
    engine_version: str
    boxes: List[OCRBox] = field(default_factory=list)
    raw_text: str = ""
    processing_time_ms: float = 0.0
    status: str = "SUCCESS"              # 'SUCCESS', 'EMPTY', 'FAILED'
    error_message: Optional[str] = None


# ==============================================================================
# Milestone 3: Document Structure Reconstruction Contracts
# ==============================================================================

class BlockType:
    """Document block structural role types."""

    HEADING = "HEADING"
    QUESTION = "QUESTION"
    OPTION = "OPTION"
    CODE = "CODE"
    TABLE = "TABLE"
    LIST_ITEM = "LIST_ITEM"
    NOTE = "NOTE"
    PARAGRAPH = "PARAGRAPH"
    UNCLASSIFIED = "UNCLASSIFIED"


@dataclass(frozen=True)
class ReconstructedLine:
    """Represents a horizontally unified line of text reconstructed from OCR boxes."""

    text: str
    box_indices: Tuple[int, ...]
    bbox: Tuple[float, float, float, float]  # (xmin, ymin, xmax, ymax)
    mean_confidence: float
    min_confidence: float
    words: Tuple[str, ...] = field(default_factory=tuple)
    confidences: Tuple[float, ...] = field(default_factory=tuple)

    @property
    def xmin(self) -> float:
        return self.bbox[0]

    @property
    def ymin(self) -> float:
        return self.bbox[1]

    @property
    def xmax(self) -> float:
        return self.bbox[2]

    @property
    def ymax(self) -> float:
        return self.bbox[3]

    @property
    def width(self) -> float:
        return max(0.0, self.xmax - self.xmin)

    @property
    def height(self) -> float:
        return max(0.0, self.ymax - self.ymin)

    @property
    def center(self) -> Tuple[float, float]:
        return (self.xmin + self.width / 2.0, self.ymin + self.height / 2.0)


@dataclass(frozen=True)
class DocumentBlock:
    """Represents a coherent structural section (e.g., question, paragraph, option)."""

    block_id: int
    block_type: str                  # Value from BlockType
    text: str
    lines: Tuple[ReconstructedLine, ...]
    bbox: Tuple[float, float, float, float]  # (xmin, ymin, xmax, ymax)
    mean_confidence: float
    min_confidence: float
    source_detection_indices: Tuple[int, ...]
    role_metadata: dict = field(default_factory=dict)
    warnings: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def xmin(self) -> float:
        return self.bbox[0]

    @property
    def ymin(self) -> float:
        return self.bbox[1]

    @property
    def xmax(self) -> float:
        return self.bbox[2]

    @property
    def ymax(self) -> float:
        return self.bbox[3]

    @property
    def width(self) -> float:
        return max(0.0, self.xmax - self.xmin)

    @property
    def height(self) -> float:
        return max(0.0, self.ymax - self.ymin)


@dataclass(frozen=True)
class QuestionOption:
    """Represents an answer option associated with a question entity."""

    option_label: str                # e.g., 'A', 'B', '1', 'a'
    option_text: str
    block_id: int
    confidence: float
    bbox: Tuple[float, float, float, float]


@dataclass(frozen=True)
class QuestionGroup:
    """Represents a question entity along with its associated answer options."""

    question_block_id: int
    question_text: str
    question_number: Optional[str] = None
    options: Tuple[QuestionOption, ...] = field(default_factory=tuple)
    bbox: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    warnings: Tuple[str, ...] = field(default_factory=tuple)


@dataclass
class DocumentStructureResult:
    """Structured output produced by the document reconstruction engine."""

    blocks: List[DocumentBlock] = field(default_factory=list)
    questions: List[QuestionGroup] = field(default_factory=list)
    raw_transcript: str = ""
    reading_order_box_indices: List[int] = field(default_factory=list)
    processing_time_ms: float = 0.0
    status: str = "SUCCESS"          # 'SUCCESS', 'EMPTY', 'PARTIAL'
    warnings: List[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


# ==============================================================================
# Milestone 4: Semantic Understanding & Domain Classification Contracts
# ==============================================================================

class QuestionIntent:
    """Classified communicative intent of a question."""

    DEFINITION = "DEFINITION"
    EXPLANATION = "EXPLANATION"
    COMPARISON = "COMPARISON"
    CALCULATION = "CALCULATION"
    DERIVATION = "DERIVATION"
    PROOF = "PROOF"
    CLASSIFICATION = "CLASSIFICATION"
    PREDICTION = "PREDICTION"
    IDENTIFICATION = "IDENTIFICATION"
    COMPLEXITY_ANALYSIS = "COMPLEXITY_ANALYSIS"
    CODE_GENERATION = "CODE_GENERATION"
    DEBUGGING = "DEBUGGING"
    EVALUATION = "EVALUATION"
    SUMMARIZATION = "SUMMARIZATION"
    MULTIPLE_CHOICE_SELECTION = "MULTIPLE_CHOICE_SELECTION"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class TechnicalLevel:
    """Estimated technical depth of academic content."""

    INTRODUCTORY = "INTRODUCTORY"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"
    RESEARCH_ORIENTED = "RESEARCH_ORIENTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class DomainCandidate:
    """Candidate domain match with similarity score and hierarchy."""

    domain_id: str
    domain_name: str
    hierarchy_path: Tuple[str, ...]
    similarity_score: float
    is_primary: bool = False
    evidence_terms: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ExtractedConcept:
    """Concept extracted from text with normalization and span."""

    text: str
    normalized_form: str
    concept_type: str                # e.g., 'ALGORITHM', 'METRIC', 'VARIABLE', 'TERM'
    span: Optional[Tuple[int, int]] = None
    confidence: float = 1.0


@dataclass(frozen=True)
class ExtractedEntity:
    """Named entity or mathematical quantity extracted from text."""

    text: str
    entity_type: str                 # e.g., 'MATH_SYMBOL', 'VARIABLE', 'LOCATION', 'NAME'
    attributes: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ConceptRelationship:
    """Typed semantic relationship connecting two concepts."""

    source: str
    relation: str                    # e.g., 'OPERATES_ON', 'PARAMETERIZED_BY', 'MEASURES'
    target: str


@dataclass(frozen=True)
class DisambiguationDetail:
    """Contextual sense disambiguation record for an ambiguous term."""

    term: str
    resolved_sense: str
    confidence: float
    candidate_senses: Tuple[str, ...]
    context_cues: Tuple[str, ...]


@dataclass(frozen=True)
class RetrievedKnowledgeItem:
    """Optional reference passage retrieved from local knowledge sources."""

    source_id: str
    title: str
    passage: str
    similarity_score: float


@dataclass(frozen=True)
class SemanticItemAnalysis:
    """Semantic analysis of a single question or document block."""

    source_id: str                   # e.g., 'question-1' or 'block-2'
    original_text: str
    normalized_text: Optional[str]
    primary_domain: Optional[str]
    domains: Tuple[DomainCandidate, ...]
    primary_topic: Optional[str]
    secondary_topics: Tuple[str, ...]
    concepts: Tuple[ExtractedConcept, ...]
    entities: Tuple[ExtractedEntity, ...]
    relationships: Tuple[ConceptRelationship, ...]
    question_intents: Tuple[str, ...]
    technical_level: str
    ambiguities: Tuple[DisambiguationDetail, ...]
    warnings: Tuple[str, ...]
    retrieved_knowledge: Tuple[RetrievedKnowledgeItem, ...]
    classification_method: str
    status: str                      # 'ANALYZED', 'AMBIGUOUS', 'INSUFFICIENT_EVIDENCE', 'UNKNOWN_DOMAIN'


@dataclass
class SemanticAnalysisResult:
    """Complete semantic analysis result for a document."""

    items: List[SemanticItemAnalysis] = field(default_factory=list)
    document_domains: List[str] = field(default_factory=list)
    processing_time_ms: float = 0.0
    embedding_engine: str = "offline_semantic_tfidf"
    status: str = "SUCCESS"          # 'SUCCESS', 'PARTIAL', 'FAILED'
    warnings: List[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


# ==============================================================================
# Milestone 5: Persistent Document Store & Context Retrieval Contracts
# ==============================================================================

@dataclass(frozen=True)
class StoredDocument:
    """Represents an ingested document persisted in the document store."""

    doc_id: str
    file_path: Path
    file_name: str
    file_hash: str
    page_count: int
    created_at: str
    status: str = "PROCESSED"
    metadata: dict = field(default_factory=dict)
    workspace_id: str = "default"


@dataclass(frozen=True)
class DocumentPageRecord:
    """Represents a single page within an ingested document."""

    page_id: str
    doc_id: str
    page_number: int
    width: int
    height: int
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievedPassage:
    """Represents an evidence-grounded passage retrieved from the document store.

    Guarantees full provenance tracing back to original file, page, block,
    and exact spatial bounding-box coordinates.
    """

    doc_id: str
    document_name: str
    page_number: int
    block_id: int
    block_type: str
    text: str
    bounding_box: Tuple[float, float, float, float]  # (xmin, ymin, xmax, ymax)
    confidence: float
    similarity_score: float
    retrieval_method: str = "hybrid"                 # "dense", "lexical", or "hybrid"
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SynthesizedContext:
    """Evidence-backed context payload packaged for downstream LLMs."""

    query: str
    passages: Tuple[RetrievedPassage, ...]
    formatted_context: str
    token_count_estimate: int
    max_budget_tokens: int
    truncated: bool = False
    metadata: dict = field(default_factory=dict)



