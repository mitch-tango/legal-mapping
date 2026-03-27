"""Conditions precedent chain mapping — DAG, critical path, cycle detection."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from src.semantic_analysis.id_generation import generate_finding_id
from src.semantic_analysis.schemas import (
    AffectedEntity,
    AnalysisResult,
    AnalysisSummary,
    Finding,
)


def extract_conditions(graph: dict) -> list[dict]:
    """Extract all CP entities from the deal graph."""
    conditions = []
    for cp in graph.get("conditions_precedent", []):
        conditions.append({
            "id": cp["id"],
            "description": cp.get("description", ""),
            "source_document_id": cp.get("source_document_id", ""),
            "required_document_id": cp.get("required_document_id"),
            "enables_document_id": cp.get("enables_document_id"),
            "status": cp.get("status", "pending"),
        })
    return conditions


def build_cp_dag(conditions: list[dict], graph: dict) -> tuple[dict, list[Finding]]:
    """Build directed graph of CP dependencies.

    Returns (adjacency_dict, cycle_findings).
    adjacency_dict: {cp_id: [list of cp_ids this depends on]}
    """
    doc_ids = set(graph.get("documents", {}).keys())
    adj: dict[str, list[str]] = {c["id"]: [] for c in conditions}
    findings: list[Finding] = []

    # Build a map: document_id -> list of CP ids that require that document
    doc_to_cps: dict[str, list[str]] = defaultdict(list)
    for c in conditions:
        if c.get("required_document_id"):
            doc_to_cps[c["required_document_id"]].append(c["id"])

    # Build a map: document_id -> list of CP ids that enable that document
    doc_enables: dict[str, list[str]] = defaultdict(list)
    for c in conditions:
        if c.get("enables_document_id"):
            doc_enables[c["enables_document_id"]].append(c["id"])

    # Infer edges: if CP-A enables doc-X, and CP-B requires doc-X, then CP-B depends on CP-A
    for c in conditions:
        if c.get("required_document_id"):
            req_doc = c["required_document_id"]
            # Find CPs that enable this required document
            for enabler_cp_id in doc_enables.get(req_doc, []):
                if enabler_cp_id != c["id"] and enabler_cp_id in adj:
                    adj[c["id"]].append(enabler_cp_id)

    # Check for missing documents
    for c in conditions:
        for doc_field in ["required_document_id", "enables_document_id"]:
            ref_doc = c.get(doc_field)
            if ref_doc and ref_doc not in doc_ids:
                findings.append(Finding(
                    id=generate_finding_id("conditions_precedent", "missing_condition_document",
                                           [c["id"], ref_doc]),
                    display_ordinal=0, severity="WARNING",
                    category="missing_condition_document",
                    title=f"Missing document referenced by condition",
                    description=f'Condition "{c["description"]}" references document {ref_doc} '
                                f"which is not in the deal set.",
                    affected_entities=[
                        AffectedEntity(entity_type="condition", entity_id=c["id"],
                                       document_id=c["source_document_id"]),
                    ],
                    confidence="high", source="explicit", verified=True,
                ))

    return adj, findings


def _detect_cycles(adj: dict[str, list[str]]) -> list[list[str]]:
    """Detect cycles in the DAG using DFS. Returns list of cycles."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in adj}
    parent: dict[str, str | None] = {n: None for n in adj}
    cycles: list[list[str]] = []

    def dfs(node):
        color[node] = GRAY
        for neighbor in adj.get(node, []):
            if neighbor not in color:
                continue
            if color[neighbor] == GRAY:
                # Found cycle — reconstruct
                cycle = [neighbor, node]
                current = node
                while parent.get(current) and parent[current] != neighbor:
                    current = parent[current]
                    cycle.append(current)
                cycles.append(cycle)
            elif color[neighbor] == WHITE:
                parent[neighbor] = node
                dfs(neighbor)
        color[node] = BLACK

    for node in adj:
        if color[node] == WHITE:
            dfs(node)

    return cycles


def topological_levels(adj: dict[str, list[str]]) -> list[list[str]]:
    """Return CPs grouped into parallel satisfaction levels using Kahn's algorithm."""
    nodes = set(adj.keys())
    in_degree = {n: 0 for n in nodes}
    for n, deps in adj.items():
        for dep in deps:
            if dep in nodes:
                in_degree[n] = in_degree.get(n, 0)  # ensure exists

    # Recount properly: edges go from dependency -> dependent
    in_degree = {n: 0 for n in nodes}
    for n, deps in adj.items():
        in_degree[n] += len([d for d in deps if d in nodes])

    levels = []
    remaining = dict(in_degree)

    while remaining:
        level = sorted(n for n, deg in remaining.items() if deg == 0)
        if not level:
            # Cycle — break remaining nodes
            break
        levels.append(level)
        for n in level:
            del remaining[n]
            # Find nodes that depend on n (n is in their adj list)
            for other, deps in adj.items():
                if other in remaining and n in deps:
                    remaining[other] -= 1

    return levels


