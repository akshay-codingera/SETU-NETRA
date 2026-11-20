"""
operations.py: Atomic, functional image transformations for SETU-NETRA.

Why this file exists:
Image operations should be pure functions that take an image and configuration
parameters and return a transformed copy without side effects. This makes each
operation independently testable, benchmarkable, and swappable.
"""

from typing import Optional, Tuple, Union
from PIL import Image, ImageEnhance, ImageOps

# Explicit safe ceiling for decompression bombs (100 Megapixels)
Image.MAX_IMAGE_PIXELS = 100_000_000

# Mapping filter names to Pillow Resampling enum values
RESAMPLE_FILTERS = {
    "LANCZOS": Image.Resampling.LANCZOS,    # High-quality sinc filter over 36 neighbors (best for text)
    "BICUBIC": Image.Resampling.BICUBIC,    # Cubic interpolation over 16 neighbors
    "BILINEAR": Image.Resampling.BILINEAR,  # Linear interpolation over 4 neighbors
    "NEAREST": Image.Resampling.NEAREST,    # Nearest-neighbor (fastest, introduces jagged edges)
}


def get_resampling_filter(filter_name: str) -> Image.Resampling:
    """Resolve a string filter name to Pillow's Resampling enum.

    Defaults to LANCZOS if unrecognized.
    """
    return RESAMPLE_FILTERS.get(filter_name.upper(), Image.Resampling.LANCZOS)


def to_grayscale(image: Image.Image) -> Image.Image:
    """Convert an image to 8-bit single-channel grayscale (mode 'L').

    Color to Grayscale Theory:
    Standard RGB images have 3 color channels per pixel (Red, Green, Blue).
    Pillow's conversion to mode 'L' applies the standard ITU-R Recommendation 601-2
    luma formula:
        L = 0.299 * R + 0.587 * G + 0.114 * B

    Why not simple arithmetic average (R + G + B) / 3?
    Human photoreceptors (cones in the retina) have peak sensitivity to green light
    (around 555 nm) and lowest sensitivity to blue light. The ITU-R 601 weights
    model perceptual brightness so green contributes ~59% and blue only ~11%.

    Returns:
        A new PIL Image in mode 'L'.
    """
    if image.mode == "L":
        return image.copy()
    return image.convert("L")


def resize_keep_aspect_ratio(
    image: Image.Image,
    max_dimension: int,
    resample_filter: str = "LANCZOS",
) -> Tuple[Image.Image, bool]:
    """Resize an image down so neither width nor height exceeds max_dimension,

    preserving the original aspect ratio.

    Why Aspect Ratio Matters:
    If width and height are scaled independently (non-uniform scaling), characters
    become horizontally stretched or vertically squished, which degrades OCR
    character recognition accuracy. Uniform scaling preserves character geometry.

    Interpolation Theory:
    When resizing, new pixel coordinates rarely align with integer source pixels.
    An interpolation filter calculates new pixel colors:
    - NEAREST: Picks closest pixel; fast, but creates blocky artifacts.
    - BILINEAR: Weighted average of 2x2 neighborhood; smooths gradients.
    - BICUBIC: Weighted average of 4x4 neighborhood; sharp curves.
    - LANCZOS: Windowed sinc filter of 6x6 neighborhood (36 pixels);
      best preserves high-frequency edge contrasts essential for OCR text.

    Args:
        image: Source PIL Image.
        max_dimension: Maximum allowed size for either width or height.
        resample_filter: Filter name ('LANCZOS', 'BICUBIC', 'BILINEAR', 'NEAREST').

    Returns:
        A tuple of (resized_image, was_resized_boolean).
    """
    width, height = image.size

    # If the image is already within bounds, avoid unnecessary resampling blur
    if width <= max_dimension and height <= max_dimension:
        return image.copy(), False

    # Compute scale factor
    scale = max_dimension / max(width, height)
    new_width = max(1, int(round(width * scale)))
    new_height = max(1, int(round(height * scale)))

    pil_filter = get_resampling_filter(resample_filter)
    resized = image.resize((new_width, new_height), resample=pil_filter)
    return resized, True


