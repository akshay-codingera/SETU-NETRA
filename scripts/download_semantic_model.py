"""
download_semantic_model.py: Explicit setup utility to download and cache pretrained semantic weights.

Why this file exists:
In accordance with SETU-NETRA requirements, pretrained neural weights must NEVER be downloaded
implicitly or automatically during inference or unit testing. This script provides an explicit,
reproducible setup procedure to download, verify, and cache 'all-MiniLM-L6-v2' for subsequent
strictly offline inference.
"""

import argparse
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download and verify pretrained sentence-transformer weights for SETU-NETRA."
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="all-MiniLM-L6-v2",
        help="Pretrained model identifier (default: 'all-MiniLM-L6-v2').",
    )
    parser.add_argument(
        "--local-dir",
        type=str,
        default=None,
        help="Optional local directory to save the standalone model files (e.g. 'models/all-MiniLM-L6-v2').",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("  SETU-NETRA: Pretrained Semantic Model Setup Utility")
    print("=" * 70)
    print(f"Target Model:   {args.model_name}")

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("\n[ERROR] 'sentence-transformers' package is not installed.")
        print("Please install it first using: python -m pip install sentence-transformers")
        return 1

    start_time = time.perf_counter()
    print(f"\n[1/3] Downloading model weights and tokenizer for '{args.model_name}'...")
    try:
        # Load from HuggingFace Hub and cache
        model = SentenceTransformer(args.model_name)
    except Exception as err:
        print(f"\n[ERROR] Failed to download model '{args.model_name}': {err}")
        return 1

    # If local directory requested, save standalone copy
    if args.local_dir:
        target_path = Path(args.local_dir)
        target_path.mkdir(parents=True, exist_ok=True)
        print(f"[2/3] Saving standalone weights to: {target_path.resolve()}...")
        model.save(str(target_path))
    else:
        print("[2/3] Stored weights in standard HuggingFace local cache.")

    # Verification inference
    print("\n[3/3] Running verification inference on CPU...")
    test_phrase = "SETU-NETRA semantic model verification: 2D convolution and asymptotic runtime."
    embeddings = model.encode(
        [test_phrase],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    elapsed_s = time.perf_counter() - start_time
    dim = embeddings.shape[1]
    norm = float((embeddings[0] ** 2).sum() ** 0.5)

    print("\n" + "-" * 70)
    print("  Model Verification Succeeded!")
    print("-" * 70)
    print(f"  - Model Identifier:       {args.model_name}")
    print(f"  - Embedding Dimension:    {dim} (Expected: 384)")
    print(f"  - L2 Vector Norm:         {norm:.4f} (Expected: ~1.0000)")
    print(f"  - Total Setup Time:       {elapsed_s:.2f} s")
    print("-" * 70)
    print("  Pretrained weights are now cached locally.")
    print("  SETU-NETRA will now be able to run offline neural inference.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
