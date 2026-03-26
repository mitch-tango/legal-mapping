"""Tests for Section 07 — Graph Manager and Validator."""

import json
from pathlib import Path

import pytest

from src.graph.manager import GRAPH_FILENAME, create_deal, load_graph, save_graph
from src.graph.validator import validate_full, validate_schema, validate_semantics
from src.models.schema import (
    DealGraph,
    DealMetadata,
    Document,
    ExtractionMetadata,
    Party,
    PartyReference,
    Relationship,
    SCHEMA_VERSION,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_extraction_metadata():
    return ExtractionMetadata(
        extracted_at="2025-01-15T10:30:00Z",
        model="claude-sonnet-4-20250514",
        model_version="20250514",
        temperature=0,
        prompt_version="abc123",
    )


def _make_minimal_graph():
    return DealGraph(
        schema_version=SCHEMA_VERSION,
        deal=DealMetadata(
            name="Test Deal", status="active",
            created_at="2025-01-15T10:00:00Z",
            updated_at="2025-01-15T10:00:00Z",
        ),
    )


def _load_sample_graph():
    return DealGraph.model_validate_json(
        (FIXTURES / "sample-graph.json").read_text()
    )


# ── Graph Manager ────────────────────────────────────────────────────────


class TestLoadGraph:
    def test_load_valid_graph(self, tmp_path):
        graph = _make_minimal_graph()
        save_graph(graph, str(tmp_path))
        loaded = load_graph(str(tmp_path))
        assert loaded is not None
        assert loaded.deal.name == "Test Deal"

    def test_load_nonexistent_returns_none(self, tmp_path):
        result = load_graph(str(tmp_path / "nonexistent"))
        assert result is None

    def test_load_invalid_json(self, tmp_path):
        (tmp_path / GRAPH_FILENAME).write_text("not json")
        with pytest.raises(ValueError):
            load_graph(str(tmp_path))


class TestSaveGraph:
    def test_round_trip(self, tmp_path):
        graph = _load_sample_graph()
        save_graph(graph, str(tmp_path))
        loaded = load_graph(str(tmp_path))
        assert loaded == graph

    def test_atomic_write(self, tmp_path):
        graph = _make_minimal_graph()
        save_graph(graph, str(tmp_path))
        # Verify file exists and no temp files left
        assert (tmp_path / GRAPH_FILENAME).exists()
        tmp_files = list(tmp_path.glob("*.tmp.json"))
        assert len(tmp_files) == 0

    def test_rejects_invalid_graph(self, tmp_path):
        graph = _make_minimal_graph()
        # Corrupt the schema version after creation
        graph.schema_version = "bad"
        with pytest.raises(ValueError):
            save_graph(graph, str(tmp_path))


class TestCreateDeal:
    def test_creates_directory_and_graph(self, tmp_path):
        deal_dir = str(tmp_path / "new-deal")
        graph = create_deal(deal_dir, "New Deal", "acquisition")
        assert graph.deal.name == "New Deal"
        assert graph.deal.deal_type == "acquisition"
        assert graph.schema_version == SCHEMA_VERSION
        assert Path(deal_dir, GRAPH_FILENAME).exists()

    def test_sets_timestamps(self, tmp_path):
        deal_dir = str(tmp_path / "new-deal")
        graph = create_deal(deal_dir, "New Deal")
        assert graph.deal.created_at
        assert graph.deal.updated_at


# ── Validator — Schema ───────────────────────────────────────────────────


class TestSchemaValidation:
    def test_valid_graph_passes(self):
        graph = _load_sample_graph()
        result = validate_schema(graph)
        assert result.is_valid

    def test_sample_graph_passes_full(self):
        graph = _load_sample_graph()
        result = validate_full(graph)
        assert result.is_valid, f"Errors: {result.errors}"


# ── Validator — Semantics ────────────────────────────────────────────────


class TestSemanticValidation:
    def test_valid_graph_passes(self):
        graph = _load_sample_graph()
        result = validate_semantics(graph)
        assert result.is_valid, f"Errors: {result.errors}"

    def test_relationship_bad_source_id(self):
        graph = _make_minimal_graph()
        graph.relationships.append(Relationship(
            id="rel-001",
            source_document_id="nonexistent",
            target_document_id="also-nonexistent",
            relationship_type="references",
            confidence="high",
            description="test",
        ))
        result = validate_semantics(graph)
        assert not result.is_valid
        assert any("nonexistent" in e for e in result.errors)

    def test_party_ref_bad_id(self):
        graph = _make_minimal_graph()
        graph.documents["doc-001"] = Document(
            id="doc-001", name="Test", document_type="loan_agreement",
            parties=[PartyReference(party_id="bad-party", role_in_document="Borrower")],
            status="executed", source_file_path="/test.pdf",
            file_hash="abc123", summary="Test doc.",
            extraction=_make_extraction_metadata(),
        )
        result = validate_semantics(graph)
        assert not result.is_valid
        assert any("bad-party" in e for e in result.errors)

    def test_duplicate_ids_flagged(self):
        graph = _make_minimal_graph()
        graph.parties["dup-id"] = Party(
            id="dup-id", canonical_name="Party A", confidence="high",
        )
        graph.documents["dup-id"] = Document(
            id="dup-id", name="Doc", document_type="other",
            status="draft", source_file_path="/test.pdf",
            file_hash="abc", summary="Test.",
            extraction=_make_extraction_metadata(),
        )
        result = validate_semantics(graph)
        assert not result.is_valid
        assert any("Duplicate" in e for e in result.errors)

    def test_supersedes_cycle_detected(self):
        graph = _make_minimal_graph()
        ext = _make_extraction_metadata()
        graph.documents["doc-a"] = Document(
            id="doc-a", name="Doc A", document_type="other",
            status="executed", source_file_path="/a.pdf",
            file_hash="aaa", summary="A.", extraction=ext,
        )
        graph.documents["doc-b"] = Document(
            id="doc-b", name="Doc B", document_type="other",
            status="executed", source_file_path="/b.pdf",
            file_hash="bbb", summary="B.", extraction=ext,
        )
        graph.relationships = [
            Relationship(
                id="rel-1", source_document_id="doc-a", target_document_id="doc-b",
                relationship_type="supersedes", confidence="high", description="A supersedes B",
            ),
            Relationship(
                id="rel-2", source_document_id="doc-b", target_document_id="doc-a",
                relationship_type="supersedes", confidence="high", description="B supersedes A",
            ),
        ]
        result = validate_semantics(graph)
        assert any("cycle" in e.lower() for e in result.errors)

    def test_directionality_warning(self):
        graph = _make_minimal_graph()
        ext = _make_extraction_metadata()
        graph.documents["doc-note"] = Document(
            id="doc-note", name="Promissory Note", document_type="promissory_note",
            status="executed", source_file_path="/note.pdf",
            file_hash="nnn", summary="Note.", extraction=ext,
        )
        graph.documents["doc-dot"] = Document(
            id="doc-dot", name="Deed of Trust", document_type="deed_of_trust",
            status="executed", source_file_path="/dot.pdf",
            file_hash="ddd", summary="DOT.", extraction=ext,
        )
        graph.relationships.append(Relationship(
            id="rel-bad", source_document_id="doc-note", target_document_id="doc-dot",
            relationship_type="secures", confidence="high",
            description="Note secures DOT (wrong direction)",
        ))
        result = validate_semantics(graph)
        assert any("inversion" in w.lower() for w in result.warnings)
