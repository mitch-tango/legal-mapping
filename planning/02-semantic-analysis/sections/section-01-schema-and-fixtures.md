# Section 01: Schema and Fixtures

## Overview

This section establishes the foundational data models and test infrastructure for the entire Semantic Analysis Engine. Every subsequent section depends on the Pydantic models and pytest fixtures defined here.

**What this section delivers:**
- Pydantic models for `deal-analysis.json` (the companion results file)
- A content-derived stable ID generation utility for findings
- Shared pytest fixtures used across all test modules

**File paths to create:**

| File | Purpose |
|------|---------|
| `src/semantic_analysis/__init__.py` | Package init |
| `src/semantic_analysis/schemas.py` | All Pydantic models |
| `src/semantic_analysis/id_generation.py` | Stable content-derived ID utility |
| `tests/__init__.py` | Test package init |
| `tests/conftest.py` | Shared pytest fixtures |
| `tests/test_schemas.py` | Schema validation tests |
| `pyproject.toml` | Project config with uv/pytest |

All paths are relative to the project root: `C:\Users\maitl\New City Dropbox\Maitland Thompson\Working\Legal Review\Mapping`.

---

## Tests (Write First)

Create `tests/test_schemas.py` with the following test stubs. Each docstring describes the exact assertion.

```python
"""Tests for the analysis results schema and ID generation."""
import pytest
from pydantic import ValidationError


class TestAnalysisResultsSchema:
    """Tests for schema validation of the complete AnalysisResults model."""

    def test_schema_validates_complete_result(self, sample_analysis_results):
        """A fully populated AnalysisResults dict passes Pydantic validation.
        Use the sample_analysis_results fixture, construct an AnalysisResults
        instance from it, and assert no ValidationError is raised."""

    def test_schema_rejects_missing_required_fields(self):
        """Constructing AnalysisResult without analysis_type or findings
        raises ValidationError."""

    def test_severity_values_constrained(self):
        """Finding.severity only accepts CRITICAL, ERROR, WARNING, INFO.
        Any other string raises ValidationError."""

    def test_completion_field_matches_status(self):
        """When status is 'completed', completion must be 'complete'.
        When status is 'failed', completion must be 'failed'."""

    def test_errors_array_populated_on_failure(self):
        """An AnalysisResult with status 'failed' must have a non-empty
        errors list. Empty errors with failed status raises ValidationError."""


class TestFindingIdGeneration:
    """Tests for the content-derived stable ID system."""

    def test_finding_id_is_content_derived(self):
        """Two Finding objects with the same (analysis_type + category +
        sorted affected_entity_ids) produce identical id values."""

    def test_finding_id_differs_for_different_content(self):
        """Two Finding objects with different affected entities produce
        different id values."""


class TestDisplayOrdinal:
    """Tests for sequential display ordering within an analysis."""

    def test_display_ordinal_sequential(self):
        """Findings within a single AnalysisResult have ordinals 1, 2, 3...
        in sequence with no gaps."""


class TestIncrementalUpdate:
    """Tests for incremental write behavior."""

    def test_incremental_update_preserves_other_analyses(self, tmp_path):
        """Writing hierarchy results to an AnalysisResults object that
        already contains conflicts results does not remove or modify
        the conflicts entry."""
```

---

## Pydantic Models

Create `src/semantic_analysis/schemas.py` with all the models below. Use Pydantic v2 (BaseModel with field validators).

### AnalysisResults (top-level)

```python
class AnalysisResults(BaseModel):
    schema_version: str                          # "1.0.0"
    deal_graph_hash: str                         # SHA-256 of deal-graph.json at analysis time
    analyses: dict[str, AnalysisResult]          # Keyed by analysis type name
    metadata: AnalysisMetadata
    staleness: dict[str, StalenessRecord]        # Keyed by analysis type name
```

### AnalysisMetadata

```python
class AnalysisMetadata(BaseModel):
    last_full_analysis: str | None               # ISO timestamp
    documents_included: list[str]                 # Document IDs from graph
    engine_version: str
```

