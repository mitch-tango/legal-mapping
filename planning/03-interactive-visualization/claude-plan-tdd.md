# TDD Plan: Interactive Visualization & Export

## Testing Approach

This is a single self-contained HTML file with no build system. Traditional unit test frameworks (jest, vitest) don't apply. Testing takes three forms:

1. **Inline console assertions** — Small self-test functions embedded in the app code behind a `DEBUG` flag. Claude Code can set `const DEBUG = true;` to run validation on load, then set it to `false` for production.
2. **Claude Code validation** — Claude Code reads the generated HTML and programmatically verifies structure, data embedding, and script presence.
3. **Manual visual verification** — Open in browser with sample data fixtures and verify rendering.

Sample data fixtures (JSON files) are the primary test infrastructure. Each fixture exercises specific scenarios.

---

## 1. HTML Skeleton + CSS Layout

### Tests to write BEFORE implementing:
- Test: Toolbar element exists and contains expected child containers (view switcher, layout switcher, search, toggles, filter, reset, export)
- Test: Graph container element exists and fills remaining viewport height
- Test: Detail panel element exists, starts hidden (display:none or off-screen)
- Test: Timeline container element exists, starts hidden
- Test: All containers have correct CSS class names matching the plan's structure
- Test: @media print stylesheet hides toolbar and sidebar (verify computed styles)
- Test: Minimum width behavior — no layout break at 1024px

### Fixtures needed:
- None (static HTML structure only)

---

## 2. Data Adapter

### Tests to write BEFORE implementing:
- Test: `getCytoscapeElements()` returns `{ nodes: [...], edges: [...] }` with correct Cytoscape format
- Test: Each node has `data.id`, `data.label`, `data.docType`, `data.status` populated from DEAL_GRAPH.documents
- Test: Each edge has deterministic ID in format `${source}::${relType}::${target}::${index}`
- Test: Edge `data.source` and `data.target` match valid document IDs
- Test: Node classes include document type category (e.g., `category-financial`, `category-primary`)
- Test: Edge classes include relationship type and confidence level
- Test: `getDocumentDetails(docId)` returns full document object for valid ID, null for invalid
- Test: `getRelationshipTypes()` returns deduplicated array of types present in data
- Test: `getDocumentTypes()` returns deduplicated array of document types present
- Test: `getFindingsForEntity('document', docId)` returns only findings matching that entity
- Test: `getFindingsSummary()` returns correct counts by severity
- Test: `getExecutionSequence()` returns ordered array from DEAL_ANALYSIS, or empty array if no analysis
- Test: `getDefinedTermFlow(termId)` returns `{ definingDoc, usingDocs }` structure
- Test: Orphaned findings (referencing non-existent doc IDs) are silently pruned, not included in output
- Test: Handles DEAL_ANALYSIS = null gracefully (all analysis methods return empty/default values)
- Test: Handles empty documents array (returns empty nodes/edges arrays)
- Test: Detects cyclic dependencies and marks those edges with `cycle` class

### Fixtures needed:
- `fixture-small.json` — 5 docs, 8 relationships, 2 findings
- `fixture-null-analysis.json` — valid graph, DEAL_ANALYSIS = null
- `fixture-orphaned-findings.json` — analysis references non-existent doc IDs
- `fixture-cycles.json` — documents with circular relationship references
- `fixture-empty.json` — empty documents array

---

## 3. Graph Rendering with Dagre

### Tests to write BEFORE implementing:
- Test: Cytoscape instance initializes without errors on the graph container
- Test: All nodes from DataAdapter are rendered (count matches)
- Test: All edges from DataAdapter are rendered (count matches)
- Test: Dagre layout positions nodes without overlap (no two nodes share identical x,y)
- Test: Node size scales with relationship count (high-degree node larger than low-degree)
- Test: Node size stays within bounds (min 40px, max 80px)
- Test: Node labels are truncated at 20 characters + ellipsis
- Test: Edge arrows are visible (target arrow shape is set)
- Test: Confidence affects edge line style (solid/dashed/dotted)
- Test: Zoom, pan, and drag interactions are enabled on the Cytoscape instance
- Test: Cyclic dependency edges render with red dashed style

