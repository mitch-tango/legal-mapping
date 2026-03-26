"""Tests for Section 02 — Schema (Pydantic models for deal-graph.json)."""

import json

import pytest
from pydantic import ValidationError

from src.models.schema import (
    Annotation,
    ConditionPrecedent,
    CrossReference,
    DealGraph,
    DealMetadata,
    DefinedTerm,
    Document,
    Evidence,
    ExtractionEvent,
    ExtractionMetadata,
    KeyProvision,
    Party,
    PartyReference,
    Relationship,
    RELATIONSHIP_TYPES,
    SCHEMA_VERSION,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_extraction_metadata(**overrides):
    defaults = dict(
        extracted_at="2025-01-15T10:30:00Z",
        model="claude-sonnet-4-20250514",
        model_version="20250514",
        temperature=0,
        prompt_version="abc123",
    )
    defaults.update(overrides)
    return ExtractionMetadata(**defaults)


def _make_document(id="doc-001", **overrides):
    defaults = dict(
        id=id,
        name="Loan Agreement",
        document_type="loan_agreement",
        status="executed",
        source_file_path="/docs/loan.pdf",
        file_hash="sha256_abc123",
        summary="A loan agreement between Borrower and Lender.",
        extraction=_make_extraction_metadata(),
    )
    defaults.update(overrides)
    return Document(**defaults)


def _make_deal_metadata(**overrides):
    defaults = dict(
        name="Sample Deal",
        status="active",
        created_at="2025-01-15T10:00:00Z",
        updated_at="2025-01-15T10:00:00Z",
    )
    defaults.update(overrides)
    return DealMetadata(**defaults)


def _make_deal_graph(**overrides):
    defaults = dict(
        schema_version=SCHEMA_VERSION,
        deal=_make_deal_metadata(),
    )
    defaults.update(overrides)
    return DealGraph(**defaults)


# ── Top-Level Graph Structure ────────────────────────────────────────────


class TestDealGraph:
    def test_all_required_fields_validates(self):
        graph = _make_deal_graph()
        assert graph.schema_version == SCHEMA_VERSION

    def test_missing_deal_raises_error(self):
        with pytest.raises(ValidationError):
            DealGraph(schema_version="1.0.0")

    def test_empty_documents_dict_valid(self):
        graph = _make_deal_graph(documents={})
        assert graph.documents == {}

    def test_schema_version_valid_semver(self):
        graph = _make_deal_graph(schema_version="2.10.3")
        assert graph.schema_version == "2.10.3"

    def test_schema_version_rejects_invalid(self):
        for bad in ["1.0", "v1.0.0", "latest", "1.0.0.0", ""]:
            with pytest.raises(ValidationError):
                _make_deal_graph(schema_version=bad)

    def test_round_trip_serialization(self):
        graph = _make_deal_graph(
            documents={"doc-001": _make_document()},
        )
        json_str = graph.model_dump_json()
        restored = DealGraph.model_validate_json(json_str)
        assert restored == graph


# ── Deal Metadata ────────────────────────────────────────────────────────


class TestDealMetadata:
    def test_all_fields(self):
        meta = DealMetadata(
            name="Big Deal",
            deal_type="acquisition",
            primary_parties=["p-001"],
            closing_date="2025-03-01",
            status="active",
            notes="Important deal",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )
        assert meta.deal_type == "acquisition"

    def test_only_required_fields(self):
        meta = _make_deal_metadata()
        assert meta.deal_type is None
        assert meta.closing_date is None

    def test_status_rejects_invalid(self):
        with pytest.raises(ValidationError):
            _make_deal_metadata(status="pending")


# ── Document Node ────────────────────────────────────────────────────────


class TestDocument:
    def test_all_fields(self):
        doc = _make_document(
            parties=[PartyReference(party_id="p-001", role_in_document="Borrower")],
            execution_date_raw="January 15, 2025",
            execution_date_iso="2025-01-15",
            key_provisions=[KeyProvision(section_reference="4.1", summary="Repayment terms")],
            obligations=["Pay principal", "Maintain insurance"],
            ai_original_values={"name": "Original Name"},
        )
        assert doc.id == "doc-001"
        assert len(doc.parties) == 1

    def test_raw_date_without_iso(self):
        doc = _make_document(execution_date_raw="sometime in January", execution_date_iso=None)
        assert doc.execution_date_raw == "sometime in January"
        assert doc.execution_date_iso is None

    def test_both_dates_null(self):
        doc = _make_document(execution_date_raw=None, execution_date_iso=None)
        assert doc.execution_date_raw is None

    def test_file_hash_required_non_empty(self):
        with pytest.raises(ValidationError):
            _make_document(file_hash="")
        with pytest.raises(ValidationError):
            _make_document(file_hash="   ")

    def test_status_rejects_invalid(self):
        with pytest.raises(ValidationError):
            _make_document(status="signed")

    def test_ai_original_values(self):
        doc = _make_document(ai_original_values={"name": "Old Name", "summary": "Old summary"})
        assert doc.ai_original_values["name"] == "Old Name"

    def test_party_reference_non_empty_id(self):
        with pytest.raises(ValidationError):
            PartyReference(party_id="", role_in_document="Borrower")
        with pytest.raises(ValidationError):
            PartyReference(party_id="   ", role_in_document="Borrower")


# ── Key Provision ────────────────────────────────────────────────────────


class TestKeyProvision:
    def test_with_all_fields(self):
        kp = KeyProvision(
            section_reference="4.1",
            title="Repayment",
            summary="Monthly payments required",
            provision_type="covenant",
        )
        assert kp.title == "Repayment"

    def test_optional_fields_null(self):
        kp = KeyProvision(section_reference="4.1", summary="Some provision")
        assert kp.title is None
        assert kp.provision_type is None


# ── Party ────────────────────────────────────────────────────────────────


class TestParty:
    def test_canonical_name_and_empty_aliases(self):
        p = Party(id="p-001", canonical_name="Acme Corp", confidence="high")
        assert p.aliases == []

    def test_multiple_aliases_preserves_order(self):
        p = Party(
            id="p-001",
            canonical_name="Acme Corp",
            aliases=["ACME", "Acme Corporation", "Acme LLC"],
            confidence="medium",
        )
        assert p.aliases == ["ACME", "Acme Corporation", "Acme LLC"]

    def test_raw_names(self):
        p = Party(
            id="p-001",
            canonical_name="Acme Corp",
            raw_names=["ACME CORP.", "Acme Corp"],
            confidence="high",
        )
        assert len(p.raw_names) == 2

    def test_deal_roles(self):
        p = Party(
            id="p-001",
            canonical_name="Acme Corp",
            deal_roles=["Borrower", "Guarantor"],
            confidence="high",
        )
        assert "Borrower" in p.deal_roles

    def test_party_reference(self):
        ref = PartyReference(party_id="p-001", role_in_document="Lender")
        assert ref.party_id == "p-001"


# ── Relationship ─────────────────────────────────────────────────────────


class TestRelationship:
    def _make_relationship(self, **overrides):
        defaults = dict(
            id="rel-001",
            source_document_id="doc-001",
            target_document_id="doc-002",
            relationship_type="controls",
            confidence="high",
            description="Loan Agreement controls Guaranty",
        )
        defaults.update(overrides)
        return Relationship(**defaults)

    def test_all_required_fields(self):
        rel = self._make_relationship()
        assert rel.relationship_type == "controls"

    def test_null_source_reference(self):
        rel = self._make_relationship(source_reference=None)
        assert rel.source_reference is None

    def test_with_evidence(self):
        rel = self._make_relationship(
            evidence=Evidence(quote="See Section 4.2", page=12)
        )
        assert rel.evidence.quote == "See Section 4.2"
        assert rel.evidence.page == 12

    def test_evidence_null_page(self):
        rel = self._make_relationship(
            evidence=Evidence(quote="Some quote", page=None)
        )
        assert rel.evidence.page is None

    def test_rejects_invalid_type(self):
        with pytest.raises(ValidationError):
            self._make_relationship(relationship_type="depends_on")

    def test_all_16_types_valid(self):
        for rt in RELATIONSHIP_TYPES:
            rel = self._make_relationship(relationship_type=rt)
            assert rel.relationship_type == rt

    def test_needs_review_defaults_false(self):
        rel = self._make_relationship()
        assert rel.needs_review is False

    def test_ai_original_values(self):
        rel = self._make_relationship(
            ai_original_values={"confidence": "low"}
        )
        assert rel.ai_original_values["confidence"] == "low"


# ── Defined Terms ────────────────────────────────────────────────────────


class TestDefinedTerm:
    def test_basic(self):
        dt = DefinedTerm(
            id="term-001",
            term="Borrower",
            defining_document_id="doc-001",
            confidence="high",
        )
        assert dt.term == "Borrower"

    def test_same_term_different_docs(self):
        dt1 = DefinedTerm(id="term-001", term="Borrower", defining_document_id="doc-001", confidence="high")
        dt2 = DefinedTerm(id="term-002", term="Borrower", defining_document_id="doc-002", confidence="medium")
        assert dt1.term == dt2.term
        assert dt1.defining_document_id != dt2.defining_document_id

    def test_optional_snippet(self):
        dt = DefinedTerm(
            id="term-001", term="Borrower", defining_document_id="doc-001",
            definition_snippet=None, confidence="high",
        )
        assert dt.definition_snippet is None

    def test_empty_used_in(self):
        dt = DefinedTerm(
            id="term-001", term="Borrower", defining_document_id="doc-001", confidence="high",
        )
        assert dt.used_in_document_ids == []


# ── Cross References ─────────────────────────────────────────────────────


class TestCrossReference:
    def test_null_target_section(self):
        cr = CrossReference(
            id="xref-001",
            source_document_id="doc-001",
            source_section="4.1",
            target_document_id="doc-002",
            target_section=None,
            reference_text="as defined in the Guaranty",
            confidence="medium",
        )
        assert cr.target_section is None

    def test_with_evidence(self):
        cr = CrossReference(
            id="xref-001",
            source_document_id="doc-001",
            source_section="4.1",
            target_document_id="doc-002",
            reference_text="See Guaranty Section 2.3",
            evidence=Evidence(quote="See Guaranty Section 2.3", page=5),
            confidence="high",
        )
        assert cr.evidence.page == 5

    def test_needs_review_defaults_false(self):
        cr = CrossReference(
            id="xref-001",
            source_document_id="doc-001",
            source_section="4.1",
            target_document_id="doc-002",
            reference_text="ref",
            confidence="low",
        )
        assert cr.needs_review is False


# ── Conditions Precedent ─────────────────────────────────────────────────


class TestConditionPrecedent:
    def test_null_required_document(self):
        cp = ConditionPrecedent(
            id="cp-001",
            description="Title insurance must be obtained",
            source_document_id="doc-001",
            required_document_id=None,
            status="pending",
            confidence="high",
        )
        assert cp.required_document_id is None

    def test_null_enables_document(self):
        cp = ConditionPrecedent(
            id="cp-001",
            description="Appraisal complete",
            source_document_id="doc-001",
            enables_document_id=None,
            status="satisfied",
            confidence="medium",
        )
        assert cp.enables_document_id is None

    def test_status_enum(self):
        for s in ("pending", "satisfied", "waived"):
            cp = ConditionPrecedent(
                id="cp-001", description="test", source_document_id="doc-001",
                status=s, confidence="high",
            )
            assert cp.status == s
        with pytest.raises(ValidationError):
            ConditionPrecedent(
                id="cp-001", description="test", source_document_id="doc-001",
                status="completed", confidence="high",
            )


# ── Annotations ──────────────────────────────────────────────────────────


class TestAnnotation:
    def test_note_no_flag(self):
        ann = Annotation(
            id="ann-001", entity_type="document", entity_id="doc-001",
            note="Check this document", flagged=False,
            created_at="2025-01-15T10:00:00Z", updated_at="2025-01-15T10:00:00Z",
        )
        assert ann.note == "Check this document"
        assert ann.flagged is False

    def test_flag_no_note(self):
        ann = Annotation(
            id="ann-001", entity_type="relationship", entity_id="rel-001",
            note=None, flagged=True,
            created_at="2025-01-15T10:00:00Z", updated_at="2025-01-15T10:00:00Z",
        )
        assert ann.flagged is True
        assert ann.note is None

    def test_entity_type_enum(self):
        valid_types = ["document", "relationship", "term", "cross_reference", "condition"]
        for et in valid_types:
            ann = Annotation(
                id="ann-001", entity_type=et, entity_id="x",
                created_at="2025-01-15T10:00:00Z", updated_at="2025-01-15T10:00:00Z",
            )
            assert ann.entity_type == et
        with pytest.raises(ValidationError):
            Annotation(
                id="ann-001", entity_type="paragraph", entity_id="x",
                created_at="2025-01-15T10:00:00Z", updated_at="2025-01-15T10:00:00Z",
            )

    def test_timestamps_required(self):
        with pytest.raises(ValidationError):
            Annotation(id="ann-001", entity_type="document", entity_id="doc-001")


# ── Extraction Metadata ──────────────────────────────────────────────────


class TestExtractionMetadata:
    def test_temperature_zero(self):
        em = _make_extraction_metadata(temperature=0)
        assert em.temperature == 0

    def test_prompt_version_hash(self):
        em = _make_extraction_metadata(prompt_version="sha256_deadbeef")
        assert em.prompt_version == "sha256_deadbeef"

    def test_extraction_event_action_enum(self):
        for action in ("initial", "re-extract_replace", "re-extract_version"):
            ev = ExtractionEvent(
                id="ev-001", document_id="doc-001", action=action,
                timestamp="2025-01-15T10:00:00Z", model="claude-sonnet-4-20250514",
            )
            assert ev.action == action
        with pytest.raises(ValidationError):
            ExtractionEvent(
                id="ev-001", document_id="doc-001", action="update",
                timestamp="2025-01-15T10:00:00Z", model="claude-sonnet-4-20250514",
            )
