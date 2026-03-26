# Interactive Visualization & Export — Complete Specification

## 1. Overview

Build a single self-contained HTML file that renders an interactive legal document dependency graph. Claude Code generates this file with deal data embedded, and the user opens it in a browser to explore, analyze, and export their deal structure.

**Key constraints:**
- Single HTML file with all JS/CSS inline and libraries loaded via CDN
- Claude Code embeds `deal-graph.json` and `deal-analysis.json` data directly into the HTML
- No server required — pure client-side rendering
- No external service calls — all AI processing happens via Claude Code separately
- User audience: solo legal professional, not developers
- V1 is **view-only + PDF export** — browser editing deferred to later phase

## 2. Architecture

### Data Flow
```
Claude Code extraction (Split 01) → deal-graph.json
Claude Code analysis (Split 02)  → deal-analysis.json
Claude Code generates HTML with both files embedded as JS variables
User opens HTML in browser → views graph, explores data, exports PDF
User describes edits to Claude Code conversationally
Claude Code regenerates HTML with updated data
```

### Technology Stack
- **Graph library:** Cytoscape.js (replacing D3.js from prototype)
- **Layouts:** cytoscape-dagre (hierarchy), cytoscape-cola (force-directed), breadthfirst (tree)
- **PDF export:** cytoscape-svg + svg2pdf.js + jsPDF + jspdf-autotable
- **No build step** — CDN script tags for all dependencies

### CDN Dependencies
```html
<!-- Core -->
<script src="https://unpkg.com/cytoscape/dist/cytoscape.min.js"></script>

<!-- Layouts -->
<script src="https://unpkg.com/dagre@0.7.4/dist/dagre.js"></script>
<script src="https://unpkg.com/cytoscape-dagre/cytoscape-dagre.js"></script>
<script src="https://unpkg.com/cytoscape-cola/cytoscape-cola.js"></script>

<!-- PDF Export -->
<script src="https://unpkg.com/jspdf/dist/jspdf.umd.min.js"></script>
<script src="https://unpkg.com/svg2pdf.js/dist/svg2pdf.umd.min.js"></script>
<script src="https://unpkg.com/jspdf-autotable/dist/jspdf.plugin.autotable.min.js"></script>
```

### Data Embedding Pattern
Claude Code generates the HTML file with data embedded as JavaScript variables:
```javascript
const DEAL_GRAPH = { /* contents of deal-graph.json */ };
const DEAL_ANALYSIS = { /* contents of deal-analysis.json */ };
```
The app reads these variables on load — no file picker needed for the primary workflow.

## 3. Input Data Schemas

### deal-graph.json (from Split 01)
```
DealGraph
├── schema_version: "1.0.0"
├── deal: { name, deal_type, parties_summary, status, dates }
├── parties: dict[party_id → Party]
├── documents: dict[doc_id → Document]
│   └── Document: { id, name, document_type (21 types), parties, execution_date_iso,
│       status (draft/executed/amended), key_provisions, summary, obligations,
│       source_file_path, file_hash, extraction metadata, ai_original_values, is_manual }
├── relationships: list[Relationship]
│   └── Relationship: { id, source_document_id, target_document_id, relationship_type (16 types),
│       source_reference, evidence {quote, page}, confidence (high/medium/low),
│       is_manual, needs_review, description }
├── defined_terms: list[DefinedTerm]
│   └── { id, term, defining_document_id, section_reference, definition_snippet,
│       used_in_document_ids, confidence }
├── cross_references: list[CrossReference]
│   └── { id, source_document_id, source_section, target_document_id, target_section,
│       reference_text, evidence, confidence, needs_review }
├── conditions_precedent: list[ConditionPrecedent]
│   └── { id, description, source_document_id, source_section, required_document_id,
│       enables_document_id, status (pending/satisfied/waived), confidence }
├── annotations: list[Annotation]
│   └── { id, entity_type, entity_id, note, flagged, created_at, updated_at }
└── extraction_log: list[ExtractionEvent]
```

**16 Relationship Types:** controls, references, subordinates_to, defines_terms_for, triggers, conditions_precedent, incorporates, amends, assigns, guarantees, secures, supersedes, restricts, consents_to, indemnifies, restates.

**21 Document Types:** Purchase Agreement, Loan Agreement, Mortgage/Deed of Trust, Promissory Note, Guaranty, Security Agreement, Title Insurance Policy, Survey, Environmental Report, Closing Certificate, Legal Opinion, Assignment, Subordination Agreement, Estoppel Certificate, Side Letter, Amendment, Easement Agreement, Condominium Declaration, Lease Agreement, License Agreement, Construction Contract.

