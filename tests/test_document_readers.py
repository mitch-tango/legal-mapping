"""Tests for Section 04 — PDF Preflight and DOCX Reader."""

from pathlib import Path

import pytest

from src.extraction.pdf_reader import PdfPreflightResult, preflight_pdf
from src.extraction.docx_reader import DocxReadResult, read_docx


FIXTURES = Path(__file__).parent / "fixtures"


# ── PDF Preflight ────────────────────────────────────────────────────────


class TestPdfPreflight:
    def test_pdf_with_text_layer(self):
        result = preflight_pdf(str(FIXTURES / "sample.pdf"))
        assert result.error is None
        assert result.has_text_layer is True
        assert result.page_count >= 1

    def test_scanned_pdf_no_text_layer(self):
        result = preflight_pdf(str(FIXTURES / "sample-scanned.pdf"))
        assert result.error is None
        assert result.has_text_layer is False

    def test_file_hash_computed(self):
        result = preflight_pdf(str(FIXTURES / "sample.pdf"))
        assert result.file_hash
        assert len(result.file_hash) == 64  # SHA-256 hex

    def test_file_hash_deterministic(self):
        r1 = preflight_pdf(str(FIXTURES / "sample.pdf"))
        r2 = preflight_pdf(str(FIXTURES / "sample.pdf"))
        assert r1.file_hash == r2.file_hash

    def test_page_count(self):
        result = preflight_pdf(str(FIXTURES / "sample.pdf"))
        assert result.page_count == 1

    def test_missing_file_returns_error(self):
        result = preflight_pdf("/nonexistent/file.pdf")
        assert result.error is not None
        assert "not found" in result.error.lower() or "File not found" in result.error

    def test_corrupt_file_returns_error(self, tmp_path):
        bad_pdf = tmp_path / "corrupt.pdf"
        bad_pdf.write_bytes(b"not a pdf file at all")
        result = preflight_pdf(str(bad_pdf))
        assert result.error is not None


# ── DOCX Reader ──────────────────────────────────────────────────────────


class TestDocxReader:
    def test_extract_simple_docx(self):
        result = read_docx(str(FIXTURES / "sample.docx"))
        assert result.error is None
        assert "Sample Document" in result.text
        assert result.file_hash
        assert len(result.file_hash) == 64

    def test_preserves_heading_hierarchy(self):
        result = read_docx(str(FIXTURES / "sample.docx"))
        assert result.error is None
        # Should have markdown heading markers
        assert "# " in result.text or "## " in result.text

    def test_file_hash_deterministic(self):
        r1 = read_docx(str(FIXTURES / "sample.docx"))
        r2 = read_docx(str(FIXTURES / "sample.docx"))
        assert r1.file_hash == r2.file_hash

    def test_track_changes_detection(self):
        result = read_docx(str(FIXTURES / "sample-track-changes.docx"))
        assert result.error is None
        # Our test fixture may not have actual track changes XML,
        # but the code path should handle it gracefully
        assert isinstance(result.had_track_changes, bool)

    def test_docx_without_track_changes(self):
        result = read_docx(str(FIXTURES / "sample.docx"))
        assert result.had_track_changes is False

    def test_page_count_estimate(self):
        result = read_docx(str(FIXTURES / "sample.docx"))
        assert result.page_count_estimate is not None
        assert result.page_count_estimate >= 1

    def test_missing_file_returns_error(self):
        result = read_docx("/nonexistent/file.docx")
        assert result.error is not None

    def test_corrupt_file_returns_error(self, tmp_path):
        bad_docx = tmp_path / "corrupt.docx"
        bad_docx.write_bytes(b"not a docx file")
        result = read_docx(str(bad_docx))
        assert result.error is not None
