<!-- SPLIT_MANIFEST
01-data-model-extraction
02-semantic-analysis
03-interactive-visualization
END_MANIFEST -->

# Project Manifest — Legal Document Mapping Tool

## Overview

A legal document intelligence system for deal closings, built as a Claude Code workflow that produces an interactive HTML visualization. The system extracts relationships from deal documents (PDF/Word), analyzes them for hierarchy, conflicts, and dependencies, and renders an interactive semantic dependency graph.

**Architecture:** Claude Code (analysis engine) → JSON data model → Interactive HTML visualization (browser) → User edits sync back to JSON → Claude Code re-analyzes

## Split Structure

### 01-data-model-extraction
**Purpose:** Define the JSON schema for the document graph and build the extraction pipeline that reads PDF/Word documents into structured data.

**Key deliverables:**
- JSON schema for the document graph (documents, relationships, defined terms, conditions, metadata)
- Extraction prompts/workflow for Claude Code to process PDFs and Word documents
- Relationship type taxonomy (controls, references, subordinates_to, defines_terms_for, triggers, conditions_precedent, incorporates)
- Document metadata extraction (parties, defined terms, obligations, key provisions, cross-references)
- Incremental extraction (add documents to an existing graph without reprocessing everything)

**This is foundational — all other splits depend on the data model.**

### 02-semantic-analysis
**Purpose:** Build the analytical layer that examines the extracted graph to answer the five core questions: document hierarchy, defined term provenance, conditions precedent chains, cross-reference conflicts, and execution sequencing.

**Key deliverables:**
- Document hierarchy analysis (which doc controls what issue, subordination chains)
- Cross-reference conflict detection (inconsistent references, contradictory provisions, circular dependencies)
- Defined term tracking (where terms are born, where they travel, where they diverge)
- Conditions precedent chain mapping (what must be true before what)
- Execution sequence derivation (closing checklist from the dependency graph)
- Risk scoring and flagging
- Analysis results format that the visualization can render

### 03-interactive-visualization
**Purpose:** Build the HTML/JS application that renders the document graph, supports editing and annotation, and exports to PDF.

**Key deliverables:**
- Interactive graph visualization (explore relationship types, zoom, filter, highlight paths)
- Multiple view modes (graph view, hierarchy view, timeline/sequence view)
- Detail panel for document and relationship inspection
- Editing capabilities (add/modify relationships, annotate, add notes)
- Conflict and risk highlighting (visual markers for flagged issues)
- PDF export for sharing with counsel and internal staff
- Data persistence via JSON file (Claude Code reads/writes the same file)
- Responsive, polished UX suitable for a legal professional

## Dependencies

```
01-data-model-extraction  (foundational — no dependencies)
        |
        ├──→ 02-semantic-analysis  (depends on: data model schema)
        |
        └──→ 03-interactive-visualization  (depends on: data model schema, analysis output format)
```

- **01 → 02:** The analysis engine needs the data model schema to know what it's analyzing. It also needs the extraction pipeline to exist so there's data to analyze.
- **01 → 03:** The visualization needs the data model schema to render. It also needs to understand the analysis output format from 02 to display results.
- **02 ↔ 03:** The visualization displays analysis results, so 03 needs to know 02's output format. But these can be developed in parallel after 01 is complete, with an agreed-upon analysis results schema.

## Execution Order

1. **Start with 01-data-model-extraction** — This is foundational. The JSON schema design decisions here cascade to everything else.
2. **Then 02 and 03 in parallel** — Once the data model is defined, semantic analysis and visualization can proceed concurrently. Define the analysis output format as part of 01 or early in 02 so 03 can build against it.

## Cross-Cutting Concerns

- **Privacy:** All document processing via Anthropic API (acceptable per interview). No third-party services. Local file storage only.
- **Document formats:** Must handle both PDF and Word (.docx) documents.
- **Claude Code integration:** The entire system is orchestrated through Claude Code. Extraction and analysis are Claude Code workflows. The visualization is a generated HTML file.
- **Data file as integration point:** A single JSON file (e.g., `deal-graph.json`) is the integration point between Claude Code and the HTML visualization. Both read and write it.
- **Export:** PDF export from the visualization for sharing with counsel/staff.

## /deep-plan Commands

Run these in order:
```
/deep-plan @planning/01-data-model-extraction/spec.md
/deep-plan @planning/02-semantic-analysis/spec.md
/deep-plan @planning/03-interactive-visualization/spec.md
```
