# Research Findings: Interactive Visualization & Export

## Part 1: Codebase Analysis

### 1. Existing Prototype

**Location:** `Reference/Legal Mapping Idea.txt` — ~11,700 token single-file HTML app with D3.js.

**Strengths:**
- D3.js force-directed graph with zoom/pan/drag
- Dual-panel architecture: graph canvas + detail sidebar
- 7 relationship types with distinct colors (controls, references, subordinates_to, defines_terms_for, triggers, conditions_precedent, incorporates)
- Deal management, PDF upload via Claude API, metadata display
- Relationship management with confidence scoring (high/medium/low)
- LocalStorage persistence, color-coded 16-type document taxonomy
- Edge labels, context-aware detail panels

**Limitations needing resolution:**
- No analysis results integration (conflicts, hierarchy overlays)
- No multiple view modes (only force-directed)
- No PDF export
- Force-directed layout doesn't scale past ~30 nodes
- No defined-term flow or conditions precedent chain visualization
- UI is developer-oriented, not polished for legal professionals
- No annotation/flagging system
- Uses localStorage instead of JSON file I/O
- No conflict detection visualization

### 2. Data Model Schema (Split 01)

The visualization consumes `deal-graph.json`:

```
DealGraph
├── schema_version: "1.0.0" (SemVer)
├── deal: DealMetadata
├── parties: dict[party_id -> Party]
├── documents: dict[doc_id -> Document]
├── relationships: list[Relationship]
├── defined_terms: list[DefinedTerm]
├── cross_references: list[CrossReference]
├── conditions_precedent: list[ConditionPrecedent]
├── annotations: list[Annotation]
└── extraction_log: list[ExtractionEvent]
```

**Document Node fields:** id, name, document_type (21-type taxonomy), parties, execution_date_iso, status (draft/executed/amended), source_file_path, file_hash, key_provisions, summary, obligations, extraction metadata, ai_original_values, is_manual.

**16 Relationship Types:** controls, references, subordinates_to, defines_terms_for, triggers, conditions_precedent, incorporates, amends, assigns, guarantees, secures, supersedes, restricts, consents_to, indemnifies, restates.

**Each Relationship:** id, source_document_id → target_document_id (directional), relationship_type, source_reference, evidence {quote, page}, confidence (high/medium/low), is_manual, needs_review, description, extraction metadata.

**Defined Terms:** id, term, defining_document_id, section_reference, definition_snippet, used_in_document_ids, confidence.

**Cross-References:** id, source_document_id/section → target_document_id/section, reference_text, evidence, confidence, needs_review.

**Conditions Precedent:** id, description, source_document_id/section, required_document_id, enables_document_id, status (pending/satisfied/waived), confidence.

**Parties:** id, canonical_name, aliases, raw_names, entity_type, jurisdiction, deal_roles, confidence.

**User Annotations:** id, entity_type, entity_id, note, flagged, created_at, updated_at.

### 3. Semantic Analysis Results (Split 02)

The visualization consumes `deal-analysis.json`:

```
AnalysisResults
├── schema_version: "1.0.0"
├── deal_graph_hash: SHA-256 of deal-graph.json
├── analyses: dict[
│   "hierarchy" → AnalysisResult,
│   "conflicts" → AnalysisResult,
│   "defined_terms" → AnalysisResult,
│   "conditions_precedent" → AnalysisResult,
│   "execution_sequence" → AnalysisResult
│ ]
├── metadata: AnalysisMetadata
└── staleness: dict[analysis_type → StalenessRecord]
```

**Each Finding:** id, severity (CRITICAL/ERROR/WARNING/INFO), category, title, description, affected_entities (with entity_type, entity_id, document_id, section), confidence, source (explicit/inferred), verified, display_ordinal.

