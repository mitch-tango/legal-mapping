# Section 05: Document Hierarchy Analysis

## Overview

This section implements the Document Hierarchy Analysis -- the first of five core analyses. For each legal issue area in a deal, it determines which document is the controlling authority and maps the subordination chain. This is a standalone analysis (no hard dependencies on other analyses) that produces results consumed by Section 06 (Conflict Detection) and Section 09 (Execution Sequence).

The analysis follows the two-pass pattern: Pass 1 sends the full graph JSON to Claude to discover issue areas and hierarchy relationships; Pass 2 verifies ambiguous hierarchy candidates against source document text.

## Dependencies

- **Section 01 (Schema and Fixtures):** Provides `Finding`, `AffectedEntity`, `AnalysisResult`, `AnalysisSummary` Pydantic models and shared test fixtures (`minimal_deal_graph`, `mock_anthropic_client`, `sample_source_documents`).
- **Section 02 (Graph Utilities):** Provides graph loading, section reference normalization, source document text retrieval, and prompt injection defense wrapper.

## File Paths

- **Source module:** `src/semantic_analysis/analyses/hierarchy.py`
- **Test file:** `tests/test_hierarchy.py`
- **Base taxonomy data:** `src/semantic_analysis/taxonomy.py`

## Tests (Write First)

All tests go in `tests/test_hierarchy.py`. These use fixtures from Section 01 (`minimal_deal_graph`, `mock_anthropic_client`, `sample_source_documents`).

```python
# tests/test_hierarchy.py

"""Tests for Document Hierarchy Analysis (Pass 1 and Pass 2)."""

# --- Issue Area Discovery ---

# Test: discovers_issue_areas_from_graph
# Given a deal graph with documents covering capital calls and distribution waterfall,
# the analysis returns issue areas with id, label, and anchor_evidence fields.
# Assert: each issue area has a non-empty anchor_evidence list referencing specific
# document+section combinations.

# Test: issue_area_ids_are_slugified
# Given an issue area with label "Capital call procedures",
# assert its id is "capital-call-procedures".

# Test: base_taxonomy_matched
# Given a graph containing provisions about "Default remedies",
# assert the returned issue area uses the taxonomy label "Default remedies / events of default"
# (not a free-form variant like "Defaults").

# Test: novel_issue_area_added
# Given a graph with provisions about a deal-specific topic not in the base taxonomy
# (e.g., "Environmental remediation schedule"), assert the analysis discovers and
# returns it as a new issue area alongside taxonomy matches.

# --- Hierarchy Detection ---

# Test: explicit_hierarchy_high_confidence
# Given a graph with a relationship of type "controls" between Document A and Document B
# for a given issue area, assert the resulting hierarchy finding has confidence "high"
# and source "explicit".

# Test: inferred_hierarchy_medium_confidence
# Given a graph where a Loan Agreement and a Promissory Note both address loan covenants
# but no explicit "controls" relationship exists, assert the hierarchy is inferred from
# document type conventions with confidence "medium" and source "inferred".

# Test: dual_authority_detected
# Given a graph where two documents both contain controlling language for the same
# issue area (e.g., both say "this agreement governs" regarding transfer restrictions),
# assert a finding with category "dual_authority_conflict" and severity ERROR or CRITICAL
# is produced.

# --- Output Structure ---

# Test: hierarchy_tree_structure
# Assert the output for each issue area is a tree: root node is the controlling document,
# children are deferring documents, leaves are merely-referencing documents.
# Each node must have document_id and role ("controlling", "deferring", "referencing").

# Test: section_level_citations_present
# Assert that every node in a hierarchy tree includes a section citation string
# (e.g., "Section 4.2(b)") linking to the specific provision that establishes the
# hierarchy relationship.
```

## Implementation Details

### Base Taxonomy

Define a constant list of common real estate deal issue areas that serves as the starting vocabulary for issue area discovery. The taxonomy provides stable labels so that the same provisions produce the same issue area identifiers across runs.

```python
# src/semantic_analysis/taxonomy.py

BASE_ISSUE_AREA_TAXONOMY: list[str] = [
    "Capital call procedures",
    "Distribution waterfall",
    "Default remedies / events of default",
    "Transfer restrictions",
    "Management authority / decision-making",
    "Insurance requirements",
    "Reporting obligations",
    "Construction / development milestones",
    "Loan covenants",
    "Exit / buyout provisions",
]
```

### Issue Area Discovery

The `discover_issue_areas` function (or equivalent) takes the graph data and returns a list of issue area objects. Each issue area has:

- `issue_area_id` -- a slugified version of the label (lowercase, hyphens for spaces, strip special characters). For example, `"Capital call procedures"` becomes `"capital-call-procedures"`.
- `label` -- human-readable name. For taxonomy matches, use the canonical taxonomy label.
- `anchor_evidence` -- a list of references (document ID + section + key terms) that anchor this issue area to the graph data. This makes discovery reproducible.

The Pass 1 prompt provides the base taxonomy and instructs Claude to: (1) match graph provisions to taxonomy labels where applicable, (2) discover deal-specific issue areas not in the taxonomy, and (3) for each issue area, cite the specific documents and sections that define it.

### Hierarchy Detection

Two methods, applied per issue area:

**Method 1: Explicit Language (High Confidence)**

Scan the graph's relationships and cross-references for explicit subordination signals. Relevant relationship types from the graph: `controls`, `subordinates_to`, `incorporates`. Relevant phrases in evidence fields: "governed by", "subject to the terms of", "in accordance with", "as set forth in".

