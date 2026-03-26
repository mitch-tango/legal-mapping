# Combined Specification — Data Model & Document Extraction

## 1. Overview

Design and build the foundational data model and extraction pipeline for a legal document dependency graph tool. This split produces:

1. A **JSON schema** (`deal-graph.json`) that captures documents, relationships, defined terms, conditions precedent, cross-references, and user annotations for a single real estate deal
2. A **document extraction pipeline** (Python scripts orchestrated by Claude Code) that reads PDF and Word documents and populates the graph via Claude's API
3. A **formalized relationship taxonomy** of 15 directional relationship types

This is the foundation — Split 02 (semantic analysis) and Split 03 (interactive visualization) depend entirely on the schema and extraction pipeline defined here.

## 2. Users & Context

- **Solo user:** Maitland Thompson, legal professional at New City Properties (real estate company)
- **Deal sizes:** 5–50 documents per deal; most documents are 3–30 pages, longest are 100+ pages
- **Document formats:** ~80% text-based PDFs (from Word/e-signing), ~20% scanned image PDFs, plus Word .docx drafts
- **Privacy:** Anthropic API acceptable (zero-retention policy). No third-party services. All data stored locally.
- **Top pain points:** (1) Following cross-reference chains across 3–4 documents, (2) Explaining deal structure to counsel/investors/partners

## 3. Architecture

```
[Word/PDF Documents on local filesystem]
    ↓
[Python extraction scripts (call Anthropic API)]
    ↓
[deal-graph.json — one per deal, in dedicated deal data folder]
    ↓
[HTML Visualization (Split 03) reads + writes back to same JSON]
    ↓
[Claude Code reads user edits on re-analysis]
```

**Data layout:** One `deal-graph.json` per deal, stored in a separate data folder (e.g., `deals/deal-name/deal-graph.json`). Source documents are referenced by file path.

**Extraction triggers:**
- **Single document:** User tells Claude Code to process a specific file path
- **Batch:** User points Claude Code at a folder of deal documents for initial setup

## 4. JSON Schema Requirements

### 4.1 Top-Level Structure

The graph file contains:
- **Deal metadata:** Deal name, parties, closing date, status, creation date
- **Documents (nodes):** Each document in the deal
- **Relationships (edges):** Typed, directional connections between documents
- **Defined terms:** Terms extracted from documents with source references
- **Cross-references:** Section-to-section references between documents
- **Conditions precedent:** What must be satisfied before what
- **User annotations:** Notes, flags, manual edits (stored separately from AI data)
- **Schema version:** For forward compatibility and migrations

### 4.2 Document Node Fields

- Unique ID (generated)
- Name / title
- Document type (from expanded type list — see §5)
- Parties (list, with canonical names and aliases)
- Execution date (if executed)
- Status: draft / executed / amended
- Source file path (relative to deal folder)
- Key provisions flagged (defaults, termination, closing conditions, reps & warranties)
- Extraction metadata: timestamp, model version, confidence
- Manual vs. auto-extracted flag

### 4.3 Relationship Edge Fields

- Source document ID → Target document ID (directional)
- Relationship type (from 15-type taxonomy — see §6)
- Source reference (section/clause number where relationship is established)
- Confidence: high / medium / low
- Manual vs. auto-extracted flag
- Description (brief text explaining the relationship)

### 4.4 Defined Terms

- Term text (e.g., "Borrower")
- Defining document ID + section reference
- List of document IDs that use the term
- No full definition text stored — reference only (look up in source doc)

### 4.5 Cross-References

- Source document ID + section reference
- Target document ID + section reference
- Reference text as it appears in the source (e.g., "as defined in Section 4.2 of the Loan Agreement")
- Confidence: high / medium / low

### 4.6 Conditions Precedent

- Condition description
- Source document ID + section reference
- What must be satisfied (document/action)
- What it enables (document/event that becomes effective)
- Status: pending / satisfied / waived

### 4.7 User Annotations

- Attached to any node, edge, term, or condition
- Fields: note text, flag (boolean), timestamp
- User edits to AI-extracted data stored as overrides (original AI data preserved underneath)

### 4.8 Schema Design Principles

- **Incremental updates:** Adding a document doesn't require reprocessing the graph
- **User edits coexist with AI data:** Separate `ai_extracted` and `user_annotations` namespaces
- **Schema versioning:** SemVer in graph metadata; `additionalProperties: true` for forward compat
- **Lean storage:** References only (no clause text, no full definition text)
- **Analysis attachment point:** Split 02 results attach to the graph as additional metadata

## 5. Document Types (Expanded)

Original 16 from prototype:
Joint Venture Agreement, Operating Agreement, Construction Loan Agreement, Guaranty (+ subtypes: Completion, Payment), Environmental Indemnity, Purchase and Sale Agreement, Ground Lease, Promissory Note, Deed of Trust, Loan Agreement, Intercreditor Agreement, Subordination Agreement, Management Agreement, Development Agreement, Title Policy, Organizational Documents

Added from interview:
Easement Agreement, Condominium Declaration, Lease Agreement, License Agreement, Construction Contract

The type list should be extensible — users may encounter types not listed here.

## 6. Relationship Taxonomy (15 types)

