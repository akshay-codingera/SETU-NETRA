"""
statistical_analyzer.py: Formal statistical testing and repeated-measures models for SETU-NETRA V1.1.
Implements:
- 2x2 Repeated-Measures Factorial ANOVA (isolating Routing main effect, Scheduling main effect, and Interaction)
- McNemar's test for paired binary classifications
- Paired Wilcoxon signed-rank test for continuous scores (F1, Latency)
- Non-parametric bootstrap confidence intervals for effect sizes
"""

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
import scipy.stats as stats


def compute_repeated_measures_factorial_anova(
    y00: Sequence[float],
    y01: Sequence[float],
    y10: Sequence[float],
    y11: Sequence[float],
    metric_name: str = "metric",
) -> Dict[str, Any]:
    """Computes a 2x2 Repeated-Measures Factorial ANOVA using orthogonal contrast vectors.

    Conditions:
        y00: Fixed Model + Round Robin (Factor A = 0, Factor B = 0)
        y01: Fixed Model + Capacity-Aware (Factor A = 0, Factor B = 1)
        y10: Adaptive Routing + Round Robin (Factor A = 1, Factor B = 0)
        y11: Adaptive Routing + Capacity-Aware (Factor A = 1, Factor B = 1)

    Returns:
        Dict containing F-statistics, degrees of freedom, p-values, and effect sizes (eta squared).
    """
    a00 = np.array(y00, dtype=float)
    a01 = np.array(y01, dtype=float)
    a10 = np.array(y10, dtype=float)
    a11 = np.array(y11, dtype=float)

    n = len(a00)
    if not (len(a01) == n and len(a10) == n and len(a11) == n):
        raise ValueError("All four condition vectors must have identical length (repeated measures).")
    if n < 4:
        raise ValueError("Sample size too small for repeated-measures ANOVA.")

    df_num = 1
    df_den = n - 1

    # 1. Main Effect of Routing (Factor A): (A1 - A0) averaged over B
    # Contrast vector per subject: (y10 + y11) - (y00 + y01)
    contrast_a = (a10 + a11) - (a00 + a01)
    t_a, p_a = stats.ttest_1samp(contrast_a, 0.0)
    f_a = float(t_a**2)

    # Partial eta-squared for A: SS_A / (SS_A + SS_error_A) = t^2 / (t^2 + df_den)
    eta_sq_a = float(f_a / (f_a + df_den)) if (f_a + df_den) > 0 else 0.0

    # 2. Main Effect of Scheduling (Factor B): (B1 - B0) averaged over A
    # Contrast vector per subject: (y01 + y11) - (y00 + y10)
    contrast_b = (a01 + a11) - (a00 + a10)
    t_b, p_b = stats.ttest_1samp(contrast_b, 0.0)
    f_b = float(t_b**2)
    eta_sq_b = float(f_b / (f_b + df_den)) if (f_b + df_den) > 0 else 0.0

    # 3. Interaction Effect (A x B): (y11 - y10) - (y01 - y00)
    contrast_ab = (a11 - a10) - (a01 - a00)
    t_ab, p_ab = stats.ttest_1samp(contrast_ab, 0.0)
    f_ab = float(t_ab**2)
    eta_sq_ab = float(f_ab / (f_ab + df_den)) if (f_ab + df_den) > 0 else 0.0

    return {
        "metric": metric_name,
        "sample_size_n": n,
        "df_numerator": df_num,
        "df_denominator": df_den,
        "main_effect_routing": {
            "contrast_mean": float(np.mean(contrast_a) / 2.0),
            "f_statistic": round(f_a, 4),
            "p_value": float(p_a),
            "partial_eta_squared": round(eta_sq_a, 4),
            "significant_at_05": bool(p_a < 0.05),
        },
        "main_effect_scheduling": {
            "contrast_mean": float(np.mean(contrast_b) / 2.0),
            "f_statistic": round(f_b, 4),
            "p_value": float(p_b),
            "partial_eta_squared": round(eta_sq_b, 4),
            "significant_at_05": bool(p_b < 0.05),
        },
        "interaction_effect": {
            "contrast_mean": float(np.mean(contrast_ab)),
            "f_statistic": round(f_ab, 4),
            "p_value": float(p_ab),
            "partial_eta_squared": round(eta_sq_ab, 4),
            "significant_at_05": bool(p_ab < 0.05),
        },
    }


def compute_mcnemar_test(
    condition1_binary: Sequence[int],
    condition2_binary: Sequence[int],
) -> Dict[str, Any]:
    """Computes McNemar's test for paired binary classifications (e.g. Correct=1, Incorrect=0).

    Contingency matrix:
        | Cond2 Correct (1) | Cond2 Incorrect (0) |
    Cond1 Correct (1)   | a (both 1)        | b (C1=1, C2=0)      |
    Cond1 Incorrect (0) | c (C1=0, C2=1)    | d (both 0)          |
    """
    c1 = np.array(condition1_binary, dtype=int)
    c2 = np.array(condition2_binary, dtype=int)

    if len(c1) != len(c2):
        raise ValueError("Vectors must have equal length for paired McNemar test.")

    a = int(np.sum((c1 == 1) & (c2 == 1)))
    b = int(np.sum((c1 == 1) & (c2 == 0)))
    c = int(np.sum((c1 == 0) & (c2 == 1)))
    d = int(np.sum((c1 == 0) & (c2 == 0)))

    # Edwards continuity correction: (|b - c| - 1)^2 / (b + c)
    discordant = b + c
    if discordant == 0:
        return {
            "statistic_chi2": 0.0,
            "p_value": 1.0,
            "contingency_table": {"both_correct": a, "cond1_only": b, "cond2_only": c, "both_incorrect": d},
            "significant_at_05": False,
            "note": "Zero discordant pairs; distributions are identical.",
        }

    chi2 = float(((abs(b - c) - 1.0) ** 2) / discordant)
    p_val = float(1.0 - stats.chi2.cdf(chi2, df=1))

    return {
        "statistic_chi2": round(chi2, 4),
        "p_value": float(p_val),
        "df": 1,
        "contingency_table": {"both_correct": a, "cond1_only": b, "cond2_only": c, "both_incorrect": d},
        "significant_at_05": bool(p_val < 0.05),
    }


def compute_paired_wilcoxon(
    condition1_scores: Sequence[float],
    condition2_scores: Sequence[float],
    metric_name: str = "score",
) -> Dict[str, Any]:
    """Computes Wilcoxon signed-rank test for paired continuous metrics."""
    s1 = np.array(condition1_scores, dtype=float)
    s2 = np.array(condition2_scores, dtype=float)
    diff = s1 - s2

    # Filter out exact zero differences
    non_zero_diff = diff[diff != 0.0]
    if len(non_zero_diff) == 0:
        return {
            "metric": metric_name,
            "statistic": 0.0,
            "p_value": 1.0,
            "mean_difference": 0.0,
            "significant_at_05": False,
            "note": "All paired differences are zero.",
        }

    stat, p_val = stats.wilcoxon(s1, s2)
    return {
        "metric": metric_name,
        "statistic": float(stat),
        "p_value": float(p_val),
        "mean_difference": float(np.mean(diff)),
        "median_difference": float(np.median(diff)),
        "significant_at_05": bool(p_val < 0.05),
    }