Findings from explicit language get `confidence: "high"` and `source: "explicit"`. Category: `explicit_hierarchy`.

**Method 2: Document Type Conventions (Medium Confidence)**

When no explicit language exists, infer hierarchy from common real estate document type patterns:

- Loan Agreement controls Promissory Note, Deed of Trust, Guaranty, Environmental Indemnity
- Operating Agreement controls Management Agreement
- Joint Venture Agreement controls Operating Agreement (if both exist)
- Ground Lease constrains all documents regarding the leased property
- Intercreditor Agreement controls relationships between loan documents

Findings from type conventions get `confidence: "medium"` and `source: "inferred"`. Category: `inferred_hierarchy`.

### Dual-Authority Conflict Detection

When two documents both contain controlling language for the same issue area (neither defers to the other), produce a finding with:

- `category`: `"dual_authority_conflict"`
- `severity`: `"ERROR"` (or `"CRITICAL"` if the issue area is one that could block closing)
- `affected_entities`: both documents with their respective sections
- `description`: identifies both documents, the issue area in dispute, and the conflicting language

### Output Structure

The hierarchy analysis produces an `AnalysisResult` (from Section 01 schema) with:

- `analysis_type`: `"hierarchy"`
- `findings`: a list of `Finding` objects covering:
  - One `controlling_authority` finding per issue area where a clear hierarchy exists
  - `dual_authority_conflict` findings where two documents compete
  - `inferred_hierarchy` findings for document-type-convention-based hierarchies
  - `explicit_hierarchy` findings for language-based hierarchies

Each finding's `affected_entities` list links to graph entity IDs (document IDs, relationship IDs) so that Section 12 (Visualization) can render hierarchy overlays.

The hierarchy tree structure per issue area is encoded in the finding's description or in a structured field. Each tree node has:

- `document_id` -- the graph document entity
- `role` -- `"controlling"`, `"deferring"`, or `"referencing"`
- `section` -- section-level citation (e.g., `"Section 4.2(b)"`)
- `confidence` -- `"high"` or `"medium"`

### Pass 2 Verification

Ambiguous hierarchy candidates (where the graph data is inconclusive about which document controls) are sent to Pass 2. The workflow:

1. Identifies candidates where confidence would be `"low"` from graph data alone
2. Retrieves the relevant sections from source documents using `source_path` from graph nodes (via Section 02's source text retrieval utility)
3. Wraps source text in `<source_text>` delimiters with injection defense (via Section 02's wrapper)
4. Prompts Claude to read the actual controlling language and determine the hierarchy
5. Updates the finding's confidence, verified flag, and description based on the verification result

Structural findings (clear explicit language or clear document type conventions) skip Pass 2 entirely.

### Finding ID Generation

Each finding's `id` is a content-derived stable hash: `hash(analysis_type + category + sorted(affected_entity_ids))`. This is provided by the Section 01 schema utilities. The same hierarchy relationship in the same graph always produces the same finding ID, enabling incremental updates and deduplication.

### Function Signatures

```python
# src/semantic_analysis/analyses/hierarchy.py

async def run_hierarchy_analysis(
    graph_data: dict,
    anthropic_client,
    source_dir: str | None = None,
) -> "AnalysisResult":
    """Run document hierarchy analysis (Pass 1 + optional Pass 2).

    Args:
        graph_data: Parsed deal-graph.json content.
        anthropic_client: Anthropic API client instance.
        source_dir: Path to deal source documents directory (for Pass 2).
            If None, Pass 2 verification is skipped.

    Returns:
        AnalysisResult with hierarchy findings.
    """

def discover_issue_areas(graph_data: dict) -> list[dict]:
    """Extract issue areas from graph data using base taxonomy + discovery.

    Returns list of dicts with keys: issue_area_id, label, anchor_evidence.
    """

def slugify_issue_area(label: str) -> str:
    """Convert issue area label to stable slug ID.

    'Capital call procedures' -> 'capital-call-procedures'
    """

def detect_explicit_hierarchy(graph_data: dict, issue_area: dict) -> list["Finding"]:
    """Detect hierarchy from explicit controlling language in graph relationships."""

def detect_inferred_hierarchy(graph_data: dict, issue_area: dict) -> list["Finding"]:
    """Detect hierarchy from document type conventions."""

def detect_dual_authority(graph_data: dict, issue_area: dict) -> list["Finding"]:
    """Detect conflicting controlling claims on the same issue area."""
```

### Prompt Design Notes

The Pass 1 prompt for hierarchy analysis follows the common prompt structure from the plan:

- System message sets the legal analyst role specializing in real estate transactions
- Graph JSON is sent as a cached system prompt (for cost efficiency across multi-analysis runs)
- User message contains: the base taxonomy, instructions to discover issue areas, instructions to identify hierarchy relationships, and the output schema via tool use
- Temperature is set to 0 for deterministic output
- Output is structured via Anthropic tool use (function calling) matching the Pydantic schema

The prompt explicitly instructs Claude to:
1. Identify all issue areas (matching taxonomy where possible, discovering novel ones)
2. For each issue area, determine which document controls and map the subordination chain
3. Cite section-level evidence for every hierarchy relationship
4. Flag dual-authority conflicts where two documents both claim control
5. Distinguish high-confidence (explicit language) from medium-confidence (document type conventions)
6. Include low-confidence findings rather than omitting uncertain ones
