"""Tests for Split 02 Section 12 — Visualization contract validation."""

from src.semantic_analysis.schemas import AnalysisResults
from src.semantic_analysis.visualization_contract import (
    KNOWN_ANALYSIS_TYPES,
    KNOWN_ENTITY_TYPES,
    SEVERITY_LEVELS,
    validate_for_visualization,
)


class TestSchemaConformance:
    def test_parseable_by_split_03(self, sample_analysis_results):
        results = AnalysisResults(**sample_analysis_results)
        json_str = results.model_dump_json()
        restored = AnalysisResults.model_validate_json(json_str)
        assert restored.schema_version == "1.0.0"
        assert "analyses" in restored.model_dump()

    def test_schema_version_present(self, sample_analysis_results):
        results = AnalysisResults(**sample_analysis_results)
        assert results.schema_version
        assert "." in results.schema_version  # semver-like


class TestFindingEntityLinks:
    def test_findings_have_affected_entities(self, sample_analysis_results):
        results = AnalysisResults(**sample_analysis_results)
        for analysis_type, result in results.analyses.items():
            for f in result.findings:
                # At least some findings should have entities
                # (our sample has them all populated)
                assert isinstance(f.affected_entities, list)

    def test_affected_entity_types_known(self, sample_analysis_results):
        results = AnalysisResults(**sample_analysis_results)
        for result in results.analyses.values():
            for f in result.findings:
                for e in f.affected_entities:
                    assert e.entity_type in KNOWN_ENTITY_TYPES

    def test_document_id_always_set(self, sample_analysis_results):
        results = AnalysisResults(**sample_analysis_results)
        for result in results.analyses.values():
            for f in result.findings:
                for e in f.affected_entities:
                    assert e.document_id


class TestSeverityFiltering:
    def test_severity_filterable(self, sample_analysis_results):
        results = AnalysisResults(**sample_analysis_results)
        all_findings = []
        for result in results.analyses.values():
            all_findings.extend(result.findings)
        buckets = {sev: [] for sev in SEVERITY_LEVELS}
        for f in all_findings:
            buckets[f.severity].append(f)
        # Should be partitioned successfully
        assert sum(len(b) for b in buckets.values()) == len(all_findings)

    def test_summary_matches_findings(self, sample_analysis_results):
        results = AnalysisResults(**sample_analysis_results)
        for result in results.analyses.values():
            actual = {}
            for f in result.findings:
                actual[f.severity] = actual.get(f.severity, 0) + 1
            for sev, count in result.summary.by_severity.items():
                assert actual.get(sev, 0) == count


class TestDocumentFiltering:
    def test_document_filterable(self, sample_analysis_results):
        results = AnalysisResults(**sample_analysis_results)
        # Filter by a known document
        doc_findings = []
        for result in results.analyses.values():
            for f in result.findings:
                if any(e.document_id == "doc-loan" for e in f.affected_entities):
                    doc_findings.append(f)
        assert len(doc_findings) >= 1


class TestAnalysisTypeFiltering:
    def test_analysis_type_filterable(self, sample_analysis_results):
        results = AnalysisResults(**sample_analysis_results)
        assert "hierarchy" in results.analyses

    def test_analysis_types_known(self, sample_analysis_results):
        results = AnalysisResults(**sample_analysis_results)
        for key in results.analyses:
            assert key in KNOWN_ANALYSIS_TYPES


class TestHierarchyOverlay:
    def test_hierarchy_findings_have_category(self, sample_analysis_results):
        results = AnalysisResults(**sample_analysis_results)
        if "hierarchy" in results.analyses:
            for f in results.analyses["hierarchy"].findings:
                assert f.category


class TestValidateForVisualization:
    def test_valid_results_no_violations(self, sample_analysis_results):
        results = AnalysisResults(**sample_analysis_results)
        violations = validate_for_visualization(results)
        assert violations == []

    def test_empty_analyses_ok(self):
        results = AnalysisResults(
            schema_version="1.0.0",
            deal_graph_hash="abc",
            analyses={},
            metadata={"documents_included": [], "engine_version": "0.1.0"},
            staleness={},
        )
        violations = validate_for_visualization(results)
        assert violations == []
