# Section 08: Conditions Precedent Chain Mapping

## Overview

This section implements the Conditions Precedent (CP) analysis, which maps closing condition dependency chains, identifies the critical path, detects circular conditions, and flags missing document references. This analysis operates as a standalone Pass 1 analysis (no prerequisite analyses required) and its results are consumed by the Execution Sequence analysis (Section 09).

**What this section delivers:**
- CP extraction from the deal graph's `conditions_precedent` entities
- DAG construction with both explicit and inferred CP dependencies
- Topological sort of conditions into parallel satisfaction levels
- Critical path identification (longest dependency chain)
- Cycle detection producing CRITICAL findings
- Missing document CP flagging

**File paths to create:**

| File | Purpose |
|------|---------|
| `src/semantic_analysis/conditions_precedent.py` | CP extraction, DAG building, analysis logic |
| `tests/test_conditions_precedent.py` | All CP analysis tests |

All paths are relative to the project root: `C:\Users\maitl\New City Dropbox\Maitland Thompson\Working\Legal Review\Mapping`.

**Dependencies (reference only, do not duplicate):**
- **Section 01 (Schema and Fixtures):** Pydantic models (`Finding`, `AnalysisResult`, `AffectedEntity`, etc.), shared fixtures (`minimal_deal_graph`, `medium_deal_graph`, `mock_anthropic_client`), stable ID generation
- **Section 02 (Graph Utilities):** Graph loading, section reference normalization

**Blocks:**
- **Section 09 (Execution Sequence):** Requires the CP topological sort and dependency DAG as its baseline

---

## Tests (Write First)

Create `tests/test_conditions_precedent.py` with the following test stubs. Each docstring describes the exact assertion.

```python
"""Tests for Conditions Precedent chain mapping analysis."""
import pytest


class TestConditionExtraction:
    """Tests for reading CP entities from the deal graph."""

    def test_conditions_extracted_from_graph(self, minimal_deal_graph):
        """All ConditionPrecedent entities in the graph are read and
        returned as structured objects. The count of extracted CPs must
        match the count of conditions_precedent entries in the fixture
        graph. Each extracted CP must have: condition_id, description,
        requiring_document, required_action, and dependencies list."""

    def test_missing_document_cp_flagged(self, minimal_deal_graph):
        """When a CP references a document not present in the deal set
        (i.e., the document ID is not among the graph's document nodes),
        a Finding is produced with category 'missing_condition_document'
        and severity WARNING or ERROR. The finding description must name
        the missing document and the condition that references it."""


class TestDAGConstruction:
    """Tests for building the CP dependency DAG."""

    def test_explicit_dependencies_mapped(self, minimal_deal_graph):
        """CP-to-CP dependency edges that exist explicitly in the graph
        (where one CP's dependencies list references another CP's ID)
        appear as edges in the constructed DAG. Verify edge count matches
        the number of explicit dependency relationships in the fixture."""

    def test_implicit_dependencies_inferred(self, medium_deal_graph):
        """When a CP involves delivery of a Guaranty document, and the
        Guaranty has a cross-reference to the Loan Agreement, an implicit
        dependency edge is added: the Loan Agreement finalization CP must
        precede the Guaranty delivery CP. The edge must be marked with
        source='inferred' to distinguish it from explicit edges."""

    def test_circular_condition_critical(self, minimal_deal_graph):
        """When CP A depends on CP B and CP B depends on CP A (directly
        or through a chain), a Finding is produced with category
        'circular_condition', severity CRITICAL, and confidence 'high'.
        The finding's affected_entities must include all CPs in the cycle."""

    def test_circular_condition_describes_resolution(self, minimal_deal_graph):
        """A circular_condition finding's description must include
        actionable guidance on how to resolve the cycle (e.g., suggesting
        which dependency to remove or reorder). The description must not
        be empty or generic."""


class TestTopologicalSort:
    """Tests for ordering CPs into parallel satisfaction levels."""

    def test_topological_sort_valid_order(self, medium_deal_graph):
        """After topological sort, no condition appears at a level before
        any of its prerequisites. For every CP at level N, all CPs it
        depends on must be at level < N."""

    def test_parallel_groups_identified(self, medium_deal_graph):
        """CPs with no mutual dependencies are grouped at the same level.
        Verify that at least one level contains more than one CP (i.e.,
        parallelism is detected, not a purely sequential chain). Each
        group is a Finding with category 'parallel_group'."""


class TestCriticalPath:
    """Tests for identifying the longest dependency chain."""

    def test_critical_path_highlighted(self, medium_deal_graph):
        """The critical path is the longest chain of sequential CP
        dependencies. The analysis must produce Finding objects with
        category 'critical_path_item' for each CP on the critical path.
        The chain length must equal the number of levels in the
        topological sort."""
```

---

## Implementation Details

### Condition Extraction

