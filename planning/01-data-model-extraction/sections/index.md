<!-- PROJECT_CONFIG
runtime: python-uv
test_command: uv run pytest
END_PROJECT_CONFIG -->

<!-- SECTION_MANIFEST
section-01-foundation
section-02-schema
section-03-extraction-models
section-04-document-readers
section-05-prompts
section-06-pipeline
section-07-graph-ops
section-08-cli
END_MANIFEST -->

# Implementation Sections Index

## Dependency Graph

| Section | Depends On | Blocks | Parallelizable |
|---------|------------|--------|----------------|
| section-01-foundation | - | all | Yes |
| section-02-schema | 01 | 03, 05, 07 | No |
| section-03-extraction-models | 01, 02 | 05, 06 | No |
| section-04-document-readers | 01 | 06 | Yes (with 02, 03) |
| section-05-prompts | 02, 03 | 06 | No |
| section-06-pipeline | 03, 04, 05 | 08 | No |
| section-07-graph-ops | 02 | 08 | Yes (with 03-06) |
| section-08-cli | 06, 07 | - | No |

## Execution Order

1. section-01-foundation (no dependencies)
2. section-02-schema (after 01)
3. section-03-extraction-models, section-04-document-readers (parallel after 02)
4. section-05-prompts (after 02, 03)
5. section-06-pipeline, section-07-graph-ops (parallel — 06 after 03+04+05, 07 after 02)
6. section-08-cli (after 06 AND 07)

## Section Summaries

### section-01-foundation
Project setup: directory structure, `pyproject.toml` with dependencies (anthropic, pydantic, python-docx, pypdf, pytest), `src/` package init files, test fixtures directory, `.env` template, deal directory scaffolding.

**Plan refs:** Section 2 (Project Structure), Section 7 (Dependencies)
**TDD refs:** Fixtures Needed

### section-02-schema
All Pydantic models for `deal-graph.json`: `DealGraph`, `DealMetadata`, `Document`, `Party`, `PartyReference`, `KeyProvision`, `Relationship`, `Evidence`, `DefinedTerm`, `CrossReference`, `ConditionPrecedent`, `Annotation`, `ExtractionMetadata`, `ExtractionEvent`. Schema versioning constant. Round-trip serialization.

**Plan refs:** Sections 3.1-3.12
**TDD refs:** Sections 3.1-3.11

### section-03-extraction-models
Pydantic models for extraction results: `DocumentExtractionResult`, `ExtractedParty`, `ExtractedTerm`, `RelationshipExtractionResult`, `ExtractedRelationship`. The 16-type relationship taxonomy as a constant with direction semantics, direction tests, extraction heuristics, and precedence rules. Normalizer utilities (party name normalization, common inversion patterns).

**Plan refs:** Sections 4 (Taxonomy), 5.3 (Extraction result schemas), 5.4 (Smart matching — normalizer portion)
**TDD refs:** Section 4, Section 5.3 (partial), Section 5.4 (partial)

### section-04-document-readers
PDF preflight with pypdf (text layer detection, page counting). DOCX text extraction with python-docx: Track Changes handling (accept all), heading hierarchy preservation, numbered lists, tables, bold/italic markers. Both readers return structured text ready for the extraction prompt.

**Plan refs:** Section 6 (DOCX Processing), plan section 5.2 (PDF preflight)
**TDD refs:** Section 6 (DOCX Processing), Section 7 (PDF Preflight)

### section-05-prompts
Extraction prompt templates: document extraction prompt (system message, untrusted content warning, output schema reference) and relationship linking prompt (system message, Document Index builder, taxonomy with direction tests). Prompt version hashing for reproducibility.

**Plan refs:** Section 5.3 (Extraction Prompts)
**TDD refs:** Section 5.3 (prompt-specific tests)

### section-06-pipeline
Single document extraction orchestrator: read document via appropriate reader, call Claude API with structured outputs (`messages.parse()`), return `DocumentExtractionResult`. Relationship linking: build Document Index from existing graph, call Claude API, return `RelationshipExtractionResult`. Smart matching logic (scoring references against existing documents). API retry with exponential backoff.

**Plan refs:** Sections 5.2 (Single Doc Flow), 5.4 (Smart Matching), 5.5 (Large Document Handling)
**TDD refs:** Sections 5.2, 5.4, 5.5

### section-07-graph-ops
Graph manager: CRUD operations on `deal-graph.json` (load, save with atomic write). Graph merger: merge extraction results into existing graph (documents, parties, terms, relationships, cross-references, CPs) with dedup and annotation preservation. Graph validator: schema validation on every write, semantic validation (referential integrity, no duplicate IDs, acyclic supersedes, directionality sanity checks, CP consistency).

**Plan refs:** Sections 5.8 (Graph Merge), 9 (Validation)
**TDD refs:** Sections 5.8, 9

### section-08-cli
CLI entry points: `extract-document` (single doc, conflict detection, `--resolve` flag), `extract-batch` (folder scan, sequential processing, relationship linking pass, party normalization), `validate-graph`, `show-graph-summary`. Re-extraction handling (detect by hash/path/name, replace vs. version modes, confidence downgrade). All commands return JSON, no stdin prompts.

**Plan refs:** Sections 8 (CLI Interface), 5.6 (Batch Extraction), 5.7 (Re-Extraction)
**TDD refs:** Sections 8, 5.6, 5.7