### StalenessRecord

```python
class StalenessRecord(BaseModel):
    is_stale: bool
    last_run: str                                # ISO timestamp
    stale_reason: str | None
    graph_hash_at_run: str                       # Hash of graph when this analysis ran
```

### AnalysisResult

```python
class AnalysisResult(BaseModel):
    analysis_type: str                           # "hierarchy" | "conflicts" | etc.
    status: str                                  # "completed" | "failed" | "partial"
    completion: str                              # "complete" | "partial" | "failed"
    run_timestamp: str                           # ISO timestamp
    model_used: str                              # e.g., "claude-sonnet-4-6"
    findings: list[Finding]
    summary: AnalysisSummary
    errors: list[str]                            # Empty if successful
```

**Validation rules to implement:**
- `status` must be one of: `"completed"`, `"failed"`, `"partial"`
- `completion` must be one of: `"complete"`, `"partial"`, `"failed"`
- When `status == "completed"`, `completion` must be `"complete"`
- When `status == "failed"`, `completion` must be `"failed"` and `errors` must be non-empty
- Use a `@model_validator(mode='after')` for these cross-field rules

### Finding

```python
class Finding(BaseModel):
    id: str                                      # Content-derived stable ID
    display_ordinal: int                         # Sequential within analysis (1-based)
    severity: Literal["CRITICAL", "ERROR", "WARNING", "INFO"]
    category: str                                # Analysis-specific category string
    title: str
    description: str
    affected_entities: list[AffectedEntity]
    confidence: Literal["high", "medium", "low"]
    source: Literal["explicit", "inferred"]
    verified: bool                               # True if Pass 2 verification performed
```

The `severity` field uses `Literal` to constrain values at the type level. This ensures any invalid severity string raises `ValidationError` automatically.

### AffectedEntity

```python
class AffectedEntity(BaseModel):
    entity_type: str                             # "document" | "relationship" | "defined_term" | etc.
    entity_id: str                               # ID from deal-graph.json
    document_id: str                             # Containing document
    section: str | None = None                   # Section-level citation
```

### AnalysisSummary

```python
class AnalysisSummary(BaseModel):
    total_findings: int
    by_severity: dict[str, int]                  # {"CRITICAL": 2, "ERROR": 5, ...}
    key_findings: list[str]                      # Top 3-5 most important finding titles
```

### Analysis-Specific Finding Categories

These are not separate models but documented constants. Define them as frozen sets for validation or reference:

```python
HIERARCHY_CATEGORIES = frozenset({
    "controlling_authority", "dual_authority_conflict",
    "inferred_hierarchy", "explicit_hierarchy",
})

CONFLICTS_CATEGORIES = frozenset({
    "dangling_reference", "circular_reference", "contradictory_provision",
    "missing_document", "stale_reference", "ambiguous_section_ref",
})

DEFINED_TERMS_CATEGORIES = frozenset({
    "conflicting_definition", "orphaned_definition", "undefined_usage",
    "cross_document_dependency", "enhanced_term",
})

CONDITIONS_PRECEDENT_CATEGORIES = frozenset({
    "circular_condition", "critical_path_item",
    "missing_condition_document", "parallel_group",
})

EXECUTION_SEQUENCE_CATEGORIES = frozenset({
    "signing_dependency", "parallel_execution_window",
    "gating_condition", "critical_path_step",
})

ANALYSIS_TYPES = frozenset({
    "hierarchy", "conflicts", "defined_terms",
    "conditions_precedent", "execution_sequence",
})
```

---

## Content-Derived Stable ID Generation

Create `src/semantic_analysis/id_generation.py`.

The finding ID must be deterministic: the same logical finding produces the same ID across separate runs. This enables deduplication (section 11, scale handling) and incremental updates.

**Algorithm:**

