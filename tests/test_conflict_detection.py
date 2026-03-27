"""Tests for Split 02 Section 06 — Cross-reference conflict detection."""

import copy

from src.semantic_analysis.analyses.conflict_detection import run_conflict_detection
from src.semantic_analysis.analyses.conflict_utils import (
    adjust_severity_with_hierarchy,
    detect_circular_references,
    detect_dangling_references,
    detect_missing_documents,
    generate_contradiction_candidates,
    rank_and_cap_candidates,
    _build_section_inventory,
)
from src.semantic_analysis.analyses.hierarchy import run_hierarchy_analysis
from src.semantic_analysis.analyses.defined_terms import run_defined_terms_analysis
from src.semantic_analysis.schemas import AffectedEntity, AnalysisResult, AnalysisSummary, Finding


class TestDanglingReferences:
    def test_dangling_ref_detected(self):
        graph = {
            "documents": {
                "doc-a": {"id": "doc-a", "name": "Doc A",
                          "key_provisions": [{"section_reference": "1.1", "summary": "test"}]},
                "doc-b": {"id": "doc-b", "name": "Doc B",
                          "key_provisions": [{"section_reference": "2.1", "summary": "test"}]},
            },
            "cross_references": [
                {"id": "xref-1", "source_document_id": "doc-a", "source_section": "1.1",
                 "target_document_id": "doc-b", "target_section": "Section 99.99",
                 "reference_text": "test", "confidence": "high"},
            ],
        }
        inv = _build_section_inventory(graph)
        findings = detect_dangling_references(graph["cross_references"], inv, graph["documents"])
        dangling = [f for f in findings if f.category == "dangling_reference"]
        assert len(dangling) == 1
        assert dangling[0].severity == "ERROR"

    def test_exact_match_no_finding(self):
        graph = {
            "documents": {
                "doc-a": {"id": "doc-a", "name": "A", "key_provisions": []},
                "doc-b": {"id": "doc-b", "name": "B",
                          "key_provisions": [{"section_reference": "4.2", "summary": "t"}]},
            },
            "cross_references": [
                {"id": "xref-1", "source_document_id": "doc-a", "source_section": "1.1",
                 "target_document_id": "doc-b", "target_section": "4.2",
                 "reference_text": "test", "confidence": "high"},
            ],
        }
        inv = _build_section_inventory(graph)
        findings = detect_dangling_references(graph["cross_references"], inv, graph["documents"])
        assert len(findings) == 0

    def test_fuzzy_match_ambiguous(self):
        graph = {
            "documents": {
                "doc-a": {"id": "doc-a", "name": "A", "key_provisions": []},
                "doc-b": {"id": "doc-b", "name": "B",
                          "key_provisions": [{"section_reference": "1.1", "summary": "t"}]},
            },
            "cross_references": [
                {"id": "xref-1", "source_document_id": "doc-a", "source_section": "1.1",
                 "target_document_id": "doc-b", "target_section": "Section 1.01",
                 "reference_text": "test", "confidence": "high"},
            ],
        }
        inv = _build_section_inventory(graph)
        findings = detect_dangling_references(graph["cross_references"], inv, graph["documents"])
        ambiguous = [f for f in findings if f.category == "ambiguous_section_ref"]
        assert len(ambiguous) == 1
        assert ambiguous[0].severity == "WARNING"

    def test_closest_candidate_in_description(self):
        graph = {
            "documents": {
                "doc-a": {"id": "doc-a", "name": "A", "key_provisions": []},
                "doc-b": {"id": "doc-b", "name": "B",
                          "key_provisions": [{"section_reference": "7.1", "summary": "t"}]},
            },
            "cross_references": [
                {"id": "xref-1", "source_document_id": "doc-a", "source_section": "1.1",
                 "target_document_id": "doc-b", "target_section": "7.2",
                 "reference_text": "test", "confidence": "high"},
            ],
        }
        inv = _build_section_inventory(graph)
        findings = detect_dangling_references(graph["cross_references"], inv, graph["documents"])
        dangling = [f for f in findings if f.category == "dangling_reference"]
        assert len(dangling) == 1
        assert "7.1" in dangling[0].description  # Closest suggestion


