<!-- PROJECT_CONFIG
runtime: python-uv
test_command: uv run pytest
END_PROJECT_CONFIG -->

<!-- SECTION_MANIFEST
section-01-schema-and-fixtures
section-02-graph-utilities
section-03-staleness-tracking
section-04-dependency-resolver
section-05-hierarchy-analysis
section-06-conflict-detection
section-07-defined-term-tracking
section-08-conditions-precedent
section-09-execution-sequence
section-10-workflow-orchestration
section-11-scale-handling
section-12-visualization-integration
END_MANIFEST -->

# Implementation Sections Index

## Dependency Graph

| Section | Depends On | Blocks | Parallelizable With |
|---------|------------|--------|---------------------|
| section-01-schema-and-fixtures | - | all | - |
| section-02-graph-utilities | 01 | 03, 04, 05, 06, 07, 08, 09 | - |
| section-03-staleness-tracking | 01, 02 | 10 | 04 |
| section-04-dependency-resolver | 01, 02 | 10 | 03 |
| section-05-hierarchy-analysis | 01, 02 | 06, 09 | 07, 08 |
| section-06-conflict-detection | 01, 02, 05 | 09 | 08 |
| section-07-defined-term-tracking | 01, 02 | - | 05, 08 |
| section-08-conditions-precedent | 01, 02 | 09 | 05, 07 |
| section-09-execution-sequence | 01, 02, 08 | - | - |
| section-10-workflow-orchestration | 01-09 | 11 | - |
| section-11-scale-handling | 01, 02, 10 | 12 | - |
| section-12-visualization-integration | 01, 10 | - | - |

## Execution Order

1. **section-01-schema-and-fixtures** (no dependencies)
2. **section-02-graph-utilities** (after 01)
3. **section-03-staleness-tracking**, **section-04-dependency-resolver** (parallel after 02)
4. **section-05-hierarchy-analysis**, **section-07-defined-term-tracking**, **section-08-conditions-precedent** (parallel after 02)
5. **section-06-conflict-detection** (after 05; can run parallel with 08)
6. **section-09-execution-sequence** (after 08)
7. **section-10-workflow-orchestration** (after all analyses)
8. **section-11-scale-handling** (after 10)
9. **section-12-visualization-integration** (after 10)

## Section Summaries

### section-01-schema-and-fixtures
Pydantic models for `deal-analysis.json`: AnalysisResults, AnalysisResult, Finding, AffectedEntity, StalenessRecord, AnalysisSummary. Content-derived stable ID generation. Shared pytest fixtures: minimal/medium/large deal graphs, mock Anthropic client, sample source documents. Maps to plan sections 1, 4 and TDD section 4.

### section-02-graph-utilities
Graph loading, canonicalization (deep sort for stable hashing), SHA-256 hash computation. Section reference normalization (1.01 <-> 1.1 fuzzy matching). Source document text retrieval using `source_path` from graph nodes. Prompt injection defense wrapper for Pass 2 source text. Maps to plan sections 2, 5 (canonicalization), 7 (section normalization).

### section-03-staleness-tracking
Staleness detection: compare current canonical graph hash against per-analysis stored hashes. Staleness rules engine mapping graph change types to affected analyses (including party changes affecting exec/CP/terms). Staleness reporting for user. Maps to plan section 5 and TDD section 5.

### section-04-dependency-resolver
Analysis dependency DAG with hard and soft dependencies. Topological sort into parallel execution batches. Auto-inclusion of missing prerequisites. Soft dependency handling (defined_terms enriches conflicts if available). Maps to plan section 3 and TDD section 3.

### section-05-hierarchy-analysis
Pass 1: Issue area discovery from graph with base taxonomy + deal-specific additions. Hierarchy detection via explicit language (high confidence) and document type conventions (medium confidence). Dual-authority conflict detection. Output: hierarchy trees per issue area with section citations. Maps to plan section 6 and TDD section 6.

### section-06-conflict-detection
Pass 1: Dangling reference detection with section normalization. Circular reference detection via directed graph cycle detection. Missing document alerts. Contradictory provision candidate generation (same issue area, overlapping terms, cross-references). Uses hierarchy results for severity calibration. Enriched by defined term data when available. Pass 2: Ranked candidate verification with top-K cap. Maps to plan section 7 and TDD section 7.

### section-07-defined-term-tracking
Phase 1: Baseline terms from graph. Phase 2: Enhancement pass finding cross-reference-defined terms, undefined capitalized usage, implicit definitions. Usage tracking across documents. Inconsistency detection (identical/equivalent/conflicting). Status classification (defined/orphaned/undefined/conflicting). Cross-document dependency detection. Maps to plan section 8 and TDD section 8.

### section-08-conditions-precedent
CP extraction from graph. DAG construction with explicit and inferred dependencies. Topological sort into parallel satisfaction levels. Critical path identification (longest chain). Cycle detection (CRITICAL findings). Missing document CP flagging. Maps to plan section 9 and TDD section 9.

### section-09-execution-sequence
Requires CP results. Layers signing, delivery, and cross-reference dependencies onto CP topological sort. Groups documents into parallel execution windows. Lists gating conditions per step. Critical path marking. Maps to plan section 10 and TDD section 10.

### section-10-workflow-orchestration
Main entry point: load graph, check staleness, resolve execution order, execute analyses, write results. Per-analysis execution flow (Pass 1 → candidate filtering → Pass 2 → write). Prompt design with cached system prompt. Tool use for structured output. Error handling (retry, partial save). Atomic file writes with lock file. Maps to plan sections 11, 12 and TDD sections 11, 12.

### section-11-scale-handling
Token estimation from graph JSON size. Automatic clustering trigger at 60% context window. Issue-area-based partitioning (not document type). Per-cluster analysis execution. Finding deduplication via stable content-derived IDs. Provenance tracking (found_in_clusters). Maps to plan section 13 and TDD section 13.

### section-12-visualization-integration
Schema contract documentation for Split 03. Verification that deal-analysis.json supports: conflict markers by severity, hierarchy overlays, term flow paths, missing document indicators, finding filtering by severity/document/type. Maps to plan section 14 and TDD section 14.
