# Section 09: Execution Sequence Derivation

## Overview

This section implements the execution sequence analysis, which derives a closing checklist -- the correct order for document execution based on conditions precedent, cross-references, and signing/delivery dependencies. It is the only analysis that has a hard dependency on another analysis result (Conditions Precedent), using the CP topological sort as its baseline and layering additional execution-order constraints on top.

**What this section delivers:**
- An execution sequence analyzer that consumes CP results and graph data
- Logic to detect signing, delivery, and cross-reference dependencies between documents
- Grouping of documents into parallel execution windows
- Gating condition identification per execution step
- Critical path marking across the execution timeline

**File paths to create:**

| File | Purpose |
|------|---------|
| `src/semantic_analysis/analyzers/execution_sequence.py` | Execution sequence analysis implementation |
| `tests/test_execution_sequence.py` | All tests for this section |

All paths are relative to the project root: `C:\Users\maitl\New City Dropbox\Maitland Thompson\Working\Legal Review\Mapping`.

**Dependencies (must be implemented first):**
- **Section 01 (Schema and Fixtures):** Pydantic models (`Finding`, `AnalysisResult`, `AffectedEntity`, etc.), stable ID generation, shared fixtures (`minimal_deal_graph`, `mock_anthropic_client`)
- **Section 02 (Graph Utilities):** Graph loading, section reference normalization, source text retrieval
- **Section 08 (Conditions Precedent):** CP analysis results including the topological sort, critical path, and dependency DAG that this analysis layers on top of

---

## Tests (Write First)

Create `tests/test_execution_sequence.py` with the following test stubs. Each docstring describes the exact assertion.

```python
"""Tests for execution sequence derivation analysis."""
import pytest


class TestExecutionSequencePrerequisites:
    """Tests that CP results are required before execution sequence can run."""

    def test_requires_cp_results(self, minimal_deal_graph, mock_anthropic_client):
        """Running execution sequence analysis without CP results in the
        existing analysis results raises an error (ValueError or similar)
        indicating that conditions_precedent analysis must be run first.
        Pass an AnalysisResults object that has no 'conditions_precedent' key
        in its analyses dict."""

    def test_accepts_completed_cp_results(self, minimal_deal_graph, mock_anthropic_client):
        """Running execution sequence analysis with completed CP results
        in the existing analysis results proceeds without error. Pass an
        AnalysisResults object that has a 'conditions_precedent' entry with
        status 'completed'."""


class TestBaselineFromCPSort:
    """Tests that CP topological sort forms the execution order baseline."""

    def test_baseline_from_cp_sort(self, minimal_deal_graph, mock_anthropic_client):
        """The execution steps produced respect the CP topological sort
        ordering. If CP says condition A must be satisfied before condition B,
        then the execution step containing A's document appears at or before
        the step containing B's document."""


class TestSigningDependencies:
    """Tests for signing dependency detection and layering."""

    def test_signing_dependencies_layered(self, minimal_deal_graph, mock_anthropic_client):
        """When a Guaranty guarantees a Loan Agreement, the Loan Agreement
        must appear in an earlier (or same) execution step than the Guaranty.
        Verify this ordering in the output execution steps."""


class TestDeliveryDependencies:
    """Tests for delivery-before-execution constraints."""

    def test_delivery_dependencies_respected(self, minimal_deal_graph, mock_anthropic_client):
        """When a document must be delivered (not just signed) before another
        can be executed, the delivery step precedes the dependent execution
        step in the output sequence."""


class TestCrossReferenceDependencies:
    """Tests for cross-reference incorporation ordering."""

    def test_crossref_dependencies_included(self, minimal_deal_graph, mock_anthropic_client):
        """When Document A incorporates Document B by reference, Document B
        appears in an earlier (or same) execution step than Document A in the
        output sequence, since B should be finalized before A references it."""


class TestParallelExecutionWindows:
    """Tests for grouping simultaneously-executable documents."""

    def test_parallel_execution_windows(self, minimal_deal_graph, mock_anthropic_client):
        """Documents with no mutual ordering constraints are grouped into the
        same execution step (parallel window). Verify that at least one step
        in the output contains more than one document when the graph has
        independent documents."""


class TestGatingConditions:
    """Tests for per-step gating condition listing."""

    def test_gating_conditions_listed(self, minimal_deal_graph, mock_anthropic_client):
        """Each execution step in the output includes a list of gating
        conditions (CPs or other prerequisites) that must be satisfied before
        that step can proceed. Verify the list is non-empty for steps that
        have known prerequisites from the CP analysis."""


class TestCriticalPath:
    """Tests for critical path marking on execution steps."""

    def test_critical_path_steps_marked(self, minimal_deal_graph, mock_anthropic_client):
        """Steps that lie on the critical path (longest sequential chain
        through the execution sequence) are marked with a critical path flag.
        Verify that at least one step is marked as critical path and that the
        marked steps form a valid chain."""
```

---

## Implementation Details

### Analysis Architecture

The execution sequence analyzer follows the same two-pass pattern as all other analyses, but in practice most of its work is Pass 1 only. The structural ordering of documents is deterministic from graph data plus CP results; Pass 2 verification is rarely needed.

### Core Algorithm

The execution sequence derivation works in these stages:

1. **Load CP results:** Read the `conditions_precedent` analysis from the existing `deal-analysis.json`. Extract the topological sort (parallel satisfaction levels) and critical path.

2. **Build execution dependency graph:** Start with CP dependency edges, then add:
   - **Signing dependencies:** Identified from relationship types in the graph. If Document A has a relationship of type `guarantees`, `secures`, or `subordinates_to` pointing at Document B, then B must be signed before A. Common patterns:
     - Loan Agreement before Guaranty, Promissory Note, Deed of Trust, Environmental Indemnity
     - Operating Agreement before Management Agreement
     - Ground Lease before sublease or development documents
   - **Delivery dependencies:** Some CPs specify "delivery of executed [Document X]" as a condition. These create delivery-before-execution edges.
   - **Cross-reference incorporation dependencies:** If Document A's relationships include `incorporates` pointing at Document B, then B should be finalized first.

3. **Topological sort with parallel grouping:** Run topological sort on the combined dependency graph. Documents with no mutual ordering constraints fall into the same level (parallel execution window).

4. **Gating condition assignment:** For each execution step, collect all CPs and signing dependencies that must be satisfied before that step can proceed.

5. **Critical path identification:** The longest sequential chain through the execution steps, carried forward from CP critical path but potentially extended by signing/delivery dependencies.

### Finding Categories

The execution sequence analysis produces findings with these categories:

| Category | Description | Severity |
|----------|-------------|----------|
| `signing_dependency` | Document A must be signed before Document B | INFO |
| `parallel_execution_window` | Documents that can be signed simultaneously | INFO |
| `gating_condition` | Condition that must be met before an execution step | WARNING or INFO |
| `critical_path_step` | Step on the longest path through execution | WARNING |

### Prompt Design (Pass 1)

The Pass 1 prompt sends the full graph JSON plus the CP analysis results to Claude. The prompt instructs Claude to:

1. Use the CP topological sort as the baseline ordering
2. Identify signing dependencies from graph relationships (guarantees, secures, subordinates_to, incorporates)
3. Identify delivery dependencies from CP descriptions mentioning "delivery of executed" documents
4. Group documents into parallel execution windows where no mutual constraints exist
5. For each step, list all gating conditions
6. Mark critical path steps

The system prompt follows the common pattern established in section 10 (Workflow Orchestration): legal analyst role, section-level citations, severity classification. The graph JSON is sent as a cached system prompt, and the analysis-specific instructions (including serialized CP results) are sent as the user message.

### Output Schema

Each execution step maps to one or more `Finding` objects. The recommended approach is:

- One `parallel_execution_window` finding per execution step, with `affected_entities` listing all documents in that window
- One `signing_dependency` finding for each identified signing ordering constraint
- One `gating_condition` finding for each step that has prerequisites, listing the conditions in the description
- One `critical_path_step` finding for each step on the critical path

The `AffectedEntity` objects use `entity_type: "document"` and reference document IDs from the graph. Gating conditions reference CP entity IDs.

### Error Handling

- If CP results have status `"failed"` or `"partial"`, the execution sequence analyzer should still attempt to run with whatever CP data is available, but mark its own status as `"partial"` and include a note in its errors array.
- If the graph has no conditions precedent at all, the analyzer falls back to deriving execution order purely from signing and cross-reference dependencies, producing a simpler but still useful checklist.

### Module Structure

`src/semantic_analysis/analyzers/execution_sequence.py` should expose:

```python
"""Execution sequence derivation analysis.

Derives closing checklist ordering from CP results plus signing, delivery,
and cross-reference dependencies found in the deal graph.
"""

async def run_execution_sequence_analysis(graph_data: dict, existing_results: "AnalysisResults", client) -> "AnalysisResult":
    """Main entry point. Requires conditions_precedent in existing_results.

    Raises ValueError if conditions_precedent analysis is not present
    in existing_results.analyses.
    """

def extract_signing_dependencies(graph_data: dict) -> list[tuple[str, str]]:
    """Extract (must_sign_first_doc_id, then_sign_doc_id) pairs from
    graph relationships like guarantees, secures, subordinates_to."""

def extract_delivery_dependencies(cp_findings: list["Finding"]) -> list[tuple[str, str]]:
    """Extract delivery-before-execution constraints from CP finding
    descriptions that mention 'delivery of executed' documents."""

def extract_crossref_dependencies(graph_data: dict) -> list[tuple[str, str]]:
    """Extract (finalize_first_doc_id, incorporating_doc_id) pairs from
    'incorporates' relationships in the graph."""

def build_execution_dag(cp_sort: list[list[str]], signing_deps: list[tuple[str, str]], delivery_deps: list[tuple[str, str]], crossref_deps: list[tuple[str, str]]) -> dict:
    """Combine all dependency sources into a single DAG for topological sort."""

def derive_execution_steps(dag: dict) -> list[dict]:
    """Topological sort the DAG into execution steps (parallel windows).
    Each step is a dict with 'documents', 'gating_conditions', 'is_critical_path'."""
```

These functions should use the graph utility functions from section 02 for graph traversal, and the schema models from section 01 for constructing `Finding` and `AnalysisResult` objects. The stable ID generation from section 01 is used to create content-derived IDs for each finding.