### Fixtures needed:
- `fixture-medium.json` — 15 docs, 25 relationships, 10 findings (primary visual test)

---

## 4. Node/Edge Interaction + Detail Panel

### Tests to write BEFORE implementing:
- Test: Clicking a node fires the selection event and populates detail panel
- Test: Detail panel shows document name, type badge, status badge, summary
- Test: Detail panel shows parties, key provisions, obligations sections
- Test: Detail panel shows defined terms list (each clickable)
- Test: Detail panel shows relationships list for the selected document
- Test: Detail panel shows findings for the selected document (if analysis exists)
- Test: Clicking an edge populates detail panel with relationship details
- Test: Relationship detail shows source, target, type, confidence, evidence quote
- Test: All text content is rendered via textContent (not innerHTML) — verify no HTML tags are interpreted
- Test: Clicking background closes detail panel and clears highlight
- Test: Clicking X button closes detail panel
- Test: Panel slides in/out with CSS transition (has transition property set)
- Test: Node highlight dims non-neighbor nodes (opacity < 1)

### Fixtures needed:
- `fixture-medium.json` (reuse)
- `fixture-xss-test.json` — documents with HTML-like content in names/summaries (e.g., `<script>`, `<img onerror=...>`)

---

## 5. Alternative Layouts

### Tests to write BEFORE implementing:
- Test: Layout switcher dropdown contains Dagre, Force-directed, Tree options
- Test: Selecting "Force-directed" applies cola layout (node positions change)
- Test: Selecting "Tree" applies breadthfirst layout
- Test: Selecting "Dagre" returns to dagre layout
- Test: Layout transition is animated (animation duration > 0)
- Test: Selection state persists across layout switch
- Test: Filter state persists across layout switch
- Test: Overlay state persists across layout switch

### Fixtures needed:
- `fixture-medium.json` (reuse)

---

## 6. Filtering

### Tests to write BEFORE implementing:
- Test: Relationship type filter checkboxes are generated from actual data (not hardcoded)
- Test: Unchecking a relationship type hides those edges
- Test: Hiding all edges of a type doesn't hide connected nodes
- Test: Document type filter checkboxes are generated from actual data
- Test: Unchecking a document type hides those nodes AND all their incident edges
- Test: Confidence filter at "High only" hides medium and low confidence edges
- Test: Confidence filter at "Medium+" hides low confidence edges
- Test: Search box dims non-matching nodes in real-time
- Test: Search matches against document name (case-insensitive)
- Test: "Reset filters" button restores all checkboxes and clears search
- Test: Visual state precedence: filtered nodes are removed, searched nodes are dimmed, highlighted nodes override dimming
- Test: Combining filters is additive (document type + relationship type + confidence all apply simultaneously)

### Fixtures needed:
- `fixture-medium.json` (reuse)

---

## 7. Analysis Overlay

### Tests to write BEFORE implementing:
- Test: "Show Issues" toggle is disabled when DEAL_ANALYSIS is null
- Test: Enabling overlay adds severity-colored border rings to affected nodes
- Test: Critical findings get red rings, error gets amber, warning gets blue, info gets gray
- Test: Finding count badges appear on nodes with findings
- Test: Summary panel shows correct counts (X critical, Y errors, Z warnings)
- Test: Disabling overlay removes all rings, badges, and summary
- Test: Clicking a finding in the detail panel highlights affected entities
- Test: Overlay state is independent of filter state (both can be active simultaneously)
- Test: Overlay decorations persist across layout changes

### Fixtures needed:
- `fixture-medium.json` (reuse — has 10 findings across severity levels)
- `fixture-null-analysis.json` (reuse — verify toggle disabled)

---

## 8. Defined Term Flow

### Tests to write BEFORE implementing:
- Test: Clicking a defined term in the detail panel triggers term flow visualization
- Test: Term flow highlights the defining document node distinctly
- Test: Term flow highlights all using document nodes
- Test: Term flow dims all unrelated nodes
- Test: Term flow detail shows term name, defining doc, list of using docs
- Test: Clicking background clears term flow highlight