def find_critical_path(adj: dict[str, list[str]], levels: list[list[str]]) -> list[str]:
    """Return the longest dependency chain (list of condition IDs)."""
    if not levels:
        return []

    # Build reverse adj (dependents of each node)
    all_nodes = {n for level in levels for n in level}
    reverse_adj: dict[str, list[str]] = {n: [] for n in all_nodes}
    for n, deps in adj.items():
        if n in all_nodes:
            for dep in deps:
                if dep in all_nodes:
                    reverse_adj[dep].append(n)

    # Find longest path using dynamic programming on topological order
    dist: dict[str, int] = {n: 0 for n in all_nodes}
    predecessor: dict[str, str | None] = {n: None for n in all_nodes}

    for level in levels:
        for node in level:
            for dependent in reverse_adj.get(node, []):
                if dist[node] + 1 > dist[dependent]:
                    dist[dependent] = dist[node] + 1
                    predecessor[dependent] = node

    # Find the node with maximum distance
    if not dist:
        return []
    end_node = max(dist, key=dist.get)

    # Reconstruct path
    path = []
    current = end_node
    while current is not None:
        path.append(current)
        current = predecessor[current]
    path.reverse()
    return path


def run_conditions_precedent_analysis(graph: dict) -> AnalysisResult:
    """Main entry point: extract, build DAG, sort, find critical path."""
    all_findings: list[Finding] = []

    conditions = extract_conditions(graph)
    if not conditions:
        return AnalysisResult(
            analysis_type="conditions_precedent",
            status="completed", completion="complete",
            run_timestamp=datetime.now(timezone.utc).isoformat(),
            model_used="graph-analysis",
            findings=[], errors=[],
            summary=AnalysisSummary(total_findings=0, by_severity={}, key_findings=[]),
        )

    adj, dag_findings = build_cp_dag(conditions, graph)
    all_findings.extend(dag_findings)

    # Cycle detection
    cycles = _detect_cycles(adj)
    cycle_nodes = set()
    for cycle in cycles:
        cycle_ids = sorted(set(cycle))
        cycle_nodes.update(cycle_ids)
        descs = {c["id"]: c["description"] for c in conditions}
        chain = " -> ".join(descs.get(cid, cid) for cid in cycle)

        all_findings.append(Finding(
            id=generate_finding_id("conditions_precedent", "circular_condition", cycle_ids),
            display_ordinal=0, severity="CRITICAL",
            category="circular_condition",
            title="Circular condition dependency detected",
            description=f"Circular dependency chain: {chain}. "
                        f"Consider removing one dependency to break the cycle.",
            affected_entities=[
                AffectedEntity(entity_type="condition", entity_id=cid,
                               document_id=next((c["source_document_id"] for c in conditions if c["id"] == cid), ""))
                for cid in cycle_ids
            ],
            confidence="high", source="explicit", verified=True,
        ))

    # Remove cycle nodes from DAG for topological sort
    clean_adj = {
        n: [d for d in deps if d not in cycle_nodes]
        for n, deps in adj.items() if n not in cycle_nodes
    }

    levels = topological_levels(clean_adj)

    # Parallel group findings
    for i, level in enumerate(levels):
        if len(level) > 1:
            all_findings.append(Finding(
                id=generate_finding_id("conditions_precedent", "parallel_group",
                                       sorted(level)),
                display_ordinal=0, severity="INFO", category="parallel_group",
                title=f"Parallel satisfaction group (level {i})",
                description=f"{len(level)} conditions can be satisfied simultaneously: "
                            + ", ".join(level),
                affected_entities=[
                    AffectedEntity(entity_type="condition", entity_id=cid,
                                   document_id=next((c["source_document_id"] for c in conditions if c["id"] == cid), ""))
                    for cid in level
                ],
                confidence="high", source="explicit", verified=True,
            ))

    # Critical path
    crit_path = find_critical_path(clean_adj, levels)
    for cid in crit_path:
        all_findings.append(Finding(
            id=generate_finding_id("conditions_precedent", "critical_path_item", [cid]),
            display_ordinal=0, severity="INFO", category="critical_path_item",
            title=f"Critical path: {next((c['description'] for c in conditions if c['id'] == cid), cid)}",
            description=f"This condition is on the critical path (longest dependency chain of {len(crit_path)} steps).",
            affected_entities=[
                AffectedEntity(entity_type="condition", entity_id=cid,
                               document_id=next((c["source_document_id"] for c in conditions if c["id"] == cid), "")),
            ],
            confidence="high", source="explicit", verified=True,
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
        analysis_type="conditions_precedent",
        status="completed", completion="complete",
        run_timestamp=datetime.now(timezone.utc).isoformat(),
        model_used="graph-analysis",
        findings=unique, errors=[],
        summary=AnalysisSummary(
            total_findings=len(unique), by_severity=by_severity,
            key_findings=[f.title for f in unique[:5]],
        ),
    )
