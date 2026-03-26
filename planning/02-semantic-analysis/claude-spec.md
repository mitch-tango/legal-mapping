# Semantic Analysis Engine — Synthesized Specification

## Overview

Build the analytical layer that examines the extracted document graph (from Split 01) to answer five core questions about deal document relationships. The analysis engine is implemented as **Claude Code workflows** — not Python CLI scripts — that read the graph JSON, call the Claude API with structured analysis prompts, and write results to a companion file (`deal-analysis.json`).

## Architecture

### Integration with Split 01

- **Input:** `deal-graph.json` produced by Split 01's extraction pipeline
- **Output:** `deal-analysis.json` — a companion file that references entities in the graph by ID
- **The analysis engine never modifies `deal-graph.json`** — it only reads it
- **Source documents** are accessed only for targeted verification (Pass 2), not bulk loading

### Claude Code Workflow Pattern

Each analysis is a Claude Code workflow that:
1. Reads `deal-graph.json` into context
2. Constructs a structured analysis prompt with the relevant graph data
3. Calls Claude API (single call for graph analysis, targeted follow-ups for verification)
4. Parses structured output
5. Writes/updates results in `deal-analysis.json`

No Python CLI scripts are needed for the analysis layer. Claude Code handles all orchestration, API calls, and file I/O directly.

### Two-Pass Analysis Strategy

**Pass 1 — Graph Analysis:** Send the full structured graph JSON in a single Claude API call. The graph data for a 20-document deal is ~50K-100K tokens, well within Claude's context window. This pass identifies candidate findings (conflicts, hierarchy relationships, term issues, etc.).

**Pass 2 — Targeted Verification:** For flagged candidates where source text verification would improve confidence, make small targeted API calls pulling only the relevant document sections. This avoids context degradation from loading all raw documents.

## Five Analysis Types

### Analysis Dependency Graph

```
Document Hierarchy ──────────────┐
  (standalone)                   ├──→ Cross-Reference Conflicts
                                 │      (uses hierarchy results)
Defined Term Tracking            │
  (standalone)                   │
                                 │
Conditions Precedent ────────────┤
  (standalone)                   └──→ Execution Sequence
                                        (requires CPs)
```

**Smart dependency execution:** User selects which analyses to run. If they select an analysis with prerequisites, the prerequisites auto-run first. For example, selecting "Cross-Reference Conflicts" automatically runs "Document Hierarchy" first.

### 1. Document Hierarchy Analysis (HIGH PRIORITY)

Determine which document controls which issues and the subordination chain.

**Inputs:** Graph documents, relationships (especially `controls`, `subordinates_to`, `incorporates`), document type metadata.

**Process:**
- Identify legal issue areas from document content (capital calls, default remedies, distribution waterfall, management authority, transfer restrictions, etc.)
- For each issue area, determine the controlling document using:
  - **Explicit language:** "governed by", "subject to the terms of", "in accordance with" (high confidence)
  - **Document type conventions:** e.g., Guaranty inherently subordinate to guaranteed obligation, Deed of Trust subordinate to Promissory Note (lower confidence, flagged as inferred)
- Map the hierarchy: controlling doc → documents that defer → documents that merely reference
- Detect provisions where two documents both claim authority on the same issue

**Output per issue area:**
- Hierarchy tree with controlling document at root
- Confidence level (high for explicit language, medium for inferred from conventions)
- Section-level citations for each hierarchy relationship
- Conflicts where multiple documents claim authority (severity: ERROR or CRITICAL)

### 2. Cross-Reference Conflict Detection (HIGH PRIORITY)

Find inconsistencies between documents that create legal risk.

**Inputs:** Graph cross-references, relationships, defined terms, hierarchy results from Analysis 1.

**Process:**
- Catalog all cross-references between documents (Doc A §3.2 references Doc B §7.1)
- Validate referenced sections exist in the graph (detect dangling references)
- Detect circular reference chains (A→B→A)
- Use hierarchy context: conflicts in controlling documents are more severe than conflicts in subordinate documents
- **Pass 2 verification:** For potential contradictions, pull the specific sections from source documents to confirm

**Findings classified by severity:**

| Severity | Criteria | Examples |
|----------|----------|----------|
| CRITICAL | Blocks closing or creates legal invalidity | Missing required exhibit; undefined party in key provision; circular condition precedent |
| ERROR | Substantive inconsistency requiring amendment | Conflicting dates; inconsistent defined terms across documents; dangling reference to non-existent section |
| WARNING | Potential issue requiring human review | Implicit reference ambiguity; near-duplicate definitions with subtle differences |
| INFO | Cosmetic or informational | Style inconsistencies; cross-reference that could be simplified |

**Missing document detection:** When a cross-reference points to a document not in the deal set, flag it prominently as a missing document so the user can upload it or acknowledge it's out of scope.

**Output:**
- Conflict report with severity, affected documents, section-level citations, description
- Missing document alerts
- Circular reference chains
- Dangling reference list

### 3. Defined Term Tracking

Map the provenance and usage of defined terms across the document set.

**Inputs:** Graph defined_terms (from Split 01 extraction), plus a deeper analysis pass.

**Process:**
- Start with terms already extracted by Split 01 as baseline
- Perform a focused deeper pass to catch terms that extraction may have missed (especially terms defined implicitly or by cross-reference to another document)
- For each term, map: where defined ("birth" document and section) → where used in other documents
- Detect inconsistencies: same term defined differently in different documents
- Detect orphaned definitions (defined but never used in operative provisions)
- Detect undefined usage (term used in capitalized form but never formally defined)
- Detect cross-document dependency: term defined in Doc A, used in Doc B without proper incorporation