The entry point reads `conditions_precedent` entities from the loaded deal graph. Each `ConditionPrecedent` entity in the graph contains:
- `condition_id`: unique identifier
- `description`: text description of the condition
- `requiring_document`: document ID that imposes this condition
- `required_action`: what must happen (deliverable, approval, etc.)
- `dependencies`: list of other condition IDs this CP explicitly depends on

The extractor must also cross-check every document ID referenced by CPs against the graph's document node list. Any reference to a document not in the deal set produces a `missing_condition_document` finding.

### DAG Construction

Build a directed graph (using Python's standard library or a simple adjacency-list dict) where:
- **Nodes** = individual conditions precedent (keyed by `condition_id`)
- **Edges** = "must be satisfied before" relationships, each annotated with `source: "explicit"` or `source: "inferred"`

**Explicit edges** come directly from each CP's `dependencies` list in the graph.

**Inferred edges** require examining cross-references and relationship types in the graph. The key inference rule: if a CP involves delivery or execution of Document X, and Document X has cross-references or relationships indicating it depends on Document Y (e.g., a Guaranty referencing a Loan Agreement), then any CP requiring Document Y's finalization must precede the CP for Document X. The prompt instructs Claude to apply this inference during Pass 1.

### Cycle Detection

Run standard cycle detection on the directed graph (e.g., depth-first search with coloring or Kahn's algorithm checking for remaining nodes). Any cycle produces a CRITICAL finding because circular conditions are legally impossible to satisfy. The finding must:
- List all CPs in the cycle in `affected_entities`
- Describe the exact cycle chain in `description` (e.g., "Condition A requires Condition B, which requires Condition C, which requires Condition A")
- Include a resolution suggestion (e.g., "Consider removing the dependency from C to A, as the Loan Agreement finalization does not logically require the Guaranty delivery")

### Topological Sort into Parallel Levels

After removing any cycles (which are reported as findings), perform a topological sort and group CPs into levels:
- **Level 0:** CPs with no prerequisites (can be satisfied immediately)
- **Level 1:** CPs whose prerequisites are all at Level 0
- **Level N:** CPs whose prerequisites are all at levels < N

CPs at the same level can be satisfied in parallel. Each level grouping produces a `parallel_group` finding of severity INFO.

### Critical Path Identification

The critical path is the longest chain of sequential dependencies through the DAG. To find it:
1. Compute the longest path from any source node (in-degree 0) to any sink node (out-degree 0) in the DAG
2. Mark each CP on this path with a `critical_path_item` finding
3. The critical path length determines the minimum number of sequential steps to close

### Output Structure

The analysis produces an `AnalysisResult` with `analysis_type: "conditions_precedent"` containing findings in these categories:

| Category | Severity | Description |
|----------|----------|-------------|
| `circular_condition` | CRITICAL | Impossible circular dependency chain |
| `critical_path_item` | INFO | Condition on the longest dependency chain |
| `missing_condition_document` | WARNING/ERROR | CP references absent document |
| `parallel_group` | INFO | Conditions satisfiable simultaneously |

All findings use the stable content-derived ID generation from Section 01 (`hash(analysis_type + category + sorted affected_entity_ids)`).

### Pass 1 vs Pass 2

CP analysis is entirely Pass 1. All finding types (cycles, critical path, missing documents, parallel groups) are structural and conclusive from graph data alone. No Pass 2 source text verification is needed.

### Integration with Section 09 (Execution Sequence)

The CP analysis must expose its results in a form that Section 09 can consume:
- The topological sort levels (ordered list of parallel groups)
- The dependency DAG edges (so execution sequence can layer additional constraints)
- The critical path chain (so execution sequence can mark critical path steps)

This means the module should provide functions that return structured data (not just findings), such as:

```python
def extract_conditions(graph: dict) -> list[dict]:
    """Extract all CP entities from the deal graph.
    Returns list of condition dicts with id, description,
    requiring_document, required_action, dependencies."""

def build_cp_dag(conditions: list[dict], graph: dict) -> dict:
    """Build directed graph of CP dependencies.
    Returns adjacency dict with edge annotations (explicit/inferred).
    Also returns any cycle findings."""

def topological_levels(dag: dict) -> list[list[str]]:
    """Return CPs grouped into parallel satisfaction levels.
    Level 0 has no prerequisites, level N depends only on < N."""

def find_critical_path(dag: dict, levels: list[list[str]]) -> list[str]:
    """Return the longest dependency chain (list of condition IDs)."""

def run_conditions_precedent_analysis(graph: dict) -> "AnalysisResult":
    """Main entry point: extract, build DAG, sort, find critical path,
    detect cycles, flag missing docs, return AnalysisResult."""
```

These are function signatures showing the module's public API. The actual implementation will construct appropriate `Finding` and `AnalysisResult` objects using the Pydantic models from Section 01.
