"""Tests for Split 02 Section 01 — Analysis results schema and ID generation."""

import pytest
from pydantic import ValidationError

from src.semantic_analysis.schemas import (
    AffectedEntity,
    AnalysisResult,
    AnalysisResults,
    AnalysisSummary,
    Finding,
)
from src.semantic_analysis.id_generation import generate_finding_id


# ── Schema Validation ────────────────────────────────────────────────────


class TestAnalysisResultsSchema:
    def test_schema_validates_complete_result(self, sample_analysis_results):
        result = AnalysisResults(**sample_analysis_results)
        assert result.schema_version == "1.0.0"
        assert "hierarchy" in result.analyses

    def test_schema_rejects_missing_required_fields(self):
        with pytest.raises(ValidationError):
            AnalysisResult(
                # Missing analysis_type and findings
                status="completed",
                completion="complete",
                run_timestamp="2025-01-15T12:00:00Z",
                model_used="test",
                summary=AnalysisSummary(total_findings=0, by_severity={}, key_findings=[]),
                errors=[],
            )

    def test_severity_values_constrained(self):
        with pytest.raises(ValidationError):
            Finding(
                id="f001", display_ordinal=1,
                severity="MAJOR",  # Invalid
                category="test", title="test", description="test",
                affected_entities=[], confidence="high",
                source="explicit", verified=False,
            )

    def test_valid_severities_accepted(self):
        for sev in ("CRITICAL", "ERROR", "WARNING", "INFO"):
            f = Finding(
                id="f001", display_ordinal=1,
                severity=sev,
                category="test", title="test", description="test",
                affected_entities=[], confidence="high",
                source="explicit", verified=False,
            )
            assert f.severity == sev

    def test_completion_field_matches_status_completed(self):
        with pytest.raises(ValidationError):
            AnalysisResult(
                analysis_type="hierarchy",
                status="completed",
                completion="partial",  # Must be "complete"
                run_timestamp="2025-01-15T12:00:00Z",
                model_used="test",
                findings=[], errors=[],
                summary=AnalysisSummary(total_findings=0, by_severity={}, key_findings=[]),
            )

    def test_completion_field_matches_status_failed(self):
        with pytest.raises(ValidationError):
            AnalysisResult(
                analysis_type="hierarchy",
                status="failed",
                completion="complete",  # Must be "failed"
                run_timestamp="2025-01-15T12:00:00Z",
                model_used="test",
                findings=[], errors=["some error"],
                summary=AnalysisSummary(total_findings=0, by_severity={}, key_findings=[]),
            )

    def test_errors_array_populated_on_failure(self):
        with pytest.raises(ValidationError):
            AnalysisResult(
                analysis_type="hierarchy",
                status="failed",
                completion="failed",
                run_timestamp="2025-01-15T12:00:00Z",
                model_used="test",
                findings=[], errors=[],  # Must be non-empty for failed
                summary=AnalysisSummary(total_findings=0, by_severity={}, key_findings=[]),
            )

    def test_failed_with_errors_succeeds(self):
        result = AnalysisResult(
            analysis_type="hierarchy",
            status="failed",
            completion="failed",
            run_timestamp="2025-01-15T12:00:00Z",
            model_used="test",
            findings=[], errors=["API timeout"],
            summary=AnalysisSummary(total_findings=0, by_severity={}, key_findings=[]),
        )
        assert result.status == "failed"

    def test_partial_status_allowed(self):
        result = AnalysisResult(
            analysis_type="conflicts",
            status="partial",
            completion="partial",
            run_timestamp="2025-01-15T12:00:00Z",
            model_used="test",
            findings=[], errors=[],
            summary=AnalysisSummary(total_findings=0, by_severity={}, key_findings=[]),
        )
        assert result.status == "partial"


# ── Finding ID Generation ────────────────────────────────────────────────


class TestFindingIdGeneration:
    def test_finding_id_is_content_derived(self):
        id1 = generate_finding_id("hierarchy", "controlling_authority", ["doc-001", "doc-002"])
        id2 = generate_finding_id("hierarchy", "controlling_authority", ["doc-001", "doc-002"])
        assert id1 == id2

    def test_finding_id_order_independent(self):
        id1 = generate_finding_id("hierarchy", "controlling_authority", ["doc-002", "doc-001"])
        id2 = generate_finding_id("hierarchy", "controlling_authority", ["doc-001", "doc-002"])
        assert id1 == id2

    def test_finding_id_differs_for_different_content(self):
        id1 = generate_finding_id("hierarchy", "controlling_authority", ["doc-001"])
        id2 = generate_finding_id("hierarchy", "controlling_authority", ["doc-002"])
        assert id1 != id2

    def test_finding_id_differs_for_different_category(self):
        id1 = generate_finding_id("hierarchy", "controlling_authority", ["doc-001"])
        id2 = generate_finding_id("hierarchy", "dual_authority_conflict", ["doc-001"])
        assert id1 != id2

    def test_finding_id_length(self):
        fid = generate_finding_id("hierarchy", "test", ["doc-001"])
        assert len(fid) == 16
        assert all(c in "0123456789abcdef" for c in fid)


# ── Display Ordinal ──────────────────────────────────────────────────────


class TestDisplayOrdinal:
    def test_display_ordinal_sequential(self, sample_analysis_results):
        results = AnalysisResults(**sample_analysis_results)
        hierarchy = results.analyses["hierarchy"]
        ordinals = [f.display_ordinal for f in hierarchy.findings]
        assert ordinals == [1, 2]


# ── Incremental Update ───────────────────────────────────────────────────


class TestIncrementalUpdate:
    def test_incremental_update_preserves_other_analyses(self, sample_analysis_results):
        results = AnalysisResults(**sample_analysis_results)

        # Add a new analysis (conflicts) alongside existing hierarchy
        results.analyses["conflicts"] = AnalysisResult(
            analysis_type="conflicts",
            status="completed",
            completion="complete",
            run_timestamp="2025-01-15T13:00:00Z",
            model_used="test",
            findings=[], errors=[],
            summary=AnalysisSummary(total_findings=0, by_severity={}, key_findings=[]),
        )

        # Hierarchy should be untouched
        assert "hierarchy" in results.analyses
        assert len(results.analyses["hierarchy"].findings) == 2
        assert results.analyses["hierarchy"].findings[0].title == "Loan Agreement controls Guaranty"
