# Section 04: Dependency Resolver

## Overview

This section implements the analysis dependency DAG and execution order resolver. The system maintains a registry of five analyses (hierarchy, conflicts, defined_terms, conditions_precedent, execution_sequence) with hard and soft dependencies between them. When the user selects which analyses to run, the resolver automatically includes missing prerequisites, performs a topological sort, and groups independent analyses into parallel execution batches.

This module is consumed by the workflow orchestrator (section-10) to determine the order in which analyses execute.

## Dependencies

- **section-01-schema-and-fixtures**: Pydantic models and shared test fixtures must exist
- **section-02-graph-utilities**: Graph loading utilities must exist (though this section does not directly use them, it shares the same project structure)

## File Locations

- **Implementation**: `src/semantic_analysis/dependency_resolver.py`
- **Tests**: `tests/test_dependency_resolver.py`

## Tests (Write First)

All tests go in `tests/test_dependency_resolver.py`. The tests validate the `resolve_execution_order` function and its supporting logic.

```python
"""Tests for analysis dependency resolution and execution ordering."""
import pytest
from semantic_analysis.dependency_resolver import resolve_execution_order


class TestResolveExecutionOrder:
    """Test the resolve_execution_order function."""

    def test_resolve_order_single_standalone(self):
        """Selecting 'hierarchy' (no deps) returns [['hierarchy']]."""

    def test_resolve_order_with_hard_dependency(self):
        """Selecting 'conflicts' returns [['hierarchy'], ['conflicts']] because
        conflicts has a hard dependency on hierarchy."""

    def test_resolve_order_with_chain(self):
        """Selecting 'execution_sequence' returns
        [['conditions_precedent'], ['execution_sequence']] because
        execution_sequence hard-depends on conditions_precedent."""

    def test_resolve_order_all(self):
        """Selecting all five analyses returns correct batches with
        parallelizable groups. Expected shape:
        Batch 0: ['hierarchy', 'defined_terms', 'conditions_precedent'] (all standalone)
        Batch 1: ['conflicts', 'execution_sequence'] (both depend on batch 0 items)
        """

    def test_resolve_order_includes_missing_prerequisites(self):
        """Selecting only 'conflicts' auto-adds 'hierarchy' even though
        the user did not request it."""

    def test_soft_dependency_included_when_available(self):
        """If 'defined_terms' is in the selected set (or already completed),
        'conflicts' should be scheduled after it to use enrichment data."""

    def test_soft_dependency_skipped_when_unavailable(self):
        """If 'defined_terms' is NOT selected and NOT already completed,
        'conflicts' proceeds without it (no error, no auto-add)."""

    def test_resolve_order_no_duplicates(self):
        """Selecting ['hierarchy', 'conflicts'] does not run hierarchy twice.
        hierarchy appears exactly once across all batches."""
```

## Implementation Details

### Dependency Registry

The module defines two constant dictionaries that encode the dependency relationships between analyses.

`HARD_DEPENDENCIES` maps each analysis to the list of analyses that **must** run before it. If a user selects an analysis but not its hard dependencies, the resolver auto-includes the missing prerequisites.

```python
HARD_DEPENDENCIES: dict[str, list[str]] = {
    "hierarchy": [],
    "conflicts": ["hierarchy"],
    "defined_terms": [],
    "conditions_precedent": [],
    "execution_sequence": ["conditions_precedent"],
}
```

`SOFT_DEPENDENCIES` maps each analysis to analyses that **improve** its results but are not required. Soft dependencies are never auto-included. They only affect scheduling order when they happen to be in the selected set already.

```python
SOFT_DEPENDENCIES: dict[str, list[str]] = {
    "conflicts": ["defined_terms"],
}
```

All five valid analysis names are: `hierarchy`, `conflicts`, `defined_terms`, `conditions_precedent`, `execution_sequence`.

### The `resolve_execution_order` Function

```python
def resolve_execution_order(selected: list[str]) -> list[list[str]]:
    """Return execution batches. Analyses in the same batch can run in parallel.

    Steps:
    1. Validate that all names in 'selected' are recognized analysis types.
    2. Auto-include missing hard prerequisites (transitively).
    3. Build a combined dependency graph using hard deps (always) and soft deps
       (only when the soft dependency target is also in the expanded selected set).
    4. Topological sort the expanded set using Kahn's algorithm.
    5. Group analyses with the same topological depth into parallel batches.
    6. Return the list of batches in execution order.

    Raises ValueError if 'selected' contains an unrecognized analysis name.
    """
```

### Algorithm: Prerequisite Expansion

Starting from the user-selected set, repeatedly check each analysis's hard dependencies. If any hard dependency is not in the set, add it. Repeat until no new additions are made. This handles transitive dependencies (though currently the dependency graph has max depth 1, the algorithm should be general).

### Algorithm: Topological Sort with Parallel Batching

Use Kahn's algorithm (BFS-based topological sort) which naturally produces "levels":

1. Compute in-degree for each analysis in the expanded set (counting only edges where both endpoints are in the set).
2. For hard dependencies, always count the edge. For soft dependencies, count the edge only if the soft dependency target is in the expanded set.
3. All analyses with in-degree 0 form batch 0.
4. Remove batch 0 from the graph, reduce in-degrees, collect new in-degree-0 nodes as batch 1.
5. Repeat until all analyses are batched.

### Soft Dependency Behavior

Soft dependencies affect **scheduling order only**, not prerequisite inclusion:

- If `defined_terms` is in the selected set (either user-selected or because something else required it), then `conflicts` should be scheduled in a batch after `defined_terms` completes, so it can use the enrichment data.
- If `defined_terms` is NOT in the selected set, `conflicts` ignores the soft dependency entirely. It does not auto-add `defined_terms`.

This means the soft dependency edge is conditionally included in the topological sort graph based on whether both endpoints are present.

### Edge Cases

- **Empty selection**: Return an empty list `[]`.
- **Single standalone analysis**: Returns `[["hierarchy"]]` (one batch with one item).
- **Duplicate entries in input**: Deduplicate before processing.
- **Unknown analysis name**: Raise `ValueError` with a message listing valid names.

### Example Outputs

| User Selects | Expanded Set | Batches |
|---|---|---|
| `["hierarchy"]` | `{"hierarchy"}` | `[["hierarchy"]]` |
| `["conflicts"]` | `{"hierarchy", "conflicts"}` | `[["hierarchy"], ["conflicts"]]` |
| `["execution_sequence"]` | `{"conditions_precedent", "execution_sequence"}` | `[["conditions_precedent"], ["execution_sequence"]]` |
| `["conflicts", "defined_terms"]` | `{"hierarchy", "conflicts", "defined_terms"}` | `[["hierarchy", "defined_terms"], ["conflicts"]]` |
| all five | all five | `[["hierarchy", "defined_terms", "conditions_precedent"], ["conflicts", "execution_sequence"]]` |

Note: within a batch, the order of items is not significant (they are parallelizable). Tests should use set comparison for items within the same batch, and list comparison for batch ordering.
