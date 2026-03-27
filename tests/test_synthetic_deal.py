"""End-to-end validation of the synthetic test deal (Acme Industrial Park).

Tests that the synthetic deal-graph.json and deal-analysis.json:
1. Pass schema validation (Pydantic round-trip)
2. Pass semantic validation (referential integrity)
3. Produce correct CLI summary output
4. Analysis results conform to the visualization contract
"""

import json
from pathlib import Path

import pytest

from src.graph.manager import load_graph
from src.graph.validator import validate_full
from src.models.schema import DealGraph
from src.semantic_analysis.schemas import AnalysisResults
from src.semantic_analysis.visualization_contract import validate_for_visualization

DEAL_DIR = str(Path(__file__).parent.parent / "deals" / "test-acme-acquisition")
GRAPH_PATH = Path(DEAL_DIR) / "deal-graph.json"
ANALYSIS_PATH = Path(DEAL_DIR) / "deal-analysis.json"


@pytest.fixture
def graph():
    return load_graph(DEAL_DIR)


@pytest.fixture
def analysis():
    with open(ANALYSIS_PATH) as f:
        return AnalysisResults.model_validate_json(f.read())


class TestGraphSchemaValidation:
    """deal-graph.json passes Pydantic schema validation."""

    def test_graph_loads_successfully(self, graph):
        assert graph is not None
        assert isinstance(graph, DealGraph)

    def test_schema_version(self, graph):
        assert graph.schema_version == "1.0.0"

    def test_round_trip_serialization(self, graph):
        """Serialize and deserialize — nothing lost."""
        json_str = graph.model_dump_json()
        roundtripped = DealGraph.model_validate_json(json_str)
        assert len(roundtripped.documents) == len(graph.documents)
        assert len(roundtripped.relationships) == len(graph.relationships)
        assert len(roundtripped.defined_terms) == len(graph.defined_terms)


class TestGraphSemanticValidation:
    """deal-graph.json passes all semantic validation rules."""

    def test_full_validation_passes(self, graph):
        result = validate_full(graph)
        assert result.is_valid, f"Validation errors: {result.errors}"
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_all_relationship_targets_exist(self, graph):
        doc_ids = set(graph.documents.keys())
        for rel in graph.relationships:
            assert rel.source_document_id in doc_ids, f"rel {rel.id}: source {rel.source_document_id} missing"
            assert rel.target_document_id in doc_ids, f"rel {rel.id}: target {rel.target_document_id} missing"

    def test_all_party_references_valid(self, graph):
        party_ids = set(graph.parties.keys())
        for doc in graph.documents.values():
            for pref in doc.parties:
                assert pref.party_id in party_ids, f"doc {doc.id}: party {pref.party_id} missing"

    def test_all_defined_term_references_valid(self, graph):
        doc_ids = set(graph.documents.keys())
        for term in graph.defined_terms:
            assert term.defining_document_id in doc_ids
            for used_id in term.used_in_document_ids:
                assert used_id in doc_ids

    def test_no_duplicate_ids(self, graph):
        all_ids = []
        all_ids.extend(graph.documents.keys())
        all_ids.extend(graph.parties.keys())
        all_ids.extend(r.id for r in graph.relationships)
        all_ids.extend(t.id for t in graph.defined_terms)
        all_ids.extend(x.id for x in graph.cross_references)
        all_ids.extend(c.id for c in graph.conditions_precedent)
        all_ids.extend(a.id for a in graph.annotations)
        all_ids.extend(e.id for e in graph.extraction_log)
        assert len(all_ids) == len(set(all_ids)), "Duplicate IDs found"


class TestGraphContent:
    """Synthetic deal has expected content."""

    def test_document_count(self, graph):
        assert len(graph.documents) == 6

    def test_party_count(self, graph):
        assert len(graph.parties) == 5

    def test_relationship_count(self, graph):
        assert len(graph.relationships) == 11

    def test_defined_term_count(self, graph):
        assert len(graph.defined_terms) == 10

    def test_cross_reference_count(self, graph):
        assert len(graph.cross_references) == 6

    def test_conditions_precedent_count(self, graph):
        assert len(graph.conditions_precedent) == 5

    def test_deal_metadata(self, graph):
        assert graph.deal.name == "Acme Industrial Park Acquisition"
        assert graph.deal.deal_type == "acquisition"
        assert graph.deal.status == "active"

    def test_relationship_types_used(self, graph):
        types = {r.relationship_type for r in graph.relationships}
        assert "controls" in types
        assert "guarantees" in types
        assert "references" in types
        assert "indemnifies" in types
        assert "triggers" in types
        assert "restricts" in types
        assert "conditions_precedent" in types

    def test_has_items_needing_review(self, graph):
        needs_review = [r for r in graph.relationships if r.needs_review]
        assert len(needs_review) >= 1, "Should have at least one item flagged for review"

    def test_has_pending_conditions(self, graph):
        pending = [c for c in graph.conditions_precedent if c.status == "pending"]
        assert len(pending) >= 1, "Should have pending conditions for testing"


class TestAnalysisValidation:
    """deal-analysis.json passes schema validation."""

    def test_analysis_loads(self, analysis):
        assert analysis is not None
        assert isinstance(analysis, AnalysisResults)

    def test_all_five_analyses_present(self, analysis):
        expected = {"hierarchy", "conflicts", "defined_terms", "conditions_precedent", "execution_sequence"}
        assert set(analysis.analyses.keys()) == expected

    def test_all_analyses_completed(self, analysis):
        for name, result in analysis.analyses.items():
            assert result.status == "completed", f"{name} not completed"
            assert result.completion == "complete", f"{name} not complete"

    def test_finding_count(self, analysis):
        total = sum(len(a.findings) for a in analysis.analyses.values())
        assert total == 14

    def test_has_critical_finding(self, analysis):
        """At least one CRITICAL finding exists (Phase I ESA)."""
        critical = []
        for a in analysis.analyses.values():
            critical.extend(f for f in a.findings if f.severity == "CRITICAL")
        assert len(critical) >= 1

    def test_no_staleness(self, analysis):
        for name, record in analysis.staleness.items():
            assert not record.is_stale, f"{name} is stale"


class TestVisualizationContract:
    """Analysis results conform to the visualization contract."""

    def test_visualization_contract(self, analysis):
        violations = validate_for_visualization(analysis)
        assert violations == [], f"Visualization contract violations: {violations}"


class TestCLIIntegration:
    """CLI commands work with synthetic deal."""

    def test_validate_graph_cli(self):
        from src.cli import validate_graph
        result = json.loads(validate_graph(DEAL_DIR))
        assert result["status"] == "valid"
        assert result["errors"] == []

    def test_show_graph_summary_cli(self):
        from src.cli import show_graph_summary
        result = json.loads(show_graph_summary(DEAL_DIR))
        assert result["status"] == "success"
        assert result["document_count"] == 6
        assert result["relationship_count"] == 11
        assert result["party_count"] == 5
        assert result["defined_term_count"] == 10
        assert result["condition_count"] == 5