### Fixtures needed:
- `fixture-terms.json` — deal with multiple defined terms, each used across several documents

---

## 9. Timeline View

### Tests to write BEFORE implementing:
- Test: View switcher shows "Graph" and "Timeline" options
- Test: Selecting "Timeline" hides graph canvas, shows timeline container
- Test: Timeline renders an HTML table with columns: Sequence #, Document Name, Dependencies, Status, Gating Conditions
- Test: Table rows match the execution sequence order from DEAL_ANALYSIS
- Test: Status badges render correctly (pending=yellow, satisfied=green, waived=gray)
- Test: Documents in same parallel execution window are visually grouped
- Test: Clicking a document name in the table switches back to graph view and selects that node
- Test: Timeline view shows "Execution sequence analysis not available" when no execution_sequence in DEAL_ANALYSIS
- Test: Switching back to Graph preserves previous graph state (filters, layout)

### Fixtures needed:
- `fixture-medium.json` (reuse)
- `fixture-null-analysis.json` (reuse — verify unavailable message)

---

## 10. PDF Export

### Tests to write BEFORE implementing:
- Test: Clicking "Export PDF" shows loading indicator
- Test: Loading indicator renders before main thread blocks (requestAnimationFrame used)
- Test: Generated PDF has page 1 in landscape orientation
- Test: Pages 2+ are in portrait orientation
- Test: Page 1 contains deal name header and date
- Test: Page 1 contains graph image (SVG or PNG fallback)
- Test: Document summary table contains all documents with correct columns
- Test: Document name column truncated at 50 chars
- Test: Evidence summary column truncated at 120 chars
- Test: Relationship list table is sorted by source document, then type
- Test: Findings report groups by severity (CRITICAL first)
- Test: Closing checklist included only when execution_sequence exists
- Test: PDF filename follows pattern `{deal_name}-analysis-{date}.pdf`
- Test: SVG export failure triggers cy.png() fallback (not html2canvas)
- Test: Loading indicator clears after generation completes
- Test: PDF generation with null DEAL_ANALYSIS omits findings report and closing checklist

### Fixtures needed:
- `fixture-medium.json` (reuse)
- `fixture-large.json` — 30 docs, 50 relationships, 20+ findings (stress test for PDF tables)
- `fixture-null-analysis.json` (reuse)

---

## 11. Polish

### Tests to write BEFORE implementing:
- Test: CDN load failure displays full-page error message (simulate by checking global existence)
- Test: Invalid DEAL_GRAPH (missing documents field) shows diagnostic message
- Test: Escape key closes detail panel
- Test: F key triggers fit-to-screen
- Test: R key triggers reset view (clears highlights, resets zoom, re-runs layout)
- Test: Reset View button in toolbar triggers same behavior as R key
- Test: Edge Labels toggle shows/hides edge label text
- Test: Loading spinner appears during initial Cytoscape setup
- Test: @media print hides toolbar, sidebar, filter panels
- Test: Tooltips appear on toolbar buttons on hover

### Fixtures needed:
- `fixture-invalid.json` — malformed data (missing required fields)

---

## Fixture Summary

| Fixture | Docs | Rels | Findings | Purpose |
|---------|------|------|----------|---------|
| `fixture-small.json` | 5 | 8 | 2 | Basic data adapter validation |
| `fixture-medium.json` | 15 | 25 | 10 | Primary visual testing fixture |
| `fixture-large.json` | 30 | 50 | 20+ | PDF stress test, layout scalability |
| `fixture-null-analysis.json` | 10 | 15 | 0 | Graph-only mode (DEAL_ANALYSIS = null) |
| `fixture-empty.json` | 0 | 0 | 0 | Empty deal edge case |
| `fixture-orphaned-findings.json` | 5 | 8 | 5 | Findings referencing non-existent IDs |
| `fixture-cycles.json` | 5 | 8 | 0 | Circular dependency detection |
| `fixture-xss-test.json` | 3 | 4 | 1 | HTML/script content in document text |
| `fixture-terms.json` | 8 | 12 | 0 | Defined term flow visualization |
| `fixture-invalid.json` | N/A | N/A | N/A | Malformed JSON for error handling |
