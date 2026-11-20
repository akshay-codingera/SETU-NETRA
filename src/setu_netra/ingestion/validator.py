"""
validator.py: Input validation and defensive checks for SETU-NETRA.

Why this file exists:
Never trust user inputs directly. Passing corrupt, non-existent, or massive files
into downstream ML models can crash the Python process, exhaust system memory,
or trigger obscure C-level library faults. Validation acts as the frontline guard.
"""

from pathlib import Path
from typing import Set
from PIL import Image, UnidentifiedImageError

from setu_netra.core.contracts import ValidationResult

# Set explicit safe ceiling for decompression bombs (100 Megapixels)
Image.MAX_IMAGE_PIXELS = 100_000_000

# Supported extensions for images (Milestone 1)
SUPPORTED_IMAGE_EXTENSIONS: Set[str] = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".tiff",
    ".tif",
    ".webp",
}

# Alias for backwards compatibility
SUPPORTED_EXTENSIONS: Set[str] = SUPPORTED_IMAGE_EXTENSIONS

# Supported extensions for multi-modal documents (Milestone 5 through Stage 3)
SUPPORTED_DOCUMENT_EXTENSIONS: Set[str] = SUPPORTED_IMAGE_EXTENSIONS | {
    ".pdf",
    ".docx",
    ".txt",
}

# 50 Megabytes safety ceiling (protects against accidental decompression bombs)
MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024


def validate_image_file(
    file_path: Path,
    max_size_bytes: int = MAX_FILE_SIZE_BYTES,
) -> ValidationResult:
    """Validate that the given path exists, is a recognized image file,

    is not empty or overly large, and has uncorrupted headers.

    Args:
        file_path: Path to the target image file.
        max_size_bytes: Maximum allowed file size on disk in bytes.

    Returns:
        ValidationResult indicating success or specific failure reason.
    """
    path = Path(file_path)

    # 1. Existence check
    if not path.exists():
        return ValidationResult(
            is_valid=False,
            error_message=f"File does not exist: {path}",
            file_path=path,
        )

    # 2. File type check (not a directory)
    if not path.is_file():
        return ValidationResult(
            is_valid=False,
            error_message=f"Path is not a regular file: {path}",
            file_path=path,
        )

    # 3. Extension check
    ext = path.suffix.lower()
    if ext not in SUPPORTED_IMAGE_EXTENSIONS:
        return ValidationResult(
            is_valid=False,
            error_message=(
                f"Unsupported file extension '{ext}'. "
                f"Supported: {sorted(SUPPORTED_IMAGE_EXTENSIONS)}"
            ),
            file_path=path,
        )

    # 4. File size check (empty or excessively large)
    try:
        file_size = path.stat().st_size
    except OSError as err:
        return ValidationResult(
            is_valid=False,
            error_message=f"Cannot inspect file system attributes: {err}",
            file_path=path,
        )

    if file_size == 0:
        return ValidationResult(
            is_valid=False,
            error_message=f"File is empty (0 bytes): {path}",
            file_path=path,
        )

    if file_size > max_size_bytes:
        size_mb = round(file_size / (1024 * 1024), 2)
        max_mb = round(max_size_bytes / (1024 * 1024), 2)
        return ValidationResult(
            is_valid=False,
            error_message=(
                f"File size ({size_mb} MB) exceeds maximum allowed limit "
                f"({max_mb} MB): {path}"
            ),
            file_path=path,
        )

    # 5. Header and integrity validation for image files
    try:
        with Image.open(path) as img:
            img.verify()
    except UnidentifiedImageError:
        return ValidationResult(
            is_valid=False,
            error_message=(
                f"Cannot identify image file format. "
                f"File may be corrupted or not a valid image: {path}"
            ),
            file_path=path,
        )
    except Exception as err:
        return ValidationResult(
            is_valid=False,
            error_message=f"Corrupt or unreadable image file: {err}",
            file_path=path,
        )

    return ValidationResult(is_valid=True, error_message=None, file_path=path)


