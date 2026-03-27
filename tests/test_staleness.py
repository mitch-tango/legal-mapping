"""Tests for Split 02 Section 03 — Staleness tracking."""

import copy

import pytest

from src.semantic_analysis.graph_utils import compute_graph_hash
from src.semantic_analysis.schemas import AnalysisResults, StalenessRecord
from src.semantic_analysis.staleness import (
    ALL_ANALYSES,
    apply_staleness_rules,
    check_staleness,
    check_staleness_with_diff,
    detect_graph_changes,
    format_staleness_report,
)


def _make_analysis_results(graph, **overrides):
    """Create AnalysisResults with staleness records matching graph hash."""
    h = compute_graph_hash(graph)
    staleness = {
        name: StalenessRecord(
            is_stale=False, last_run="2025-01-15T12:00:00Z",
            stale_reason=None, graph_hash_at_run=h,
        )
        for name in ALL_ANALYSES
    }
    staleness.update(overrides)
    return AnalysisResults(
        schema_version="1.0.0",
        deal_graph_hash=h,
        analyses={},
        metadata={
            "last_full_analysis": "2025-01-15T12:00:00Z",
            "documents_included": [],
            "engine_version": "0.1.0",
        },
        staleness=staleness,
    )


class TestHashBasedStaleness:
    def test_fresh_analysis_not_stale(self, minimal_deal_graph):
        results = _make_analysis_results(minimal_deal_graph)
        records = check_staleness(minimal_deal_graph, results)
        for name in ALL_ANALYSES:
            assert records[name].is_stale is False

    def test_stale_after_graph_change(self, minimal_deal_graph):
        results = _make_analysis_results(minimal_deal_graph)
        # Modify graph
        modified = copy.deepcopy(minimal_deal_graph)
        modified["documents"]["doc-new"] = {"id": "doc-new", "name": "New Doc"}
        records = check_staleness(modified, results)
        # At least some should be stale since hash changed
        assert any(r.is_stale for r in records.values())

    def test_no_prior_results_all_stale(self, minimal_deal_graph):
        records = check_staleness(minimal_deal_graph, None)
        for name in ALL_ANALYSES:
            assert records[name].is_stale is True
            assert "no prior" in records[name].stale_reason


class TestStalenessRulesEngine:
    def test_document_added_stales_all(self):
        stale = apply_staleness_rules({"documents"})
        assert stale == set(ALL_ANALYSES)

    def test_relationship_change_stales_hierarchy_and_conflicts(self):
        stale = apply_staleness_rules({"relationships"})
        assert stale == {"hierarchy", "conflicts"}

    def test_term_change_stales_defined_terms_only(self):
        stale = apply_staleness_rules({"defined_terms"})
        assert stale == {"defined_terms"}

    def test_crossref_change_stales_conflicts_only(self):
        stale = apply_staleness_rules({"cross_references"})
        assert stale == {"conflicts"}

    def test_cp_change_stales_cp_and_execution_sequence(self):
        stale = apply_staleness_rules({"conditions_precedent"})
        assert stale == {"conditions_precedent", "execution_sequence"}

    def test_party_change_stales_exec_cp_terms(self):
        stale = apply_staleness_rules({"parties"})
        assert stale == {"execution_sequence", "conditions_precedent", "defined_terms"}

    def test_annotation_change_stales_nothing(self):
        stale = apply_staleness_rules({"annotations"})
        assert stale == set()


class TestDetectGraphChanges:
    def test_detects_document_change(self, minimal_deal_graph):
        modified = copy.deepcopy(minimal_deal_graph)
        modified["documents"]["doc-new"] = {"id": "doc-new"}
        changes = detect_graph_changes(minimal_deal_graph, modified)
        assert "documents" in changes

    def test_detects_no_changes(self, minimal_deal_graph):
        changes = detect_graph_changes(minimal_deal_graph, minimal_deal_graph)
        assert changes == set()

    def test_detects_relationship_change(self, minimal_deal_graph):
        modified = copy.deepcopy(minimal_deal_graph)
        modified["relationships"].append({"id": "rel-new"})
        changes = detect_graph_changes(minimal_deal_graph, modified)
        assert "relationships" in changes
        assert "documents" not in changes


class TestGranularStaleness:
    def test_term_change_only_stales_defined_terms(self, minimal_deal_graph):
        results = _make_analysis_results(minimal_deal_graph)
        modified = copy.deepcopy(minimal_deal_graph)
        modified["defined_terms"].append({
            "id": "term-new", "term": "New Term",
            "defining_document_id": "doc-loan",
            "confidence": "high",
        })
        records = check_staleness_with_diff(modified, minimal_deal_graph, results)
        assert records["defined_terms"].is_stale is True
        assert records["hierarchy"].is_stale is False
        assert records["conflicts"].is_stale is False

    def test_annotation_change_stales_nothing(self, minimal_deal_graph):
        results = _make_analysis_results(minimal_deal_graph)
        modified = copy.deepcopy(minimal_deal_graph)
        modified["annotations"].append({"id": "ann-new", "note": "test"})
        records = check_staleness_with_diff(modified, minimal_deal_graph, results)
        for name in ALL_ANALYSES:
            assert records[name].is_stale is False


class TestCanonicalizationIntegration:
    def test_stable_hash(self, minimal_deal_graph):
        reordered = copy.deepcopy(minimal_deal_graph)
        reordered["relationships"] = list(reversed(reordered["relationships"]))
        assert compute_graph_hash(minimal_deal_graph) == compute_graph_hash(reordered)

    def test_different_data_different_hash(self, minimal_deal_graph):
        modified = copy.deepcopy(minimal_deal_graph)
        modified["deal"]["name"] = "Different Deal"
        assert compute_graph_hash(minimal_deal_graph) != compute_graph_hash(modified)


class TestFormatReport:
    def test_format_report(self, minimal_deal_graph):
        records = check_staleness(minimal_deal_graph, None)
        report = format_staleness_report(records)
        assert "STALE" in report
        for name in ALL_ANALYSES:
            assert name in report
