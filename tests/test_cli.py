"""Tests for Section 08 — CLI Entry Points."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.cli import (
    extract_batch,
    extract_document,
    show_graph_summary,
    validate_graph,
)
from src.graph.manager import save_graph
from src.models.extraction import (
    DocumentExtractionResult,
    ExtractedParty,
    ExtractedRelationship,
    RelationshipExtractionResult,
)
from src.models.schema import (
    DealGraph,
    DealMetadata,
    Document,
    ExtractionMetadata,
    Relationship,
    SCHEMA_VERSION,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ── Helpers ──────────────────────────────────────────────────────────────


def _load_fixture_json(name: str):
    return json.loads((FIXTURES / name).read_text())


def _make_ext_meta():
    return ExtractionMetadata(
        extracted_at="2025-01-15T10:30:00Z",
        model="claude-sonnet-4-20250514",
        model_version="20250514",
        temperature=0,
        prompt_version="abc123",
    )


def _make_mock_extraction_result():
    fixture = _load_fixture_json("extraction-response-loan-agreement.json")
    result = DocumentExtractionResult(**fixture)
    result._extraction_meta = {  # type: ignore[attr-defined]
        "model": "claude-sonnet-4-20250514",
        "prompt_version": "abc123",
        "processing_time_ms": 1000,
        "file_hash": "sha256_test",
        "has_text_layer": True,
    }
    return result


def _make_graph_with_doc(deal_dir: str, file_hash: str = "sha256_test"):
    graph = DealGraph(
        schema_version=SCHEMA_VERSION,
        deal=DealMetadata(
            name="Test Deal", status="active",
            created_at="2025-01-15T10:00:00Z", updated_at="2025-01-15T10:00:00Z",
        ),
        documents={
            "doc-existing": Document(
                id="doc-existing", name="Loan Agreement",
                document_type="loan_agreement", status="executed",
                source_file_path=str(FIXTURES / "sample.pdf"),
                file_hash=file_hash, summary="Test loan.",
                extraction=_make_ext_meta(),
            ),
        },
    )
    save_graph(graph, deal_dir)
    return graph


def _mock_client():
    """Create mock client that returns appropriate result based on response_model."""
    doc_result = _make_mock_extraction_result()
    rel_result = RelationshipExtractionResult(relationships=[])

    client = MagicMock()

    def mock_parse(**kwargs):
        response_model = kwargs.get("response_model")
        if response_model is RelationshipExtractionResult:
            return rel_result
        return doc_result

    client.messages.parse.side_effect = mock_parse
    return client


# ── extract-document ─────────────────────────────────────────────────────


class TestExtractDocument:
    def test_returns_json(self, tmp_path):
        client = _mock_client()
        output = extract_document(
            str(FIXTURES / "sample.pdf"), str(tmp_path / "deal"), client=client,
        )
        result = json.loads(output)
        assert result["status"] == "success"
        assert "document_id" in result

    def test_nonexistent_file(self, tmp_path):
        output = extract_document("/nonexistent.pdf", str(tmp_path))
        result = json.loads(output)
        assert result["status"] == "error"

    def test_unsupported_file_type(self, tmp_path):
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("hello")
        output = extract_document(str(txt_file), str(tmp_path / "deal"))
        result = json.loads(output)
        assert result["status"] == "error"
        assert "Unsupported" in result["message"]

    def test_conflict_detected_without_resolve(self, tmp_path):
        deal_dir = str(tmp_path / "deal")
        # Compute the actual hash of sample.pdf
        import hashlib
        h = hashlib.sha256((FIXTURES / "sample.pdf").read_bytes()).hexdigest()
        _make_graph_with_doc(deal_dir, file_hash=h)

        output = extract_document(str(FIXTURES / "sample.pdf"), deal_dir)
        result = json.loads(output)
        assert result["status"] == "conflict"
        assert result["reason"] == "document_exists"
        assert "replace" in result["options"]
        assert "version" in result["options"]

    @patch("src.cli.extract_single_document")
    def test_resolve_replace(self, mock_extract, tmp_path):
        deal_dir = str(tmp_path / "deal")
        import hashlib
        h = hashlib.sha256((FIXTURES / "sample.pdf").read_bytes()).hexdigest()
        _make_graph_with_doc(deal_dir, file_hash=h)

        mock_result = _make_mock_extraction_result()
        mock_extract.return_value = mock_result

        # Also mock relationship extraction to avoid API call
        with patch("src.cli.extract_relationships") as mock_rel:
            mock_rel.return_value = RelationshipExtractionResult(relationships=[])
            output = extract_document(
                str(FIXTURES / "sample.pdf"), deal_dir, resolve="replace",
            )

        result = json.loads(output)
        assert result["status"] == "success"
        assert result["document_id"] == "doc-existing"  # ID preserved

    @patch("src.cli.extract_single_document")
    def test_resolve_version(self, mock_extract, tmp_path):
        deal_dir = str(tmp_path / "deal")
        import hashlib
        h = hashlib.sha256((FIXTURES / "sample.pdf").read_bytes()).hexdigest()
        _make_graph_with_doc(deal_dir, file_hash=h)

        mock_result = _make_mock_extraction_result()
        mock_extract.return_value = mock_result

        with patch("src.cli.extract_relationships") as mock_rel:
            mock_rel.return_value = RelationshipExtractionResult(relationships=[])
            output = extract_document(
                str(FIXTURES / "sample.pdf"), deal_dir, resolve="version",
            )

        result = json.loads(output)
        assert result["status"] == "success"
        # New document ID, different from old
        assert result["document_id"] != "doc-existing"

        # Verify supersedes edge exists
        from src.graph.manager import load_graph
        graph = load_graph(deal_dir)
        supersedes = [r for r in graph.relationships if r.relationship_type == "supersedes"]
        assert len(supersedes) == 1
        assert supersedes[0].target_document_id == "doc-existing"


# ── extract-batch ────────────────────────────────────────────────────────


class TestExtractBatch:
    def test_returns_json_summary(self, tmp_path):
        # Create folder with files
        folder = tmp_path / "docs"
        folder.mkdir()
        import shutil
        shutil.copy(FIXTURES / "sample.pdf", folder / "loan.pdf")
        shutil.copy(FIXTURES / "sample.docx", folder / "guaranty.docx")

        client = _mock_client()
        output = extract_batch(str(folder), str(tmp_path / "deal"), "Test Deal", client=client)
        result = json.loads(output)
        assert result["status"] == "success"
        assert result["deal_name"] == "Test Deal"
        assert result["documents_processed"] == 2

    def test_ignores_non_pdf_docx(self, tmp_path):
        folder = tmp_path / "docs"
        folder.mkdir()
        (folder / "notes.txt").write_text("notes")
        (folder / "data.csv").write_text("a,b,c")
        import shutil
        shutil.copy(FIXTURES / "sample.pdf", folder / "loan.pdf")

        client = _mock_client()
        output = extract_batch(str(folder), str(tmp_path / "deal"), "Test Deal", client=client)
        result = json.loads(output)
        assert result["documents_processed"] == 1

    def test_empty_folder(self, tmp_path):
        folder = tmp_path / "docs"
        folder.mkdir()
        output = extract_batch(str(folder), str(tmp_path / "deal"), "Test Deal")
        result = json.loads(output)
        assert result["status"] == "error"

    def test_nonexistent_folder(self, tmp_path):
        output = extract_batch(str(tmp_path / "nope"), str(tmp_path / "deal"), "Test")
        result = json.loads(output)
        assert result["status"] == "error"

    def test_creates_valid_graph(self, tmp_path):
        folder = tmp_path / "docs"
        folder.mkdir()
        import shutil
        shutil.copy(FIXTURES / "sample.pdf", folder / "loan.pdf")

        client = _mock_client()
        extract_batch(str(folder), str(tmp_path / "deal"), "Test Deal", client=client)

        from src.graph.manager import load_graph
        graph = load_graph(str(tmp_path / "deal"))
        assert graph is not None
        assert graph.deal.name == "Test Deal"


# ── validate-graph ───────────────────────────────────────────────────────


class TestValidateGraph:
    def test_valid_graph(self, tmp_path):
        deal_dir = str(tmp_path / "deal")
        graph = DealGraph.model_validate_json((FIXTURES / "sample-graph.json").read_text())
        save_graph(graph, deal_dir)

        output = validate_graph(deal_dir)
        result = json.loads(output)
        assert result["status"] == "valid"
        assert "errors" in result
        assert "warnings" in result

    def test_no_graph_file(self, tmp_path):
        output = validate_graph(str(tmp_path / "nope"))
        result = json.loads(output)
        assert result["status"] == "error"

    def test_invalid_graph_reports_errors(self, tmp_path):
        deal_dir = str(tmp_path / "deal")
        # Create graph with referential integrity error
        graph = DealGraph(
            schema_version=SCHEMA_VERSION,
            deal=DealMetadata(
                name="Bad", status="active",
                created_at="2025-01-15T10:00:00Z", updated_at="2025-01-15T10:00:00Z",
            ),
            relationships=[
                Relationship(
                    id="rel-bad", source_document_id="nonexistent",
                    target_document_id="also-nonexistent",
                    relationship_type="references", confidence="high",
                    description="bad ref",
                ),
            ],
        )
        save_graph(graph, deal_dir)

        output = validate_graph(deal_dir)
        result = json.loads(output)
        assert result["status"] == "invalid"
        assert len(result["errors"]) > 0


# ── show-graph-summary ───────────────────────────────────────────────────


class TestShowGraphSummary:
    def test_returns_summary(self, tmp_path):
        deal_dir = str(tmp_path / "deal")
        graph = DealGraph.model_validate_json((FIXTURES / "sample-graph.json").read_text())
        save_graph(graph, deal_dir)

        output = show_graph_summary(deal_dir)
        result = json.loads(output)
        assert result["status"] == "success"
        assert result["deal_name"] == "Riverside Office Acquisition"
        assert result["document_count"] == 4
        assert result["relationship_count"] == 5
        assert result["party_count"] == 4
        assert "documents" in result
        assert "parties" in result
        assert "needs_review_count" in result

    def test_no_graph_file(self, tmp_path):
        output = show_graph_summary(str(tmp_path / "nope"))
        result = json.loads(output)
        assert result["status"] == "error"