class TestCircularReferences:
    def test_circular_ref_detected(self):
        xrefs = [
            {"id": "x1", "source_document_id": "doc-a", "target_document_id": "doc-b"},
            {"id": "x2", "source_document_id": "doc-b", "target_document_id": "doc-c"},
            {"id": "x3", "source_document_id": "doc-c", "target_document_id": "doc-a"},
        ]
        findings = detect_circular_references(xrefs)
        circular = [f for f in findings if f.category == "circular_reference"]
        assert len(circular) >= 1
        assert "chain" in circular[0].description.lower() or "->" in circular[0].description


class TestMissingDocuments:
    def test_missing_document_detected(self):
        graph = {
            "documents": {"doc-a": {"id": "doc-a"}},
            "relationships": [
                {"id": "r1", "source_document_id": "doc-a",
                 "target_document_id": "doc-missing",
                 "relationship_type": "references", "description": "references missing doc"},
            ],
            "cross_references": [],
        }
        findings = detect_missing_documents(graph)
        missing = [f for f in findings if f.category == "missing_document"]
        assert len(missing) >= 1


class TestContradictionCandidates:
    def test_candidate_generated(self, minimal_deal_graph):
        hierarchy = run_hierarchy_analysis(minimal_deal_graph)
        candidates = generate_contradiction_candidates(minimal_deal_graph, hierarchy, None)
        assert isinstance(candidates, list)

    def test_enriched_by_term_data(self):
        graph = {
            "documents": {
                "doc-a": {"id": "doc-a", "name": "A", "key_provisions": [], "summary": "", "obligations": []},
                "doc-b": {"id": "doc-b", "name": "B", "key_provisions": [], "summary": "", "obligations": []},
            },
            "defined_terms": [
                {"id": "t1", "term": "Borrower", "defining_document_id": "doc-a",
                 "definition_snippet": "means X", "confidence": "high"},
                {"id": "t2", "term": "Borrower", "defining_document_id": "doc-b",
                 "definition_snippet": "means Y", "confidence": "high"},
            ],
            "relationships": [], "cross_references": [],
            "conditions_precedent": [], "parties": {},
        }
        term_results = run_defined_terms_analysis(graph)
        candidates = generate_contradiction_candidates(graph, None, term_results)
        # Should have a candidate with conflicting term reason
        scored = [c for c in candidates if c["score"] > 0]
        assert len(scored) >= 1


class TestCandidateRanking:
    def test_ranking_and_cap(self):
        candidates = [{"doc_a": f"d{i}", "doc_b": f"d{i+1}", "score": i, "reasons": []}
                      for i in range(30)]
        ranked = rank_and_cap_candidates(candidates, cap=20)
        assert len(ranked) == 20
        assert ranked[0]["score"] >= ranked[-1]["score"]


class TestHierarchyIntegration:
    def test_hierarchy_adjusts_severity(self):
        finding = Finding(
            id="f1", display_ordinal=1, severity="WARNING",
            category="dangling_reference", title="test", description="test",
            affected_entities=[AffectedEntity(entity_type="document", entity_id="doc-a", document_id="doc-a")],
            confidence="high", source="explicit", verified=True,
        )
        hierarchy = AnalysisResult(
            analysis_type="hierarchy", status="completed", completion="complete",
            run_timestamp="2025-01-01T00:00:00Z", model_used="test",
            findings=[Finding(
                id="h1", display_ordinal=1, severity="INFO",
                category="explicit_hierarchy", title="A controls B",
                description="test",
                affected_entities=[AffectedEntity(entity_type="document", entity_id="doc-a", document_id="doc-a")],
                confidence="high", source="explicit", verified=True,
            )],
            summary=AnalysisSummary(total_findings=1, by_severity={"INFO": 1}, key_findings=[]),
            errors=[],
        )
        adjusted = adjust_severity_with_hierarchy(finding, hierarchy)
        assert adjusted.severity == "ERROR"

    def test_no_hierarchy_still_works(self, minimal_deal_graph):
        result = run_conflict_detection(minimal_deal_graph, hierarchy_results=None)
        assert result.status == "completed"


class TestFullAnalysis:
    def test_returns_analysis_result(self, minimal_deal_graph):
        result = run_conflict_detection(minimal_deal_graph)
        assert result.analysis_type == "conflicts"
        assert result.status == "completed"

    def test_ordinals_sequential(self, minimal_deal_graph):
        result = run_conflict_detection(minimal_deal_graph)
        if result.findings:
            ordinals = [f.display_ordinal for f in result.findings]
            assert ordinals == list(range(1, len(ordinals) + 1))