### deal-analysis.json (from Split 02)
```
AnalysisResults
├── schema_version: "1.0.0"
├── deal_graph_hash: SHA-256
├── analyses: dict[
│   "hierarchy" → AnalysisResult,
│   "conflicts" → AnalysisResult,
│   "defined_terms" → AnalysisResult,
│   "conditions_precedent" → AnalysisResult,
│   "execution_sequence" → AnalysisResult
│ ]
├── metadata: { model, timestamp, processing_time }
└── staleness: dict[analysis_type → StalenessRecord]
```

**Each Finding:** id, severity (CRITICAL/ERROR/WARNING/INFO), category, title, description, affected_entities (list of {entity_type, entity_id, document_id, section}), confidence, source, verified, display_ordinal.

**Severity rendering:** CRITICAL → red, ERROR → yellow/amber, WARNING → blue, INFO → gray.

## 4. Views & Layout

### 4.1 Default View: Dependency Graph (Dagre Hierarchy)

The primary view — an interactive dependency graph using dagre layout (top-to-bottom hierarchy).

**Nodes:**
- Each node = one document from deal-graph.json
- Sized by number of relationships (more connections = larger node)
- Colored by document_type using a consistent color palette
- Label shows document name (truncated if long, full name on hover)
- Badge/icon indicators for: needs_review items, manual entries, findings count

