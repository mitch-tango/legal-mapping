# Section 12: Visualization Integration

## Overview

This section defines the schema contract between Split 02 (Semantic Analysis Engine) and Split 03 (Interactive Visualization). It does not add new analysis logic. Instead, it verifies that the `deal-analysis.json` output produced by the workflow orchestration (section-10) contains all the fields, structures, and metadata that Split 03 needs to render graph annotations, report views, and filtering/navigation features.

**What this section delivers:**
- A documented schema contract specifying what Split 03 expects from `deal-analysis.json`
- Validation tests proving the output supports all visualization features: conflict markers by severity, hierarchy overlays, term flow paths, missing document indicators, and finding filtering by severity/document/type
- A lightweight contract-validation utility that can be run independently to verify any `deal-analysis.json` file

**File paths to create:**

| File | Purpose |
|------|---------|
| `src/semantic_analysis/visualization_contract.py` | Schema contract validator and documentation |
| `tests/test_visualization_contract.py` | Tests verifying deal-analysis.json supports all Split 03 needs |

All paths are relative to the project root: `C:\Users\maitl\New City Dropbox\Maitland Thompson\Working\Legal Review\Mapping`.

**Dependencies:**
- **section-01-schema-and-fixtures** -- Pydantic models (`AnalysisResults`, `Finding`, `AffectedEntity`, etc.) and shared test fixtures (`sample_analysis_results`, `minimal_deal_graph`)
- **section-10-workflow-orchestration** -- The workflow that produces `deal-analysis.json`; this section validates that its output meets visualization requirements

---

## Tests (Write First)

Create `tests/test_visualization_contract.py` with the following test stubs. These tests verify that the schema and data structures in `deal-analysis.json` satisfy every visualization feature Split 03 requires.