def validate_document_file(
    file_path: Path,
    max_size_bytes: int = MAX_FILE_SIZE_BYTES,
) -> ValidationResult:
    """Validate that the given path exists, is a recognized document file

    (Image, PDF, DOCX, TXT), is not empty or overly large, and has intact headers.

    Args:
        file_path: Path to the target document.
        max_size_bytes: Maximum allowed file size on disk in bytes.

    Returns:
        ValidationResult indicating success or specific failure reason.
    """
    path = Path(file_path)

    # 1. Existence check
    if not path.exists():
        return ValidationResult(
            is_valid=False,
            error_message=f"File does not exist: {path}",
            file_path=path,
        )

    # 2. File type check (not a directory)
    if not path.is_file():
        return ValidationResult(
            is_valid=False,
            error_message=f"Path is not a regular file: {path}",
            file_path=path,
        )

    # 3. Extension check
    ext = path.suffix.lower()
    if ext not in SUPPORTED_DOCUMENT_EXTENSIONS:
        return ValidationResult(
            is_valid=False,
            error_message=(
                f"Unsupported document extension '{ext}'. "
                f"Supported: {sorted(SUPPORTED_DOCUMENT_EXTENSIONS)}"
            ),
            file_path=path,
        )

    # 4. File size check (empty or excessively large)
    try:
        file_size = path.stat().st_size
    except OSError as err:
        return ValidationResult(
            is_valid=False,
            error_message=f"Cannot inspect file system attributes: {err}",
            file_path=path,
        )

    if file_size == 0:
        return ValidationResult(
            is_valid=False,
            error_message=f"File is empty (0 bytes): {path}",
            file_path=path,
        )

    if file_size > max_size_bytes:
        size_mb = round(file_size / (1024 * 1024), 2)
        max_mb = round(max_size_bytes / (1024 * 1024), 2)
        return ValidationResult(
            is_valid=False,
            error_message=(
                f"File size ({size_mb} MB) exceeds maximum allowed limit "
                f"({max_mb} MB): {path}"
            ),
            file_path=path,
        )

    # 5. Format-specific header and integrity validation
    if ext == ".pdf":
        try:
            with open(path, "rb") as f:
                header = f.read(1024)
            if not header.startswith(b"%PDF") and b"%PDF" not in header[:1024]:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Invalid PDF header: file does not start with '%PDF': {path}",
                    file_path=path,
                )
        except Exception as err:
            return ValidationResult(
                is_valid=False,
                error_message=f"Cannot read PDF header: {err}",
                file_path=path,
            )
        return ValidationResult(is_valid=True, error_message=None, file_path=path)

    if ext == ".docx":
        import zipfile
        try:
            with open(path, "rb") as f:
                magic = f.read(4)
            if not magic.startswith(b"PK\x03\x04"):
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Invalid DOCX file: missing standard PK ZIP header: {path}",
                    file_path=path,
                )
            with zipfile.ZipFile(path, "r") as zf:
                if "word/document.xml" not in zf.namelist():
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"Invalid DOCX document: archive missing 'word/document.xml': {path}",
                        file_path=path,
                    )
        except Exception as err:
            return ValidationResult(
                is_valid=False,
                error_message=f"Corrupt or unreadable DOCX archive: {err}",
                file_path=path,
            )
        return ValidationResult(is_valid=True, error_message=None, file_path=path)

    if ext == ".txt":
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                sample = f.read(2048)
            if not sample.strip():
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Text file contains only whitespace: {path}",
                    file_path=path,
                )
        except Exception as err:
            return ValidationResult(
                is_valid=False,
                error_message=f"Unreadable text file: {err}",
                file_path=path,
            )
        return ValidationResult(is_valid=True, error_message=None, file_path=path)

    # For image extensions, delegate to validate_image_file logic
    try:
        with Image.open(path) as img:
            img.verify()
    except UnidentifiedImageError:
        return ValidationResult(
            is_valid=False,
            error_message=(
                f"Cannot identify image file format. "
                f"File may be corrupted or not a valid image: {path}"
            ),
            file_path=path,
        )
    except Exception as err:
        return ValidationResult(
            is_valid=False,
            error_message=f"Corrupt or unreadable image file: {err}",
            file_path=path,
        )

    return ValidationResult(is_valid=True, error_message=None, file_path=path)

