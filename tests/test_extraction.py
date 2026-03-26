"""Tests for Section 03 — Extraction Models, Taxonomy, and Normalizer."""

import pytest
from pydantic import ValidationError

from src.models.extraction import (
    DocumentExtractionResult,
    ExtractedParty,
    ExtractedRelationship,
    ExtractedTerm,
    PRECEDENCE_RULES,
    RELATIONSHIP_TAXONOMY,
    RelationshipExtractionResult,
    RelationshipTypeInfo,
)
from src.models.schema import RELATIONSHIP_TYPES, KeyProvision
from src.extraction.normalizer import (
    COMMON_INVERSIONS,
    check_directionality,
    match_party,
    normalize_party_name,
)
from src.models.schema import Party


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_doc_result(**overrides):
    defaults = dict(
        document_type="loan_agreement",
        name="Loan Agreement",
        parties=[ExtractedParty(name="Acme Corp", role="Borrower")],
        summary="A loan agreement.",
    )
    defaults.update(overrides)
    return DocumentExtractionResult(**defaults)


def _make_relationship(**overrides):
    defaults = dict(
        target_document_name="Guaranty Agreement",
        relationship_type="controls",
        direction_test_result="The Loan Agreement governs Guaranty Agreement",
        confidence="high",
        description="Loan controls Guaranty",
    )
    defaults.update(overrides)
    return ExtractedRelationship(**defaults)


# ── Extraction Result Models ─────────────────────────────────────────────


class TestDocumentExtractionResult:
    def test_all_required_fields(self):
        result = _make_doc_result()
        assert result.name == "Loan Agreement"

    def test_empty_parties_valid(self):
        result = _make_doc_result(parties=[])
        assert result.parties == []

    def test_extracted_party_with_aliases(self):
        party = ExtractedParty(
            name="Acme Corp", role="Borrower",
            aliases=["ACME", "Acme Corporation"],
        )
        assert party.aliases == ["ACME", "Acme Corporation"]

    def test_extracted_party_basic(self):
        party = ExtractedParty(name="Acme Corp", role="Lender")
        assert party.entity_type is None

    def test_extracted_term_basic(self):
        term = ExtractedTerm(term="Borrower", section_reference="Section 1.1")
        assert term.term == "Borrower"

    def test_extracted_term_null_snippet(self):
        term = ExtractedTerm(term="Borrower", definition_snippet=None)
        assert term.definition_snippet is None


class TestRelationshipExtractionResult:
    def test_empty_relationships_valid(self):
        result = RelationshipExtractionResult(relationships=[])
        assert result.relationships == []

    def test_valid_relationship(self):
        rel = _make_relationship()
        assert rel.relationship_type == "controls"

    def test_invalid_relationship_type(self):
        with pytest.raises(ValidationError):
            _make_relationship(relationship_type="depends_on")

    def test_result_schema(self):
        result = RelationshipExtractionResult(
            relationships=[_make_relationship(), _make_relationship(relationship_type="guarantees")]
        )
        assert len(result.relationships) == 2

    def test_doc_result_schema(self):
        result = _make_doc_result(
            key_provisions=[KeyProvision(section_reference="4.1", summary="Repayment terms")],
            obligations=["Pay monthly"],
            document_references=["Guaranty Agreement"],
        )
        assert len(result.key_provisions) == 1
        assert len(result.document_references) == 1


# ── Relationship Taxonomy ────────────────────────────────────────────────


class TestRelationshipTaxonomy:
    def test_all_16_types_defined(self):
        assert len(RELATIONSHIP_TAXONOMY) == 16
        for rt in RELATIONSHIP_TYPES:
            assert rt in RELATIONSHIP_TAXONOMY

    def test_each_type_has_required_fields(self):
        for key, info in RELATIONSHIP_TAXONOMY.items():
            assert isinstance(info, RelationshipTypeInfo)
            assert info.direction_semantics
            assert info.direction_test
            assert len(info.extraction_heuristics) > 0

    def test_direction_test_pattern(self):
        for key, info in RELATIONSHIP_TAXONOMY.items():
            assert "[source]" in info.direction_test or "source" in info.direction_test.lower(), (
                f"Direction test for '{key}' should reference source: {info.direction_test}"
            )
            assert "[target]" in info.direction_test or "target" in info.direction_test.lower(), (
                f"Direction test for '{key}' should reference target: {info.direction_test}"
            )

    def test_precedence_subject_to(self):
        assert PRECEDENCE_RULES["subject to"] == "subordinates_to"

    def test_precedence_incorporated_by_reference(self):
        assert PRECEDENCE_RULES["incorporated by reference"] == "incorporates"

    def test_precedence_governed_by(self):
        assert PRECEDENCE_RULES["governed by"] == "controls"


# ── Normalizer — Party Names ─────────────────────────────────────────────


class TestNormalizePartyName:
    def test_strips_punctuation_variations(self):
        assert normalize_party_name("L.L.C.") == normalize_party_name("LLC")

    def test_collapses_whitespace(self):
        assert normalize_party_name("Acme  Corp") == normalize_party_name("Acme Corp")

    def test_casefold(self):
        assert normalize_party_name("ACME CORP") == normalize_party_name("acme corp")

    def test_strips_entity_suffix(self):
        norm1 = normalize_party_name("Riverside Holdings LLC")
        norm2 = normalize_party_name("Riverside Holdings")
        assert norm1 == norm2


class TestMatchParty:
    def _make_parties(self):
        return {
            "p-001": Party(
                id="p-001", canonical_name="Riverside Holdings LLC",
                aliases=["Riverside", "Riverside Holdings"],
                raw_names=["RIVERSIDE HOLDINGS, LLC"],
                confidence="high",
            ),
            "p-002": Party(
                id="p-002", canonical_name="First National Bank",
                aliases=["FNB"],
                raw_names=["First National Bank, N.A."],
                confidence="high",
            ),
        }

    def test_exact_canonical_match(self):
        parties = self._make_parties()
        pid, conf = match_party("Riverside Holdings LLC", parties)
        assert pid == "p-001"
        assert conf == "high"

    def test_alias_match(self):
        parties = self._make_parties()
        pid, conf = match_party("FNB", parties)
        assert pid == "p-002"
        assert conf == "medium"

    def test_raw_name_match(self):
        parties = self._make_parties()
        pid, conf = match_party("RIVERSIDE HOLDINGS, LLC", parties)
        # Should match on raw_names
        assert pid == "p-001"

    def test_no_match(self):
        parties = self._make_parties()
        pid, conf = match_party("Unknown Entity Inc", parties)
        assert pid is None
        assert conf == "low"


# ── Normalizer — Directionality ──────────────────────────────────────────


class TestDirectionality:
    def test_known_inversion_rejected(self):
        # "Note secures Mortgage" is wrong
        assert check_directionality("secures", "promissory_note", "deed_of_trust") is False

    def test_correct_direction_accepted(self):
        # "Mortgage secures Note" is correct
        assert check_directionality("secures", "deed_of_trust", "promissory_note") is True

    def test_guaranty_inversion(self):
        # "Loan Agreement guarantees Guaranty" is wrong
        assert check_directionality("guarantees", "loan_agreement", "guaranty") is False

    def test_guaranty_correct(self):
        # "Guaranty guarantees Loan Agreement" is correct
        assert check_directionality("guarantees", "guaranty", "loan_agreement") is True

    def test_unknown_combo_accepted(self):
        # Not in the inversions table — assume correct
        assert check_directionality("references", "loan_agreement", "deed_of_trust") is True
