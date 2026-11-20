"""
loader.py: Safe image loading, metadata extraction, and orientation correction.

Why this file exists:
Image loading must be isolated from processing. This module ensures that:
1. File handles are safely closed after reading.
2. Original disk files are never altered (original image preservation).
3. EXIF orientation metadata (from smartphone cameras) is corrected.
4. Comprehensive metadata (dimensions, color mode, uncompressed memory size)
   is captured up front for logging and downstream pipeline decisions.
"""

from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageOps

from setu_netra.core.contracts import ImageMetadata

# Set explicit safe ceiling for decompression bombs (100 Megapixels)
Image.MAX_IMAGE_PIXELS = 100_000_000


# Channel counts and bytes per pixel across standard Pillow modes
MODE_CHANNELS = {
    "1": 1,      # 1-bit bi-level (black and white)
    "L": 1,      # 8-bit grayscale
    "P": 1,      # 8-bit palette-mapped to color
    "RGB": 3,    # 3x8-bit true color
    "RGBA": 4,   # 4x8-bit true color with alpha transparency
    "CMYK": 4,   # 4x8-bit color separation
    "YCbCr": 3,  # 3x8-bit color video format
    "LAB": 3,    # 3x8-bit lightness + a/b color space
    "HSV": 3,    # 3x8-bit Hue, Saturation, Value
    "I": 4,      # 32-bit signed integer pixels
    "F": 4,      # 32-bit floating point pixels
}


def _get_exif_orientation(image: Image.Image) -> Optional[int]:
    """Extract EXIF orientation tag (Tag 0x0112 / 274) if present."""
    try:
        exif = image.getexif()
        if exif:
            return exif.get(0x0112)
    except Exception:
        # Some formats or corrupt EXIF segments can fail; fail gracefully
        pass
    return None


def extract_metadata(image: Image.Image, file_path: Path) -> ImageMetadata:
    """Extract comprehensive metadata from a loaded PIL Image and its disk file.

    Args:
        image: A loaded PIL Image instance.
        file_path: The filesystem path where the image originated.

    Returns:
        ImageMetadata populated with dimensions, format, mode, and memory estimates.
    """
    path = Path(file_path)
    file_size = path.stat().st_size if path.exists() else 0
    width, height = image.size
    mode = image.mode
    img_format = image.format or path.suffix.replace(".", "").upper()

    channels = MODE_CHANNELS.get(mode, 3)
    # Memory formula: Width * Height * Channels * 1 byte (for 8-bit modes)
    estimated_memory = width * height * channels

    orientation = _get_exif_orientation(image)

    return ImageMetadata(
        file_path=path.resolve(),
        file_name=path.name,
        file_size_bytes=file_size,
        format=img_format,
        color_mode=mode,
        width=width,
        height=height,
        channels=channels,
        estimated_memory_bytes=estimated_memory,
        exif_orientation=orientation,
    )


def load_image(
    file_path: Path,
    auto_orient: bool = True,
) -> Tuple[Image.Image, ImageMetadata]:
    """Safely load an image from disk into memory and extract its metadata.

    Preservation Guarantee:
    - The original file on disk is opened read-only.
    - We load the pixel buffer into RAM using .copy() and immediately close
      the file descriptor.
    - If auto_orient is True, smartphone rotation tags are normalized so the
      image is upright for human viewing and OCR.

    Args:
        file_path: Filesystem path to the image.
        auto_orient: If True, transpose image according to EXIF orientation.

    Returns:
        A tuple of (in_memory_PIL_image, ImageMetadata).
    """
    path = Path(file_path)

    # Step 1: Open and read metadata while bound to the file
    with Image.open(path) as raw_img:
        # Extract initial metadata before any orientation transformation
        initial_metadata = extract_metadata(raw_img, path)

        # Step 2: Create a completely independent in-memory copy
        # so the disk file descriptor can be closed immediately.
        in_memory_img = raw_img.copy()

    # Step 3: Normalize orientation if requested and orientation EXIF tag exists
    if auto_orient and initial_metadata.exif_orientation:
        # ImageOps.exif_transpose detects orientation tags (1-8) and performs
        # necessary 90/180/270 rotations or flips, resetting the tag to 1.
        transposed_img = ImageOps.exif_transpose(in_memory_img)
        if transposed_img is not None:
            in_memory_img = transposed_img
            # Re-extract metadata to reflect new upright dimensions (W and H swap on 90 deg rotation)
            initial_metadata = extract_metadata(in_memory_img, path)

    # Step 4: Composite transparent images over solid white to prevent black-background text loss
    if in_memory_img.mode in ("RGBA", "LA") or (in_memory_img.mode == "P" and "transparency" in in_memory_img.info):
        alpha_img = in_memory_img.convert("RGBA")
        white_bg = Image.new("RGBA", alpha_img.size, (255, 255, 255, 255))
        in_memory_img = Image.alpha_composite(white_bg, alpha_img).convert("RGB")
        final_metadata = extract_metadata(in_memory_img, path)
        return in_memory_img, final_metadata

    return in_memory_img, initial_metadata