```python
def generate_finding_id(analysis_type: str, category: str, affected_entity_ids: list[str]) -> str:
    """Generate a stable, content-derived ID for a finding.

    Concatenate analysis_type + category + sorted(affected_entity_ids),
    then compute SHA-256 hex digest (first 16 chars for readability).

    Sorting entity IDs ensures order-independence: the same set of
    affected entities always produces the same ID regardless of
    discovery order.
    """
```

Key properties:
- Same `(analysis_type, category, sorted entity IDs)` always yields the same ID
- Different inputs yield different IDs (collision-resistant via SHA-256)
- IDs are short enough for display (16 hex chars = 64 bits, sufficient for a single deal)

---

## Shared Pytest Fixtures

Create `tests/conftest.py` with these fixtures. They are used by every subsequent section's tests.

### minimal_deal_graph

A small 3-document graph with known relationships, defined terms, cross-references, and conditions precedent. Structure:

- **Documents:** Loan Agreement, Guaranty, Environmental Indemnity
- **Relationships:** Loan Agreement `controls` Guaranty; Loan Agreement `controls` Environmental Indemnity
- **Defined Terms:** "Borrower" (defined in Loan Agreement, used in all three); "Guaranteed Obligations" (defined in Guaranty)
- **Cross-References:** Guaranty Section 1.1 references Loan Agreement Section 2.1; Environmental Indemnity Section 3.1 references Loan Agreement Section 5.2
- **Conditions Precedent:** Execution of Loan Agreement (no dependencies); Delivery of Guaranty (depends on Loan Agreement execution); Delivery of Environmental Indemnity (depends on Loan Agreement execution)
- Each document node includes a `source_path` field (pointing to a placeholder path)

Return this as a Python dict matching the `deal-graph.json` structure from Split 01.

### medium_deal_graph

A 10-document graph covering all entity types. Builds on the minimal graph by adding: Operating Agreement, Management Agreement, Promissory Note, Deed of Trust, Intercreditor Agreement, Ground Lease, and a Joint Venture Agreement. Should include at least one instance of every entity type (document, relationship, defined_term, cross_reference, condition_precedent, party, annotation).

### large_deal_graph

A 25-document graph for scale testing. Can be programmatically generated by duplicating and varying the medium graph. Include enough cross-references and defined terms to produce realistic candidate counts for Pass 2 cap testing.

### sample_source_documents

A `tmp_path`-based fixture that creates a directory of small text files simulating deal documents. Each file contains a few sections with realistic legal placeholder text. The file paths match the `source_path` values in the graph fixtures. This is needed for Pass 2 source text retrieval tests.

### mock_anthropic_client

A mock of the Anthropic API client that returns pre-canned analysis responses. Should support:
- Configurable responses per call (for testing multi-pass flows)
- Response delay simulation (for timeout testing)
- Failure injection (for error handling tests)

Use `unittest.mock.AsyncMock` since the Anthropic client is async.

### sample_analysis_results

A complete, valid `AnalysisResults` dict (not yet a model instance) that passes schema validation. Includes at least one completed analysis with findings. Used by `test_schema_validates_complete_result`.

---

## pyproject.toml Setup

Create `pyproject.toml` at the project root with:

```toml
[project]
name = "legal-mapping-semantic-analysis"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.0",
    "anthropic>=0.39.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## Dependencies on Other Sections

This section has **no dependencies** on other sections. All subsequent sections (02 through 12) depend on this section for:

- The Pydantic models in `schemas.py` (imported as `from semantic_analysis.schemas import ...`)
- The ID generation utility in `id_generation.py`
- The shared fixtures in `conftest.py`

---

## Implementation Checklist

1. Create `pyproject.toml` and directory structure (`src/semantic_analysis/`, `tests/`)
2. Write all test stubs in `tests/test_schemas.py`
3. Implement Pydantic models in `src/semantic_analysis/schemas.py` with validators
4. Implement `generate_finding_id` in `src/semantic_analysis/id_generation.py`
5. Build all fixtures in `tests/conftest.py`
6. Run `uv run pytest tests/test_schemas.py` and confirm all tests pass