| # | Type | Meaning | Example |
|---|------|---------|---------|
| 1 | controls | Doc A governs/takes precedence over Doc B on an issue | JV Agreement controls capital call procedures in Operating Agreement |
| 2 | references | Doc A cites or mentions Doc B | Loan Agreement references Environmental Indemnity |
| 3 | subordinates_to | Doc A is contractually subordinate to Doc B | Ground Lease subordinates to Deed of Trust |
| 4 | defines_terms_for | Defined terms in Doc A flow into Doc B | Operating Agreement defines "Capital Account" used in JV Agreement |
| 5 | triggers | Events in Doc A activate obligations in Doc B | Default under Loan triggers obligations under Guaranty |
| 6 | conditions_precedent | Doc A must be satisfied before Doc B becomes effective | Title Policy must be delivered before Loan closes |
| 7 | incorporates | Doc A pulls in provisions by reference from Doc B | Deed of Trust incorporates Loan Agreement terms |
| 8 | amends | Doc A modifies specific provisions of Doc B | First Amendment amends Operating Agreement |
| 9 | assigns | Doc A transfers rights/obligations from Doc B | Assignment Agreement assigns Lease Agreement |
| 10 | guarantees | Doc A guarantees performance/payment obligations in Doc B | Guaranty guarantees Loan Agreement obligations |
| 11 | secures | Doc A provides security/collateral for Doc B | Deed of Trust secures Promissory Note |
| 12 | supersedes | Doc A entirely replaces Doc B | Amended & Restated OA supersedes Original OA |
| 13 | restricts | Doc A restricts rights or use established in Doc B | Easement restricts use rights in Ground Lease |
| 14 | consents_to | Doc A provides consent/approval for action in Doc B | Lender Consent consents to Assignment |
| 15 | indemnifies | Doc A provides indemnification for claims related to Doc B | Environmental Indemnity indemnifies Lender re: Loan |
| 16 | restates | Doc A restates Doc B (amended and restated) | A&R Loan Agreement restates Original Loan |

Note: `restates` added per user — distinct from `amends` (modifies specific provisions) and `supersedes` (entirely replaces). An A&R document both restates and supersedes.

The taxonomy should be extensible — users may need custom types for unusual deal structures.

## 7. Extraction Pipeline Requirements

### 7.1 Single Document Extraction

Input: File path (PDF or .docx) + existing deal graph (if any)
Output: Structured extraction result ready to merge into graph

**Extracts:**
- Document type, parties (with alias detection), execution date, status
- Defined terms (term name + section reference)
- Key provisions (defaults, termination, closing conditions, reps & warranties)
- Cross-references to other documents (with section references)
- Obligations (key obligations, 2-4 per document)
- Summary (2-3 sentences)

**Document handling:**
- PDFs: Send directly to Claude API (text-based PDFs work well; scanned PDFs use Claude's vision)
- Word .docx: Extract text with python-docx (preserves heading structure) → send as plain text
- Large documents (100+ pages): Chunking strategy needed (see §7.4)

### 7.2 Relationship Extraction (Smart Matching)

When adding a document to an existing graph:
- Use document type and extracted references to narrow which existing docs to compare against
- Don't compare against every document — smart matching only
- Match inferred document references against existing doc names/types
- Confidence-scored: high/medium/low

### 7.3 Incremental Graph Update

- Add new extraction results without losing user edits or prior extractions
- When re-extracting a document: prompt user whether to replace AI data or create a new version
- User annotations and manual overrides are never overwritten by re-extraction

### 7.4 Large Document Handling

For documents exceeding context window (~40-60 pages of dense legal text):
- **Structure-aware chunking:** Split on articles/sections/numbered clauses using heading detection
- **Overlap:** 20-25% at chunk boundaries for cross-reference detection
- **Map-reduce pattern:**
  1. MAP: Extract per chunk (defined terms, parties, references, obligations) tagged with position
  2. REDUCE: Synthesize into unified extraction (deduplicate, resolve cross-references, merge)
- Pass entity summary from adjacent chunks as context for inter-chunk dependencies

### 7.5 Batch Extraction

For initial deal setup:
- Accept a folder path containing deal documents
- Process each document sequentially (or with controlled parallelism)
- Build the graph incrementally — each document adds to the graph
- After all documents processed, run a relationship-linking pass across the full graph

### 7.6 Party Name Normalization

- Auto-detect canonical party names from preambles
- Map aliases across documents (e.g., "XYZ Corp" = "Borrower" = "Developer")
- Flag uncertain matches for user review
- Store canonical name + list of aliases per party

## 8. Implementation Approach

**Recommended: Hybrid Python scripts + Claude Code orchestration**

- **Python scripts** handle: file reading, .docx parsing, API calls to Claude, JSON schema validation, graph merging
- **Claude Code** handles: orchestration, user interaction, edge case resolution, prompting for re-extraction decisions

This gives repeatability (scripts) with flexibility (Claude Code for judgment calls).

## 9. Technical Considerations

- **Structured outputs:** Use Claude's `messages.parse()` with Pydantic models for reliable extraction
- **Prompt caching:** Enable for repeated analysis of the same document
- **Model selection:** Claude Sonnet for routine extraction (cost-effective), Opus for complex/ambiguous documents
- **Validation:** Schema validation on every graph write to catch extraction errors early
- **Error handling:** Graceful degradation — if extraction partially fails, save what succeeded and flag the rest

## 10. What This Split Does NOT Include

- Semantic analysis (hierarchy detection, conflict detection, term tracking) → Split 02
- Interactive visualization, editing UI, PDF export → Split 03
- Multi-user collaboration (solo user only)
- Document storage/management (user manages their own files)
