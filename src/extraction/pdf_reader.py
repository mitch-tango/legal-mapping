"""PDF preflight — text layer detection, page counting, file hashing."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass
class PdfPreflightResult:
    """Result of PDF preflight analysis."""
    file_path: str
    page_count: int
    has_text_layer: bool
    file_hash: str
    error: str | None = None


# Minimum characters across sampled pages to consider text layer present
_MIN_TEXT_CHARS = 50

# Number of pages to sample for text layer detection
_SAMPLE_PAGES = 5


def _compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of file contents."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def preflight_pdf(file_path: str) -> PdfPreflightResult:
    """Run preflight checks on a PDF file.

    Checks:
    1. File is readable and valid PDF
    2. Count pages
    3. Detect text layer by attempting text extraction on first few pages
    4. Compute SHA-256 file hash for identity tracking

    Returns PdfPreflightResult with findings.
    On error (corrupt file, unreadable), returns result with error field set.
    """
    path = Path(file_path)
    if not path.exists():
        return PdfPreflightResult(
            file_path=file_path, page_count=0,
            has_text_layer=False, file_hash="",
            error=f"File not found: {file_path}",
        )

    try:
        file_hash = _compute_file_hash(file_path)
    except OSError as e:
        return PdfPreflightResult(
            file_path=file_path, page_count=0,
            has_text_layer=False, file_hash="",
            error=f"Cannot read file: {e}",
        )

    try:
        reader = PdfReader(file_path)
        page_count = len(reader.pages)
    except Exception as e:
        return PdfPreflightResult(
            file_path=file_path, page_count=0,
            has_text_layer=False, file_hash=file_hash,
            error=f"Cannot parse PDF: {e}",
        )

    # Sample first N pages for text extraction
    total_text = ""
    pages_to_check = min(_SAMPLE_PAGES, page_count)
    for i in range(pages_to_check):
        try:
            page_text = reader.pages[i].extract_text() or ""
            total_text += page_text
        except Exception:
            continue

    has_text_layer = len(total_text.strip()) >= _MIN_TEXT_CHARS

    return PdfPreflightResult(
        file_path=file_path,
        page_count=page_count,
        has_text_layer=has_text_layer,
        file_hash=file_hash,
    )
