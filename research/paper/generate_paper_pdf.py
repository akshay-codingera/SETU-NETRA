import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak, HRFlowable, Image
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#4A5568"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 755, "SETU-NETRA: Adaptive Neuro-Symbolic Document Intelligence & Reasoning")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 748, 558, 748)
            
        # Footer
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 36, page_text)
        self.drawString(54, 36, "CONFIDENTIAL & PROPRIETARY — DOCUMENT INTELLIGENCE RESEARCH LAB")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 46, 558, 46)
        self.restoreState()

def build_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()
    
    # Custom Palette
    c_primary = colors.HexColor("#1E3A8A")    # Deep Navy
    c_secondary = colors.HexColor("#0D9488")  # Teal Accent
    c_dark = colors.HexColor("#0F172A")       # Slate 900
    c_body = colors.HexColor("#334155")       # Slate 700
    c_border = colors.HexColor("#E2E8F0")     # Light gray border
    c_bg_light = colors.HexColor("#F8FAFC")   # Off white / slate 50
    c_highlight = colors.HexColor("#EFF6FF")  # Blue 50

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=c_primary,
        alignment=1, # Centered
        spaceAfter=6
    )
    
    author_style = ParagraphStyle(
        'AuthorBlock',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=c_body,
        alignment=1,
        spaceAfter=10
    )

    h1_style = ParagraphStyle(
        'SectionH1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=c_primary,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.2,
        leading=11.2,
        textColor=c_body,
        spaceAfter=5,
        alignment=4 # Justified
    )

    abstract_style = ParagraphStyle(
        'AbstractText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.2,
        leading=11.5,
        textColor=c_dark,
        leftIndent=14,
        rightIndent=14,
        spaceAfter=8,
        alignment=4
    )

    fig_cap = ParagraphStyle(
        'FigCapStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=7.2,
        leading=9.2,
        textColor=c_dark,
        alignment=4,
        spaceBefore=3,
        spaceAfter=5
    )

    table_header_style = ParagraphStyle(
        'TH',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.2,
        leading=9.2,
        textColor=colors.white,
        alignment=1
    )

    table_cell_style = ParagraphStyle(
        'TC',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.2,
        leading=9.2,
        textColor=c_dark,
        alignment=0
    )

    table_cell_center = ParagraphStyle(
        'TCC',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.2,
        leading=9.2,
        textColor=c_dark,
        alignment=1
    )

    story = []

    # =========================================================================
    # PAGE 1: TITLE, ABSTRACT, MOTIVATING PARADOX & THE THREE FALLACIES
    # =========================================================================
    story.append(Paragraph("SETU-NETRA: An Adaptive Neuro-Symbolic Framework for Intelligent Document Understanding, Evidence-Grounded QA, and Context-Aware Reasoning", title_style))
    story.append(Paragraph("<b>Akshat Sharma</b>, <i>Senior AI Research Scientist & Document Intelligence Architect</i><br/>Autonomous Systems & Architecture Research Group | Project: SETU-NETRA | November 2026", author_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_primary, spaceBefore=0, spaceAfter=6))

    # Abstract Box
    abstract_text = (
        "<b>Abstract—</b>Conventional document Question Answering (QA) and Retrieval-Augmented Generation (RAG) pipelines suffer from three "
        "fundamental structural vulnerabilities: (1) <i>the geometric fallacy</i>, which assumes reading-order heuristics preserve semantic hierarchy; "
        "(2) <i>the epistemic fallacy</i>, which equates semantic retrieval similarity with factual sufficiency; and (3) <i>the universal generation fallacy</i>, "
        "which delegates deterministic relational and mathematical queries to uncalibrated autoregressive models, causing catastrophic hallucinations. "
        "We present <b>SETU-NETRA</b>, an adaptive neuro-symbolic framework for visually-rich document understanding, epistemic verification, and dynamic reasoning "
        "strategy selection constrained to edge execution (≤ 16 GB RAM, CPU-only). SETU-NETRA contributes: (1) <b>SR-EdgeNet</b> (414K parameters), "
        "a spatial-relational edge classifier mapping OCR blocks to directed hierarchy multigraphs (99.46% synthetic accuracy, 0.9909 Macro F1); "
        "(2) <b>ER-SP</b> (560K parameters), a 5-class epistemic gating network predicting factual sufficiency before generation (86.18% accuracy, "
        "0.8553 Macro F1, 0.0889 ECE); and (3) <b>CM-RP</b> (63K parameters), a contextual meta-reasoning policy mapping a 423-dimensional state vector to 7 concrete actions. "
        "Through a critical statistical audit, we resolve earlier zero-support reporting anomalies via an independent 7-action benchmark (N = 245, 35/class), "
        "demonstrating that pure neural CM-RP v2 achieves <b>94.29% accuracy</b> and <b>0.9433 Macro F1</b>. Controlled ablation proves that under verified grounded "
        "contexts, the complete architecture achieves <b>92.00% accuracy</b>, <b>0.9524 Abstention F1</b>, and <b>0.946 Grounding Score</b>, outperforming isolated components by 20–68%."
    )
    story.append(Paragraph(abstract_text, abstract_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=c_border, spaceBefore=0, spaceAfter=6))

    # Section 1
    story.append(Paragraph("1. Introduction & The Motivating Paradox", h1_style))
    story.append(Paragraph(
        "Real-world enterprise and academic document understanding is strictly governed by a sequential dependency: "
        "<b>Document Ingestion → Structural Understanding → Evidence Evaluation → Reasoning Strategy Selection → Grounded Execution / Abstention</b>. "
        "When any stage in this pipeline fails, compounding error cascades propagate through the system, producing confident hallucinations.",
        body_style
    ))
    story.append(Paragraph(
        "Standard document systems are undermined by three recurring fallacies:<br/>"
        "• <b>The Geometric Fallacy:</b> Deterministic layout heuristics (e.g., Recursive XY-Cut) assume 2D spatial proximity mirrors semantic hierarchy. "
        "On multi-column layouts, tables, and examination papers, naive line sorting interleaves question stems with unrelated options (Kendall's τ = 0.85). "
        "Merely extracting text blocks into a flat string strips away the directed parent-child dependencies and horizontal continuations, destroying structural context.<br/>"
        "• <b>The Epistemic Fallacy:</b> Standard RAG presumes that high cosine similarity implies factual sufficiency. A passage sharing 88% lexical similarity "
        "frequently omits the necessary condition (producing incomplete premise hallucination) or asserts an opposing factual polarity (producing polarity blindness). "
        "Semantic similarity measures topical alignment, not deductive entailment.<br/>"
        "• <b>The Universal Generation Fallacy:</b> Autoregressive language models generate tokens probabilistically. For database normalization, "
        "symbolic logic proofs, or arithmetic derivations, LLMs suffer stochastic drift, producing plausible mathematical errors that cannot be audited. "
        "Conversely, deterministic algorithms solve them with 100% precision in sub-millisecond execution times.",
        body_style
    ))
    story.append(Paragraph(
        "<b>SETU-NETRA</b> overcomes these barriers by coupling learned layout reconstruction, epistemic gating, and adaptive policy dispatching with deterministic symbolic engines under strict local edge constraints (≤ 16 GB RAM, CPU execution).",
        body_style
    ))

    # Page 1 Break
    story.append(PageBreak())

    # =========================================================================
    # PAGE 2: FIGURE 1 (VISION) + SECTION 2 + FIGURE 2 (ARCHITECTURE)
    # =========================================================================
    fig1_img = os.path.abspath("research/paper/figures/setu_netra_platform_vision.png")
    story.append(Image(fig1_img, width=504, height=160))
    story.append(Paragraph("<b>Figure 1.</b> Conceptual illustration of SETU-NETRA, showing heterogeneous users submitting documents and natural-language queries to an adaptive document intelligence engine that performs structural understanding (R1: SR-EdgeNet), evidence evaluation (R2: ER-SP), context-aware reasoning policy selection (R3: CM-RP), and evidence-grounded response generation or safe abstention under edge hardware constraints.", fig_cap))
    story.append(Spacer(1, 4))

    story.append(Paragraph("2. Architectural Evolution & Chronology", h1_style))
    story.append(Paragraph(
        "SETU-NETRA evolved from early heuristic baselines through empirical failure analysis:<br/>"
        "• <i>Phase 0 (Baselines):</i> EasyOCR (CRAFT+CRNN) provided raw bounding boxes. Recursive XY-Cut line sorting failed on warped mobile camera scans (3–8° skew). "
        "A 500-line regex domain router suffered severe keyword collisions (e.g., 'B+ tree indexing with M=4' tripped arithmetic regexes).<br/>"
        "• <i>Phase 1 (Hybrid Retrieval):</i> Pretrained all-MiniLM-L6-v2 (384-d) was combined with BM25 via Reciprocal Rank Fusion (RRF). Fixed cosine thresholds (τ = 0.45) "
        "failed to catch contradictory or partial context.<br/>"
        "• <i>Phase 2 (Trainable Modules):</i> The system transitioned to three dedicated lightweight neural components: R1 (SR-EdgeNet), R2 (ER-SP), and R3 (CM-RP).",
        body_style
    ))
    story.append(Spacer(1, 4))

    fig2_img = os.path.abspath("research/paper/figures/architecture_pipeline.png")
    story.append(Image(fig2_img, width=504, height=165))
    story.append(Paragraph("<b>Figure 2.</b> SETU-NETRA technical architecture, tensor dimensionalities (384-d, 15-d, 1,537-d, 423-d), parameter counts (414K, 560K, 63K), and multi-stage execution pipeline connecting document ingestion, SR-EdgeNet multigraph reconstruction, ER-SP epistemic sufficiency gating, CM-RP policy selection, deterministic solver dispatch, and CitationVerifier source grounding.", fig_cap))

    # Page 2 Break
    story.append(PageBreak())

    # =========================================================================
    # PAGE 3: SECTION 3 (SR-EDGENET) + TABLE 1 + SECTION 4 (ER-SP) + TABLE 2
    # =========================================================================
    story.append(Paragraph("3. R1 — SR-EdgeNet: Structural Relationship Understanding", h1_style))
    story.append(Paragraph(
        "<b>SR-EdgeNet</b> (414,088 parameters, 5.0 MB checkpoint) replaces geometric line-cutting heuristics with a pairwise neural edge classifier. "
        "For candidate block pair (b<sub>i</sub>, b<sub>j</sub>), the model classifies directed edges into: <i>PARENT_OF, OPTION_OF, CONTINUATION_OF, NONE</i>. "
        "The model integrates: (1) a 256-d text relation vector f<sub>text</sub> from frozen MiniLM embeddings; (2) a 15-d normalized geometric offset vector e<sub>ij</sub>; "
        "and (3) a 3-layer MLP classification head with residual skip connections and dropout (p=0.15).",
        body_style
    ))

    # Table 1: SETU-SR Dataset & Performance
    t1_data = [
        [Paragraph("Split File", table_header_style), Paragraph("Docs", table_header_style), Paragraph("Edges", table_header_style), Paragraph("Accuracy", table_header_style), Paragraph("Macro F1", table_header_style), Paragraph("OPTION_OF F1", table_header_style)],
        [Paragraph("Train (FUNSD + Synth)", table_cell_style), Paragraph("349", table_cell_center), Paragraph("36,346", table_cell_center), Paragraph("99.82%", table_cell_center), Paragraph("0.9971", table_cell_center), Paragraph("0.9985", table_cell_center)],
        [Paragraph("Val (FUNSD + Synth)", table_cell_style), Paragraph("75", table_cell_center), Paragraph("6,584", table_cell_center), Paragraph("99.51%", table_cell_center), Paragraph("0.9918", table_cell_center), Paragraph("0.9942", table_cell_center)],
        [Paragraph("Test Synthetic (Held-Out)", table_cell_style), Paragraph("25", table_cell_center), Paragraph("4,423", table_cell_center), Paragraph("99.46%", table_cell_center), Paragraph("0.9909", table_cell_center), Paragraph("1.0000", table_cell_center)],
        [Paragraph("Test Real In-Domain (Gold)", table_cell_style), Paragraph("21", table_cell_center), Paragraph("204", table_cell_center), Paragraph("65.69%", table_cell_center), Paragraph("0.5843", table_cell_center), Paragraph("0.7619", table_cell_center)],
    ]
    t1 = Table(t1_data, colWidths=[140, 45, 55, 65, 65, 80])
    t1.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_primary),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_bg_light]),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
    ]))
    story.append(t1)
    story.append(Spacer(1, 3))
    story.append(Paragraph(
        "<i>Domain-Shift Finding:</i> Synthetic performance reached 99.46%, but dropped to 65.69% on real mobile phone scans due to 3–8° angular perspective skew. "
        "Crucially, OPTION_OF precision remained high at 88.89% (F1 = 0.7619), successfully preventing question-option interleaving.",
        body_style
    ))

    # Section 4: ER-SP
    story.append(Paragraph("4. R2 — ER-SP: Evidence Relevance & Sufficiency Predictor", h1_style))
    story.append(Paragraph(
        "<b>ER-SP</b> (560,134 parameters, 2.25 MB checkpoint) operates downstream of dense retrieval, projecting a 1,537-dimensional cross-interaction tensor "
        "[q || p || |q - p| || q ⊙ p || cos(q, p)] through an attention-pooled multi-evidence aggregator into a 5-class epistemic state: "
        "<i>SUFFICIENT, PARTIALLY_SUFFICIENT, CONTRADICTORY, IRRELEVANT, UNVERIFIABLE</i>. Trained with Focal Loss (γ = 2.0).",
        body_style
    ))

    # Table 2: ER-SP Benchmark
    t2_data = [
        [Paragraph("Metric", table_header_style), Paragraph("Cosine Threshold (τ=0.55)", table_header_style), Paragraph("Lexical Heuristic", table_header_style), Paragraph("ER-SP (Proposed)", table_header_style)],
        [Paragraph("Overall Accuracy (%)", table_cell_style), Paragraph("37.65%", table_cell_center), Paragraph("45.88%", table_cell_center), Paragraph("<b>86.18%</b>", table_cell_center)],
        [Paragraph("Macro F1-Score", table_cell_style), Paragraph("0.2185", table_cell_center), Paragraph("0.3621", table_cell_center), Paragraph("<b>0.8553</b>", table_cell_center)],
        [Paragraph("Contradiction Precision (%)", table_cell_style), Paragraph("0.00%", table_cell_center), Paragraph("42.10%", table_cell_center), Paragraph("<b>100.00%</b>", table_cell_center)],
        [Paragraph("Contradiction Recall (%)", table_cell_style), Paragraph("0.00%", table_cell_center), Paragraph("58.82%", table_cell_center), Paragraph("<b>95.59%</b>", table_cell_center)],
        [Paragraph("Abstention F1-Score", table_cell_style), Paragraph("0.0000", table_cell_center), Paragraph("0.5217", table_cell_center), Paragraph("<b>0.9318</b>", table_cell_center)],
        [Paragraph("Expected Calibration Error (ECE)", table_cell_style), Paragraph("0.4120", table_cell_center), Paragraph("0.2840", table_cell_center), Paragraph("<b>0.0889</b>", table_cell_center)],
        [Paragraph("CPU Inference Latency", table_cell_style), Paragraph("0.002 ms", table_cell_center), Paragraph("0.045 ms", table_cell_center), Paragraph("<b>0.450 ms</b>", table_cell_center)],
    ]
    t2 = Table(t2_data, colWidths=[160, 110, 90, 90])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_primary),
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_bg_light]),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
    ]))
    story.append(t2)
    story.append(Spacer(1, 3))
    story.append(Paragraph(
        "<i>Epistemic Grounding:</i> Standard cosine thresholding exhibits 0.0000 Abstention F1, blindly passing contradictory context. ER-SP achieves 100.00% contradiction precision and 95.59% recall with an ECE of 0.0889, establishing an audited epistemic barrier.",
        body_style
    ))

    # Page 3 Break
    story.append(PageBreak())

    # =========================================================================
    # PAGE 4: SECTION 5 (CM-RP) + FIGURE 3 (TRACE) + SECTION 6 + FIGURE 4 (MATRICES)
    # =========================================================================
    story.append(Paragraph("5. R3 — CM-RP: Contextual Multi-Strategy Reasoning Policy", h1_style))
    story.append(Paragraph(
        "<b>CM-RP</b> (63,367 parameters, 265 KB checkpoint) dynamically selects among 7 concrete reasoning strategies: "
        "<i>ARITHMETIC_SOLVER</i> (Python AST math evaluator), <i>DBMS_SOLVER</i> (Armstrong's closure/normalization prover), "
        "<i>FORMAL_LOGIC_SOLVER</i> (model-theoretic syllogism prover), <i>EXTRACTIVE_QA</i> (verified quote extractor), "
        "<i>LOCAL_SLM</i> (local 3B/7B language model), <i>ADDITIONAL_RETRIEVAL</i> (graph-expanded context search), and <i>ABSTAIN</i> (epistemic refusal). "
        "The policy maps a 423-dimensional context state: s<sub>t</sub> = [e<sub>query</sub>(384) || f<sub>struct</sub>(8) || f<sub>evidence</sub>(8) || f<sub>domain</sub>(11) || f<sub>telemetry</sub>(5) || f<sub>history</sub>(7)]. "
        "Dynamic hardware masking disables LOCAL_SLM if available RAM < 1.5 GB or CPU load > 92%, preventing edge OOM crashes.",
        body_style
    ))
    story.append(Spacer(1, 3))

    # Figure 3: Real Document Execution Trace Demo
    fig5_img = os.path.abspath("research/paper/figures/execution_trace_demo.png")
    story.append(Image(fig5_img, width=504, height=160))
    story.append(Paragraph("<b>Figure 3.</b> Real-world document execution trace on an authentic examination scan (<code>quest7.png</code>). Step 1: EasyOCR extracts normalized planar bounding boxes; Step 2: SR-EdgeNet reconstructs the directed structural hierarchy multigraph; Step 3: ER-SP performs epistemic sufficiency gating (SUFFICIENT) and CM-RP dispatches the query to the DBMS Normalization Solver; Step 4: Deterministic Armstrong closure algorithm computes minimal candidate keys (<code>{AB}</code>) with verified source coordinate citation grounding.", fig_cap))
    story.append(Spacer(1, 4))

    # Section 6: Statistical Audit
    story.append(Paragraph("6. Critical Statistical Audit & Complete 7-Action Validation", h1_style))
    story.append(Paragraph(
        "The R4 statistical audit resolved two critical reporting anomalies:<br/>"
        "<b>Problem 1 (Zero-Support Resolution):</b> The original 340-sample test split evaluated only 4 actions. An independent benchmark was assembled "
        "(N = 245, exactly 35 verified examples per action across all 7 actions). CM-RP v2 pure neural achieved <b>94.29% accuracy</b> and <b>0.9433 Macro F1</b>, "
        "with zero zero-support classes and zero zero-recall classes, outperforming the rule fallback version (88.16%).",
        body_style
    ))
    story.append(Spacer(1, 3))

    # Figure 4: Empirical Confusion Matrices Heatmap
    fig3_img = os.path.abspath("research/paper/figures/confusion_matrices.png")
    story.append(Image(fig3_img, width=504, height=145))
    story.append(Paragraph("<b>Figure 4.</b> Empirical confusion matrix heatmaps across all three trainable research components: (Left) SR-EdgeNet 4×4 spatial-relational edge classifier (99.46% synthetic test accuracy); (Center) ER-SP 5×5 epistemic evidence gating network on held-out unseen topics (86.18% accuracy, 100% contradiction precision); (Right) CM-RP v2 7×7 contextual policy network on the independent balanced audit benchmark (N = 245, 94.29% accuracy, 0.9433 Macro F1), with zero zero-support and zero zero-recall classes.", fig_cap))

    # Page 4 Break
    story.append(PageBreak())

    # =========================================================================
    # PAGE 5: TABLE 3 + SECTION 7 + TABLE 4 + FIGURE 5 (ABLATION) + LIMITATIONS & CONCLUSION
    # =========================================================================
    # Table 3: 7x7 Per-Class Metrics
    t3_data = [
        [Paragraph("Strategy Action Class", table_header_style), Paragraph("True Support", table_header_style), Paragraph("Pred Count", table_header_style), Paragraph("Precision", table_header_style), Paragraph("Recall", table_header_style), Paragraph("F1-Score", table_header_style)],
        [Paragraph("ARITHMETIC_SOLVER", table_cell_style), Paragraph("35", table_cell_center), Paragraph("36", table_cell_center), Paragraph("94.44%", table_cell_center), Paragraph("97.14%", table_cell_center), Paragraph("0.9577", table_cell_center)],
        [Paragraph("DBMS_SOLVER", table_cell_style), Paragraph("35", table_cell_center), Paragraph("40", table_cell_center), Paragraph("80.00%", table_cell_center), Paragraph("91.43%", table_cell_center), Paragraph("0.8533", table_cell_center)],
        [Paragraph("FORMAL_LOGIC_SOLVER", table_cell_style), Paragraph("35", table_cell_center), Paragraph("38", table_cell_center), Paragraph("92.11%", table_cell_center), Paragraph("100.00%", table_cell_center), Paragraph("0.9589", table_cell_center)],
        [Paragraph("EXTRACTIVE_QA", table_cell_style), Paragraph("35", table_cell_center), Paragraph("29", table_cell_center), Paragraph("100.00%", table_cell_center), Paragraph("82.86%", table_cell_center), Paragraph("0.9062", table_cell_center)],
        [Paragraph("LOCAL_SLM", table_cell_style), Paragraph("35", table_cell_center), Paragraph("35", table_cell_center), Paragraph("97.14%", table_cell_center), Paragraph("97.14%", table_cell_center), Paragraph("0.9714", table_cell_center)],
        [Paragraph("ADDITIONAL_RETRIEVAL", table_cell_style), Paragraph("35", table_cell_center), Paragraph("35", table_cell_center), Paragraph("100.00%", table_cell_center), Paragraph("100.00%", table_cell_center), Paragraph("1.0000", table_cell_center)],
        [Paragraph("ABSTAIN", table_cell_style), Paragraph("35", table_cell_center), Paragraph("32", table_cell_center), Paragraph("100.00%", table_cell_center), Paragraph("91.43%", table_cell_center), Paragraph("0.9552", table_cell_center)],
        [Paragraph("<b>Macro Average (Unweighted)</b>", table_cell_style), Paragraph("<b>35.0</b>", table_cell_center), Paragraph("<b>35.0</b>", table_cell_center), Paragraph("<b>94.81%</b>", table_cell_center), Paragraph("<b>94.29%</b>", table_cell_center), Paragraph("<b>0.9433</b>", table_cell_center)],
    ]
    t3 = Table(t3_data, colWidths=[150, 60, 60, 60, 60, 60])
    t3.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_secondary),
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, c_bg_light]),
        ('BACKGROUND', (0,-1), (-1,-1), c_highlight),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(t3)
    story.append(Spacer(1, 4))

    # Section 7: Ablation
    story.append(Paragraph("7. Forensic Ablation Investigation & System Superiority", h1_style))
    story.append(Paragraph(
        "<b>Problem 2 (Ablation Resolution):</b> Initial reporting showed C4 (CM-RP alone: 72%) outperforming Complete R4 (C6: 70%), while ER-SP alone (C3) collapsed to 24%.<br/>"
        "• <i>Forensic Cause of C3 (24%):</i> ER-SP is an epistemic gating head, not an execution solver. Without CM-RP, all non-abstaining queries defaulted to EXTRACTIVE_QA, scoring 0/38 on arithmetic, DBMS, and logic, but 12/12 on extractive queries (12/50 = 24.00%).<br/>"
        "• <i>Forensic Cause of C6 Inversion (70% vs 92%):</i> In the initial run, C6 was evaluated on dummy placeholder context strings. CitationVerifier detected zero source citation tokens and strictly triggered an epistemic refusal. The test scored this refusal as an error, penalizing C6 for preventing hallucination.<br/>"
        "• <i>Fair Re-Evaluation:</i> When evaluated under verified grounded passage context, <b>C6 surges to 92.00% accuracy</b>, Abstention F1 reaches <b>0.9524</b>, and Grounding Score reaches <b>0.946</b>, definitively proving the superiority of the complete unified architecture.",
        body_style
    ))

    # Table 4: Controlled Ablation Matrix
    t4_data = [
        [Paragraph("Configuration", table_header_style), Paragraph("Structure", table_header_style), Paragraph("Evidence", table_header_style), Paragraph("Policy", table_header_style), Paragraph("Context", table_header_style), Paragraph("Accuracy", table_header_style), Paragraph("Abstain F1", table_header_style), Paragraph("Grounding", table_header_style)],
        [Paragraph("C1 (Classical Baseline)", table_cell_style), Paragraph("XY-Cut", table_cell_center), Paragraph("Cosine τ", table_cell_center), Paragraph("Regex", table_cell_center), Paragraph("Grounded", table_cell_center), Paragraph("44.00%", table_cell_center), Paragraph("0.0000", table_cell_center), Paragraph("0.608", table_cell_center)],
        [Paragraph("C2 (+SR-EdgeNet)", table_cell_style), Paragraph("SR-Edge", table_cell_center), Paragraph("Cosine τ", table_cell_center), Paragraph("Regex", table_cell_center), Paragraph("Grounded", table_cell_center), Paragraph("42.00%", table_cell_center), Paragraph("0.0000", table_cell_center), Paragraph("0.594", table_cell_center)],
        [Paragraph("C3 (+ER-SP alone)", table_cell_style), Paragraph("XY-Cut", table_cell_center), Paragraph("ER-SP", table_cell_center), Paragraph("Regex", table_cell_center), Paragraph("Grounded", table_cell_center), Paragraph("24.00%", table_cell_center), Paragraph("0.0000", table_cell_center), Paragraph("0.468", table_cell_center)],
        [Paragraph("C4 (+CM-RP alone)", table_cell_style), Paragraph("XY-Cut", table_cell_center), Paragraph("Cosine τ", table_cell_center), Paragraph("CM-RP v2", table_cell_center), Paragraph("Grounded", table_cell_center), Paragraph("72.00%", table_cell_center), Paragraph("0.5517", table_cell_center), Paragraph("0.932", table_cell_center)],
        [Paragraph("C5 (SR-Edge + ER-SP)", table_cell_style), Paragraph("SR-Edge", table_cell_center), Paragraph("ER-SP", table_cell_center), Paragraph("Regex", table_cell_center), Paragraph("Grounded", table_cell_center), Paragraph("44.00%", table_cell_center), Paragraph("0.0000", table_cell_center), Paragraph("0.608", table_cell_center)],
        [Paragraph("C6 (Placeholder Context)", table_cell_style), Paragraph("SR-Edge", table_cell_center), Paragraph("ER-SP", table_cell_center), Paragraph("CM-RP v2", table_cell_center), Paragraph("Placeholder", table_cell_center), Paragraph("70.00%", table_cell_center), Paragraph("0.5333", table_cell_center), Paragraph("0.930", table_cell_center)],
        [Paragraph("<b>C6 (Grounded Context)</b>", table_cell_style), Paragraph("SR-Edge", table_cell_center), Paragraph("ER-SP", table_cell_center), Paragraph("CM-RP v2", table_cell_center), Paragraph("Grounded", table_cell_center), Paragraph("<b>92.00%</b>", table_cell_center), Paragraph("<b>0.9524</b>", table_cell_center), Paragraph("<b>0.946</b>", table_cell_center)],
    ]
    t4 = Table(t4_data, colWidths=[110, 50, 50, 55, 55, 45, 45, 40])
    t4.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_primary),
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, c_bg_light]),
        ('BACKGROUND', (0,-1), (-1,-1), c_highlight),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(t4)
    story.append(Spacer(1, 4))

    # Figure 5: Controlled Ablation Benchmark Comparison Bar Chart
    fig4_img = os.path.abspath("research/paper/figures/ablation_barchart.png")
    story.append(Image(fig4_img, width=504, height=150))
    story.append(Paragraph("<b>Figure 5.</b> Controlled ablation benchmark comparison across configurations C1 through C6 Grounded (N = 50 challenge suite). Complete SETU-NETRA (C6 Grounded) achieves 92.00% accuracy, 0.9524 Abstention F1, and 0.946 Grounding Score, demonstrating the necessity of coupling structural understanding (R1), epistemic gating (R2), and contextual multi-strategy policy dispatching (R3). Note the collapse of ER-SP alone (C3: 24%) due to missing execution solvers and the recovery of C6 Grounded over ungrounded placeholder context (70% vs 92%).", fig_cap))
    story.append(Spacer(1, 4))

    # Section 8 & 9
    story.append(Paragraph("8. Engineering Limitations & Conclusion", h1_style))
    story.append(Paragraph(
        "<b>Limitations:</b> (1) Perspective warping on smartphone scans lowers SR-EdgeNet recall (65.69%), requiring future affine pre-alignment; "
        "(2) ER-SP multi-hop reasoning over >4 disconnected pages occasionally triggers partial sufficiency; "
        "(3) End-to-end CPU pipeline latency is 24.44 ms (isolated model inferences execute in <0.5 ms).<br/>"
        "<b>Conclusion:</b> SETU-NETRA demonstrates that enterprise-grade document intelligence on commodity edge hardware requires learned "
        "structural graph modeling, epistemic gating, and adaptive neuro-symbolic solver dispatching. By eliminating blind autoregressive generation, "
        "the architecture achieves <b>92.00% accuracy</b> and an Abstention F1 of <b>0.9524</b> under a 16 GB RAM boundary.",
        body_style
    ))

    # Build Document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated publication-style PDF: {output_path}")

if __name__ == "__main__":
    out_pdf = os.path.abspath("research/paper/SETU_NETRA_RESEARCH_PAPER.pdf")
    build_pdf(out_pdf)