def adjust_contrast(image: Image.Image, factor: float) -> Image.Image:
    """Adjust the contrast of an image.

    Contrast Theory:
    Contrast is the difference in luminance or color that makes an object
    distinguishable from the background.
    - factor = 1.0 -> Original image unchanged.
    - factor > 1.0 -> Increases contrast (pushes bright pixels brighter, dark
      pixels darker). In document OCR, this separates faint ink/text from gray
      paper shadows or scanner bleed-through.
    - factor < 1.0 -> Decreases contrast (moves all pixels toward neutral gray).

    Args:
        image: Source PIL Image.
        factor: Float multiplier (>0.0). Typical OCR boost is 1.2 to 1.5.

    Returns:
        A new PIL Image with adjusted contrast.
    """
    if abs(factor - 1.0) < 1e-4:
        return image.copy()

    enhancer = ImageEnhance.Contrast(image)
    return enhancer.enhance(factor)


def safe_composite_on_white(image: Image.Image) -> Image.Image:
    """Composite RGBA, LA, or paletted image with alpha transparency onto a solid white background.

    Why this matters:
    When transparent PNGs or scans with transparent backgrounds containing black/dark text
    are converted directly via .convert('RGB'), Pillow defaults to a black background.
    Black text on a black background renders the text invisible, causing complete OCR failure.
    Compositing onto pure white (#FFFFFF) ensures optimal contrast for text recognition.
    """
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        alpha_img = image.convert("RGBA")
        white_bg = Image.new("RGBA", alpha_img.size, (255, 255, 255, 255))
        composited = Image.alpha_composite(white_bg, alpha_img)
        return composited.convert("RGB")
    elif image.mode not in ("RGB", "L"):
        return image.convert("RGB")
    return image.copy()


def normalize_exif_orientation(image: Image.Image) -> Image.Image:
    """Safely normalize image orientation using EXIF tags (e.g. mobile photo uploads)."""
    try:
        transposed = ImageOps.exif_transpose(image)
        if transposed is not None:
            return transposed
    except Exception:
        pass
    return image.copy()


def map_bbox_to_original(
    bbox: Tuple[float, float, float, float],
    orig_size: Tuple[int, int],
    proc_size: Tuple[int, int],
) -> Tuple[float, float, float, float]:
    """Map a bounding box (xmin, ymin, xmax, ymax) from processed image coordinates

    back to the original image coordinate space.

    Args:
        bbox: (xmin, ymin, xmax, ymax) in processed image coordinates.
        orig_size: (width, height) of the original unscaled image.
        proc_size: (width, height) of the processed image seen by OCR.

    Returns:
        (xmin, ymin, xmax, ymax) scaled back to original image space.
    """
    orig_w, orig_h = orig_size
    proc_w, proc_h = proc_size

    if proc_w <= 0 or proc_h <= 0 or (orig_w == proc_w and orig_h == proc_h):
        return bbox

    scale_x = orig_w / float(proc_w)
    scale_y = orig_h / float(proc_h)

    xmin, ymin, xmax, ymax = bbox
    return (
        round(xmin * scale_x, 2),
        round(ymin * scale_y, 2),
        round(xmax * scale_x, 2),
        round(ymax * scale_y, 2),
    )


def map_bbox_to_processed(
    bbox: Tuple[float, float, float, float],
    orig_size: Tuple[int, int],
    proc_size: Tuple[int, int],
) -> Tuple[float, float, float, float]:
    """Map a bounding box (xmin, ymin, xmax, ymax) from original image coordinates

    into processed image coordinates.
    """
    orig_w, orig_h = orig_size
    proc_w, proc_h = proc_size

    if orig_w <= 0 or orig_h <= 0 or (orig_w == proc_w and orig_h == proc_h):
        return bbox

    scale_x = proc_w / float(orig_w)
    scale_y = proc_h / float(orig_h)

    xmin, ymin, xmax, ymax = bbox
    return (
        round(xmin * scale_x, 2),
        round(ymin * scale_y, 2),
        round(xmax * scale_x, 2),
        round(ymax * scale_y, 2),
    )


def sniff_image_format(data_bytes: bytes) -> Optional[str]:
    """Verify magic bytes from binary header to detect true file format regardless of extension.

    Signatures:
    - JPEG: \\xFF\\xD8\\xFF
    - PNG: \\x89PNG\\r\\n\\x1a\\n
    - TIFF: II*\\x00 (little endian) or MM\\x00* (big endian)
    - BMP: BM
    - WEBP: RIFF....WEBP
    """
    if len(data_bytes) < 12:
        return None

    if data_bytes.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if data_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if data_bytes.startswith(b"II*\x00") or data_bytes.startswith(b"MM\x00*"):
        return "TIFF"
    if data_bytes.startswith(b"BM"):
        return "BMP"
    if data_bytes.startswith(b"RIFF") and data_bytes[8:12] == b"WEBP":
        return "WEBP"

    return None

