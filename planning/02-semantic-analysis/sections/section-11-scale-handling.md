# Section 11: Scale Handling

## Overview

This section implements token estimation, automatic clustering for large deals, issue-area-based graph partitioning, per-cluster analysis execution, and finding deduplication. It ensures the analysis engine gracefully handles deals ranging from 5 documents to 40+ documents without quality degradation.

**Dependencies:**
- Section 01 (Schema and Fixtures) -- Pydantic models, especially `Finding` with its content-derived stable ID, and the `large_deal_graph` fixture
- Section 02 (Graph Utilities) -- Graph loading and canonicalization utilities
- Section 10 (Workflow Orchestration) -- Main entry point that invokes scale handling when needed

**Files to create/modify:**
- `src/semantic_analysis/scale.py` -- Core scale handling module (token estimation, clustering, deduplication)
- `tests/test_scale.py` -- All tests for this section

---

## Tests

Write these tests in `tests/test_scale.py` before implementing. All tests use fixtures from Section 01 (conftest.py).

```python
# tests/test_scale.py

import pytest

# --- Token Estimation ---

# Test: small_deal_single_call
# A 5-document deal graph should result in a single Pass 1 API call
# (no clustering triggered). Verify that estimate_tokens() returns
# a value below the 60% context window threshold and that
# should_cluster() returns False.

# Test: token_estimation_from_json_size
# Given a graph JSON string of known byte length, verify that
# estimate_tokens() returns a reasonable approximation.
# The heuristic is: token_count ~ len(json_string) / 4
# (roughly 4 characters per token for structured JSON).
# Verify the estimate is within 20% of the expected value.

# --- Clustering Trigger ---

# Test: clustered_approach_triggered
# Create a graph JSON whose estimated token count exceeds 60% of the
# model context window (200K tokens, so threshold is 120K tokens).
# Verify should_cluster() returns True.
# Verify that cluster_graph() is called by the orchestrator when
# should_cluster() is True.

# --- Issue-Area Clustering ---

# Test: clustering_by_issue_area
# Given a deal graph with documents touching multiple issue areas
# (e.g., "insurance", "capital-calls", "transfer-restrictions"),
# verify that cluster_graph() produces clusters grouped by issue area,
# NOT by document type. Each cluster should contain all documents
# and cross-references related to a single issue area, even if those
# documents span different types (e.g., an LLC Agreement and a Side
# Letter both touching "insurance" appear in the same cluster).

# --- Finding Deduplication ---

# Test: cross_cluster_findings_deduplicated
# Run analysis on two overlapping clusters that both produce a finding
# with the same stable content-derived ID (same analysis_type +
# category + sorted affected_entity_ids). Verify that
# deduplicate_findings() merges them into a single finding.

# Test: dedup_keeps_higher_confidence
# Given two findings with the same ID but different confidence levels
# ("high" vs "medium"), verify the deduplicated result retains the
# "high" confidence version.

# Test: provenance_records_clusters
# After deduplication, verify the retained finding has a
# found_in_clusters field listing all cluster IDs where it appeared
# (e.g., ["insurance-cluster", "capital-calls-cluster"]).
```

---

## Implementation Details

### Token Estimation

The token estimation function converts graph JSON size to an approximate token count. This is a pre-API-call check, not a precise count.

```python
# src/semantic_analysis/scale.py

# Constants
MODEL_CONTEXT_WINDOW = 200_000  # Claude's context window in tokens
CLUSTER_THRESHOLD_RATIO = 0.60  # Trigger clustering at 60% of context window
CHARS_PER_TOKEN = 4             # Rough heuristic for structured JSON

def estimate_tokens(graph_json: str) -> int:
    """Estimate token count from graph JSON string length.

    Uses a heuristic of ~4 characters per token for structured JSON.
    This is intentionally conservative (overestimates slightly) to
    avoid hitting context limits.
    """
    ...

def should_cluster(graph_json: str) -> bool:
    """Return True if the graph is large enough to require clustering.

    Threshold: estimated tokens > 60% of MODEL_CONTEXT_WINDOW.
    """
    ...
```

### Issue-Area-Based Clustering

When clustering is needed, the graph is partitioned by issue area. This is the critical design decision: clustering by document type would defeat the tool's primary purpose (catching cross-document conflicts within the same issue area).