**Five Analysis Types:**
1. **Hierarchy** — controlling_authority, dual_authority_conflict, inferred/explicit hierarchy
2. **Conflicts** — dangling_reference, circular_reference, contradictory_provision, missing_document, stale_reference, ambiguous_section_ref
3. **Defined Terms** — conflicting_definition, orphaned_definition, undefined_usage, cross_document_dependency
4. **Conditions Precedent** — circular_condition, critical_path_item, missing_condition_document, parallel_group
5. **Execution Sequence** — signing_dependency, parallel_execution_window, gating_condition, critical_path_step (has display_ordinal for sequencing)

**Severity mapping:** CRITICAL → Red (blocks closing), ERROR → Yellow (needs amendment), WARNING → Blue (needs review), INFO → Gray.

### 4. Integration Points

**From deal-graph.json — Read:** document nodes, relationships, defined_terms, cross_references, conditions_precedent, parties. **Write back:** user annotations, manual relationship edits, confidence overrides. **Never write:** extraction metadata, ai_original_values (read-only).

**From deal-analysis.json — Read only:** findings grouped by analysis_type, affected_entities for graph highlighting, severity for coloring. User requests re-analysis via Claude Code rather than editing analysis directly.

**Feedback loop:** User edits graph → JSON modified → Claude Code detects via staleness tracking (graph hash) → re-runs analysis → updated deal-analysis.json → visualization reloads.

### 5. Existing Infrastructure

- No package.json, tsconfig.json, or test framework established
- Project structure is planning-focused across 3 splits
- Pattern: Schema-first development, TDD, modular architecture

---

## Part 2: Web Research

### Topic 1: Graph Library — D3.js vs Cytoscape.js vs vis.js

| Feature | **Cytoscape.js** | **D3.js** | **vis-network** | **Sigma.js** |
|---|---|---|---|---|
| Focus | Graph/network-specific | General data viz | Network viz | Large graph perf |
| Rendering | Canvas | SVG (default) | Canvas | WebGL |
| Bundle (min+gz) | ~112 KB | ~80 KB (core) | ~200 KB (standalone) | ~70 KB |
| Built-in layouts | 6+ (circle, grid, breadthfirst, concentric, cose, random) | None (build from d3-force) | Force-directed only | Requires graphology |
| Extension layouts | dagre, elk, cola, euler, fcose, klay | d3-dag, dagre | N/A | ForceAtlas2 |
| Interactions | All built-in (zoom, pan, pinch, box-select, drag) | Must be coded manually | Built-in | Built-in |
| Export | PNG built-in, SVG via extension, JSON serialization | SVG native, PNG via canvas | Canvas export | PNG via WebGL |
| Maintenance | Active (v3.33.1, 2025) | Active (v7.x) | Community-maintained (original deprecated) | Active (v3.x) |

**Recommendation: Cytoscape.js** — Purpose-built for graph visualization, richest layout ecosystem via CDN extensions, all interactions built in, compound nodes for grouping, reasonable size (~112 KB). D3.js requires significantly more development effort for the same features.

### Topic 2: Browser File System Access API

**Support:** Chrome/Edge 105+ only (~33% global coverage). Firefox and Safari do not support it and have no plans to. Does NOT work from `file://` protocol — requires secure context (HTTPS or localhost).

**Recommended approach:**
- **Loading:** `<input type="file">` + drag-and-drop via FileReader API (100% cross-browser, works from `file://`)
- **Saving:** Blob URL download triggering browser save dialog (100% cross-browser)
- **Progressive enhancement:** Layer File System Access API for Chrome/Edge users (feature-detect with `if ('showOpenFilePicker' in window)`) for smoother save-in-place UX

### Topic 3: Client-Side PDF Export

| Approach | Text Selectable? | SVG Quality | Tables | Bundle Size | Complexity |
|---|---|---|---|---|---|
| html2canvas + jsPDF | No (raster) | Decent (rasterized) | Good | ~400 KB | Low |
| **jsPDF + svg2pdf.js** | **Yes (vector)** | **Excellent (vector)** | Manual | ~300 KB | Medium |
| pdfmake | Yes (vector) | Must rebuild layout | Excellent | ~500 KB | Medium-High |
| @media print CSS | Yes (native) | Depends | Native | 0 KB | Low |