```python
"""Tests verifying deal-analysis.json schema supports all Split 03 visualization features.

These are contract tests -- they prove the analysis output contains the fields
and structures needed by the Interactive Visualization layer.
"""
import pytest


class TestSchemaConformance:
    """Verify deal-analysis.json conforms to the documented schema contract."""

    def test_analysis_json_parseable_by_split_03(self, sample_analysis_results):
        """A complete AnalysisResults object can be serialized to JSON and
        deserialized back without data loss. All top-level keys required by
        Split 03 are present: schema_version, analyses, metadata, staleness."""

    def test_schema_version_present(self, sample_analysis_results):
        """schema_version is a non-empty string following semver format.
        Split 03 uses this to handle schema evolution gracefully."""


class TestFindingEntityLinks:
    """Every finding must link back to graph entity IDs so Split 03 can highlight them."""

    def test_findings_have_affected_entities(self, sample_analysis_results):
        """Every Finding in every AnalysisResult has a non-empty
        affected_entities list. Each AffectedEntity has entity_type,
        entity_id, and document_id fields that reference valid graph IDs."""

    def test_affected_entity_types_are_known(self, sample_analysis_results):
        """AffectedEntity.entity_type is one of the known types:
        'document', 'relationship', 'defined_term', 'cross_reference',
        'condition_precedent'. Split 03 uses entity_type to choose
        which visual element to highlight (node, edge, label, etc.)."""

    def test_affected_entity_document_id_always_set(self, sample_analysis_results):
        """Every AffectedEntity has a non-empty document_id.
        Split 03 uses this to filter findings per document."""


class TestSeverityFiltering:
    """Split 03 filters findings by severity level."""

    def test_severity_filterable(self, sample_analysis_results):
        """Findings can be grouped/filtered by severity. Collect all
        findings across all analyses and verify they can be partitioned
        into CRITICAL, ERROR, WARNING, INFO buckets. Each bucket is
        a valid (possibly empty) list."""

    def test_summary_by_severity_matches_findings(self, sample_analysis_results):
        """AnalysisSummary.by_severity counts match the actual number
        of findings at each severity level in the findings list.
        Split 03 uses by_severity for dashboard counts."""


class TestDocumentFiltering:
    """Split 03 filters findings by document ID."""

    def test_document_filterable(self, sample_analysis_results):
        """Given a document_id, filtering all findings where any
        affected_entity.document_id matches returns a non-empty list
        for documents that appear in the analysis. This is how Split 03
        shows 'all findings affecting Document X'."""


class TestAnalysisTypeFiltering:
    """Split 03 filters findings by analysis type."""

    def test_analysis_type_filterable(self, sample_analysis_results):
        """Findings can be filtered by analysis type using the
        analyses dict keys. Each key (hierarchy, conflicts,
        defined_terms, conditions_precedent, execution_sequence)
        maps to an AnalysisResult with its own findings list."""

    def test_analysis_types_are_known(self, sample_analysis_results):
        """All keys in analyses dict are from the known set:
        hierarchy, conflicts, defined_terms, conditions_precedent,
        execution_sequence. Split 03 maps these to specific UI tabs."""


class TestConflictMarkerSupport:
    """Split 03 renders red/yellow/blue conflict markers on graph edges."""

    def test_conflict_findings_have_severity_for_color_mapping(self, sample_analysis_results):
        """Conflict findings have severity values that map to colors:
        CRITICAL -> red, ERROR -> yellow, WARNING -> blue.
        Verify conflict findings (analysis_type='conflicts') have
        severity set to one of these three levels."""

    def test_conflict_findings_reference_relationships(self, sample_analysis_results):
        """Conflict findings affecting edges must have at least one
        AffectedEntity with entity_type='relationship' or entity_type='document'
        so Split 03 knows which graph edge/node to annotate."""


class TestHierarchyOverlaySupport:
    """Split 03 renders visual grouping of documents by controlling authority."""

    def test_hierarchy_findings_have_category(self, sample_analysis_results):
        """Hierarchy findings include category values that Split 03 uses
        for overlay rendering: controlling_authority, dual_authority_conflict,
        inferred_hierarchy, explicit_hierarchy."""


class TestTermFlowPathSupport:
    """Split 03 renders lines showing defined term travel across documents."""

    def test_defined_term_findings_reference_terms(self, sample_analysis_results):
        """Defined term findings include AffectedEntity entries with
        entity_type='defined_term', providing the term ID that Split 03
        uses to draw flow paths between documents."""


class TestMissingDocumentIndicatorSupport:
    """Split 03 renders dashed-outline nodes for referenced but absent documents."""

    def test_missing_document_findings_identifiable(self, sample_analysis_results):
        """Findings with category='missing_document' can be identified
        and their affected_entities contain the document_id of the
        missing document, which Split 03 renders as a dashed node."""


class TestExecutionChecklistSupport:
    """Split 03 renders a step-by-step closing checklist."""

    def test_execution_findings_have_display_ordinal(self, sample_analysis_results):
        """Execution sequence findings have display_ordinal set,
        which Split 03 uses to order the closing checklist steps."""
```

---

## Implementation Details

### Schema Contract Documentation

The file `src/semantic_analysis/visualization_contract.py` serves two purposes: (1) human-readable documentation of what Split 03 expects, and (2) a runtime validator that checks a `deal-analysis.json` file against the contract.

The module should contain:

**A `VISUALIZATION_CONTRACT` constant** -- a dictionary documenting each visualization feature and the schema fields it requires:

```python
VISUALIZATION_CONTRACT = {
    "conflict_markers": {
        "description": "Red/yellow/blue icons on edges colored by severity",
        "requires": {
            "analysis_key": "conflicts",
            "finding_fields": ["severity", "affected_entities"],
            "entity_types": ["relationship", "document"],
            "severity_to_color": {"CRITICAL": "red", "ERROR": "yellow", "WARNING": "blue"},
        },
    },
    "hierarchy_overlays": {
        "description": "Visual grouping of documents by controlling authority",
        "requires": {
            "analysis_key": "hierarchy",
            "finding_fields": ["category", "affected_entities"],
            "categories": [
                "controlling_authority",
                "dual_authority_conflict",
                "inferred_hierarchy",
                "explicit_hierarchy",
            ],
        },
    },
    "term_flow_paths": {
        "description": "Lines showing where defined terms travel across documents",
        "requires": {
            "analysis_key": "defined_terms",
            "finding_fields": ["affected_entities"],
            "entity_types": ["defined_term"],
        },
    },
    "missing_document_indicators": {
        "description": "Dashed-outline nodes for referenced but absent documents",
        "requires": {
            "analysis_key": "conflicts",
            "finding_fields": ["category", "affected_entities"],
            "categories": ["missing_document"],
        },
    },
    "execution_checklist": {
        "description": "Step-by-step closing checklist with conditions and dependencies",
        "requires": {
            "analysis_key": "execution_sequence",
            "finding_fields": ["display_ordinal", "category", "affected_entities"],
        },
    },
}
```

