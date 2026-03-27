"""Execution sequence derivation — closing checklist ordering."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from src.semantic_analysis.id_generation import generate_finding_id
from src.semantic_analysis.schemas import (
    AffectedEntity,
    AnalysisResult,
    AnalysisResults,
    AnalysisSummary,
    Finding,
)

# Relationship types that imply signing order
_SIGNING_ORDER_TYPES = {"guarantees", "secures", "subordinates_to"}


def extract_signing_dependencies(graph_data: dict) -> list[tuple[str, str]]:
    """Extract (must_sign_first, then_sign) pairs from graph relationships."""
    deps = []
    for rel in graph_data.get("relationships", []):
        rel_type = rel.get("relationship_type", "")
        if rel_type in _SIGNING_ORDER_TYPES:
            # Target must be signed before source
            # e.g., Guaranty guarantees Loan Agreement -> Loan Agreement first
            deps.append((rel["target_document_id"], rel["source_document_id"]))
    return deps


def extract_crossref_dependencies(graph_data: dict) -> list[tuple[str, str]]:
    """Extract (finalize_first, incorporating_doc) pairs from incorporates relationships."""
    deps = []
    for rel in graph_data.get("relationships", []):
        if rel.get("relationship_type") == "incorporates":
            # Source incorporates target -> target must be finalized first
            deps.append((rel["target_document_id"], rel["source_document_id"]))
    return deps


def extract_delivery_dependencies(cp_findings: list[Finding]) -> list[tuple[str, str]]:
    """Extract delivery-before-execution constraints from CP findings."""
    deps = []
    for f in cp_findings:
        if "delivery" in f.description.lower():
            doc_ids = [e.entity_id for e in f.affected_entities if e.entity_type == "document"]
            if len(doc_ids) >= 2:
                deps.append((doc_ids[0], doc_ids[1]))
    return deps


def _build_doc_dag(
    all_doc_ids: set[str],
    signing_deps: list[tuple[str, str]],
    crossref_deps: list[tuple[str, str]],
    delivery_deps: list[tuple[str, str]],
) -> dict[str, set[str]]:
    """Build combined dependency DAG: doc_id -> set of docs that must come first."""
    deps: dict[str, set[str]] = {d: set() for d in all_doc_ids}
    for first, then in signing_deps + crossref_deps + delivery_deps:
        if first in all_doc_ids and then in all_doc_ids:
            deps[then].add(first)
    return deps


def _topological_sort_docs(deps: dict[str, set[str]]) -> list[list[str]]:
    """Topological sort documents into parallel execution windows."""
    remaining = {d: set(prereqs) for d, prereqs in deps.items()}
    levels = []

    while remaining:
        level = sorted(d for d, prereqs in remaining.items()
                       if not prereqs.intersection(remaining.keys()) or not prereqs)
        # More precise: nodes whose remaining prerequisites have all been placed
        level = sorted(d for d, prereqs in remaining.items()
                       if all(p not in remaining for p in prereqs))
        if not level:
            # Cycle — break by taking arbitrary node
            level = [sorted(remaining.keys())[0]]
        levels.append(level)
        for d in level:
            del remaining[d]

    return levels


def _find_critical_path(levels: list[list[str]], deps: dict[str, set[str]]) -> list[str]:
    """Find the longest sequential chain through the execution DAG."""
    if not levels:
        return []

    all_docs = {d for level in levels for d in level}
    # Build forward adjacency
    fwd: dict[str, list[str]] = defaultdict(list)
    for doc, prereqs in deps.items():
        if doc in all_docs:
            for p in prereqs:
                if p in all_docs:
                    fwd[p].append(doc)

    # Longest path via DP
    dist: dict[str, int] = {d: 0 for d in all_docs}
    pred: dict[str, str | None] = {d: None for d in all_docs}

    for level in levels:
        for doc in level:
            for dependent in fwd.get(doc, []):
                if dist[doc] + 1 > dist[dependent]:
                    dist[dependent] = dist[doc] + 1
                    pred[dependent] = doc

    if not dist:
        return []
    end = max(dist, key=dist.get)
    path = []
    current = end
    while current is not None:
        path.append(current)
        current = pred[current]
    path.reverse()
    return path


def run_execution_sequence_analysis(
    graph_data: dict,
    existing_results: AnalysisResults | None = None,
    client=None,
) -> AnalysisResult:
    """Derive execution sequence from CP results + signing/delivery/xref dependencies.

    Raises ValueError if conditions_precedent analysis is not present.
    """
    # Validate CP prerequisite
    cp_result = None
    if existing_results and "conditions_precedent" in existing_results.analyses:
        cp_result = existing_results.analyses["conditions_precedent"]
    else:
        raise ValueError(
            "Execution sequence analysis requires conditions_precedent analysis to be run first. "
            "Run conditions_precedent analysis before execution_sequence."
        )

    all_findings: list[Finding] = []
    documents = graph_data.get("documents", {})
    doc_ids = set(documents.keys())

    # Extract all dependency types
    signing_deps = extract_signing_dependencies(graph_data)
    crossref_deps = extract_crossref_dependencies(graph_data)
    delivery_deps = extract_delivery_dependencies(cp_result.findings if cp_result else [])

    # Generate signing dependency findings
    for first, then in signing_deps:
        if first in doc_ids and then in doc_ids:
            first_name = documents[first].get("name", first)
            then_name = documents[then].get("name", then)
            all_findings.append(Finding(
                id=generate_finding_id("execution_sequence", "signing_dependency",
                                       [first, then]),
                display_ordinal=0, severity="INFO",
                category="signing_dependency",
                title=f"{first_name} must be signed before {then_name}",
                description=f"{first_name} must be signed before {then_name} based on "
                            f"their relationship in the deal structure.",
                affected_entities=[
                    AffectedEntity(entity_type="document", entity_id=first, document_id=first),
                    AffectedEntity(entity_type="document", entity_id=then, document_id=then),
                ],
                confidence="high", source="explicit", verified=True,
            ))

    # Build DAG and sort
    deps = _build_doc_dag(doc_ids, signing_deps, crossref_deps, delivery_deps)
    levels = _topological_sort_docs(deps)

    # Parallel execution window findings
    for i, level in enumerate(levels):
        if len(level) > 1:
            doc_names = [documents.get(d, {}).get("name", d) for d in level]
            all_findings.append(Finding(
                id=generate_finding_id("execution_sequence", "parallel_execution_window",
                                       sorted(level)),
                display_ordinal=0, severity="INFO",
                category="parallel_execution_window",
                title=f"Parallel execution window (step {i + 1})",
                description=f"These documents can be executed simultaneously: "
                            + ", ".join(doc_names),
                affected_entities=[
                    AffectedEntity(entity_type="document", entity_id=d, document_id=d)
                    for d in level
                ],
                confidence="high", source="inferred", verified=True,
            ))

    # Gating conditions per step
    for i, level in enumerate(levels):
        gating = []
        for doc_id in level:
            for prereq in deps.get(doc_id, set()):
                prereq_name = documents.get(prereq, {}).get("name", prereq)
                gating.append(f"Execution of {prereq_name}")

        if gating:
            all_findings.append(Finding(
                id=generate_finding_id("execution_sequence", "gating_condition",
                                       sorted(level) + [f"step-{i}"]),
                display_ordinal=0, severity="INFO",
                category="gating_condition",
                title=f"Gating conditions for step {i + 1}",
                description=f"Prerequisites: {'; '.join(sorted(set(gating)))}",
                affected_entities=[
                    AffectedEntity(entity_type="document", entity_id=d, document_id=d)
                    for d in level
                ],
                confidence="high", source="explicit", verified=True,
            ))

    # Critical path
    crit_path = _find_critical_path(levels, deps)
    for doc_id in crit_path:
        doc_name = documents.get(doc_id, {}).get("name", doc_id)
        all_findings.append(Finding(
            id=generate_finding_id("execution_sequence", "critical_path_step", [doc_id]),
            display_ordinal=0, severity="WARNING",
            category="critical_path_step",
            title=f"Critical path: {doc_name}",
            description=f"{doc_name} is on the critical execution path "
                        f"({len(crit_path)} steps total).",
            affected_entities=[
                AffectedEntity(entity_type="document", entity_id=doc_id, document_id=doc_id),
            ],
            confidence="high", source="inferred", verified=True,
        ))

    # Deduplicate and assign ordinals
    seen = set()
    unique = []
    for f in all_findings:
        if f.id not in seen:
            seen.add(f.id)
            unique.append(f)
    for i, f in enumerate(unique, 1):
        f.display_ordinal = i

    by_severity: dict[str, int] = {}
    for f in unique:
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1

    return AnalysisResult(
        analysis_type="execution_sequence",
        status="completed", completion="complete",
        run_timestamp=datetime.now(timezone.utc).isoformat(),
        model_used="graph-analysis",
        findings=unique, errors=[],
        summary=AnalysisSummary(
            total_findings=len(unique), by_severity=by_severity,
            key_findings=[f.title for f in unique[:5]],
        ),
    )
