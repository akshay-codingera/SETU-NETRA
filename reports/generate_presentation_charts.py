"""
generate_presentation_charts.py: Generates high-density presentation charts
for the master numerical compendium of SETU-NETRA.
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUTPUT_DIR = "reports/figures"
os.makedirs(OUTPUT_DIR, exist_ok=True)

plt.rcParams["font.sans-serif"] = "DejaVu Sans"
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["axes.edgecolor"] = "#CBD5E1"
plt.rcParams["axes.linewidth"] = 0.8
plt.rcParams["grid.color"] = "#F1F5F9"
plt.rcParams["grid.linestyle"] = "--"
plt.rcParams["grid.linewidth"] = 0.6

# -----------------------------------------------------------------------------
# Chart 5: Model Execution Frontier (Throughput vs Latency on Log-Log Scale)
# -----------------------------------------------------------------------------
def make_chart5():
    fig, ax = plt.subplots(figsize=(6.5, 3.4), dpi=300)
    
    models = [
        ("Extractive QA\n(0.05 ms, 10k req/s)", 0.05, 10000.0, "#059669", "s", 80),
        ("Offline SimHash\n(0.64 ms, 1.5k req/s)", 0.64, 1554.41, "#0284C7", "o", 70),
        ("MiniLM-L6-v2\n(8.57 ms, 116 req/s)", 8.57, 116.64, "#6366F1", "^", 75),
        ("SmolLM2-135M\n(1,208 ms, 0.83 req/s)", 1208.14, 0.83, "#D97706", "D", 75),
        ("Qwen 3.5 2B\n(4,500 ms, 0.22 req/s)", 4500.0, 0.22, "#EA580C", "v", 80),
        ("EasyOCR CRAFT\n(4,497 ms, 0.22 req/s)", 4497.32, 0.22, "#DC2626", "X", 85),
    ]

    for label, lat, tp, color, marker, size in models:
        ax.scatter(lat, tp, color=color, marker=marker, s=size, label=label.split("\n")[0], zorder=4, edgecolor="#0F172A", linewidth=0.6)
        # Position label
        offset_x = 1.3
        offset_y = 1.1
        if "Extractive" in label:
            offset_x, offset_y = 1.25, 0.5
        elif "EasyOCR" in label:
            offset_x, offset_y = 1.2, 0.55
        elif "Qwen" in label:
            offset_x, offset_y = 0.15, 0.35
        ax.annotate(label, (lat, tp), xytext=(lat * offset_x, tp * offset_y),
                    fontsize=7, fontweight="bold", color="#1E293B")

    # Connect trade-off frontier
    frontier_x = [0.05, 0.64, 8.57, 1208.14, 4500.0]
    frontier_y = [10000.0, 1554.41, 116.64, 0.83, 0.22]
    ax.plot(frontier_x, frontier_y, "--", color="#94A3B8", linewidth=1.2, zorder=2)

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Mean Execution Latency (ms) — Log Scale", fontsize=8.5, fontweight="bold", color="#1E293B")
    ax.set_ylabel("Inference Throughput (req/s) — Log Scale", fontsize=8.5, fontweight="bold", color="#1E293B")
    ax.set_title("Figure 5: Model Execution Frontier (200,000x Speed Range on Laptop CPU)", fontsize=9.5, fontweight="bold", color="#0F172A", pad=10)
    ax.grid(True, which="both", alpha=0.5)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "fig5_model_execution_frontier.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print("Generated:", path)

# -----------------------------------------------------------------------------
# Chart 6: CPU Utilization vs Hardware RAM Profile
# -----------------------------------------------------------------------------
def make_chart6():
    fig, ax = plt.subplots(figsize=(6.5, 3.4), dpi=300)
    
    models = ["Extractive QA", "Offline Hash", "MiniLM Embed", "EasyOCR Vision", "SmolLM2-135M", "Qwen 3.5 2B"]
    cpu_percent = [0.5, 2.0, 26.4, 65.0, 87.0, 96.5]
    ram_used_mb = [10.0, 15.0, 120.0, 480.0, 450.0, 1920.0]

    x = np.arange(len(models))
    width = 0.35

    ax2 = ax.twinx()
    rects1 = ax.bar(x - width/2, cpu_percent, width, label="CPU Utilization (%)", color="#3B82F6", edgecolor="#1D4ED8", alpha=0.9)
    rects2 = ax2.bar(x + width/2, ram_used_mb, width, label="RAM Working Set (MB)", color="#F59E0B", edgecolor="#D97706", alpha=0.9)

    ax.set_ylabel("Peak CPU Utilization (%)", fontsize=8.5, fontweight="bold", color="#1D4ED8")
    ax2.set_ylabel("RAM Working Set (MB)", fontsize=8.5, fontweight="bold", color="#D97706")
    ax.set_ylim(0, 115)
    ax2.set_ylim(0, 2300)
    ax.set_title("Figure 6: Hardware Resource Footprint Across All Evaluated Models", fontsize=9.5, fontweight="bold", color="#0F172A", pad=10)
    ax.set_xticks(x)
    ax.set_xticklabels(models, fontsize=8, color="#334155")
    
    # Combined legend
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=8, frameon=True, facecolor="#FFFFFF", edgecolor="#CBD5E1")
    ax.grid(axis="y", alpha=0.6)

    for rect in rects1:
        h = rect.get_height()
        ax.annotate(f"{h:.1f}%", xy=(rect.get_x() + rect.get_width() / 2, h), xytext=(0, 2),
                    textcoords="offset points", ha="center", va="bottom", fontsize=7, fontweight="bold", color="#1E40AF")

    for rect in rects2:
        h = rect.get_height()
        ax2.annotate(f"{int(h)}MB", xy=(rect.get_x() + rect.get_width() / 2, h), xytext=(0, 2),
                     textcoords="offset points", ha="center", va="bottom", fontsize=7, fontweight="bold", color="#B45309")

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "fig6_hardware_resource_footprint.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print("Generated:", path)

# -----------------------------------------------------------------------------
# Chart 7: Retrieval Recall & Precision Across K in {1, 3, 5, 10}
# -----------------------------------------------------------------------------
def make_chart7():
    fig, ax = plt.subplots(figsize=(6.5, 3.2), dpi=300)
    
    k_vals = [1, 3, 5, 10]
    recall_vals = [60.0, 100.0, 100.0, 100.0]
    precision_vals = [60.0, 33.33, 20.0, 10.0]

    ax.plot(k_vals, recall_vals, "o-", color="#10B981", linewidth=2.2, markersize=7, label="Retrieval Recall@K (%) [Coverage]", zorder=4)
    ax.plot(k_vals, precision_vals, "s--", color="#6366F1", linewidth=2.0, markersize=6, label="Retrieval Precision@K (%) [Density]", zorder=4)

    ax.set_xlabel("Top-K Retrieved Passages Window (K)", fontsize=8.5, fontweight="bold", color="#1E293B")
    ax.set_ylabel("Retrieval Metric (%)", fontsize=8.5, fontweight="bold", color="#1E293B")
    ax.set_ylim(0, 115)
    ax.set_xticks(k_vals)
    ax.set_title("Figure 7: Evidence Retrieval Recall vs. Density Across Candidate Window K", fontsize=9.5, fontweight="bold", color="#0F172A", pad=10)
    ax.legend(frameon=True, facecolor="#FFFFFF", edgecolor="#CBD5E1", fontsize=8, loc="center right")
    ax.grid(True, alpha=0.6)

    # Annotate K=3 sweet spot
    ax.annotate("Optimal Sweet Spot (K=3)\n100% Recall @ High Density",
                xy=(3, 100), xytext=(3.5, 80),
                arrowprops=dict(facecolor="#059669", shrink=0.08, width=1.5, headwidth=6),
                fontsize=7.5, fontweight="bold", color="#047857",
                bbox=dict(boxstyle="round,pad=0.3", fc="#ECFDF5", ec="#10B981", lw=0.8))

    for k, r in zip(k_vals, recall_vals):
        ax.annotate(f"{r:.0f}%", (k, r), xytext=(0, 4), textcoords="offset points", ha="center", fontsize=7.5, fontweight="bold", color="#065F46")

    for k, p in zip(k_vals, precision_vals):
        ax.annotate(f"{p:.1f}%", (k, p), xytext=(0, -11), textcoords="offset points", ha="center", fontsize=7.5, fontweight="bold", color="#3730A3")

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "fig7_retrieval_window_tradeoff.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print("Generated:", path)

if __name__ == "__main__":
    make_chart5()
    make_chart6()
    make_chart7()
    print("All additional presentation figures created.")
