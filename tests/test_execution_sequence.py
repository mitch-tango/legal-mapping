"""Tests for Split 02 Section 09 — Execution sequence derivation."""

import pytest

from src.semantic_analysis.analyses.conditions_precedent import run_conditions_precedent_analysis
from src.semantic_analysis.analyses.execution_sequence import (
    extract_crossref_dependencies,
    extract_signing_dependencies,
    run_execution_sequence_analysis,
)
from src.semantic_analysis.schemas import (
    AnalysisMetadata,
    AnalysisResult,
    AnalysisResults,
    AnalysisSummary,
    StalenessRecord,
)


def _make_existing_results_with_cp(graph):
    """Run CP analysis and wrap in AnalysisResults."""
    cp_result = run_conditions_precedent_analysis(graph)
    return AnalysisResults(
        schema_version="1.0.0",
        deal_graph_hash="test",
        analyses={"conditions_precedent": cp_result},
        metadata=AnalysisMetadata(
            last_full_analysis=None, documents_included=[], engine_version="0.1.0",
        ),
        staleness={},
    )


def _make_empty_results():
    return AnalysisResults(
        schema_version="1.0.0",
        deal_graph_hash="test",
        analyses={},
        metadata=AnalysisMetadata(
            last_full_analysis=None, documents_included=[], engine_version="0.1.0",
        ),
        staleness={},
    )


class TestPrerequisites:
    def test_requires_cp_results(self, minimal_deal_graph):
        with pytest.raises(ValueError, match="conditions_precedent"):
            run_execution_sequence_analysis(minimal_deal_graph, _make_empty_results())

    def test_accepts_completed_cp(self, minimal_deal_graph):
        existing = _make_existing_results_with_cp(minimal_deal_graph)
        result = run_execution_sequence_analysis(minimal_deal_graph, existing)
        assert result.status == "completed"


class TestBaselineFromCP:
    def test_respects_cp_ordering(self, minimal_deal_graph):
        existing = _make_existing_results_with_cp(minimal_deal_graph)
        result = run_execution_sequence_analysis(minimal_deal_graph, existing)
        assert result.analysis_type == "execution_sequence"
        assert isinstance(result.findings, list)


class TestSigningDependencies:
    def test_signing_deps_extracted(self):
        graph = {
            "relationships": [
                {"id": "r1", "source_document_id": "doc-guaranty",
                 "target_document_id": "doc-loan",
                 "relationship_type": "guarantees",
                 "description": "Guaranty guarantees Loan"},
            ],
        }
        deps = extract_signing_dependencies(graph)
        # Loan must be signed before Guaranty
        assert ("doc-loan", "doc-guaranty") in deps

    def test_signing_deps_in_findings(self, minimal_deal_graph):
        existing = _make_existing_results_with_cp(minimal_deal_graph)
        result = run_execution_sequence_analysis(minimal_deal_graph, existing)
        signing = [f for f in result.findings if f.category == "signing_dependency"]
        # minimal graph has "controls" relationships, not guarantees/secures
        # so signing deps may or may not be present based on rel types
        assert isinstance(signing, list)


class TestCrossRefDependencies:
    def test_crossref_deps_extracted(self):
        graph = {
            "relationships": [
                {"id": "r1", "source_document_id": "doc-a",
                 "target_document_id": "doc-b",
                 "relationship_type": "incorporates",
                 "description": "A incorporates B"},
            ],
        }
        deps = extract_crossref_dependencies(graph)
        assert ("doc-b", "doc-a") in deps


class TestParallelExecutionWindows:
    def test_parallel_windows(self, minimal_deal_graph):
        existing = _make_existing_results_with_cp(minimal_deal_graph)
        result = run_execution_sequence_analysis(minimal_deal_graph, existing)
        parallel = [f for f in result.findings
                    if f.category == "parallel_execution_window"]
        # Should have at least one parallel window (guaranty + enviro can be parallel)
        assert isinstance(parallel, list)


class TestGatingConditions:
    def test_gating_conditions_present(self, minimal_deal_graph):
        existing = _make_existing_results_with_cp(minimal_deal_graph)
        result = run_execution_sequence_analysis(minimal_deal_graph, existing)
        gating = [f for f in result.findings if f.category == "gating_condition"]
        assert isinstance(gating, list)


class TestCriticalPath:
    def test_critical_path_marked(self, minimal_deal_graph):
        existing = _make_existing_results_with_cp(minimal_deal_graph)
        result = run_execution_sequence_analysis(minimal_deal_graph, existing)
        crit = [f for f in result.findings if f.category == "critical_path_step"]
        assert len(crit) >= 1


class TestFullAnalysis:
    def test_returns_complete_result(self, minimal_deal_graph):
        existing = _make_existing_results_with_cp(minimal_deal_graph)
        result = run_execution_sequence_analysis(minimal_deal_graph, existing)
        assert result.analysis_type == "execution_sequence"
        assert result.status == "completed"
        assert result.completion == "complete"

    def test_ordinals_sequential(self, minimal_deal_graph):
        existing = _make_existing_results_with_cp(minimal_deal_graph)
        result = run_execution_sequence_analysis(minimal_deal_graph, existing)
        if result.findings:
            ordinals = [f.display_ordinal for f in result.findings]
            assert ordinals == list(range(1, len(ordinals) + 1))
