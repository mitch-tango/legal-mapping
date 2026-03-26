# 01 — Data Model & Document Extraction

## Purpose

Design the JSON data model for the legal document dependency graph and build the extraction pipeline that reads PDF and Word documents into structured data via Claude Code.

This is the foundational split. Everything else — semantic analysis (split 02) and interactive visualization (split 03) — depends on the schema and extraction pipeline defined here.

## Context

See `requirements.md` in the project root for full project context. Key points:

- **Architecture:** Claude Code is the analysis engine. It processes documents and writes a JSON data file (`deal-graph.json`). An HTML visualization reads this file. User edits in the HTML app write back to the same file. Claude Code reads edits on re-analysis.
- **Users:** Solo user (legal professional at a real estate company) — building for own workflow first.
- **Document types:** Mix of PDF (executed/final) and Word (.docx, drafts in negotiation). Real estate deal documents: JV agreements, operating agreements, loan agreements, guaranties, environmental indemnities, PSAs, ground leases, notes, deeds of trust, intercreditor agreements, subordination agreements, management agreements, development agreements, title policies, organizational docs.
- **Privacy:** Anthropic API is acceptable. No third-party services. Local file storage only.

## Deliverables

### 1. JSON Schema for the Document Graph

Design the data model that captures:

- **Documents:** Name, type, parties, execution date, status (draft/executed), source file path
- **Defined terms:** Term text, defining document, definition text, documents that use the term
- **Relationships between documents:** Typed, directional edges with:
  - Relationship taxonomy: controls, references, subordinates_to, defines_terms_for, triggers, conditions_precedent, incorporates
  - Source reference (section/clause number where the relationship is established)
  - Confidence score (high/medium/low) for AI-extracted relationships
  - Manual vs. auto-extracted flag
  - Description of the relationship
- **Cross-references:** Specific section-to-section references between documents
- **Conditions precedent:** What must be satisfied in which document before what can occur
- **User annotations:** Notes, flags, and manual edits made in the visualization
- **Deal metadata:** Deal name, parties, closing date, status

The schema must support:
- Incremental updates (adding documents without reprocessing the entire graph)
- User edits coexisting with AI-extracted data (manual overrides, annotations)
- Analysis results from split 02 being stored/attached to the graph

### 2. Document Extraction Pipeline

Claude Code workflows that process documents and populate the graph:

- **Single document extraction:** Read one PDF or Word doc, extract metadata (parties, defined terms, obligations, key provisions, cross-references to other documents)
- **Relationship extraction:** When adding a document to an existing graph, identify relationships to documents already in the graph
- **Incremental graph update:** Add extraction results to the existing JSON file without losing user edits or prior extractions
- **Batch extraction:** Process multiple documents for a new deal

Technical considerations:
- PDF text extraction (Claude can read PDFs directly via the API)
- Word document text extraction (.docx parsing)
- Prompt engineering for reliable, structured extraction
- Handling large documents (may exceed context window — chunking strategy)
- Extraction quality validation (what does "good enough" look like?)

### 3. Relationship Type Taxonomy

Formalize the relationship types with clear definitions and extraction heuristics:

| Type | Meaning | Example |
|------|---------|---------|
| controls | Doc A governs/takes precedence over Doc B on an issue | JV Agreement controls capital call procedures referenced in Operating Agreement |
| references | Doc A cites or mentions Doc B | Loan Agreement references Environmental Indemnity |
| subordinates_to | Doc A is contractually subordinate to Doc B | Ground Lease subordinates to Deed of Trust |
| defines_terms_for | Defined terms in Doc A flow into and are used by Doc B | Operating Agreement defines "Capital Account" used in JV Agreement |
| triggers | Events in Doc A activate obligations in Doc B | Default under Loan Agreement triggers obligations under Guaranty |
| conditions_precedent | Doc A must be satisfied/delivered before Doc B becomes effective | Title Policy must be delivered before Loan Agreement closes |
| incorporates | Doc A pulls in provisions by reference from Doc B | Deed of Trust incorporates Loan Agreement terms by reference |

## Dependencies

- **Provides to 02-semantic-analysis:** The JSON schema and populated graph data for analysis
- **Provides to 03-interactive-visualization:** The JSON schema that the HTML app reads and renders
- **No upstream dependencies** — this is the foundation

## Key Design Decisions for /deep-plan

- How to handle documents that exceed Claude's context window (chunking vs. summarization)
- Schema versioning strategy (as the model evolves)
- How user edits and AI extractions coexist without conflicts
- Whether to store the full extracted text or just references/summaries
- How to handle re-extraction when a document is updated (new draft version)

## Reference

The prototype HTML file at `Reference/Legal Mapping Idea.txt` contains a working extraction prompt and relationship taxonomy. It's a useful reference for the extraction approach but was designed for a different architecture (client-side API calls, localStorage).
