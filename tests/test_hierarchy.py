"""Tests for Split 02 Section 05 — Document hierarchy analysis."""

from src.semantic_analysis.analyses.hierarchy import (
    detect_dual_authority,
    detect_explicit_hierarchy,
    detect_inferred_hierarchy,
    discover_issue_areas,
    run_hierarchy_analysis,
    slugify_issue_area,
)


class TestIssueAreaDiscovery:
    def test_discovers_issue_areas(self, minimal_deal_graph):
        areas = discover_issue_areas(minimal_deal_graph)
        assert isinstance(areas, list)

    def test_issue_area_ids_are_slugified(self):
        assert slugify_issue_area("Capital call procedures") == "capital-call-procedures"
        assert slugify_issue_area("Default remedies / events of default") == "default-remedies-events-of-default"

    def test_slug_strips_special_chars(self):
        assert slugify_issue_area("Test (special) chars!") == "test-special-chars"


class TestHierarchyDetection:
    def test_explicit_hierarchy_high_confidence(self, minimal_deal_graph):
        areas = discover_issue_areas(minimal_deal_graph)
        # Use a broad issue area covering our test docs
        test_area = {
            "issue_area_id": "test",
            "label": "Test area",
            "anchor_evidence": [
                {"document_id": "doc-loan", "section": ""},
                {"document_id": "doc-guaranty", "section": ""},
            ],
        }
        findings = detect_explicit_hierarchy(minimal_deal_graph, test_area)
        explicit = [f for f in findings if f.category == "explicit_hierarchy"]
        assert len(explicit) >= 1
        for f in explicit:
            assert f.confidence == "high"
            assert f.source == "explicit"

    def test_inferred_hierarchy_medium_confidence(self, minimal_deal_graph):
        test_area = {
            "issue_area_id": "test",
            "label": "Test area",
            "anchor_evidence": [
                {"document_id": did, "section": ""}
                for did in minimal_deal_graph["documents"]
            ],
        }
        findings = detect_inferred_hierarchy(minimal_deal_graph, test_area)
        inferred = [f for f in findings if f.category == "inferred_hierarchy"]
        for f in inferred:
            assert f.confidence == "medium"
            assert f.source == "inferred"


class TestDualAuthority:
    def test_dual_authority_detected(self):
        """Two documents both control for same issue area."""
        graph = {
            "documents": {
                "doc-a": {"id": "doc-a", "name": "Doc A", "document_type": "loan_agreement"},
                "doc-b": {"id": "doc-b", "name": "Doc B", "document_type": "operating_agreement"},
            },
            "relationships": [
                {"id": "r1", "source_document_id": "doc-a", "target_document_id": "doc-b",
                 "relationship_type": "controls", "confidence": "high", "description": "A controls B"},
                {"id": "r2", "source_document_id": "doc-b", "target_document_id": "doc-a",
                 "relationship_type": "controls", "confidence": "high", "description": "B controls A"},
            ],
        }
        area = {
            "issue_area_id": "test",
            "label": "Test",
            "anchor_evidence": [
                {"document_id": "doc-a", "section": ""},
                {"document_id": "doc-b", "section": ""},
            ],
        }
        findings = detect_dual_authority(graph, area)
        dual = [f for f in findings if f.category == "dual_authority_conflict"]
        assert len(dual) == 1
        assert dual[0].severity == "ERROR"


class TestFullAnalysis:
    def test_run_returns_analysis_result(self, minimal_deal_graph):
        result = run_hierarchy_analysis(minimal_deal_graph)
        assert result.analysis_type == "hierarchy"
        assert result.status == "completed"
        assert isinstance(result.findings, list)

    def test_findings_have_sequential_ordinals(self, minimal_deal_graph):
        result = run_hierarchy_analysis(minimal_deal_graph)
        if result.findings:
            ordinals = [f.display_ordinal for f in result.findings]
            assert ordinals == list(range(1, len(ordinals) + 1))

    def test_section_citations_in_explicit(self, minimal_deal_graph):
        result = run_hierarchy_analysis(minimal_deal_graph)
        explicit = [f for f in result.findings if f.category == "explicit_hierarchy"]
        for f in explicit:
            assert len(f.affected_entities) >= 2