**Term status classification:** defined | undefined | orphaned | conflicting

**Output:**
- Term registry with definition source, all usage locations, status
- Inconsistency flags with severity (ERROR for substantive conflicts, WARNING for subtle differences, INFO for style variations)

### 4. Conditions Precedent Chain Mapping

Map the dependency chains for closing conditions.

**Inputs:** Graph conditions_precedent entities, relationships of type `conditions_precedent` and `triggers`.

**Process:**
- Extract all conditions precedent from the graph
- Build dependency DAG: what must be satisfied before what
- Use topological sorting to determine valid satisfaction order
- Identify parallel execution windows (conditions with no mutual dependencies)
- Calculate critical path (longest sequential chain)
- Detect circular conditions (impossible to satisfy) using cycle detection
- Flag conditions that reference documents not in the deal set

**Output:**
- Ordered list of conditions with dependencies
- Parallel execution groupings
- Critical path highlighted
- Circular dependency alerts (severity: CRITICAL)
- Missing document conditions

### 5. Execution Sequence Derivation

Derive the closing checklist from the dependency graph.

**Inputs:** Conditions precedent results from Analysis 4, graph relationships, document metadata.

**Process:**
- Determine correct order for document execution based on CPs, cross-references, and dependencies
- Group documents that can be executed simultaneously (parallel windows)
- Identify signing dependencies (Doc A must be signed before Doc B)
- Map each step to the conditions that gate it

**Output:**
- Execution order with parallel groupings
- Per-step conditions that must be met
- Signing dependencies
- Critical path through the execution sequence

## Analysis Results Format (deal-analysis.json)

### Design Principles

- **Companion file:** Separate from `deal-graph.json` — keeps extraction data clean
- **References by ID:** All references to documents, relationships, terms, etc. use IDs from the graph
- **Incremental updates:** Re-running one analysis replaces only that analysis's results, preserving others
- **Staleness tracking:** Each analysis records what graph version it was run against; edits to the graph mark affected analyses as stale
- **Metadata:** When run, which documents were included, analysis engine version

### Top-Level Structure

```json
{
  "schema_version": "1.0.0",
  "deal_graph_hash": "<SHA-256 of deal-graph.json at analysis time>",
  "analyses": {
    "hierarchy": { ... },
    "conflicts": { ... },
    "defined_terms": { ... },
    "conditions_precedent": { ... },
    "execution_sequence": { ... }
  },
  "metadata": {
    "last_full_analysis": "<ISO timestamp>",
    "documents_included": ["<doc_id>", ...],
    "engine_version": "1.0.0"
  },
  "staleness": {
    "hierarchy": { "is_stale": false, "last_run": "<ISO timestamp>", "stale_reason": null },
    "conflicts": { "is_stale": true, "last_run": "<ISO timestamp>", "stale_reason": "document added: doc_xyz" }
  }
}
```

### Analysis Result Structure (per analysis type)

Each analysis result contains:
- `findings`: Array of individual findings
- `summary`: High-level summary statistics (counts by severity, key findings)
- `metadata`: When run, documents included, model used

Each finding contains:
- `id`: Unique finding ID
- `severity`: CRITICAL | ERROR | WARNING | INFO
- `category`: Analysis-specific category (e.g., "dangling_reference", "circular_chain", "conflicting_definition")
- `title`: Short description
- `description`: Detailed explanation
- `affected_entities`: Array of `{entity_type, entity_id, document_id, section}` references
- `confidence`: high | medium | low
- `source`: "explicit" | "inferred" (for hierarchy analysis)

### Visualization Integration

The analysis results format supports rendering by Split 03 as:
- **Graph annotations:** Conflict markers on edges, hierarchy overlays on nodes
- **Standalone reports:** Conflict report, term registry, execution checklist
- **Filtered views:** Show only CRITICAL/ERROR findings, filter by document, filter by analysis type

## Re-Analysis and Staleness

### Staleness Detection

When the graph changes (document added/removed/updated, relationship modified, term edited), the system marks affected analyses as stale:

- **Document added/removed:** All analyses become stale
- **Relationship modified:** Hierarchy, conflicts become stale
- **Term modified:** Defined terms analysis becomes stale
- **CP modified:** Conditions precedent, execution sequence become stale

### User-Triggered Re-Run

The system tracks and displays staleness, but the user decides when to re-run. This avoids unnecessary API costs and lets the user batch edits before re-analyzing.

## Scale Handling

### Optimized for 10-20 Documents

The primary design target is medium-sized deals (10-20 documents). The structured graph JSON for this size is well within a single Claude API call.

### Handling Larger Deals (20-40+ Documents)

For very large deals:
- Pass 1 (graph analysis) still works in a single call — the graph JSON is compact even for 40+ docs
- Pass 2 (targeted verification) scales naturally — only flagged issues trigger follow-up calls
- If graph JSON exceeds context limits: partition by document clusters (e.g., loan docs, equity docs, property docs) and merge results

### Handling Small Deals (5-10 Documents)

Small deals get the same treatment but complete faster with fewer API calls (fewer candidates to verify in Pass 2).

## Privacy and Security

- All processing via Anthropic API (acceptable per privacy requirements)
- No third-party services
- System prompt marks document text as untrusted content
- Analysis results stored locally alongside the graph