**Edges:**
- Each edge = one relationship
- Colored by relationship_type (extend prototype's 7-color scheme to cover all 16 types)
- Directional arrows showing source → target
- Edge labels showing relationship type (toggleable to reduce clutter)
- Line style varies: solid for high confidence, dashed for medium, dotted for low

**Interactions:**
- Zoom (scroll wheel), pan (click-drag on background), drag nodes to rearrange
- Click node → detail panel slides in from right (preserving prototype's useful sidebar pattern)
- Click edge → detail panel shows relationship details
- Hover node → highlight all connected edges and neighbor nodes
- Double-click node → focus mode (dim all non-connected nodes)

**Controls toolbar:**
- View mode switcher (Graph / Hierarchy / Timeline / Layout selector)
- Relationship type filter (checkboxes to show/hide by type)
- Search box (filter documents by name or type)
- "Show Issues" toggle (conflict overlay — see 4.4)
- Edge labels toggle (show/hide)
- Confidence filter (show only high, show medium+, show all)
- "Fit to screen" button
- PDF export button

### 4.2 Alternative Layout: Force-Directed (Cola)

Same nodes and edges as 4.1, but using cola.js constraint-based force-directed layout. Shows natural clustering of related documents rather than hierarchy. Useful for seeing document groups and density of relationships.

Switching layouts preserves all other state (selected node, active filters, etc.) — only the node positions change with an animated transition.

### 4.3 Timeline / Execution Sequence View

A simple sorted table showing the closing execution sequence, derived from the `execution_sequence` analysis results.

**Columns:**
- Sequence # (display_ordinal)
- Document name (linked — clicking scrolls/switches to that node in graph view)
- Dependencies (which documents must be signed first)
- Status (from conditions_precedent: pending/satisfied/waived)
- Gating conditions (from findings with category signing_dependency or gating_condition)

**Sorting:** Primary sort by display_ordinal. Secondary grouping by parallel execution windows (documents that can be signed simultaneously shown in the same group).

This is a data table, not a Gantt chart. Simple and scannable.

### 4.4 Conflict/Risk Overlay

Not a separate view — a toggle overlay on the graph view.

When "Show Issues" is toggled on:
- Nodes with findings get colored border rings: red (CRITICAL), amber (ERROR), blue (WARNING)
- Edges with findings get thickened and colored by severity
- A findings count badge appears on each affected node
- A summary panel appears at the bottom or in the sidebar showing: X critical, Y errors, Z warnings
- Clicking a finding badge in the sidebar highlights the affected nodes/edges on the graph

When toggled off, the graph returns to normal coloring.

## 5. Detail Panel (Right Sidebar)

Slides in when a node or edge is clicked. Preserves the prototype's useful sidebar pattern.

### Node Detail (Document)
- **Header:** Document name, type badge, status badge (draft/executed/amended)
- **Summary:** 2-3 sentence overview
- **Parties:** List of parties and their roles in this document
- **Key Provisions:** Expandable list of {section, title, summary, provision_type}
- **Obligations:** Key obligations list
- **Defined Terms:** Terms defined in this document, with links showing where each term is used
- **Relationships:** Grouped list — "This document controls: [X, Y]", "Referenced by: [A, B]"
- **Cross-References:** Sections referencing other documents
- **Conditions Precedent:** Conditions involving this document
- **Findings:** Any analysis findings affecting this document (severity badge + title + description)
- **Metadata:** Extraction timestamp, confidence, source file path

### Edge Detail (Relationship)
- **Header:** "Document A → Document B" with relationship type badge
- **Type:** Relationship type with description
- **Evidence:** Quote from source document, page reference
- **Confidence:** High/medium/low with visual indicator
- **Source Reference:** Section number in source document
- **Findings:** Any analysis findings affecting this relationship
- **Flags:** needs_review, is_manual indicators

## 6. Defined Term Flow

A specialized exploration within the graph view:
- When viewing a document's defined terms in the detail panel, clicking a term highlights:
  - The defining document (source node, bright highlight)
  - All documents using that term (target nodes, secondary highlight)
  - Edges connecting them (if defines_terms_for relationships exist)
- A small floating panel shows: "Term: [X] — Defined in [Doc A], used in [Doc B, Doc C, Doc D]"
- Clicking another term or clicking the background clears the highlight

## 7. PDF Export

Single "Export PDF" button in the toolbar. Generates a multi-page professional PDF.

### Page Structure
1. **Header:** Deal name, date generated, "Document Dependency Analysis"
2. **Graph snapshot:** Vector SVG export of the current graph view (via cytoscape-svg → svg2pdf.js)
3. **Document summary table:** All documents listed with type, status, party summary, key provision count (via jspdf-autotable)
4. **Relationship matrix or list:** All relationships with source, target, type, confidence
5. **Conflict/risk report:** All findings sorted by severity (CRITICAL first), each with title, description, affected documents
6. **Closing checklist:** Execution sequence table (same data as timeline view)

### Quality Requirements
- Vector graph rendering (not rasterized screenshot)
- Professional typography and spacing
- Tables with alternating row shading
- Severity badges rendered as colored markers
- Page numbers and headers on each page
- Letter-size (8.5 x 11") portrait orientation for tables, landscape for graph page

## 8. Search & Filtering

### Document Search
- Text input in toolbar filters nodes by name (case-insensitive substring match)
- Non-matching nodes fade/dim (not removed — user can still see graph context)
- Matching nodes highlighted with distinct border

### Relationship Type Filter
- Checkbox group showing all 16 relationship types with color swatches
- Unchecking a type hides those edges (nodes remain visible)
- "Show All" / "Show None" toggle buttons

### Confidence Filter
- Three-level toggle: All / Medium+ / High only
- Filters both edges (relationships) and node data (defined terms, cross-references)

### Document Type Filter
- Checkbox group showing document types present in this deal
- Unchecking hides those document nodes and their edges

## 9. Visual Design

### Color Palette for Document Types
Extend the prototype's color scheme to cover all 21 types. Use a professional palette suitable for legal context — avoid neon/bright colors. Muted blues, grays, warm tones.

### Relationship Type Colors
Extend the prototype's 7-color scheme to 16 types. Group related types by hue:
- Control/hierarchy relationships (controls, subordinates_to, supersedes): reds/oranges
- Reference relationships (references, incorporates, cross_references): blues
- Financial relationships (guarantees, secures, assigns, indemnifies): greens
- Modification relationships (amends, restricts, restates): purples
- Conditional relationships (triggers, conditions_precedent, consents_to): yellows/amber
- Term relationships (defines_terms_for): teal/cyan

### Typography
- Clean sans-serif font (system font stack or a loaded web font)
- Clear hierarchy: deal name > document names > metadata > body text
- Readable at default zoom level

### Responsive Considerations
- Graph canvas takes full available width/height
- Detail sidebar is a fixed-width overlay (e.g., 400px), doesn't squish the graph
- Toolbar collapses gracefully on smaller screens
- Minimum viable width: 1024px (legal professionals use desktops/large monitors)

## 10. Edge Cases & Error Handling

- **Empty deal:** If DEAL_GRAPH has no documents, show a friendly "No documents in this deal" message
- **No analysis results:** If DEAL_ANALYSIS is null or empty, disable the "Show Issues" toggle and timeline view; graph still works
- **Missing relationships:** Some documents may have no edges — they appear as isolated nodes
- **Long document names:** Truncate node labels with ellipsis, show full name on hover and in detail panel
- **Many edges between same nodes:** Multiple relationships between two documents shown as parallel edges or combined with a count badge
- **CDN failure:** If a CDN script fails to load, show a clear error message explaining the app requires internet for initial load

## 11. What's Deferred (Not in V1)

- **Browser editing** (add/remove/edit relationships, annotations, flagging) — user describes edits to Claude Code instead
- **JSON file picker / drag-and-drop loading** — data is embedded; no separate file I/O needed
- **Cover page / branding on PDF** — content first, branding later
- **Expand/collapse compound nodes** — deal sizes are 5-30 docs, manageable without clustering
- **Real-time collaboration** — single user tool
- **Dark mode** — light theme only for v1
- **Undo/redo** — not needed when view-only
