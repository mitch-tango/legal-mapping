# Section 03: Staleness Tracking

## Overview

This section implements staleness detection for the semantic analysis engine. When the user modifies `deal-graph.json` (via Split 01 tools or manual edit), the staleness system detects which analyses are out of date by comparing canonical graph hashes and applying change-type-specific rules that map graph modifications to affected analyses.

The staleness system has three responsibilities:

1. **Hash comparison** -- compare the current canonical graph hash against the per-analysis stored hash in `deal-analysis.json`
2. **Rules engine** -- determine which specific analyses are stale based on the type of graph change (not just "something changed")
3. **Staleness reporting** -- present staleness status to the user before any analysis execution

The system never auto-re-runs analyses. The user decides when to re-run.

## Dependencies

- **section-01-schema-and-fixtures**: Provides the `StalenessRecord` Pydantic model, `AnalysisResults` top-level schema, shared pytest fixtures (`minimal_deal_graph`, `medium_deal_graph`, `mock_anthropic_client`), and content-derived stable ID generation.
- **section-02-graph-utilities**: Provides `load_graph()`, `canonicalize_graph()` (deep sort all object keys and arrays by a stable key), and `compute_graph_hash()` (SHA-256 of the canonicalized JSON).

## File Paths

- **Implementation**: `src/semantic_analysis/staleness.py`
- **Tests**: `tests/test_staleness.py`

## Tests (Write First)

All tests go in `tests/test_staleness.py`. Write these test stubs before implementing.

```python
"""Tests for staleness tracking.

Depends on fixtures from conftest.py (section-01):
- minimal_deal_graph: 3-doc graph with known relationships, terms, cross-refs, CPs
- medium_deal_graph: 10-doc graph covering all entity types

Depends on utilities from section-02:
- canonicalize_graph, compute_graph_hash
"""
import pytest


# --- Hash-based staleness detection ---

# Test: fresh_analysis_not_stale
# Setup: create an AnalysisResults where hierarchy's graph_hash_at_run matches
#   the current graph hash. Assert is_stale is False.

# Test: stale_after_graph_change
# Setup: create AnalysisResults with a hash, then modify the graph (add a field),
#   recompute hash. Assert is_stale is True and stale_reason is populated.

# --- Staleness rules engine: which change types affect which analyses ---

ALL_ANALYSES = [
    "hierarchy", "conflicts", "defined_terms",
    "conditions_precedent", "execution_sequence",
]

# Test: document_added_stales_all
# Given a graph diff where a document was added, assert all 5 analyses are
#   marked stale.

# Test: relationship_change_stales_hierarchy_and_conflicts
# Given a graph diff where a relationship was modified, assert only
#   "hierarchy" and "conflicts" are marked stale. Other 3 remain fresh.

# Test: term_change_stales_defined_terms_only
# Given a graph diff where a defined_term was added/modified/removed,
#   assert only "defined_terms" is marked stale.

# Test: crossref_change_stales_conflicts_only
# Given a graph diff where a cross_reference was changed, assert only
#   "conflicts" is marked stale.

# Test: cp_change_stales_cp_and_execution_sequence
# Given a graph diff where a condition_precedent was changed, assert
#   "conditions_precedent" and "execution_sequence" are marked stale.

# Test: party_change_stales_exec_cp_terms
# Given a graph diff where a party was modified, assert
#   "execution_sequence", "conditions_precedent", and "defined_terms"
#   are marked stale. "hierarchy" and "conflicts" remain fresh.

# Test: annotation_change_stales_nothing
# Given a graph diff where only annotations changed, assert no analyses
#   are marked stale.

# --- Canonicalization stability (integration with section-02 utilities) ---

# Test: canonicalization_produces_stable_hash
# Create two graph dicts that are semantically identical but have arrays
#   in different orders. Assert compute_graph_hash returns the same value
#   for both.

# Test: canonicalization_different_data_different_hash
# Create two graph dicts with different content. Assert their hashes differ.
```

## Implementation Details

### The Five Analysis Types

The staleness system tracks these five analysis types (matching the analysis dependency graph from section-04):

- `hierarchy` -- Document hierarchy analysis
- `conflicts` -- Cross-reference conflict detection
- `defined_terms` -- Defined term tracking
- `conditions_precedent` -- Conditions precedent chain mapping
- `execution_sequence` -- Execution sequence derivation

### Staleness Rules Table

The rules engine maps graph change types to affected analyses:

| Graph Change | Analyses Marked Stale |
|---|---|
| Document added or removed | All five analyses |
| Relationship added/modified/removed | `hierarchy`, `conflicts` |
| Defined term added/modified/removed | `defined_terms` |
| Cross-reference added/modified/removed | `conflicts` |
| Condition precedent added/modified/removed | `conditions_precedent`, `execution_sequence` |
| Party modified | `execution_sequence`, `conditions_precedent`, `defined_terms` |
| Annotation modified | None (annotations are user-owned) |

### Core Functions

```python
"""Staleness tracking for semantic analysis results.

Compares graph state against stored analysis hashes and applies
change-type-specific rules to determine which analyses need re-running.
"""

STALENESS_RULES: dict[str, list[str]] = {
    "documents": ALL_ANALYSES,
    "relationships": ["hierarchy", "conflicts"],
    "defined_terms": ["defined_terms"],
    "cross_references": ["conflicts"],
    "conditions_precedent": ["conditions_precedent", "execution_sequence"],
    "parties": ["execution_sequence", "conditions_precedent", "defined_terms"],
    "annotations": [],
}

ALL_ANALYSES = [
    "hierarchy", "conflicts", "defined_terms",
    "conditions_precedent", "execution_sequence",
]


def check_staleness(
    current_graph: dict,
    analysis_results: "AnalysisResults | None",
) -> dict[str, "StalenessRecord"]:
    """Check which analyses are stale given the current graph state.

    Returns a dict mapping analysis type names to StalenessRecord objects.
    If analysis_results is None (no prior results), all analyses are stale.
    """
    ...


def detect_graph_changes(
    old_graph: dict,
    new_graph: dict,
) -> set[str]:
    """Compare two canonicalized graphs and return the set of change types.

    Returns a subset of STALENESS_RULES keys indicating which parts of
    the graph changed (e.g., {"documents", "relationships"}).

    Compares top-level sections of the graph independently so the rules
    engine can do targeted staleness marking rather than marking everything
    stale on any change.
    """
    ...


def apply_staleness_rules(
    change_types: set[str],
) -> set[str]:
    """Given a set of graph change types, return the set of analysis names
    that should be marked stale.

    Unions the affected analyses across all change types.
    """
    ...


def format_staleness_report(
    staleness: dict[str, "StalenessRecord"],
) -> str:
    """Format staleness status for user display.

    Shows which analyses are current, which are stale, and why.
    Called by the workflow orchestration (section-10) before execution.
    """
    ...
```

### Staleness Check Workflow

The full staleness check, performed before any analysis execution, follows this sequence:

1. Load current `deal-graph.json` using `load_graph()` from section-02
2. Canonicalize the graph using `canonicalize_graph()` from section-02 and compute its SHA-256 hash using `compute_graph_hash()` from section-02
3. Load `deal-analysis.json` if it exists and parse it into `AnalysisResults` (section-01 schema)
4. For each analysis in `analysis_results.staleness`:
   - If `graph_hash_at_run` matches the current hash, the analysis is **current**
   - If hashes differ, call `detect_graph_changes()` to determine what changed, then `apply_staleness_rules()` to determine which analyses are stale with a specific reason
5. Return staleness records and format them for user display via `format_staleness_report()`

### Graph Change Detection Strategy

The `detect_graph_changes` function works by comparing specific top-level sections of the canonicalized graph independently. For each key in `STALENESS_RULES` (documents, relationships, defined_terms, cross_references, conditions_precedent, parties, annotations), it hashes or compares that sub-section of the old and new graph. If a sub-section differs, its key is added to the change set.

This approach enables targeted staleness marking. For example, if only a defined term changed, only `defined_terms` analysis is marked stale -- not all five analyses. When the overall hash differs but sub-section comparison is not possible (e.g., the graph structure changed in unexpected ways), fall back to marking all analyses stale.

### Stale Reason Strings

When an analysis is marked stale, the `stale_reason` field should be human-readable and specific. Examples:

- `"document added or removed"` -- when the documents section changed
- `"relationship modified"` -- when relationships changed
- `"defined term changed"` -- when defined_terms section changed
- `"cross-reference modified"` -- when cross_references changed
- `"condition precedent changed"` -- when conditions_precedent changed
- `"party modified"` -- when parties changed
- `"multiple changes: documents, relationships"` -- when multiple sections changed

### Edge Cases

- **No prior `deal-analysis.json`**: All analyses are stale with reason `"no prior analysis results"`.
- **Analysis present in results but missing staleness record**: Treat as stale with reason `"missing staleness record"`.
- **Graph hash matches but specific sub-section comparison is unavailable**: If the overall hash matches, the analysis is current regardless of sub-section availability.
- **Empty graph**: Valid state; hash is computed on the empty canonical form. If the graph was previously non-empty, all analyses are stale.
