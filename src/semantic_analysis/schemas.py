"""Pydantic models for deal-analysis.json — semantic analysis results."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, model_validator

SCHEMA_VERSION = "1.0.0"

# ── Analysis-Specific Finding Categories ─────────────────────────────────

ANALYSIS_TYPES = frozenset({
    "hierarchy", "conflicts", "defined_terms",
    "conditions_precedent", "execution_sequence",
})

HIERARCHY_CATEGORIES = frozenset({
    "controlling_authority", "dual_authority_conflict",
    "inferred_hierarchy", "explicit_hierarchy",
})

CONFLICTS_CATEGORIES = frozenset({
    "dangling_reference", "circular_reference", "contradictory_provision",
    "missing_document", "stale_reference", "ambiguous_section_ref",
})

DEFINED_TERMS_CATEGORIES = frozenset({
    "conflicting_definition", "orphaned_definition", "undefined_usage",
    "cross_document_dependency", "enhanced_term",
})

CONDITIONS_PRECEDENT_CATEGORIES = frozenset({
    "circular_condition", "critical_path_item",
    "missing_condition_document", "parallel_group",
})

EXECUTION_SEQUENCE_CATEGORIES = frozenset({
    "signing_dependency", "parallel_execution_window",
    "gating_condition", "critical_path_step",
})


# ── Models ───────────────────────────────────────────────────────────────


class AffectedEntity(BaseModel):
    entity_type: str
    entity_id: str
    document_id: str
    section: str | None = None


class Finding(BaseModel):
    id: str
    display_ordinal: int
    severity: Literal["CRITICAL", "ERROR", "WARNING", "INFO"]
    category: str
    title: str
    description: str
    affected_entities: list[AffectedEntity]
    confidence: Literal["high", "medium", "low"]
    source: Literal["explicit", "inferred"]
    verified: bool


class AnalysisSummary(BaseModel):
    total_findings: int
    by_severity: dict[str, int]
    key_findings: list[str]


class AnalysisResult(BaseModel):
    analysis_type: str
    status: Literal["completed", "failed", "partial"]
    completion: Literal["complete", "partial", "failed"]
    run_timestamp: str
    model_used: str
    findings: list[Finding]
    summary: AnalysisSummary
    errors: list[str]

    @model_validator(mode="after")
    def validate_status_completion_consistency(self) -> "AnalysisResult":
        if self.status == "completed" and self.completion != "complete":
            raise ValueError(
                f"When status is 'completed', completion must be 'complete', got '{self.completion}'"
            )
        if self.status == "failed" and self.completion != "failed":
            raise ValueError(
                f"When status is 'failed', completion must be 'failed', got '{self.completion}'"
            )
        if self.status == "failed" and not self.errors:
            raise ValueError(
                "When status is 'failed', errors list must be non-empty"
            )
        return self


class StalenessRecord(BaseModel):
    is_stale: bool
    last_run: str
    stale_reason: str | None = None
    graph_hash_at_run: str


class AnalysisMetadata(BaseModel):
    last_full_analysis: str | None = None
    documents_included: list[str]
    engine_version: str


class AnalysisResults(BaseModel):
    schema_version: str
    deal_graph_hash: str
    analyses: dict[str, AnalysisResult]
    metadata: AnalysisMetadata
    staleness: dict[str, StalenessRecord]
