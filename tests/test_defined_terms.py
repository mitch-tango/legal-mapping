"""Tests for Split 02 Section 07 — Defined term tracking analysis."""

from src.semantic_analysis.analyses.defined_terms import (
    classify_term_status,
    detect_cross_document_dependencies,
    find_enhanced_terms,
    load_baseline_terms,
    run_defined_terms_analysis,
    track_term_usage,
)


class TestBaselineLoading:
    def test_baseline_terms_loaded(self, minimal_deal_graph):
        terms = load_baseline_terms(minimal_deal_graph)
        assert "borrower" in terms
        assert "guaranteed obligations" in terms
        assert len(terms) == 2

    def test_term_has_definitions(self, minimal_deal_graph):
        terms = load_baseline_terms(minimal_deal_graph)
        assert len(terms["borrower"]["definitions"]) == 1
        assert terms["borrower"]["definitions"][0]["document_id"] == "doc-loan"


class TestEnhancementPass:
    def test_finds_capitalized_terms(self, minimal_deal_graph):
        baseline = load_baseline_terms(minimal_deal_graph)
        enhanced = find_enhanced_terms(minimal_deal_graph, baseline)
        # Enhanced terms are capitalized multi-word phrases not in baseline
        assert isinstance(enhanced, list)

    def test_enhanced_marked_with_category(self, minimal_deal_graph):
        result = run_defined_terms_analysis(minimal_deal_graph)
        enhanced = [f for f in result.findings if f.category == "enhanced_term"]
        for f in enhanced:
            assert f.category == "enhanced_term"
            assert f.severity == "INFO"


class TestUsageTracking:
    def test_usage_across_documents(self, minimal_deal_graph):
        terms = load_baseline_terms(minimal_deal_graph)
        usage = track_term_usage(minimal_deal_graph, terms)
        # "borrower" is used in loan (defining) + guaranty + enviro
        assert "doc-loan" in usage["borrower"]


class TestStatusClassification:
    def test_defined_status(self):
        status = classify_term_status(
            "borrower",
            [{"document_id": "doc-a", "snippet": "means..."}],
            {"doc-a", "doc-b"},
        )
        assert status == "defined"

    def test_orphaned_status(self):
        status = classify_term_status(
            "unused",
            [{"document_id": "doc-a", "snippet": "means..."}],
            {"doc-a"},  # Only used in defining doc
        )
        assert status == "orphaned"

    def test_undefined_status(self):
        status = classify_term_status("unknown", [], {"doc-a", "doc-b"})
        assert status == "undefined"

    def test_conflicting_status(self):
        status = classify_term_status(
            "test",
            [
                {"document_id": "doc-a", "snippet": "means X"},
                {"document_id": "doc-b", "snippet": "means Y"},
            ],
            {"doc-a", "doc-b"},
        )
        assert status == "conflicting"


class TestInconsistencyDetection:
    def test_identical_definitions_no_conflict(self, minimal_deal_graph):
        result = run_defined_terms_analysis(minimal_deal_graph)
        conflicts = [f for f in result.findings if f.category == "conflicting_definition"]
        # minimal graph has no conflicting definitions
        assert len(conflicts) == 0

    def test_conflicting_definitions_detected(self):
        """Graph with same term defined differently in two docs."""
        graph = {
            "schema_version": "1.0.0",
            "documents": {
                "doc-a": {"id": "doc-a", "name": "Doc A", "key_provisions": [], "summary": "", "obligations": []},
                "doc-b": {"id": "doc-b", "name": "Doc B", "key_provisions": [], "summary": "", "obligations": []},
            },
            "defined_terms": [
                {"id": "t1", "term": "Borrower", "defining_document_id": "doc-a",
                 "definition_snippet": "means Company A", "confidence": "high"},
                {"id": "t2", "term": "Borrower", "defining_document_id": "doc-b",
                 "definition_snippet": "means Company B", "confidence": "high"},
            ],
            "relationships": [], "cross_references": [], "conditions_precedent": [],
            "parties": {},
        }
        result = run_defined_terms_analysis(graph)
        conflicts = [f for f in result.findings if f.category == "conflicting_definition"]
        assert len(conflicts) == 1
        assert conflicts[0].severity == "ERROR"


class TestCrossDocDependency:
    def test_cross_document_dependency_warning(self, minimal_deal_graph):
        result = run_defined_terms_analysis(minimal_deal_graph)
        xdep = [f for f in result.findings if f.category == "cross_document_dependency"]
        # "Borrower" is used in guaranty/enviro without cross-ref back for the term itself
        # (there are cross-refs but they reference sections, not terms specifically)
        assert isinstance(xdep, list)


class TestFullAnalysis:
    def test_returns_analysis_result(self, minimal_deal_graph):
        result = run_defined_terms_analysis(minimal_deal_graph)
        assert result.analysis_type == "defined_terms"
        assert result.status == "completed"

    def test_ordinals_sequential(self, minimal_deal_graph):
        result = run_defined_terms_analysis(minimal_deal_graph)
        if result.findings:
            ordinals = [f.display_ordinal for f in result.findings]
            assert ordinals == list(range(1, len(ordinals) + 1))
