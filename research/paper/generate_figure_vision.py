import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Circle

def create_platform_vision_figure(output_png, output_svg):
    # Canvas size: 16:9 ratio
    fig = plt.figure(figsize=(16, 9), dpi=300)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1600)
    ax.set_ylim(0, 900)
    ax.axis('off')

    # Background
    bg = Rectangle((0, 0), 1600, 900, facecolor='#F8FAFC', edgecolor='none')
    ax.add_patch(bg)

    # Header Banner
    header_box = FancyBboxPatch((40, 825), 1520, 60, boxstyle="round,pad=0,rounding_size=8",
                                facecolor='#0F172A', edgecolor='#1E293B', linewidth=1.5)
    ax.add_patch(header_box)
    ax.text(800, 860, "SETU-NETRA: An Adaptive Multi-User Document Intelligence and Reasoning Platform",
            ha='center', va='center', fontsize=17, fontweight='bold', color='#FFFFFF', fontfamily='sans-serif')
    ax.text(800, 838, "Holistic Research Vision: Heterogeneous Document Ingestion -> Learned Structure (R1) -> Epistemic Gating (R2) -> Multi-Strategy Policy (R3) -> Grounded Execution",
            ha='center', va='center', fontsize=9.5, color='#94A3B8', fontfamily='sans-serif')

    # Color Palette
    c_reg1_bg = '#EFF6FF'
    c_reg1_border = '#3B82F6'
    c_reg2_bg = '#F0FDFA'
    c_reg2_border = '#0D9488'
    c_reg3_bg = '#FFFFFF'
    c_reg3_border = '#4F46E5'
    c_reg4_bg = '#F5F3FF'
    c_reg4_border = '#8B5CF6'

    # ================= REGION CONTAINERS =================
    # Region 1: Users & Devices (x: 40 to 330)
    r1 = FancyBboxPatch((40, 45), 290, 765, boxstyle="round,pad=0,rounding_size=10",
                        facecolor=c_reg1_bg, edgecolor=c_reg1_border, linewidth=1.5, alpha=0.9)
    ax.add_patch(r1)
    ax.text(185, 785, "REGION 1: MULTI-USER ACCESS", ha='center', va='center',
            fontsize=10.5, fontweight='bold', color='#1E40AF', fontfamily='sans-serif')
    ax.text(185, 768, "Heterogeneous Devices & Operating Environments", ha='center', va='center',
            fontsize=7.5, color='#475569', fontfamily='sans-serif')

    # Region 2: Input Documents & Queries (x: 350 to 600)
    r2 = FancyBboxPatch((350, 45), 250, 765, boxstyle="round,pad=0,rounding_size=10",
                        facecolor=c_reg2_bg, edgecolor=c_reg2_border, linewidth=1.5, alpha=0.9)
    ax.add_patch(r2)
    ax.text(475, 785, "REGION 2: MULTIMODAL INPUTS", ha='center', va='center',
            fontsize=10.5, fontweight='bold', color='#0F766E', fontfamily='sans-serif')
    ax.text(475, 768, "Documents, Tables, Images & Inquiries", ha='center', va='center',
            fontsize=7.5, color='#475569', fontfamily='sans-serif')

    # Region 3: Central Intelligence Engine (x: 620 to 1180)
    r3 = FancyBboxPatch((620, 45), 560, 765, boxstyle="round,pad=0,rounding_size=10",
                        facecolor=c_reg3_bg, edgecolor=c_reg3_border, linewidth=2.0, alpha=0.95)
    ax.add_patch(r3)
    ax.text(900, 785, "REGION 3: SETU-NETRA CORE INTELLIGENCE ENGINE", ha='center', va='center',
            fontsize=11.5, fontweight='bold', color='#3730A3', fontfamily='sans-serif')
    ax.text(900, 768, "Local-First CPU Orchestration | <= 16 GB RAM Edge Hardware Constraint", ha='center', va='center',
            fontsize=8, color='#475569', fontfamily='sans-serif')

    # Region 4: Grounded Results & Verification (x: 1200 to 1560)
    r4 = FancyBboxPatch((1200, 45), 360, 765, boxstyle="round,pad=0,rounding_size=10",
                        facecolor=c_reg4_bg, edgecolor=c_reg4_border, linewidth=1.5, alpha=0.9)
    ax.add_patch(r4)
    ax.text(1380, 785, "REGION 4: VERIFIED RESULTS", ha='center', va='center',
            fontsize=10.5, fontweight='bold', color='#6D28D9', fontfamily='sans-serif')
    ax.text(1380, 768, "Symbolic Proofs, Citations & Safe Abstentions", ha='center', va='center',
            fontsize=7.5, color='#475569', fontfamily='sans-serif')

    # ================= REGION 1: USER CARDS =================
    users_data = [
        ("Student / Examinee", "Laptop (Linux / Web Browser)", "Multi-Choice Exam Query:\n'Identify correct answer to Q4 & Q5'", 680, "#3B82F6"),
        ("Academic Researcher", "Desktop Workstation (Ubuntu / CLI)", "Deductive Proof Inquiry:\n'Check premise consistency in Theorem 2'", 510, "#0284C7"),
        ("Financial Auditor", "Touchscreen Tablet (Windows 11)", "Relational Query:\n'Find candidate keys & BCNF violations'", 340, "#2563EB"),
        ("Field Professional", "Mobile Phone (Android / Camera)", "Camera Capture of Skewed Exam Form:\n'Parse text blocks & options'", 170, "#1D4ED8")
    ]

    for title, device, query, y_pos, b_color in users_data:
        # Card
        ucard = FancyBboxPatch((55, y_pos - 65), 260, 130, boxstyle="round,pad=0,rounding_size=6",
                               facecolor='#FFFFFF', edgecolor='#CBD5E1', linewidth=1)
        ax.add_patch(ucard)
        # Device badge
        badge = FancyBboxPatch((65, y_pos + 38), 65, 18, boxstyle="round,pad=0,rounding_size=3",
                               facecolor=b_color, edgecolor='none')
        ax.add_patch(badge)
        ax.text(97.5, y_pos + 47, "USER", ha='center', va='center', fontsize=6.5, fontweight='bold', color='#FFFFFF')
        
        ax.text(140, y_pos + 47, title, ha='left', va='center', fontsize=8.5, fontweight='bold', color='#0F172A')
        ax.text(65, y_pos + 22, f"Environment: {device}", ha='left', va='center', fontsize=7, color='#64748B')
        
        # Query speech bubble
        qbox = FancyBboxPatch((65, y_pos - 55), 240, 68, boxstyle="round,pad=0,rounding_size=4",
                              facecolor='#F1F5F9', edgecolor='#E2E8F0', linewidth=0.8)
        ax.add_patch(qbox)
        ax.text(72, y_pos - 22, query, ha='left', va='center', fontsize=6.8, color='#334155', fontfamily='sans-serif')

    # ================= REGION 2: INPUT DOCUMENTS =================
    inputs_data = [
        ("Mobile Scans / Exam Photos", "2-Column exams, 3-8 deg skew, perspective warp", 680, "#0D9488"),
        ("Scientific Research PDFs", "Multi-page papers, equations, citations", 510, "#0F766E"),
        ("Structured Tables / Sheets", "Financial balances, functional dependencies", 340, "#115E59"),
        ("Natural-Language Queries", "High-entropy prompts, multi-hop questions", 170, "#134E4A")
    ]

    for title, subtitle, y_pos, i_color in inputs_data:
        icard = FancyBboxPatch((365, y_pos - 65), 220, 130, boxstyle="round,pad=0,rounding_size=6",
                               facecolor='#FFFFFF', edgecolor='#CBD5E1', linewidth=1)
        ax.add_patch(icard)
        # Document Icon header
        ibadge = FancyBboxPatch((375, y_pos + 38), 50, 18, boxstyle="round,pad=0,rounding_size=3",
                                facecolor=i_color, edgecolor='none')
        ax.add_patch(ibadge)
        ax.text(400, y_pos + 47, "INPUT", ha='center', va='center', fontsize=6.5, fontweight='bold', color='#FFFFFF')
        
        ax.text(435, y_pos + 47, title, ha='left', va='center', fontsize=8, fontweight='bold', color='#0F172A')
        ax.text(375, y_pos + 18, subtitle, ha='left', va='center', fontsize=6.8, color='#64748B')
        
        # Visual mini-thumbnail representation
        thumb = Rectangle((375, y_pos - 55), 200, 60, facecolor='#F8FAFC', edgecolor='#E2E8F0', linewidth=0.8)
        ax.add_patch(thumb)
        # lines inside thumbnail
        for line_idx in range(4):
            ax.plot([385, 560], [y_pos - 15 - line_idx * 11, y_pos - 15 - line_idx * 11], color='#CBD5E1', linewidth=1.2)
        ax.plot([385, 480], [y_pos - 15 - 44, y_pos - 15 - 44], color='#0D9488', linewidth=1.5)

    # Arrows Region 1 -> Region 2
    for y_pos in [680, 510, 340, 170]:
        arrow = FancyArrowPatch((315, y_pos), (360, y_pos), arrowstyle='-|>', mutation_scale=10,
                                color='#94A3B8', linewidth=1.2)
        ax.add_patch(arrow)

    # Arrows Region 2 -> Region 3
    for y_pos in [680, 510, 340, 170]:
        arrow = FancyArrowPatch((585, y_pos), (635, y_pos), arrowstyle='-|>', mutation_scale=12,
                                color='#0D9488', linewidth=1.5)
        ax.add_patch(arrow)

    # ================= REGION 3: INTELLIGENCE ENGINE =================
    # Sub-block 1: R1 SR-EdgeNet
    r1_box = FancyBboxPatch((640, 560), 520, 185, boxstyle="round,pad=0,rounding_size=8",
                            facecolor='#F0FDFA', edgecolor='#0D9488', linewidth=1.5)
    ax.add_patch(r1_box)
    ax.text(655, 725, "MODULE R1: SR-EdgeNet (Spatial-Relational Structural Classifier)", fontsize=9.5, fontweight='bold', color='#0F766E')
    ax.text(655, 708, "Parameters: 414K | Replaces Recursive XY-Cut with Pairwise Multigraph Link Prediction", fontsize=7.5, color='#475569')

    # Visual representation of graph nodes inside R1
    # Node 1: Question
    n1 = FancyBboxPatch((655, 620), 140, 65, boxstyle="round,pad=0,rounding_size=4", facecolor='#FFFFFF', edgecolor='#0D9488', linewidth=1)
    ax.add_patch(n1)
    ax.text(725, 660, "Question Stem (v1)", ha='center', va='center', fontsize=7.5, fontweight='bold', color='#0F172A')
    ax.text(725, 640, "MiniLM 384-d || BBox", ha='center', va='center', fontsize=6.5, color='#64748B')

    # Node 2: Option A
    n2 = FancyBboxPatch((840, 655), 130, 45, boxstyle="round,pad=0,rounding_size=4", facecolor='#FFFFFF', edgecolor='#0D9488', linewidth=1)
    ax.add_patch(n2)
    ax.text(905, 678, "Option [A] (v2)", ha='center', va='center', fontsize=7, fontweight='bold', color='#0F172A')

    # Node 3: Option B
    n3 = FancyBboxPatch((840, 600), 130, 45, boxstyle="round,pad=0,rounding_size=4", facecolor='#FFFFFF', edgecolor='#0D9488', linewidth=1)
    ax.add_patch(n3)
    ax.text(905, 623, "Option [B] (v3)", ha='center', va='center', fontsize=7, fontweight='bold', color='#0F172A')

    # Directed edges
    e1 = FancyArrowPatch((795, 665), (840, 678), arrowstyle='-|>', mutation_scale=10, color='#0D9488', linewidth=1.5)
    ax.add_patch(e1)
    ax.text(817, 680, "OPTION_OF", ha='center', va='bottom', fontsize=5.8, fontweight='bold', color='#0D9488')

    e2 = FancyArrowPatch((795, 640), (840, 623), arrowstyle='-|>', mutation_scale=10, color='#0D9488', linewidth=1.5)
    ax.add_patch(e2)
    ax.text(817, 622, "OPTION_OF", ha='center', va='top', fontsize=5.8, fontweight='bold', color='#0D9488')

    # Summary metric badge inside R1
    mbadge1 = FancyBboxPatch((990, 605), 155, 95, boxstyle="round,pad=0,rounding_size=4", facecolor='#FFFFFF', edgecolor='#CBD5E1', linewidth=1)
    ax.add_patch(mbadge1)
    ax.text(1067, 685, "EMPIRICAL PERFORMANCE", ha='center', va='center', fontsize=6.8, fontweight='bold', color='#0F766E')
    ax.text(1067, 665, "• Synthetic Acc: 99.46%", ha='center', va='center', fontsize=6.8, color='#334155')
    ax.text(1067, 645, "• OPTION_OF Prec: 88.89%", ha='center', va='center', fontsize=6.8, color='#334155')
    ax.text(1067, 625, "• Reading Order F1: 0.9682", ha='center', va='center', fontsize=6.8, color='#334155')

    # Downward connector R1 -> R2
    arr_r1_r2 = FancyArrowPatch((900, 560), (900, 535), arrowstyle='-|>', mutation_scale=10, color='#6366F1', linewidth=1.5)
    ax.add_patch(arr_r1_r2)
    ax.text(915, 547, "Reconstructed Subgraph", ha='left', va='center', fontsize=6.5, color='#4338CA')

    # Sub-block 2: R2 ER-SP
    r2_box = FancyBboxPatch((640, 360), 520, 175, boxstyle="round,pad=0,rounding_size=8",
                            facecolor='#FFFBEB', edgecolor='#D97706', linewidth=1.5)
    ax.add_patch(r2_box)
    ax.text(655, 515, "MODULE R2: ER-SP (Evidence Relevance & Sufficiency Predictor)", fontsize=9.5, fontweight='bold', color='#B45309')
    ax.text(655, 498, "Parameters: 560K | 5 Epistemic States via 1,537-d Interaction Tensor + Attention Pooling", fontsize=7.5, color='#475569')

    # Epistemic states visualization
    states = [
        ("SUFFICIENT", "#059669", "Complete context entailing proof"),
        ("PARTIALLY_SUFF", "#D97706", "Topical overlap but missing condition"),
        ("CONTRADICTORY", "#DC2626", "Polarity mismatch / opposes query"),
        ("UNVERIFIABLE", "#7C3AED", "Speculative / subjective claim")
    ]
    for idx, (s_name, s_col, s_desc) in enumerate(states):
        bx = 655 + idx * 125
        sbox = FancyBboxPatch((bx, 420), 115, 65, boxstyle="round,pad=0,rounding_size=4", facecolor='#FFFFFF', edgecolor=s_col, linewidth=1.2)
        ax.add_patch(sbox)
        # title
        ax.text(bx + 57.5, 468, s_name, ha='center', va='center', fontsize=6.5, fontweight='bold', color=s_col)
        ax.text(bx + 57.5, 442, s_desc, ha='center', va='center', fontsize=5.8, color='#475569', wrap=True)

    # Downward connector R2 -> R3
    arr_r2_r3 = FancyArrowPatch((900, 360), (900, 335), arrowstyle='-|>', mutation_scale=10, color='#6366F1', linewidth=1.5)
    ax.add_patch(arr_r2_r3)
    ax.text(915, 347, "Epistemic Probability Vector", ha='left', va='center', fontsize=6.5, color='#4338CA')

    # Sub-block 3: R3 CM-RP & Dispatch Triage
    r3_box = FancyBboxPatch((640, 60), 520, 275, boxstyle="round,pad=0,rounding_size=8",
                            facecolor='#FAF5FF', edgecolor='#7C3AED', linewidth=1.5)
    ax.add_patch(r3_box)
    ax.text(655, 315, "MODULE R3: CM-RP (Contextual Multi-Strategy Reasoning Policy)", fontsize=9.5, fontweight='bold', color='#6D28D9')
    ax.text(655, 298, "Parameters: 63K | 423-d State (Query + Structure + Evidence + Telemetry) | Dynamic HW Masking", fontsize=7.5, color='#475569')

    # 7 concrete solver tiles
    solvers = [
        ("ARITHMETIC_SOLVER", "Python AST Evaluator", "#2563EB", 655, 230),
        ("DBMS_SOLVER", "Armstrong's Axiom Normalizer", "#0D9488", 820, 230),
        ("FORMAL_LOGIC_SOLVER", "Model-Theoretic Venn Prover", "#B45309", 985, 230),
        ("EXTRACTIVE_QA", "CitationVerifier Quote Span", "#4F46E5", 655, 145),
        ("LOCAL_SLM", "Local 3B/7B Synthesis", "#7C3AED", 820, 145),
        ("ABSTAIN", "Safe Epistemic Refusal", "#DC2626", 985, 145)
    ]

    for s_id, s_sub, s_col, sx, sy in solvers:
        sbox = FancyBboxPatch((sx, sy), 150, 55, boxstyle="round,pad=0,rounding_size=4", facecolor='#FFFFFF', edgecolor=s_col, linewidth=1.2)
        ax.add_patch(sbox)
        ax.text(sx + 75, sy + 38, s_id, ha='center', va='center', fontsize=6.8, fontweight='bold', color=s_col)
        ax.text(sx + 75, sy + 18, s_sub, ha='center', va='center', fontsize=6, color='#475569')

    # Hardware Guardrail Banner inside R3
    hw_bar = FancyBboxPatch((655, 75), 485, 45, boxstyle="round,pad=0,rounding_size=4", facecolor='#FFFFFF', edgecolor='#CBD5E1', linewidth=0.8)
    ax.add_patch(hw_bar)
    ax.text(665, 102, "Hardware Telemetry Guardrail: Host RAM & CPU Monitor", ha='left', va='center', fontsize=7, fontweight='bold', color='#0F172A')
    ax.text(665, 87, "m_t(LOCAL_SLM) = 0 when RAM < 1.5 GB or CPU > 92% -> Prevents Edge Out-Of-Memory Crashes", ha='left', va='center', fontsize=6.2, color='#64748B')

    # Arrows Region 3 -> Region 4
    # Arithmetic -> Math answer
    ax.add_patch(FancyArrowPatch((1135, 255), (1215, 700), arrowstyle='-|>', mutation_scale=10, color='#2563EB', linewidth=1.5, connectionstyle="arc3,rad=-0.1"))
    # DBMS -> Relational answer
    ax.add_patch(FancyArrowPatch((1135, 255), (1215, 540), arrowstyle='-|>', mutation_scale=10, color='#0D9488', linewidth=1.5, connectionstyle="arc3,rad=-0.05"))
    # Logic -> Logic answer
    ax.add_patch(FancyArrowPatch((1135, 255), (1215, 380), arrowstyle='-|>', mutation_scale=10, color='#B45309', linewidth=1.5, connectionstyle="arc3,rad=0.0"))
    # Extractive -> Quoted citation answer
    ax.add_patch(FancyArrowPatch((1135, 170), (1215, 220), arrowstyle='-|>', mutation_scale=10, color='#4F46E5', linewidth=1.5, connectionstyle="arc3,rad=0.05"))
    # Abstain -> Safe refusal
    ax.add_patch(FancyArrowPatch((1135, 170), (1215, 100), arrowstyle='-|>', mutation_scale=10, color='#DC2626', linewidth=1.5, connectionstyle="arc3,rad=0.1"))

    # ================= REGION 4: INTELLIGENT RESULTS =================
    outputs_data = [
        ("Deterministic Numerical Proof", "Specialized SafeArithmeticEvaluator\nAnswer: Total Amortized Value = $14,250.00\n[Verified Python AST Calculation: 100% Precision]", 680, "#2563EB"),
        ("Relational Normalization Proof", "Specialized DBMSNormalizationSolver\nCandidate Key: {StudentID, CourseCode}\nViolates BCNF: Functional Dependency Verified", 520, "#0D9488"),
        ("Model-Theoretic Logic Derivation", "FormalLogicSolver Countermodel Prover\nDeductive Status: VALID Modus Tollens\nNo Venn Counterexample Found", 360, "#B45309"),
        ("Grounded Citation Response", "CitationVerifier Audited Extraction\nQuote: 'Statutory limitation period is 3 years'\nCitation: [Doc: 1, Page: 4, Block: 12] (Grounded)", 200, "#4F46E5"),
        ("Safe Epistemic Refusal", "Epistemic Gating Safeguard (ER-SP Active)\nOutput: '[ABSTAIN: Insufficient citation support]'\nZero Speculative Hallucination Emitted", 70, "#DC2626")
    ]

    for title, desc, y_pos, o_col in outputs_data:
        ocard = FancyBboxPatch((1215, y_pos - 45), 330, 95, boxstyle="round,pad=0,rounding_size=6",
                               facecolor='#FFFFFF', edgecolor=o_col, linewidth=1.2)
        ax.add_patch(ocard)
        # badge
        obadge = FancyBboxPatch((1225, y_pos + 32), 60, 16, boxstyle="round,pad=0,rounding_size=3",
                                facecolor=o_col, edgecolor='none')
        ax.add_patch(obadge)
        ax.text(1255, y_pos + 40, "RESULT", ha='center', va='center', fontsize=6.2, fontweight='bold', color='#FFFFFF')
        
        ax.text(1295, y_pos + 40, title, ha='left', va='center', fontsize=7.5, fontweight='bold', color='#0F172A')
        ax.text(1225, y_pos - 10, desc, ha='left', va='center', fontsize=6.2, color='#334155')

    # Save to high-resolution PNG and clean vector SVG
    plt.savefig(output_png, dpi=300, bbox_inches='tight', pad_inches=0.1)
    plt.savefig(output_svg, format='svg', bbox_inches='tight', pad_inches=0.1)
    plt.close()
    print(f"Generated Figure 1 PNG: {output_png}")
    print(f"Generated Figure 1 SVG: {output_svg}")

if __name__ == "__main__":
    out_dir = os.path.abspath("research/paper/figures")
    os.makedirs(out_dir, exist_ok=True)
    png_path = os.path.join(out_dir, "setu_netra_platform_vision.png")
    svg_path = os.path.join(out_dir, "setu_netra_platform_vision.svg")
    create_platform_vision_figure(png_path, svg_path)
