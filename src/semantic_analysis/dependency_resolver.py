"""Analysis dependency DAG and execution order resolver."""

from __future__ import annotations

from src.semantic_analysis.schemas import ANALYSIS_TYPES

HARD_DEPENDENCIES: dict[str, list[str]] = {
    "hierarchy": [],
    "conflicts": ["hierarchy"],
    "defined_terms": [],
    "conditions_precedent": [],
    "execution_sequence": ["conditions_precedent"],
}

SOFT_DEPENDENCIES: dict[str, list[str]] = {
    "conflicts": ["defined_terms"],
}


def resolve_execution_order(selected: list[str]) -> list[list[str]]:
    """Return execution batches. Analyses in the same batch can run in parallel.

    1. Validate names
    2. Auto-include missing hard prerequisites (transitively)
    3. Build dependency graph (hard always, soft only when both endpoints present)
    4. Topological sort with Kahn's algorithm
    5. Group by topological depth into parallel batches
    """
    if not selected:
        return []

    # Validate
    unique = set(selected)
    invalid = unique - ANALYSIS_TYPES
    if invalid:
        raise ValueError(
            f"Unknown analysis types: {sorted(invalid)}. "
            f"Valid types: {sorted(ANALYSIS_TYPES)}"
        )

    # Expand hard prerequisites transitively
    expanded = set(unique)
    changed = True
    while changed:
        changed = False
        for analysis in list(expanded):
            for dep in HARD_DEPENDENCIES.get(analysis, []):
                if dep not in expanded:
                    expanded.add(dep)
                    changed = True

    # Build adjacency: dep -> analysis (dep must come before analysis)
    in_degree: dict[str, int] = {a: 0 for a in expanded}
    dependents: dict[str, list[str]] = {a: [] for a in expanded}

    for analysis in expanded:
        # Hard dependencies
        for dep in HARD_DEPENDENCIES.get(analysis, []):
            if dep in expanded:
                in_degree[analysis] += 1
                dependents[dep].append(analysis)

        # Soft dependencies (only if both endpoints in expanded set)
        for dep in SOFT_DEPENDENCIES.get(analysis, []):
            if dep in expanded:
                in_degree[analysis] += 1
                dependents[dep].append(analysis)

    # Kahn's algorithm with batching
    batches: list[list[str]] = []
    remaining = dict(in_degree)

    while remaining:
        # Collect all nodes with in-degree 0
        batch = sorted(a for a, deg in remaining.items() if deg == 0)
        if not batch:
            # Cycle detected (shouldn't happen with our DAG)
            raise ValueError(f"Cycle in dependency graph involving: {sorted(remaining.keys())}")

        batches.append(batch)

        # Remove batch from graph, reduce in-degrees
        for node in batch:
            del remaining[node]
            for dependent in dependents.get(node, []):
                if dependent in remaining:
                    remaining[dependent] -= 1

    return batches
