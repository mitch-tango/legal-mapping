"""Tests for Section 07 — Graph Merger."""

from pathlib import Path

import pytest

from src.graph.merger import merge_document_extraction, merge_relationships, _gen_id
from src.models.extraction import (
    DocumentExtractionResult,
    ExtractedParty,
    ExtractedRelationship,
    ExtractedTerm,
    RelationshipExtractionResult,
)
from src.models.schema import (
    Annotation,
    DealGraph,
    DealMetadata,
    Document,
    ExtractionMetadata,
    KeyProvision,
    Party,
    PartyReference,
    Relationship,
    SCHEMA_VERSION,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_ext_meta():
    return ExtractionMetadata(
        extracted_at="2025-01-15T10:30:00Z",
        model="claude-sonnet-4-20250514",
        model_version="20250514",
        temperature=0,
        prompt_version="abc123",
    )


def _make_empty_graph():
    return DealGraph(
        schema_version=SCHEMA_VERSION,
        deal=DealMetadata(
            name="Test Deal", status="active",
            created_at="2025-01-15T10:00:00Z",
            updated_at="2025-01-15T10:00:00Z",
        ),
    )


def _make_graph_with_party():
    graph = _make_empty_graph()
    graph.parties["p-001"] = Party(
        id="p-001", canonical_name="Riverside Holdings LLC",
        aliases=["Riverside"], raw_names=["RIVERSIDE HOLDINGS, LLC"],
        entity_type="LLC", deal_roles=["Buyer"],
        confidence="high",
    )
    return graph


def _make_extraction(**overrides):
    defaults = dict(
        document_type="loan_agreement",
        name="Loan Agreement",
        parties=[ExtractedParty(name="Acme Corp", role="Borrower")],
        summary="A loan agreement.",
    )
    defaults.update(overrides)
    return DocumentExtractionResult(**defaults)


# ── Document Merge ───────────────────────────────────────────────────────


class TestMergeDocument:
    def test_adds_to_empty_graph(self):
        graph = _make_empty_graph()
        extraction = _make_extraction()
        graph, doc_id = merge_document_extraction(
            graph, extraction, "/docs/loan.pdf", "sha256_abc", _make_ext_meta(),
        )
        assert doc_id in graph.documents
        assert graph.documents[doc_id].name == "Loan Agreement"
        assert len(graph.parties) == 1

    def test_adds_to_graph_with_existing_docs(self):
        graph = _make_empty_graph()
        ext1 = _make_extraction(name="Loan Agreement")
        graph, doc1 = merge_document_extraction(
            graph, ext1, "/docs/loan.pdf", "hash1", _make_ext_meta(),
        )
        ext2 = _make_extraction(
            name="Guaranty", document_type="guaranty",
            parties=[ExtractedParty(name="Thompson Corp", role="Guarantor")],
            summary="A guaranty.",
        )
        graph, doc2 = merge_document_extraction(
            graph, ext2, "/docs/guaranty.pdf", "hash2", _make_ext_meta(),
        )
        assert len(graph.documents) == 2
        assert doc1 != doc2

    def test_matches_existing_party(self):
        graph = _make_graph_with_party()
        extraction = _make_extraction(
            parties=[ExtractedParty(name="Riverside Holdings LLC", role="Borrower")],
        )
        graph, _ = merge_document_extraction(
            graph, extraction, "/docs/loan.pdf", "hash", _make_ext_meta(),
        )
        # Should reuse existing party, not create a new one
        assert len(graph.parties) == 1
        party = graph.parties["p-001"]
        assert "Borrower" in party.deal_roles

    def test_adds_new_aliases(self):
        graph = _make_graph_with_party()
        extraction = _make_extraction(
            parties=[ExtractedParty(
                name="Riverside Holdings LLC", role="Borrower",
                aliases=["RH LLC", "Riverside Holdings"],
            )],
        )
        graph, _ = merge_document_extraction(
            graph, extraction, "/docs/loan.pdf", "hash", _make_ext_meta(),
        )
        party = graph.parties["p-001"]
        assert "RH LLC" in party.aliases

    def test_adds_new_raw_names(self):
        graph = _make_graph_with_party()
        extraction = _make_extraction(
            parties=[ExtractedParty(name="Riverside Holdings, L.L.C.", role="Borrower")],
        )
        graph, _ = merge_document_extraction(
            graph, extraction, "/docs/loan.pdf", "hash", _make_ext_meta(),
        )
        # The normalized name should match, and the raw name should be added
        assert len(graph.parties) == 1
        party = graph.parties["p-001"]
        assert "Riverside Holdings, L.L.C." in party.raw_names

    def test_creates_new_party_when_no_match(self):
        graph = _make_graph_with_party()
        extraction = _make_extraction(
            parties=[ExtractedParty(name="First National Bank", role="Lender")],
        )
        graph, _ = merge_document_extraction(
            graph, extraction, "/docs/loan.pdf", "hash", _make_ext_meta(),
        )
        assert len(graph.parties) == 2

    def test_merge_defined_terms(self):
        graph = _make_empty_graph()
        extraction = _make_extraction(
            defined_terms=[
                ExtractedTerm(term="Borrower", section_reference="Preamble"),
                ExtractedTerm(term="Loan", section_reference="Section 1.1"),
            ],
        )
        graph, doc_id = merge_document_extraction(
            graph, extraction, "/docs/loan.pdf", "hash", _make_ext_meta(),
        )
        assert len(graph.defined_terms) == 2
        assert graph.defined_terms[0].defining_document_id == doc_id

    def test_same_term_different_doc_creates_new(self):
        graph = _make_empty_graph()
        ext1 = _make_extraction(
            name="Loan Agreement",
            defined_terms=[ExtractedTerm(term="Borrower", section_reference="Preamble")],
        )
        graph, doc1 = merge_document_extraction(
            graph, ext1, "/docs/loan.pdf", "hash1", _make_ext_meta(),
        )
        ext2 = _make_extraction(
            name="Guaranty", document_type="guaranty",
            parties=[ExtractedParty(name="Other Corp", role="Guarantor")],
            defined_terms=[ExtractedTerm(term="Borrower", section_reference="Section 1")],
            summary="A guaranty.",
        )
        graph, doc2 = merge_document_extraction(
            graph, ext2, "/docs/guaranty.pdf", "hash2", _make_ext_meta(),
        )
        borrower_terms = [t for t in graph.defined_terms if t.term == "Borrower"]
        assert len(borrower_terms) == 2

    def test_updates_used_in_for_existing_terms(self):
        graph = _make_empty_graph()
        ext1 = _make_extraction(
            name="Loan Agreement",
            defined_terms=[ExtractedTerm(term="Borrower", section_reference="Preamble")],
        )
        graph, doc1 = merge_document_extraction(
            graph, ext1, "/docs/loan.pdf", "hash1", _make_ext_meta(),
        )
        # Second doc references same term
        ext2 = _make_extraction(
            name="Guaranty", document_type="guaranty",
            parties=[ExtractedParty(name="Other Corp", role="Guarantor")],
            defined_terms=[ExtractedTerm(term="Borrower")],
            summary="A guaranty.",
        )
        graph, doc2 = merge_document_extraction(
            graph, ext2, "/docs/guaranty.pdf", "hash2", _make_ext_meta(),
        )
        # The original term defined in doc1 should now list doc2 as a user
        original_term = [
            t for t in graph.defined_terms
            if t.term == "Borrower" and t.defining_document_id == doc1
        ][0]
        assert doc2 in original_term.used_in_document_ids

    def test_never_modifies_annotations(self):
        graph = _make_empty_graph()
        graph.annotations.append(Annotation(
            id="ann-001", entity_type="document", entity_id="doc-old",
            note="User note", flagged=True,
            created_at="2025-01-15T10:00:00Z", updated_at="2025-01-15T10:00:00Z",
        ))
        extraction = _make_extraction()
        graph, _ = merge_document_extraction(
            graph, extraction, "/docs/loan.pdf", "hash", _make_ext_meta(),
        )
        assert len(graph.annotations) == 1
        assert graph.annotations[0].note == "User note"
        assert graph.annotations[0].flagged is True

    def test_adds_extraction_event(self):
        graph = _make_empty_graph()
        extraction = _make_extraction()
        graph, doc_id = merge_document_extraction(
            graph, extraction, "/docs/loan.pdf", "hash", _make_ext_meta(),
        )
        assert len(graph.extraction_log) == 1
        assert graph.extraction_log[0].document_id == doc_id
        assert graph.extraction_log[0].action == "initial"


# ── Relationship Merge ───────────────────────────────────────────────────


class TestMergeRelationships:
    def _make_graph_with_two_docs(self):
        graph = _make_empty_graph()
        ext = _make_ext_meta()
        graph.documents["doc-001"] = Document(
            id="doc-001", name="Loan Agreement", document_type="loan_agreement",
            status="executed", source_file_path="/loan.pdf",
            file_hash="aaa", summary="Loan.", extraction=ext,
        )
        graph.documents["doc-002"] = Document(
            id="doc-002", name="Guaranty Agreement", document_type="guaranty",
            status="executed", source_file_path="/guaranty.pdf",
            file_hash="bbb", summary="Guaranty.", extraction=ext,
        )
        return graph

    def test_adds_relationships(self):
        graph = self._make_graph_with_two_docs()
        rels = RelationshipExtractionResult(relationships=[
            ExtractedRelationship(
                target_document_name="Guaranty Agreement",
                relationship_type="controls",
                direction_test_result="Loan controls Guaranty",
                confidence="high",
                description="Loan controls Guaranty",
            ),
        ])
        graph = merge_relationships(
            graph, rels, "doc-001",
            {"Guaranty Agreement": "doc-002"},
            _make_ext_meta(),
        )
        assert len(graph.relationships) == 1
        assert graph.relationships[0].source_document_id == "doc-001"
        assert graph.relationships[0].target_document_id == "doc-002"

    def test_no_duplicate_relationships(self):
        graph = self._make_graph_with_two_docs()
        graph.relationships.append(Relationship(
            id="rel-existing",
            source_document_id="doc-001", target_document_id="doc-002",
            relationship_type="controls", confidence="high",
            description="Existing relationship",
        ))
        rels = RelationshipExtractionResult(relationships=[
            ExtractedRelationship(
                target_document_name="Guaranty Agreement",
                relationship_type="controls",
                direction_test_result="Loan controls Guaranty",
                confidence="high",
                description="Duplicate",
            ),
        ])
        graph = merge_relationships(
            graph, rels, "doc-001",
            {"Guaranty Agreement": "doc-002"},
            _make_ext_meta(),
        )
        # Should still have just the one relationship
        controls_rels = [r for r in graph.relationships if r.relationship_type == "controls"]
        assert len(controls_rels) == 1