**A `validate_for_visualization(analysis_results) -> list[str]` function** that takes an `AnalysisResults` object and returns a list of contract violation messages (empty list means the output is visualization-ready). The function should check:

1. All expected analysis keys are present in `analyses` dict
2. Every finding has non-empty `affected_entities`
3. Every `AffectedEntity` has `entity_type`, `entity_id`, and `document_id` populated
4. `entity_type` values are from the known set
5. `AnalysisSummary.by_severity` counts match actual findings
6. `severity` values are from the valid set (CRITICAL, ERROR, WARNING, INFO)
7. Conflict findings include entity references suitable for edge/node annotation
8. Hierarchy findings use known category values
9. Defined term findings reference `defined_term` entity types
10. Execution sequence findings have `display_ordinal` set

**Known constants:**

```python
KNOWN_ENTITY_TYPES = {"document", "relationship", "defined_term", "cross_reference", "condition_precedent"}
KNOWN_ANALYSIS_TYPES = {"hierarchy", "conflicts", "defined_terms", "conditions_precedent", "execution_sequence"}
SEVERITY_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO"}
```

### Standalone Report View Requirements

Split 03 expects to render these standalone views from the data:

| View | Data Source | Required Fields |
|------|-------------|-----------------|
| Conflict report | `analyses["conflicts"].findings` | `severity`, `category`, `title`, `description`, `affected_entities[].document_id` |
| Term registry | `analyses["defined_terms"].findings` | `category`, `title`, `affected_entities[]` with `entity_type="defined_term"` |
| Execution checklist | `analyses["execution_sequence"].findings` | `display_ordinal`, `category`, `title`, `affected_entities` |
| Hierarchy tree | `analyses["hierarchy"].findings` | `category`, `affected_entities[].document_id`, `affected_entities[].section` |

### Filtering and Navigation Requirements

Split 03 supports three filtering axes:

1. **Filter by severity** -- `Finding.severity` field enables partitioning into CRITICAL/ERROR/WARNING/INFO
2. **Filter by document** -- `AffectedEntity.document_id` field enables showing all findings that touch a given document
3. **Filter by analysis type** -- `analyses` dict keys enable tab-based navigation between analysis types

### Click-to-highlight Requirement

When a user clicks a finding in Split 03, the visualization highlights the affected entities on the graph. This requires:
- `AffectedEntity.entity_id` matches an ID in `deal-graph.json`
- `AffectedEntity.entity_type` tells the renderer whether to highlight a node, edge, or label
- `AffectedEntity.section` (when present) enables section-level highlighting within a document node

### Integration with Workflow Orchestration

The `validate_for_visualization` function should be called at the end of the workflow orchestration (section-10) after writing `deal-analysis.json`. If violations are found, they should be logged as warnings but should not prevent the file from being written.

```python
from semantic_analysis.visualization_contract import validate_for_visualization

violations = validate_for_visualization(results)
if violations:
    for v in violations:
        logger.warning(f"Visualization contract violation: {v}")
```

---

## Summary of Finding Categories by Analysis Type

For reference, these are the complete finding category values that Split 03 expects to handle:

**hierarchy**: `controlling_authority`, `dual_authority_conflict`, `inferred_hierarchy`, `explicit_hierarchy`

**conflicts**: `dangling_reference`, `circular_reference`, `contradictory_provision`, `missing_document`, `stale_reference`, `ambiguous_section_ref`

**defined_terms**: `conflicting_definition`, `orphaned_definition`, `undefined_usage`, `cross_document_dependency`, `enhanced_term`

**conditions_precedent**: `circular_condition`, `critical_path_item`, `missing_condition_document`, `parallel_group`

**execution_sequence**: `signing_dependency`, `parallel_execution_window`, `gating_condition`, `critical_path_step`
