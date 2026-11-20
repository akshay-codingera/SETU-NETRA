"""
disambiguation.py: Contextual sense disambiguation for polysemous academic terminology.

Why this file exists:
Words like 'kernel', 'model', 'normalization', 'regression', and 'cell' have radically
different technical meanings across disciplines. This module analyzes lexical co-occurrence,
syntactic context, and surrounding document cues to resolve the active domain sense, or
explicitly declare an ambiguous state when evidence is insufficient.
"""

import re
from typing import Dict, List, Set, Tuple
from setu_netra.core.contracts import DisambiguationDetail


# Disambiguation knowledge base: term -> sense -> context indicator keywords
AMBIGUOUS_TERM_SENSES: Dict[str, Dict[str, Set[str]]] = {
    "kernel": {
        "Image Processing / Spatial Convolution": {
            "image", "convolution", "filter", "stride", "k", "kxk", "hxw", "spatial",
            "pixel", "window", "blur", "pooling", "padding", "2d",
        },
        "Operating Systems / System Architecture": {
            "os", "operating", "system", "linux", "unix", "process", "syscall",
            "system call", "user space", "scheduler", "driver", "monolithic", "microkernel",
        },
        "Machine Learning / Support Vector Machines": {
            "svm", "support vector", "support vector machines", "rbf", "trick", "feature space", "hilbert",
            "reproducing", "gram matrix", "hyperplane", "mercer", "kernel trick",
        },
        "Linear Algebra & Group Theory": {
            "homomorphism", "group", "ring", "null space", "linear map",
            "isomorphism", "vector space", "dimension", "rank-nullity",
        },
    },
    "model": {
        "Machine Learning / Statistical Predictor": {
            "train", "training", "test", "loss", "neural", "parameter", "weight",
            "predict", "prediction", "accuracy", "classifier", "fit", "epoch",
        },
        "Relational Database Schema": {
            "schema", "relational", "entity", "table", "attribute", "er diagram",
            "sql", "foreign key", "normalization",
        },
        "Mathematical Physics / Simulation": {
            "differential equation", "dynamical", "simulation", "fluid",
            "newtonian", "continuum", "numerical",
        },
    },
    "normalization": {
        "Database Systems (Normal Forms)": {
            "1nf", "2nf", "3nf", "bcnf", "relational", "redundancy", "table",
            "schema", "database", "anomaly", "decomposition",
        },
        "Machine Learning / Feature Preprocessing": {
            "batch norm", "layer norm", "scaling", "min-max", "standardization",
            "features", "distribution", "zero mean", "activation",
        },
        "Linear Algebra (Vector Norm)": {
            "vector", "unit vector", "l2 norm", "magnitude", "length", "direction",
        },
    },
    "regression": {
        "Statistics & Machine Learning": {
            "linear", "logistic", "target", "continuous", "r-squared", "mse",
            "fit", "predictor", "coefficients", "variance", "loss",
        },
        "Software Engineering (Defect Regression)": {
            "bug", "test suite", "ci/cd", "commit", "release", "failure",
            "broken", "version", "patch", "git",
        },
    },
    "cell": {
        "Cellular Biology": {
            "membrane", "mitochondria", "dna", "cytoplasm", "organism", "nucleus",
            "tissue", "biological", "protein", "division", "mitosis",
        },
        "Spreadsheet / Data Grid": {
            "excel", "row", "column", "formula", "csv", "table", "sheet", "grid",
        },
        "Electrochemistry & Batteries": {
            "anode", "cathode", "voltage", "battery", "electrolyte", "electrochemical",
            "current", "charge",
        },
    },
}


def disambiguate_terms(text: str, context_text: str = "") -> List[DisambiguationDetail]:
    """Scan text for polysemous terms and resolve their technical sense using contextual evidence.

    Args:
        text: Target text being analyzed.
        context_text: Optional surrounding text (e.g. whole document or adjacent blocks).

    Returns:
        List of DisambiguationDetail records.
    """
    combined_lower = f"{text} {context_text}".lower()
    combined_tokens = set(re.findall(r"[a-z0-9_\-]+", combined_lower))

    results: List[DisambiguationDetail] = []

    for term, senses in AMBIGUOUS_TERM_SENSES.items():
        # Check if the ambiguous term itself appears in the target text as a distinct word
        pattern = rf"\b{re.escape(term)}s?\b"
        if not re.search(pattern, text.lower()):
            continue

        best_sense: str | None = None
        best_count = 0
        best_cues: List[str] = []
        candidate_names = tuple(senses.keys())

        # Count matching cues for each sense
        sense_scores: Dict[str, Tuple[int, List[str]]] = {}
        for sense_name, cues in senses.items():
            matching_cues = [cue for cue in cues if cue in combined_tokens or cue in combined_lower]
            sense_scores[sense_name] = (len(matching_cues), matching_cues)
            if len(matching_cues) > best_count:
                best_count = len(matching_cues)
                best_sense = sense_name
                best_cues = matching_cues

        # Evaluate ambiguity: multiple senses with equal non-zero matches, or zero matches
        sorted_senses = sorted(sense_scores.items(), key=lambda it: it[1][0], reverse=True)

        if best_count == 0:
            # No context cues available to resolve the ambiguity
            results.append(
                DisambiguationDetail(
                    term=term,
                    resolved_sense="AMBIGUOUS / UNRESOLVED",
                    confidence=0.33,
                    candidate_senses=candidate_names,
                    context_cues=(),
                )
            )
        elif len(sorted_senses) >= 2 and sorted_senses[0][1][0] == sorted_senses[1][1][0] and sorted_senses[0][1][0] > 0:
            # Tied top senses (conflicting context evidence)
            results.append(
                DisambiguationDetail(
                    term=term,
                    resolved_sense=f"AMBIGUOUS (Tie between '{sorted_senses[0][0]}' and '{sorted_senses[1][0]}')",
                    confidence=0.50,
                    candidate_senses=candidate_names,
                    context_cues=tuple(best_cues),
                )
            )
        else:
            # Clearly resolved sense
            conf = min(0.98, 0.65 + 0.10 * best_count)
            results.append(
                DisambiguationDetail(
                    term=term,
                    resolved_sense=best_sense or "UNKNOWN",
                    confidence=round(conf, 2),
                    candidate_senses=candidate_names,
                    context_cues=tuple(best_cues),
                )
            )

    return results
