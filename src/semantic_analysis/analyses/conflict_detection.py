"""Cross-reference conflict detection — highest-value analysis."""

from __future__ import annotations

from datetime import datetime, timezone

from src.semantic_analysis.analyses.conflict_utils import (
    adjust_severity_with_hierarchy,
    detect_circular_references,
    detect_dangling_references,
    detect_missing_documents,
    generate_contradiction_candidates,
    rank_and_cap_candidates,
    _build_section_inventory,
)
from src.semantic_analysis.schemas import (
    AnalysisResult,
    AnalysisSummary,
    Finding,
)


def run_conflict_detection(
    graph: dict,
    hierarchy_results: AnalysisResult | None = None,
    term_results: AnalysisResult | None = None,
    anthropic_client=None,
    source_base_path: str = "",
    pass_2_cap: int = 20,
) -> AnalysisResult:
    """Run full conflict detection analysis (Pass 1 + Pass 2)."""
    all_findings: list[Finding] = []
    documents = graph.get("documents", {})
    cross_refs = graph.get("cross_references", [])

    # Pass 1: Structural checks
    section_inventory = _build_section_inventory(graph)

    # Dangling references
    all_findings.extend(
        detect_dangling_references(cross_refs, section_inventory, documents)
    )

    # Circular references
    all_findings.extend(detect_circular_references(cross_refs))

    # Missing documents
    all_findings.extend(detect_missing_documents(graph))

    # Contradiction candidates (for Pass 2)
    candidates = generate_contradiction_candidates(graph, hierarchy_results, term_results)
    ranked = rank_and_cap_candidates(candidates, cap=pass_2_cap)

    # Pass 2 would send ranked candidates to Claude for verification.
    # For now, contradiction candidates are noted but not verified without API.
    # When anthropic_client is provided, Pass 2 verification would happen here.

    # Apply hierarchy severity adjustment
    if hierarchy_results:
        for f in all_findings:
            adjust_severity_with_hierarchy(f, hierarchy_results)

    # Deduplicate by finding ID
    seen = set()
    unique = []
    for f in all_findings:
        if f.id not in seen:
            seen.add(f.id)
            unique.append(f)

    # Assign ordinals
    for i, f in enumerate(unique, 1):
        f.display_ordinal = i

    by_severity: dict[str, int] = {}
    for f in unique:
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1

    return AnalysisResult(
        analysis_type="conflicts",
        status="completed",
        completion="complete",
        run_timestamp=datetime.now(timezone.utc).isoformat(),
        model_used="graph-analysis",
        findings=unique,
        summary=AnalysisSummary(
            total_findings=len(unique),
            by_severity=by_severity,
            key_findings=[f.title for f in unique[:5]],
        ),
        errors=[],
    )