**Recommended hybrid approach:**
1. **Graph:** cytoscape-svg extension → SVG → svg2pdf.js → vector PDF (crisp at any zoom)
2. **Tables/text:** jsPDF + jspdf-autotable plugin for native PDF elements (selectable, searchable)
3. **Fallback:** `@media print` CSS for quick Ctrl+P backup

### Topic 4: Graph Layout Scalability (30-50+ nodes)

At 30-50 nodes, **all libraries perform well** — the differentiator is layout quality, not speed.

**Best layout algorithms:**
- **dagre** — Hierarchical/layered DAG, minimizes edge crossings, clean top-to-bottom flow. Perfect for dependency graphs. Simple API: `{ name: 'dagre', rankDir: 'TB' }`
- **ELK** — More configurable but larger bundle (~700 KB). Consider for very precise edge routing.
- **cola.js** — Constraint-based force-directed, good alternative view
- **fcose/cose-bilkent** — Compound spring embedder, good for grouped graphs

**Clustering strategies with Cytoscape.js:**
- **Compound nodes** — native grouping (e.g., by deal phase: Pre-Closing, Closing, Post-Closing)
- **cytoscape-expand-collapse extension** — click to expand/collapse groups with animation
- **Filtering** — `cy.$('node[status="complete"]').hide()` style show/hide
- **Focus mode** — `ele.neighborhood()` to highlight node + direct dependencies, dim rest
- **Layout switching** — `cy.layout({ name: 'dagre' }).run()` to toggle between views at runtime

### CDN Script Tags for Single HTML File

```html
<!-- Core -->
<script src="https://unpkg.com/cytoscape/dist/cytoscape.min.js"></script>

<!-- Layouts -->
<script src="https://unpkg.com/dagre@0.7.4/dist/dagre.js"></script>
<script src="https://unpkg.com/cytoscape-dagre/cytoscape-dagre.js"></script>
<script src="https://unpkg.com/cytoscape-cola/cytoscape-cola.js"></script>

<!-- Grouping -->
<script src="https://unpkg.com/cytoscape-expand-collapse/cytoscape-expand-collapse.js"></script>

<!-- SVG Export (for PDF) -->
<script src="https://unpkg.com/cytoscape-svg/cytoscape-svg.js"></script>

<!-- PDF Export -->
<script src="https://unpkg.com/jspdf/dist/jspdf.umd.min.js"></script>
<script src="https://unpkg.com/svg2pdf.js/dist/svg2pdf.umd.min.js"></script>
<script src="https://unpkg.com/jspdf-autotable/dist/jspdf.plugin.autotable.min.js"></script>
```

---

## Summary of Key Decisions

| Decision | Recommendation | Rationale |
|---|---|---|
| Graph library | **Cytoscape.js** | Purpose-built; best layout ecosystem; built-in interactions; CDN-friendly |
| Primary layout | **dagre** (via cytoscape-dagre) | Clean hierarchical DAG layout for dependency graphs |
| Alternative layouts | cola (force-directed), breadthfirst (tree) | Multiple views of same data |
| File loading | `<input type="file">` + drag-and-drop | Universal browser support |
| File saving | Blob URL download | Universal; FSAA as progressive enhancement for Chrome |
| PDF (graph) | cytoscape-svg → svg2pdf.js → jsPDF | Vector quality output |
| PDF (tables/text) | jsPDF + jspdf-autotable | Selectable, searchable text |
| Node grouping | Compound nodes + expand-collapse | Native progressive disclosure |
| Architecture | Single self-contained HTML file | Matches prototype pattern; no build step needed |

### Testing Considerations

No test framework exists. For a single-file HTML application:
- **Unit testing:** Could use a lightweight browser-based test runner, but given this is a generated HTML file, testing may be more practical via Claude Code validation (checking the HTML output renders correctly)
- **Integration testing:** Verify JSON loading/saving round-trips correctly
- **Visual testing:** Manual verification of graph rendering with sample deal data
- **Export testing:** Verify PDF output contains expected content
