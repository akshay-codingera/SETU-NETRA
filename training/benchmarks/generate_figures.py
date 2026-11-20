"""
generate_figures.py: Generates publication-grade SVG diagrams for SETU-NETRA Milestone R4:
1. architecture_pipeline.svg (End-to-End System Architecture)
2. confusion_matrices.svg (4x4, 5x5, and 7x7 Matrices Visualized)
3. ablation_barchart.svg (C1 to C6 Performance Comparison)
"""

import os
import json

os.makedirs("research/paper/figures", exist_ok=True)

# 1. Architecture Pipeline SVG
arch_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 700" width="100%" height="100%">
  <defs>
    <style>
      .title { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 22px; font-weight: bold; fill: #1e293b; }
      .subtitle { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 13px; fill: #64748b; }
      .box { rx: 8px; stroke-width: 1.5px; }
      .box-input { fill: #f8fafc; stroke: #94a3b8; }
      .box-r1 { fill: #eff6ff; stroke: #3b82f6; }
      .box-r2 { fill: #f0fdf4; stroke: #22c55e; }
      .box-r3 { fill: #faf5ff; stroke: #a855f7; }
      .box-solver { fill: #fff7ed; stroke: #f97316; }
      .box-verify { fill: #fef2f2; stroke: #ef4444; }
      .box-output { fill: #f1f5f9; stroke: #475569; }
      .node-title { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 13px; font-weight: bold; fill: #0f172a; }
      .node-desc { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 11px; fill: #475569; }
      .badge { font-family: monospace; font-size: 10px; font-weight: bold; }
      .badge-r1 { fill: #1d4ed8; }
      .badge-r2 { fill: #15803d; }
      .badge-r3 { fill: #7e22ce; }
      .arrow { stroke: #64748b; stroke-width: 2; marker-end: url(#arrowhead); fill: none; }
      .arrow-opt { stroke: #94a3b8; stroke-dasharray: 4,4; stroke-width: 1.5; marker-end: url(#arrowhead-gray); fill: none; }
    </style>
    <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
      <polygon points="0 0, 8 3, 0 6" fill="#64748b" />
    </marker>
    <marker id="arrowhead-gray" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
      <polygon points="0 0, 8 3, 0 6" fill="#94a3b8" />
    </marker>
  </defs>

  <!-- Canvas Background -->
  <rect width="1100" height="700" fill="#ffffff" />

  <!-- Header -->
  <text x="40" y="45" class="title">SETU-NETRA: Milestone R4 Integrated Neural Pipeline</text>
  <text x="40" y="68" class="subtitle">CPU-First Hierarchical Document Intelligence: Structural Layout (R1) → Epistemic Gating (R2) → Multi-Strategy Dispatch (R3)</text>

  <!-- Stage 1 & 2: Ingestion & OCR -->
  <g transform="translate(40, 100)">
    <rect width="200" height="90" class="box box-input" />
    <text x="15" y="30" class="node-title">1. Document Ingestion</text>
    <text x="15" y="50" class="node-desc">PDF, Scanned Images, DOCX</text>
    <text x="15" y="68" class="node-desc">Pillow &amp; Structural Normalizer</text>
  </g>

  <g transform="translate(40, 230)">
    <rect width="200" height="90" class="box box-input" />
    <text x="15" y="30" class="node-title">2. OCR &amp; Bounding Boxes</text>
    <text x="15" y="50" class="node-desc">Tesseract / Native Geometry</text>
    <text x="15" y="68" class="node-desc">Token Blocks &amp; Normalization</text>
  </g>

  <!-- Stage 3: R1 SR-EdgeNet -->
  <g transform="translate(290, 160)">
    <rect width="220" height="120" class="box box-r1" />
    <text x="15" y="28" class="node-title">3. R1: SR-EdgeNet</text>
    <text x="15" y="45" class="badge badge-r1">414K Params | Spatial-Relational</text>
    <text x="15" y="65" class="node-desc">Dual Text/Spatial Projections</text>
    <text x="15" y="83" class="node-desc">Hierarchy &amp; Reading Graph</text>
    <text x="15" y="101" class="node-desc">PARENT / OPTION / CONT / NONE</text>
  </g>

  <!-- Stage 4: Retrieval -->
  <g transform="translate(560, 100)">
    <rect width="200" height="90" class="box box-input" />
    <text x="15" y="30" class="node-title">4. Hybrid Search Engine</text>
    <text x="15" y="50" class="node-desc">Dense MiniLM + BM25 Lexical</text>
    <text x="15" y="68" class="node-desc">Top-K Candidate Passages</text>
  </g>

  <!-- Stage 5: R2 ER-SP -->
  <g transform="translate(560, 230)">
    <rect width="220" height="120" class="box box-r2" />
    <text x="15" y="28" class="node-title">5. R2: ER-SP Gating</text>
    <text x="15" y="45" class="badge badge-r2">560K Params | Epistemic Predictor</text>
    <text x="15" y="65" class="node-desc">Multi-Head Question-Passage Attn</text>
    <text x="15" y="83" class="node-desc">Detects Contradictions &amp; Gaps</text>
    <text x="15" y="101" class="node-desc">SUFFICIENT / CONTRADICTORY / etc.</text>
  </g>

  <!-- Stage 6: R3 CM-RP -->
  <g transform="translate(300, 390)">
    <rect width="480" height="110" class="box box-r3" />
    <text x="20" y="28" class="node-title">6. R3: CM-RP Contextual Multi-Strategy Reasoning Policy</text>
    <text x="20" y="45" class="badge badge-r3">63K Params (v2) | 423-d Context Vectors | System Telemetry Aware</text>
    <text x="20" y="65" class="node-desc">Evaluates Question Embeddings + Structure (R1) + Evidence Sufficiency (R2) + RAM Constraints</text>
    <text x="20" y="85" class="node-desc">Guards: High-Confidence Fallback &amp; Low-Memory Action Masking (LOCAL_SLM disabled &lt;1.5GB)</text>
  </g>

  <!-- Solvers Execution -->
  <g transform="translate(80, 540)">
    <rect width="180" height="90" class="box box-solver" />
    <text x="15" y="30" class="node-title">Deterministic Solvers</text>
    <text x="15" y="50" class="node-desc">Arithmetic AST Evaluator</text>
    <text x="15" y="68" class="node-desc">DBMS Relational Normalizer</text>
    <text x="15" y="84" class="node-desc">Formal Syllogism Engine</text>
  </g>

  <g transform="translate(320, 540)">
    <rect width="180" height="90" class="box box-solver" />
    <text x="15" y="30" class="node-title">Extractive QA</text>
    <text x="15" y="50" class="node-desc">Exact Context Quotation</text>
    <text x="15" y="68" class="node-desc">Provenance Tracing</text>
    <text x="15" y="84" class="node-desc">[Doc: X, Page: P, Block: B]</text>
  </g>

  <g transform="translate(560, 540)">
    <rect width="180" height="90" class="box box-solver" />
    <text x="15" y="30" class="node-title">Local SLM Adapter</text>
    <text x="15" y="50" class="node-desc">Grounded Synthesis</text>
    <text x="15" y="68" class="node-desc">Hardware Gated Execution</text>
  </g>

  <g transform="translate(800, 540)">
    <rect width="220" height="90" class="box box-verify" />
    <text x="15" y="30" class="node-title">Citation Verification / Abstain</text>
    <text x="15" y="50" class="node-desc">Tripartite Audit Grounding</text>
    <text x="15" y="68" class="node-desc">Zero-Hallucination Gate</text>
    <text x="15" y="84" class="node-desc">Epistemic Non-Generation</text>
  </g>

  <!-- Connections -->
  <path d="M 140 190 L 140 230" class="arrow" />
  <path d="M 240 275 L 290 220" class="arrow" />
  <path d="M 240 145 L 560 145" class="arrow" />
  <path d="M 660 190 L 660 230" class="arrow" />
  <path d="M 400 280 L 400 390" class="arrow" />
  <path d="M 660 350 L 660 390" class="arrow" />
  <path d="M 400 500 L 170 540" class="arrow" />
  <path d="M 470 500 L 410 540" class="arrow" />
  <path d="M 580 500 L 650 540" class="arrow" />
  <path d="M 720 500 L 880 540" class="arrow" />
  <path d="M 500 585 L 800 585" class="arrow" />
</svg>
"""

with open("research/paper/figures/architecture_pipeline.svg", "w", encoding="utf-8") as f:
    f.write(arch_svg)

print("Saved architecture_pipeline.svg")

# 2. Confusion Matrices Visual SVG
with open("research/paper/evidence/FINAL_METRICS.json", "r", encoding="utf-8") as f:
    metrics = json.load(f)

sr_cm = metrics["confusion_matrices"]["sr_edgenet_synthetic_4x4"]["normalized_percent"]
er_cm = metrics["confusion_matrices"]["er_sp_unseen_5x5"]["normalized_percent"]
cm_cm = metrics["confusion_matrices"]["cm_rp_fallback_7x7"]["normalized_percent"]

cm_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 650" width="100%" height="100%">
  <defs>
    <style>
      .title {{ font-family: sans-serif; font-size: 20px; font-weight: bold; fill: #0f172a; }}
      .sub {{ font-family: sans-serif; font-size: 12px; fill: #64748b; }}
      .header {{ font-family: sans-serif; font-size: 11px; font-weight: bold; fill: #334155; }}
      .lbl {{ font-family: monospace; font-size: 9px; fill: #475569; }}
      .val {{ font-family: sans-serif; font-size: 10px; font-weight: bold; text-anchor: middle; }}
    </style>
  </defs>
  <rect width="1200" height="650" fill="#ffffff" />
  <text x="40" y="40" class="title">SETU-NETRA: Empirical Confusion Matrices (Milestone R4 Real Test Splits)</text>
  <text x="40" y="60" class="sub">Row-Normalized Recall Percentages (%) Across All Three Research Components</text>

  <!-- 1. SR-EdgeNet (4x4) -->
  <g transform="translate(40, 100)">
    <text x="0" y="0" class="header">1. SR-EdgeNet 4x4 (Synthetic Test, N=4,423)</text>
    <text x="0" y="16" class="lbl">Acc: 99.46% | Macro F1: 0.9909</text>
    <!-- Grid -->
    <g transform="translate(100, 40)">
      <!-- Col Headers -->
      <text x="25" y="-10" class="lbl" text-anchor="middle">PARENT</text>
      <text x="75" y="-10" class="lbl" text-anchor="middle">OPTION</text>
      <text x="125" y="-10" class="lbl" text-anchor="middle">CONT</text>
      <text x="175" y="-10" class="lbl" text-anchor="middle">NONE</text>
      <!-- Row Headers -->
      <text x="-10" y="30" class="lbl" text-anchor="end">PARENT</text>
      <text x="-10" y="80" class="lbl" text-anchor="end">OPTION</text>
      <text x="-10" y="130" class="lbl" text-anchor="end">CONT</text>
      <text x="-10" y="180" class="lbl" text-anchor="end">NONE</text>
      <!-- Cells -->
      <!-- Row 0 -->
      <rect x="0" y="0" width="50" height="50" fill="#3b82f6" fill-opacity="{sr_cm[0][0]/100.0 * 0.8 + 0.1}" stroke="#cbd5e1" />
      <text x="25" y="30" class="val" fill="{ '#fff' if sr_cm[0][0] > 50 else '#000' }">{sr_cm[0][0]}%</text>
      <rect x="50" y="0" width="50" height="50" fill="#f8fafc" stroke="#cbd5e1" />
      <text x="75" y="30" class="val">{sr_cm[0][1]}%</text>
      <rect x="100" y="0" width="50" height="50" fill="#f8fafc" stroke="#cbd5e1" />
      <text x="125" y="30" class="val">{sr_cm[0][2]}%</text>
      <rect x="150" y="0" width="50" height="50" fill="#f8fafc" stroke="#cbd5e1" />
      <text x="175" y="30" class="val">{sr_cm[0][3]}%</text>

      <!-- Row 1 -->
      <rect x="0" y="50" width="50" height="50" fill="#f8fafc" stroke="#cbd5e1" />
      <text x="25" y="80" class="val">{sr_cm[1][0]}%</text>
      <rect x="50" y="50" width="50" height="50" fill="#3b82f6" fill-opacity="{sr_cm[1][1]/100.0 * 0.8 + 0.1}" stroke="#cbd5e1" />
      <text x="75" y="80" class="val" fill="{ '#fff' if sr_cm[1][1] > 50 else '#000' }">{sr_cm[1][1]}%</text>
      <rect x="100" y="50" width="50" height="50" fill="#f8fafc" stroke="#cbd5e1" />
      <text x="125" y="80" class="val">{sr_cm[1][2]}%</text>
      <rect x="150" y="50" width="50" height="50" fill="#f8fafc" stroke="#cbd5e1" />
      <text x="175" y="80" class="val">{sr_cm[1][3]}%</text>

      <!-- Row 2 -->
      <rect x="0" y="100" width="50" height="50" fill="#f8fafc" stroke="#cbd5e1" />
      <text x="25" y="130" class="val">{sr_cm[2][0]}%</text>
      <rect x="50" y="100" width="50" height="50" fill="#f8fafc" stroke="#cbd5e1" />
      <text x="75" y="130" class="val">{sr_cm[2][1]}%</text>
      <rect x="100" y="100" width="50" height="50" fill="#3b82f6" fill-opacity="{sr_cm[2][2]/100.0 * 0.8 + 0.1}" stroke="#cbd5e1" />
      <text x="125" y="130" class="val" fill="{ '#fff' if sr_cm[2][2] > 50 else '#000' }">{sr_cm[2][2]}%</text>
      <rect x="150" y="100" width="50" height="50" fill="#f8fafc" stroke="#cbd5e1" />
      <text x="175" y="130" class="val">{sr_cm[2][3]}%</text>

      <!-- Row 3 -->
      <rect x="0" y="150" width="50" height="50" fill="#f8fafc" stroke="#cbd5e1" />
      <text x="25" y="180" class="val">{sr_cm[3][0]}%</text>
      <rect x="50" y="150" width="50" height="50" fill="#f8fafc" stroke="#cbd5e1" />
      <text x="75" y="180" class="val">{sr_cm[3][1]}%</text>
      <rect x="100" y="150" width="50" height="50" fill="#f8fafc" stroke="#cbd5e1" />
      <text x="125" y="180" class="val">{sr_cm[3][2]}%</text>
      <rect x="150" y="150" width="50" height="50" fill="#3b82f6" fill-opacity="{sr_cm[3][3]/100.0 * 0.8 + 0.1}" stroke="#cbd5e1" />
      <text x="175" y="180" class="val" fill="{ '#fff' if sr_cm[3][3] > 50 else '#000' }">{sr_cm[3][3]}%</text>
    </g>
  </g>

  <!-- 2. ER-SP (5x5) -->
  <g transform="translate(420, 100)">
    <text x="0" y="0" class="header">2. ER-SP 5x5 (Unseen Topics, N=340)</text>
    <text x="0" y="16" class="lbl">Acc: 86.18% | Macro F1: 0.8553</text>
    <g transform="translate(100, 40)">
      <!-- Col Headers -->
      <text x="22" y="-10" class="lbl" text-anchor="middle">SUFF</text>
      <text x="67" y="-10" class="lbl" text-anchor="middle">PART</text>
      <text x="112" y="-10" class="lbl" text-anchor="middle">CONTRA</text>
      <text x="157" y="-10" class="lbl" text-anchor="middle">IRREL</text>
      <text x="202" y="-10" class="lbl" text-anchor="middle">UNVER</text>
      <!-- Row Headers -->
      <text x="-10" y="27" class="lbl" text-anchor="end">SUFF</text>
      <text x="-10" y="72" class="lbl" text-anchor="end">PART</text>
      <text x="-10" y="117" class="lbl" text-anchor="end">CONTRA</text>
      <text x="-10" y="162" class="lbl" text-anchor="end">IRREL</text>
      <text x="-10" y="207" class="lbl" text-anchor="end">UNVER</text>
      <!-- Matrix Cells -->
      {"".join([f'<rect x="{c*45}" y="{r*45}" width="45" height="45" fill="#22c55e" fill-opacity="{er_cm[r][c]/100.0 * 0.8 + 0.05}" stroke="#cbd5e1" /><text x="{c*45+22}" y="{r*45+27}" class="val" fill="{"#fff" if er_cm[r][c] > 50 else "#000"}">{er_cm[r][c]:.1f}%</text>' for r in range(5) for c in range(5)])}
    </g>
  </g>

  <!-- 3. CM-RP (7x7) -->
  <g transform="translate(800, 100)">
    <text x="0" y="0" class="header">3. CM-RP v2 7x7 (Unseen Topics + Fallback, N=340)</text>
    <text x="0" y="16" class="lbl">Acc: 93.53% | Macro F1: 0.7646</text>
    <g transform="translate(90, 40)">
      <!-- Col Headers -->
      {"".join([f'<text x="{c*36+18}" y="-8" class="lbl" text-anchor="middle">{["AR","DB","LG","EX","SL","RT","AB"][c]}</text>' for c in range(7)])}
      <!-- Row Headers -->
      {"".join([f'<text x="-8" y="{r*36+22}" class="lbl" text-anchor="end">{["ARITH","DBMS","LOGIC","EXT_QA","SLM","RETR","ABSTAIN"][r]}</text>' for r in range(7)])}
      <!-- Matrix Cells -->
      {"".join([f'<rect x="{c*36}" y="{r*36}" width="36" height="36" fill="#a855f7" fill-opacity="{cm_cm[r][c]/100.0 * 0.8 + 0.05}" stroke="#cbd5e1" /><text x="{c*36+18}" y="{r*36+22}" class="val" font-size="8px" fill="{"#fff" if cm_cm[r][c] > 50 else "#000"}">{int(cm_cm[r][c])}%</text>' for r in range(7) for c in range(7)])}
    </g>
  </g>
</svg>
"""

with open("research/paper/figures/confusion_matrices.svg", "w", encoding="utf-8") as f:
    f.write(cm_svg)

print("Saved confusion_matrices.svg")

# 3. Ablation Barchart SVG
abl = metrics["ablation_study"]
configs = list(abl.keys())
c_labels = ["C1: Baseline", "C2: +SR-Edge", "C3: +ER-SP", "C4: +CM-RP", "C5: SR+ER", "C6: Complete"]

abl_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 480" width="100%" height="100%">
  <defs>
    <style>
      .title {{ font-family: sans-serif; font-size: 18px; font-weight: bold; fill: #0f172a; }}
      .sub {{ font-family: sans-serif; font-size: 12px; fill: #64748b; }}
      .axis-lbl {{ font-family: monospace; font-size: 11px; fill: #475569; }}
      .bar-txt {{ font-family: sans-serif; font-size: 10px; font-weight: bold; text-anchor: middle; }}
      .legend {{ font-family: sans-serif; font-size: 11px; fill: #334155; }}
    </style>
  </defs>
  <rect width="900" height="480" fill="#ffffff" />
  <text x="40" y="35" class="title">SETU-NETRA: Ablation Study Comparison (C1 through C6)</text>
  <text x="40" y="55" class="sub">Impact of Component Integration on Task Accuracy, Abstention F1, and Grounding Score</text>

  <!-- Legend -->
  <g transform="translate(520, 30)">
    <rect x="0" y="0" width="14" height="14" fill="#3b82f6" rx="2" />
    <text x="20" y="11" class="legend">Accuracy (%)</text>
    <rect x="120" y="0" width="14" height="14" fill="#22c55e" rx="2" />
    <text x="140" y="11" class="legend">Abstain F1 (x100)</text>
    <rect x="250" y="0" width="14" height="14" fill="#f97316" rx="2" />
    <text x="270" y="11" class="legend">Grounding Score (x100)</text>
  </g>

  <!-- Chart Axis -->
  <g transform="translate(60, 90)">
    <!-- Y Grid lines -->
    <line x1="0" y1="280" x2="780" y2="280" stroke="#e2e8f0" stroke-width="1" />
    <text x="-10" y="284" class="axis-lbl" text-anchor="end">0%</text>
    <line x1="0" y1="210" x2="780" y2="210" stroke="#f1f5f9" stroke-width="1" />
    <text x="-10" y="214" class="axis-lbl" text-anchor="end">25%</text>
    <line x1="0" y1="140" x2="780" y2="140" stroke="#f1f5f9" stroke-width="1" />
    <text x="-10" y="144" class="axis-lbl" text-anchor="end">50%</text>
    <line x1="0" y1="70" x2="780" y2="70" stroke="#f1f5f9" stroke-width="1" />
    <text x="-10" y="74" class="axis-lbl" text-anchor="end">75%</text>
    <line x1="0" y1="0" x2="780" y2="0" stroke="#f1f5f9" stroke-width="1" />
    <text x="-10" y="4" class="axis-lbl" text-anchor="end">100%</text>

    <!-- Bars for C1 - C6 -->
    {"".join([f'''
    <g transform="translate({i * 125 + 20}, 0)">
      <!-- Accuracy Bar -->
      <rect x="0" y="{280 - (abl[cfg]["accuracy"] / 100.0 * 280)}" width="28" height="{abl[cfg]["accuracy"] / 100.0 * 280}" fill="#3b82f6" rx="3" />
      <text x="14" y="{280 - (abl[cfg]["accuracy"] / 100.0 * 280) - 5}" class="bar-txt" fill="#1e40af">{abl[cfg]["accuracy"]}%</text>

      <!-- Abstain F1 Bar -->
      <rect x="32" y="{280 - (abl[cfg]["abstention_f1"] * 280)}" width="28" height="{abl[cfg]["abstention_f1"] * 280}" fill="#22c55e" rx="3" />
      <text x="46" y="{280 - (abl[cfg]["abstention_f1"] * 280) - 5}" class="bar-txt" fill="#166534">{int(abl[cfg]["abstention_f1"]*100)}</text>

      <!-- Grounding Bar -->
      <rect x="64" y="{280 - (abl[cfg]["grounding_score"] * 280)}" width="28" height="{abl[cfg]["grounding_score"] * 280}" fill="#f97316" rx="3" />
      <text x="78" y="{280 - (abl[cfg]["grounding_score"] * 280) - 5}" class="bar-txt" fill="#c2410c">{int(abl[cfg]["grounding_score"]*100)}</text>

      <!-- X Label -->
      <text x="46" y="305" class="axis-lbl" text-anchor="middle">{c_labels[i]}</text>
    </g>
    ''' for i, cfg in enumerate(configs)])}
  </g>
</svg>
"""

with open("research/paper/figures/ablation_barchart.svg", "w", encoding="utf-8") as f:
    f.write(abl_svg)

print("Saved ablation_barchart.svg")
