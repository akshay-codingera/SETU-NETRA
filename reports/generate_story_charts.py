"""
generate_story_charts.py: Generates publication-grade empirical error reduction charts
for SETU-NETRA using Matplotlib.
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUTPUT_DIR = "reports/figures"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Visual styling
plt.rcParams["font.sans-serif"] = "DejaVu Sans"
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["axes.edgecolor"] = "#CBD5E1"
plt.rcParams["axes.linewidth"] = 0.8
plt.rcParams["grid.color"] = "#F1F5F9"
plt.rcParams["grid.linestyle"] = "--"
plt.rcParams["grid.linewidth"] = 0.6

# -----------------------------------------------------------------------------
# Chart 1: Latency & Tail Latency Collapse Across 4 Experimental Conditions
# -----------------------------------------------------------------------------
def make_chart1():
    fig, ax = plt.subplots(figsize=(6.5, 3.2), dpi=300)
    conditions = ["Condition A\n(Fixed + RR)", "Condition B\n(Fixed + CAS)", "Condition C\n(Adaptive + RR)", "Condition D\n(SETU-NETRA Full)"]
    mean_latencies = [2593.62, 6003.94, 289.78, 104.64]
    p95_latencies = [3507.56, 20105.99, 2027.12, 72.78]

    x = np.arange(len(conditions))
    width = 0.35

    rects1 = ax.bar(x - width/2, mean_latencies, width, label="Mean Latency (ms)", color="#3B82F6", edgecolor="#1D4ED8", alpha=0.9)
    rects2 = ax.bar(x + width/2, p95_latencies, width, label="p95 Tail Latency (ms)", color="#EF4444", edgecolor="#B91C1C", alpha=0.9)

    ax.set_ylabel("Latency (ms) — Log Scale", fontsize=9, fontweight="bold", color="#1E293B")
    ax.set_yscale("log")
    ax.set_title("Figure 1: Latency & p95 Tail Latency Collapse Across 4 Conditions (N=100 Queries)", fontsize=9.5, fontweight="bold", color="#0F172A", pad=10)
    ax.set_xticks(x)
    ax.set_xticklabels(conditions, fontsize=8, color="#334155")
    ax.legend(frameon=True, facecolor="#FFFFFF", edgecolor="#CBD5E1", fontsize=8)
    ax.grid(axis="y", alpha=0.7)

    # Annotate Condition D reduction
    ax.annotate("96.0% Latency Drop\n97.9% p95 Tail Drop",
                xy=(3 + width/2, 72.78), xytext=(2.3, 800),
                arrowprops=dict(facecolor="#059669", shrink=0.08, width=1.5, headwidth=6),
                fontsize=7.5, fontweight="bold", color="#059669",
                bbox=dict(boxstyle="round,pad=0.3", fc="#ECFDF5", ec="#10B981", lw=0.8))

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "fig1_latency_collapse.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print("Generated:", path)

# -----------------------------------------------------------------------------
# Chart 2: Grounded Citation Precision & Retrieval Recall Progression
# -----------------------------------------------------------------------------
def make_chart2():
    fig, ax = plt.subplots(figsize=(6.5, 3.2), dpi=300)
    conditions = ["Condition A\n(Naive Baseline)", "Condition B\n(CAS Only)", "Condition C\n(Adaptive Router)", "Condition D\n(SETU-NETRA Full)"]
    citation_precision = [10.0, 10.0, 82.0, 82.0]
    retrieval_recall = [94.0, 94.0, 94.0, 94.0]

    x = np.arange(len(conditions))
    width = 0.35

    rects1 = ax.bar(x - width/2, citation_precision, width, label="Citation Precision (%)", color="#10B981", edgecolor="#047857", alpha=0.9)
    rects2 = ax.bar(x + width/2, retrieval_recall, width, label="Top-3 Retrieval Recall (%)", color="#6366F1", edgecolor="#4338CA", alpha=0.9)

    ax.set_ylabel("Accuracy Percentage (%)", fontsize=9, fontweight="bold", color="#1E293B")
    ax.set_ylim(0, 115)
    ax.set_title("Figure 2: 8.2x Surge in Grounded Citation Precision (ANOVA F=231.6, p < 1e-26)", fontsize=9.5, fontweight="bold", color="#0F172A", pad=10)
    ax.set_xticks(x)
    ax.set_xticklabels(conditions, fontsize=8, color="#334155")
    ax.legend(frameon=True, facecolor="#FFFFFF", edgecolor="#CBD5E1", fontsize=8, loc="upper left")
    ax.grid(axis="y", alpha=0.7)

    for rect in rects1:
        h = rect.get_height()
        ax.annotate(f"{h:.1f}%", xy=(rect.get_x() + rect.get_width() / 2, h), xytext=(0, 2),
                    textcoords="offset points", ha="center", va="bottom", fontsize=7.5, fontweight="bold", color="#065F46")

    for rect in rects2:
        h = rect.get_height()
        ax.annotate(f"{h:.1f}%", xy=(rect.get_x() + rect.get_width() / 2, h), xytext=(0, 2),
                    textcoords="offset points", ha="center", va="bottom", fontsize=7.5, fontweight="bold", color="#3730A3")

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "fig2_citation_precision_surge.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print("Generated:", path)

# -----------------------------------------------------------------------------
# Chart 3: Epistemic Abstention vs Hallucination Rate
# -----------------------------------------------------------------------------
def make_chart3():
    fig, ax = plt.subplots(figsize=(6.5, 3.2), dpi=300)
    stages = ["Unconstrained LLM\n(Raw Autoregressive)", "Basic RAG\n(Dense Bi-Encoder)", "RAG + Thresholding\n(Cosine Gate)", "SETU-NETRA\n(Tripartite Verifier)"]
    hallucination_rate = [45.0, 32.5, 12.0, 0.0]
    abstention_accuracy = [15.0, 40.0, 75.0, 100.0]

    x = np.arange(len(stages))
    width = 0.35

    rects1 = ax.bar(x - width/2, hallucination_rate, width, label="Hallucination Rate (%) [Lower is Better]", color="#F43F5E", edgecolor="#BE123C", alpha=0.9)
    rects2 = ax.bar(x + width/2, abstention_accuracy, width, label="Epistemic Abstention Accuracy (%) [Higher is Better]", color="#0EA5E9", edgecolor="#0369A1", alpha=0.9)

    ax.set_ylabel("Error vs Safety Rate (%)", fontsize=9, fontweight="bold", color="#1E293B")
    ax.set_ylim(0, 115)
    ax.set_title("Figure 3: Systematic Eradication of Hallucinations via Epistemic Gating", fontsize=9.5, fontweight="bold", color="#0F172A", pad=10)
    ax.set_xticks(x)
    ax.set_xticklabels(stages, fontsize=8, color="#334155")
    ax.legend(frameon=True, facecolor="#FFFFFF", edgecolor="#CBD5E1", fontsize=8, loc="upper right")
    ax.grid(axis="y", alpha=0.7)

    # Highlight 0% hallucination
    ax.annotate("0.0% Hallucination Rate\n100.0% Safe Abstention",
                xy=(3 - width/2, 0), xytext=(2.2, 55),
                arrowprops=dict(facecolor="#0284C7", shrink=0.08, width=1.5, headwidth=6),
                fontsize=7.5, fontweight="bold", color="#0369A1",
                bbox=dict(boxstyle="round,pad=0.3", fc="#F0F9FF", ec="#0EA5E9", lw=0.8))

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "fig3_hallucination_elimination.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print("Generated:", path)

# -----------------------------------------------------------------------------
# Chart 4: Resilience Under Worker Crash (The "Black Hole" Failure Mode)
# -----------------------------------------------------------------------------
def make_chart4():
    fig, ax = plt.subplots(figsize=(6.5, 3.2), dpi=300)
    schedulers = ["Round Robin (RR)", "Least Outstanding (LOR)\n[Catastrophic Failure]", "Capacity-Aware (CAS)", "Adaptive Resilient (ARS)\n[SETU-NETRA Circuit Breaker]"]
    success_rates = [90.0, 70.0, 85.0, 100.0]
    colors_list = ["#F59E0B", "#EF4444", "#3B82F6", "#10B981"]
    edge_colors = ["#D97706", "#B91C1C", "#1D4ED8", "#047857"]

    bars = ax.bar(schedulers, success_rates, width=0.55, color=colors_list, edgecolor=edge_colors, alpha=0.9)

    ax.set_ylabel("Request Success Rate (%) Under Worker Crash", fontsize=8.5, fontweight="bold", color="#1E293B")
    ax.set_ylim(0, 115)
    ax.set_title("Figure 4: Resilience Under Worker Crash & Resolution of the 'Black Hole' Bug", fontsize=9.5, fontweight="bold", color="#0F172A", pad=10)
    ax.grid(axis="y", alpha=0.7)

    for bar in bars:
        h = bar.get_height()
        ax.annotate(f"{h:.1f}%", xy=(bar.get_x() + bar.get_width() / 2, h), xytext=(0, 3),
                    textcoords="offset points", ha="center", va="bottom", fontsize=8, fontweight="bold", color="#1E293B")

    ax.annotate("LOR traps requests in dead node\n(Black Hole Effect: 30% Loss)",
                xy=(1, 70), xytext=(0.4, 30),
                arrowprops=dict(facecolor="#DC2626", shrink=0.08, width=1.5, headwidth=6),
                fontsize=7.5, fontweight="bold", color="#B91C1C",
                bbox=dict(boxstyle="round,pad=0.3", fc="#FEF2F2", ec="#EF4444", lw=0.8))

    ax.annotate("Circuit Breaker trips -> 100% Retried",
                xy=(3, 100), xytext=(2.2, 85),
                arrowprops=dict(facecolor="#059669", shrink=0.08, width=1.5, headwidth=6),
                fontsize=7.5, fontweight="bold", color="#047857",
                bbox=dict(boxstyle="round,pad=0.3", fc="#ECFDF5", ec="#10B981", lw=0.8))

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "fig4_resilience_blackhole.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print("Generated:", path)

if __name__ == "__main__":
    make_chart1()
    make_chart2()
    make_chart3()
    make_chart4()
    print("All 4 empirical story figures successfully created.")