```python
def cluster_graph(graph_data: dict) -> list[dict]:
    """Partition a deal graph into issue-area clusters.

    Each cluster contains:
    - All documents touching a specific issue area
    - All cross-references between those documents
    - All defined terms used across those documents
    - All conditions precedent involving those documents

    A document may appear in multiple clusters if it touches
    multiple issue areas. This is intentional -- it ensures
    cross-document analysis within each issue area is complete.

    Returns a list of cluster dicts, each with:
    - cluster_id: str (slugified issue area name)
    - documents: list[dict] (subset of graph documents)
    - relationships: list[dict] (subset of graph relationships)
    - defined_terms: list[dict] (subset of graph terms)
    - cross_references: list[dict] (subset of graph xrefs)
    - conditions_precedent: list[dict] (subset of graph CPs)
    """
    ...
```

The clustering algorithm:

1. **Identify issue areas** from the graph. Issue areas come from document relationships and hierarchy analysis results (if available). Each document may be tagged with one or more issue areas based on its content type, cross-references, and explicit hierarchy relationships.

2. **Assign documents to issue areas.** A single document (e.g., an LLC Agreement) may touch multiple issue areas (insurance, capital calls, transfer restrictions). It appears in each relevant cluster.

3. **Pull related entities into each cluster.** For each issue-area cluster, include all cross-references between documents in the cluster, all defined terms used by those documents, and all CPs referencing those documents.

4. **Validate cluster sizes.** If a single cluster still exceeds the token threshold (unlikely but possible for a deal dominated by one issue area), split it further by document sub-grouping while preserving cross-references.

### Per-Cluster Analysis Execution

When the clustered approach is active, the orchestrator (from Section 10) runs each analysis type against each cluster independently. The flow is:

1. `should_cluster()` returns `True`
2. `cluster_graph()` produces N clusters
3. For each analysis type in the execution order, run it against each cluster
4. Collect all findings from all clusters
5. Deduplicate findings using `deduplicate_findings()`
6. Write the merged results to `deal-analysis.json`

The orchestrator integration point is a function that wraps the normal single-call execution:

```python
async def run_clustered_analysis(
    graph_data: dict,
    analysis_type: str,
    run_single_analysis,  # callable from orchestrator
) -> list:
    """Run an analysis across all issue-area clusters and merge results.

    Parameters:
        graph_data: The full deal graph
        analysis_type: Which analysis to run (e.g., "hierarchy")
        run_single_analysis: Async callable that takes a graph subset
            and analysis_type, returns a list of Finding objects

    Returns:
        Deduplicated list of Finding objects with provenance tracking
    """
    ...
```

### Finding Deduplication

Findings are deduplicated using the stable content-derived ID defined in Section 01's `Finding` schema. The ID is a hash of `(analysis_type, category, sorted_affected_entity_ids)`, so identical findings from different clusters will share the same ID.

```python
def deduplicate_findings(
    clustered_findings: list[tuple[str, list]]
) -> list:
    """Merge findings from multiple clusters, deduplicating by stable ID.

    Parameters:
        clustered_findings: List of (cluster_id, findings_list) tuples

    Deduplication rules:
    - Same finding ID across clusters: keep the higher-confidence version
    - If confidence is equal: keep the one with more detailed description
    - Record all source cluster IDs in found_in_clusters field

    Returns:
        Deduplicated list of findings with found_in_clusters populated
    """
    ...
```

The `found_in_clusters` field is added to findings that appeared in multiple clusters. For findings that appeared in only one cluster, this field can be omitted or set to a single-element list. This provenance information helps the user understand which issue areas surfaced a given finding.

### Integration with Finding Schema

The `Finding` model from Section 01 needs a `found_in_clusters` optional field to support provenance tracking:

```python
# Addition to Finding model in src/semantic_analysis/models.py
# (defined in Section 01, extended here)
found_in_clusters: list[str] | None = None  # Cluster IDs where this finding appeared
```

This is an optional field with a default of `None`, so it does not affect findings produced by the non-clustered (single-call) path.

### Scale Tiers Summary

| Deal Size | Documents | Estimated Tokens | Approach | API Calls (approx) |
|-----------|-----------|-----------------|----------|-------------------|
| Small | 5-10 | 10K-40K | Single Pass 1 call | 2-5 per analysis |
| Medium | 10-20 | 50K-100K | Single Pass 1 call | 5-15 per analysis |
| Large | 20-40+ | 100K-200K+ | Clustered by issue area | 10-30+ per analysis |

The 60% threshold (120K tokens for a 200K context window) leaves 40% headroom for the system prompt, analysis instructions, and response generation.
