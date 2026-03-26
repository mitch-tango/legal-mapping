import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    """Path to the test fixtures directory."""
    return FIXTURES_DIR


# ── Split 02: Semantic Analysis Fixtures ─────────────────────────────────


def _make_ext_meta_dict():
    return {
        "extracted_at": "2025-01-15T10:30:00Z",
        "model": "claude-sonnet-4-20250514",
        "model_version": "20250514",
        "temperature": 0,
        "prompt_version": "abc123",
    }


@pytest.fixture
def minimal_deal_graph():
    """3-document graph: Loan Agreement, Guaranty, Environmental Indemnity."""
    ext = _make_ext_meta_dict()
    return {
        "schema_version": "1.0.0",
        "deal": {
            "name": "Minimal Test Deal",
            "status": "active",
            "created_at": "2025-01-15T10:00:00Z",
            "updated_at": "2025-01-15T10:00:00Z",
        },
        "parties": {
            "p-001": {
                "id": "p-001", "canonical_name": "Borrower LLC",
                "aliases": [], "raw_names": [], "deal_roles": ["Borrower"],
                "confidence": "high",
            },
            "p-002": {
                "id": "p-002", "canonical_name": "Lender Bank",
                "aliases": [], "raw_names": [], "deal_roles": ["Lender"],
                "confidence": "high",
            },
        },
        "documents": {
            "doc-loan": {
                "id": "doc-loan", "name": "Loan Agreement",
                "document_type": "loan_agreement",
                "parties": [
                    {"party_id": "p-001", "role_in_document": "Borrower"},
                    {"party_id": "p-002", "role_in_document": "Lender"},
                ],
                "status": "executed",
                "source_file_path": "documents/loan-agreement.pdf",
                "file_hash": "sha256_loan", "summary": "Loan agreement.",
                "extraction": ext,
            },
            "doc-guaranty": {
                "id": "doc-guaranty", "name": "Guaranty",
                "document_type": "guaranty",
                "parties": [
                    {"party_id": "p-001", "role_in_document": "Guarantor"},
                    {"party_id": "p-002", "role_in_document": "Lender"},
                ],
                "status": "executed",
                "source_file_path": "documents/guaranty.pdf",
                "file_hash": "sha256_guaranty", "summary": "Guaranty agreement.",
                "extraction": ext,
            },
            "doc-enviro": {
                "id": "doc-enviro", "name": "Environmental Indemnity",
                "document_type": "environmental_indemnity",
                "parties": [
                    {"party_id": "p-001", "role_in_document": "Indemnitor"},
                    {"party_id": "p-002", "role_in_document": "Indemnitee"},
                ],
                "status": "executed",
                "source_file_path": "documents/environmental-indemnity.pdf",
                "file_hash": "sha256_enviro", "summary": "Environmental indemnity.",
                "extraction": ext,
            },
        },
        "relationships": [
            {
                "id": "rel-001", "source_document_id": "doc-loan",
                "target_document_id": "doc-guaranty",
                "relationship_type": "controls", "confidence": "high",
                "description": "Loan Agreement controls Guaranty",
            },
            {
                "id": "rel-002", "source_document_id": "doc-loan",
                "target_document_id": "doc-enviro",
                "relationship_type": "controls", "confidence": "high",
                "description": "Loan Agreement controls Environmental Indemnity",
            },
        ],
        "defined_terms": [
            {
                "id": "term-001", "term": "Borrower",
                "defining_document_id": "doc-loan",
                "section_reference": "Preamble",
                "used_in_document_ids": ["doc-guaranty", "doc-enviro"],
                "confidence": "high",
            },
            {
                "id": "term-002", "term": "Guaranteed Obligations",
                "defining_document_id": "doc-guaranty",
                "section_reference": "Section 1.1",
                "used_in_document_ids": [],
                "confidence": "high",
            },
        ],
        "cross_references": [
            {
                "id": "xref-001", "source_document_id": "doc-guaranty",
                "source_section": "Section 1.1",
                "target_document_id": "doc-loan",
                "target_section": "Section 2.1",
                "reference_text": "as defined in Section 2.1 of the Loan Agreement",
                "confidence": "high",
            },
            {
                "id": "xref-002", "source_document_id": "doc-enviro",
                "source_section": "Section 3.1",
                "target_document_id": "doc-loan",
                "target_section": "Section 5.2",
                "reference_text": "as set forth in Section 5.2 of the Loan Agreement",
                "confidence": "medium",
            },
        ],
        "conditions_precedent": [
            {
                "id": "cp-001", "description": "Execution of Loan Agreement",
                "source_document_id": "doc-loan",
                "status": "satisfied", "confidence": "high",
            },
            {
                "id": "cp-002", "description": "Delivery of Guaranty",
                "source_document_id": "doc-loan",
                "required_document_id": "doc-guaranty",
                "enables_document_id": "doc-loan",
                "status": "pending", "confidence": "high",
            },
            {
                "id": "cp-003", "description": "Delivery of Environmental Indemnity",
                "source_document_id": "doc-loan",
                "required_document_id": "doc-enviro",
                "enables_document_id": "doc-loan",
                "status": "pending", "confidence": "high",
            },
        ],
        "annotations": [],
        "extraction_log": [],
    }


@pytest.fixture
def sample_analysis_results():
    """A complete, valid AnalysisResults dict for schema validation tests."""
    return {
        "schema_version": "1.0.0",
        "deal_graph_hash": "abc123def456",
        "analyses": {
            "hierarchy": {
                "analysis_type": "hierarchy",
                "status": "completed",
                "completion": "complete",
                "run_timestamp": "2025-01-15T12:00:00Z",
                "model_used": "claude-sonnet-4-20250514",
                "findings": [
                    {
                        "id": "f001",
                        "display_ordinal": 1,
                        "severity": "INFO",
                        "category": "controlling_authority",
                        "title": "Loan Agreement controls Guaranty",
                        "description": "The Loan Agreement is the controlling document for all guaranteed obligations.",
                        "affected_entities": [
                            {"entity_type": "document", "entity_id": "doc-loan", "document_id": "doc-loan"},
                            {"entity_type": "document", "entity_id": "doc-guaranty", "document_id": "doc-guaranty"},
                        ],
                        "confidence": "high",
                        "source": "explicit",
                        "verified": True,
                    },
                    {
                        "id": "f002",
                        "display_ordinal": 2,
                        "severity": "WARNING",
                        "category": "inferred_hierarchy",
                        "title": "Inferred hierarchy for Environmental Indemnity",
                        "description": "Environmental Indemnity is subordinate to Loan Agreement by convention.",
                        "affected_entities": [
                            {"entity_type": "document", "entity_id": "doc-enviro", "document_id": "doc-enviro"},
                        ],
                        "confidence": "medium",
                        "source": "inferred",
                        "verified": False,
                    },
                ],
                "summary": {
                    "total_findings": 2,
                    "by_severity": {"INFO": 1, "WARNING": 1},
                    "key_findings": ["Loan Agreement controls Guaranty"],
                },
                "errors": [],
            },
        },
        "metadata": {
            "last_full_analysis": "2025-01-15T12:00:00Z",
            "documents_included": ["doc-loan", "doc-guaranty", "doc-enviro"],
            "engine_version": "0.1.0",
        },
        "staleness": {
            "hierarchy": {
                "is_stale": False,
                "last_run": "2025-01-15T12:00:00Z",
                "stale_reason": None,
                "graph_hash_at_run": "abc123def456",
            },
        },
    }
