"""Tests for Section 06 — Pipeline (Extraction Orchestrator)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.extraction.pipeline import (
    _ABBREVIATIONS,
    call_api_with_retry,
    extract_single_document,
    extract_relationships,
    score_document_match,
    validate_extraction_result,
)
from src.models.extraction import (
    DocumentExtractionResult,
    ExtractedParty,
    ExtractedRelationship,
    ExtractedTerm,
    RelationshipExtractionResult,
)
from src.models.schema import (
    DealGraph,
    DealMetadata,
    Document,
    ExtractionMetadata,
    KeyProvision,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ── Helpers ──────────────────────────────────────────────────────────────


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _make_extraction_result(**overrides) -> DocumentExtractionResult:
    defaults = dict(
        document_type="loan_agreement",
        name="Loan Agreement",
        parties=[ExtractedParty(name="Acme Corp", role="Borrower")],
        summary="A loan agreement.",
    )
    defaults.update(overrides)
    return DocumentExtractionResult(**defaults)


def _make_extraction_metadata():
    return ExtractionMetadata(
        extracted_at="2025-01-15T10:30:00Z",
        model="claude-sonnet-4-20250514",
        model_version="20250514",
        temperature=0,
        prompt_version="abc123",
    )


def _make_document(id="doc-001", name="Loan Agreement", doc_type="loan_agreement"):
    return Document(
        id=id, name=name, document_type=doc_type,
        status="executed", source_file_path="/docs/test.pdf",
        file_hash="sha256_test", summary="Test document.",
        extraction=_make_extraction_metadata(),
    )


def _make_graph_with_docs() -> DealGraph:
    return DealGraph(
        schema_version="1.0.0",
        deal=DealMetadata(
            name="Test Deal", status="active",
            created_at="2025-01-15T10:00:00Z", updated_at="2025-01-15T10:00:00Z",
        ),
        documents={
            "doc-001": _make_document("doc-001", "Loan Agreement", "loan_agreement"),
            "doc-002": _make_document("doc-002", "Guaranty Agreement", "guaranty"),
            "doc-003": _make_document("doc-003", "Deed of Trust", "deed_of_trust"),
        },
    )


def _mock_client_returning(result):
    """Create a mock Anthropic client that returns the given result from messages.parse()."""
    client = MagicMock()
    client.messages.parse.return_value = result
    return client


# ── Single Document Extraction ───────────────────────────────────────────


class TestExtractDocument:
    def test_pdf_extraction(self):
        fixture = _load_fixture("extraction-response-loan-agreement.json")
        mock_result = DocumentExtractionResult(**fixture)
        client = _mock_client_returning(mock_result)

        result = extract_single_document(
            str(FIXTURES / "sample.pdf"), client=client,
        )
        assert isinstance(result, DocumentExtractionResult)
        assert result.name == "Loan Agreement"

    def test_docx_extraction(self):
        fixture = _load_fixture("extraction-response-loan-agreement.json")
        mock_result = DocumentExtractionResult(**fixture)
        client = _mock_client_returning(mock_result)

        result = extract_single_document(
            str(FIXTURES / "sample.docx"), client=client,
        )
        assert isinstance(result, DocumentExtractionResult)

    def test_unsupported_file_type(self):
        result = extract_single_document("/some/file.txt")
        assert isinstance(result, dict)
        assert "error" in result
        assert "Unsupported" in result["error"]

    def test_nonexistent_file(self):
        result = extract_single_document("/nonexistent/file.pdf")
        assert isinstance(result, dict)
        assert "error" in result

    def test_extraction_includes_required_fields(self):
        fixture = _load_fixture("extraction-response-loan-agreement.json")
        mock_result = DocumentExtractionResult(**fixture)
        client = _mock_client_returning(mock_result)

        result = extract_single_document(
            str(FIXTURES / "sample.pdf"), client=client,
        )
        assert result.document_type
        assert result.parties is not None
        assert result.summary

    def test_uses_temperature_zero(self):
        fixture = _load_fixture("extraction-response-loan-agreement.json")
        mock_result = DocumentExtractionResult(**fixture)
        client = _mock_client_returning(mock_result)

        extract_single_document(str(FIXTURES / "sample.pdf"), client=client)

        call_kwargs = client.messages.parse.call_args
        assert call_kwargs.kwargs["temperature"] == 0

    def test_records_extraction_metadata(self):
        fixture = _load_fixture("extraction-response-loan-agreement.json")
        mock_result = DocumentExtractionResult(**fixture)
        client = _mock_client_returning(mock_result)

        result = extract_single_document(
            str(FIXTURES / "sample.pdf"), client=client,
        )
        meta = result._extraction_meta  # type: ignore[attr-defined]
        assert "model" in meta
        assert "prompt_version" in meta
        assert "processing_time_ms" in meta
        assert "file_hash" in meta


# ── Smart Matching ───────────────────────────────────────────────────────


class TestSmartMatching:
    def test_exact_name_match_high_confidence(self):
        docs = {"doc-001": _make_document("doc-001", "Loan Agreement", "loan_agreement")}
        matches = score_document_match("Loan Agreement", docs)
        assert len(matches) >= 1
        assert matches[0][2] == "high"
        assert matches[0][0] == "doc-001"

    def test_type_match_medium_confidence(self):
        docs = {"doc-001": _make_document("doc-001", "Senior Loan Agreement", "loan_agreement")}
        matches = score_document_match("loan agreement", docs)
        assert len(matches) >= 1
        assert matches[0][2] in ("high", "medium")

    def test_no_match(self):
        docs = {"doc-001": _make_document("doc-001", "Loan Agreement", "loan_agreement")}
        matches = score_document_match("Environmental Report", docs)
        assert len(matches) == 0

    def test_case_insensitive(self):
        docs = {"doc-001": _make_document("doc-001", "Loan Agreement", "loan_agreement")}
        matches = score_document_match("LOAN AGREEMENT", docs)
        assert len(matches) >= 1
        assert matches[0][2] == "high"

    def test_abbreviation_expansion(self):
        docs = {"doc-001": _make_document("doc-001", "Guaranty Agreement", "guaranty")}
        matches = score_document_match("Gty Agmt", docs)
        # "gty agmt" -> "guaranty agreement" should match
        assert len(matches) >= 1

    def test_partial_name_match(self):
        docs = {"doc-001": _make_document("doc-001", "Guaranty Agreement", "guaranty")}
        matches = score_document_match("the Guaranty", docs)
        assert len(matches) >= 1


# ── Post-Parse Validation ────────────────────────────────────────────────


class TestPostParseValidation:
    def test_clean_result_no_warnings(self):
        result = _make_extraction_result()
        warnings = validate_extraction_result(result)
        assert warnings == []

    def test_long_summary_warns(self):
        result = _make_extraction_result(summary="x" * 3000)
        warnings = validate_extraction_result(result)
        assert any("Summary" in w for w in warnings)

    def test_too_many_parties_warns(self):
        parties = [ExtractedParty(name=f"Party {i}", role="Role") for i in range(60)]
        result = _make_extraction_result(parties=parties)
        warnings = validate_extraction_result(result)
        assert any("party" in w.lower() for w in warnings)

    def test_long_term_name_warns(self):
        terms = [ExtractedTerm(term="x" * 300)]
        result = _make_extraction_result(defined_terms=terms)
        warnings = validate_extraction_result(result)
        assert any("Term" in w for w in warnings)


# ── API Retry Logic ──────────────────────────────────────────────────────


class TestApiRetry:
    def test_success_on_first_try(self):
        result = call_api_with_retry(lambda: "success")
        assert result == "success"

    @patch("src.extraction.pipeline.time.sleep")
    def test_retries_on_rate_limit(self, mock_sleep):
        import anthropic
        call_count = 0

        def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise anthropic.RateLimitError(
                    message="rate limited",
                    response=MagicMock(status_code=429),
                    body=None,
                )
            return "success"

        result = call_api_with_retry(failing_then_success)
        assert result == "success"
        assert call_count == 3
        assert mock_sleep.call_count == 2

    @patch("src.extraction.pipeline.time.sleep")
    def test_max_retries_exceeded(self, mock_sleep):
        import anthropic

        def always_fails():
            raise anthropic.RateLimitError(
                message="rate limited",
                response=MagicMock(status_code=429),
                body=None,
            )

        result = call_api_with_retry(always_fails, max_retries=3)
        assert isinstance(result, dict)
        assert "error" in result
        assert "retries" in result["error"]

    def test_validation_error_not_retried(self):
        from pydantic import ValidationError

        call_count = 0

        def bad_response():
            nonlocal call_count
            call_count += 1
            raise ValidationError.from_exception_data(
                title="test",
                line_errors=[],
                input_type="json",
            )

        result = call_api_with_retry(bad_response)
        assert isinstance(result, dict)
        assert "Malformed" in result["error"]
        assert call_count == 1  # Not retried


# ── Relationship Extraction ──────────────────────────────────────────────


class TestRelationshipExtraction:
    def test_empty_graph_returns_empty(self):
        empty_graph = DealGraph(
            schema_version="1.0.0",
            deal=DealMetadata(
                name="Test", status="active",
                created_at="2025-01-15T10:00:00Z", updated_at="2025-01-15T10:00:00Z",
            ),
        )
        result = extract_relationships(
            "test.pdf", b"content", empty_graph,
        )
        assert isinstance(result, RelationshipExtractionResult)
        assert result.relationships == []

    def test_with_existing_documents(self):
        fixture = _load_fixture("relationship-response.json")
        mock_result = RelationshipExtractionResult(**fixture)
        client = _mock_client_returning(mock_result)
        graph = _make_graph_with_docs()

        result = extract_relationships(
            "test.pdf", b"content", graph, client=client,
        )
        assert isinstance(result, RelationshipExtractionResult)
        assert len(result.relationships) == 3
