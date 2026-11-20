"""
pipeline.py: Orchestrates image preprocessing steps into a coherent pipeline.

Why this file exists:
Individual operations (operations.py) should not know how they are sequenced.
The pipeline coordinates validation, step application, auditing, and saving,
ensuring strict separation between the original image and the processed variant.
"""

from pathlib import Path
from typing import Optional
from PIL import Image

from setu_netra.core.contracts import (
    ImageMetadata,
    PreprocessConfig,
    ProcessedImageResult,
)
from setu_netra.ingestion.loader import extract_metadata
from setu_netra.preprocessing.operations import (
    to_grayscale,
    resize_keep_aspect_ratio,
    adjust_contrast,
)


class ImagePreprocessor:
    """Configurable pipeline for preprocessing document images for OCR."""

    def __init__(self, config: Optional[PreprocessConfig] = None):
        """Initialize the pipeline with a given configuration.

        If no configuration is passed, defaults are used.
        """
        self.config = config or PreprocessConfig()

    def process(
        self,
        image: Image.Image,
        original_metadata: ImageMetadata,
        output_dir: Optional[Path] = None,
    ) -> ProcessedImageResult:
        """Run the configured preprocessing operations on an in-memory image.

        Guarantee:
        - The input `image` is never modified in-place; a distinct copy is created.
        - Every transformation applied is logged in `steps_applied`.
        - If an output_dir is provided, the processed copy is saved with a clear prefix.

        Args:
            image: In-memory PIL Image.
            original_metadata: Metadata of the original input.
            output_dir: Optional directory where the processed image should be saved.

        Returns:
            ProcessedImageResult containing metadata of both states, audit log,
            and the saved output path (if saved).
        """
        # Step 0: Create a distinct processing copy to guarantee non-destructive execution
        current_img = image.copy()
        steps_applied = []

        # Step 1: Grayscale conversion
        if self.config.convert_grayscale and current_img.mode != "L":
            current_img = to_grayscale(current_img)
            steps_applied.append(
                f"Converted from '{original_metadata.color_mode}' to Grayscale (mode 'L')"
            )

        # Step 2: Aspect-ratio preserving resize
        if self.config.max_dimension is not None:
            resized_img, was_resized = resize_keep_aspect_ratio(
                current_img,
                max_dimension=self.config.max_dimension,
                resample_filter=self.config.resample_filter,
            )
            if was_resized:
                steps_applied.append(
                    f"Resized down from ({original_metadata.width}x{original_metadata.height}) "
                    f"to ({resized_img.width}x{resized_img.height}) using {self.config.resample_filter}"
                )
                current_img = resized_img

        # Step 3: Contrast enhancement
        if abs(self.config.contrast_factor - 1.0) > 1e-4:
            current_img = adjust_contrast(current_img, self.config.contrast_factor)
            steps_applied.append(
                f"Contrast adjusted by factor {self.config.contrast_factor:.2f}"
            )

        # Step 4: Save processed image if output directory is specified
        saved_path: Optional[Path] = None
        if output_dir is not None:
            out_dir = Path(output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)

            # Generate output filename preserving extension
            stem = original_metadata.file_path.stem
            # If in grayscale, saving as PNG is ideal for lossless text reproduction
            out_filename = f"preprocessed_{stem}.png"
            saved_path = (out_dir / out_filename).resolve()

            # Save the processed image
            current_img.save(saved_path, format="PNG")
            steps_applied.append(f"Saved processed copy to: {saved_path}")

        # Extract metadata from the final processed state
        # (Use saved_path if saved, otherwise reference original path)
        ref_path = saved_path if saved_path else original_metadata.file_path
        processed_metadata = extract_metadata(current_img, ref_path)

        return ProcessedImageResult(
            original_metadata=original_metadata,
            processed_metadata=processed_metadata,
            steps_applied=steps_applied,
            output_path=saved_path,
        )
