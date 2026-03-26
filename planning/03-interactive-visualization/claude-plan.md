# Implementation Plan: Interactive Visualization & Export

## 1. What We're Building

A single self-contained HTML file that renders an interactive dependency graph of legal deal documents. Claude Code generates this file with deal data embedded as JavaScript variables, and the user opens it in a browser to explore document relationships, view analysis results, and export a professional PDF report.

This is the user-facing layer of a three-part system:
- **Split 01** extracts document metadata and relationships into `deal-graph.json`
- **Split 02** analyzes the graph for conflicts, hierarchy, term flow, and execution sequence, producing `deal-analysis.json`
- **Split 03** (this plan) visualizes both files as an interactive, explorable graph with PDF export

The user is a solo legal professional reviewing deal closings. The interface must be polished, professional, and usable without technical knowledge. V1 is **view-only with PDF export** — browser-based editing is deferred.

## 2. Architecture

### Data Flow

Claude Code generates the HTML file by embedding two JSON data objects as `<script type="application/json">` data islands:

```html
<script type="application/json" id="deal-graph-data">
  { /* deal-graph.json contents */ }
</script>
<script type="application/json" id="deal-analysis-data">
  { /* deal-analysis.json contents, or null if not yet analyzed */ }
</script>
```

The application code parses these on load:
```javascript
const DEAL_GRAPH = JSON.parse(document.getElementById('deal-graph-data').textContent);
const DEAL_ANALYSIS = JSON.parse(document.getElementById('deal-analysis-data').textContent);
```

This approach avoids the `</script>` injection vulnerability that would occur if legal document text (e.g., evidence quotes containing angle brackets) were embedded directly as JavaScript variables. It also prevents XSS from arbitrary text in deal data.

The user opens the HTML file in any modern browser. No server, no file picker, no login. When the user wants changes, they describe edits to Claude Code, which regenerates the HTML with updated data.

### Technology Choices

**Cytoscape.js** replaces D3.js from the prototype. Reasons:
- Built-in graph interactions (zoom, pan, drag, click, select) — no manual coding
- Plugin ecosystem for layouts: dagre (hierarchical), cola (force-directed), breadthfirst (tree)
- Built-in PNG export, SVG export via extension
- Compound node support for future grouping features
- All loadable via CDN with zero configuration — extensions auto-register

**PDF export** uses a hybrid approach:
- Graph: cytoscape-svg extension exports the graph as SVG, then svg2pdf.js converts to vector PDF
- Tables: jsPDF with jspdf-autotable plugin renders native PDF tables with selectable text
- Both combined in a single multi-page jsPDF document

### Single-File Architecture

Everything lives in one HTML file:
- `<style>` block with all CSS
- `<script>` tags loading CDN dependencies
- `<script>` block with embedded deal data
- `<script>` block with application code
- HTML structure for layout (toolbar, graph container, sidebar)

CDN dependencies (loaded in order, all with Subresource Integrity hashes and `crossorigin="anonymous"`):
1. `cytoscape.min.js` (~112 KB) — core graph library
2. `dagre.js` (~30 KB) — dagre layout algorithm
3. `cytoscape-dagre.js` (~5 KB) — Cytoscape dagre adapter
4. `cytoscape-cola.js` (~50 KB) — constraint-based force-directed layout
5. `jspdf.umd.min.js` (~280 KB) — PDF generation
6. `svg2pdf.js` (~45 KB) — SVG to PDF conversion
7. `jspdf.plugin.autotable.min.js` (~50 KB) — PDF table generation

All CDN script tags must include `integrity` (SRI hashes) and `crossorigin="anonymous"` attributes. Pin exact versions (not `@latest`) to prevent breaking changes. Claude Code generates the SRI hashes when building the HTML file.

Total CDN payload: ~570 KB (loaded once, cached by browser).

## 3. Application Structure

The HTML file contains these logical modules, all within a single `<script>` block. A central **`AppState`** object manages shared state (activeView, layout, filters, searchQuery, overlayEnabled, selectedEntity) and coordinates between modules via simple callbacks, preventing ad-hoc synchronization between features that interact (e.g., search + filter + overlay).

### 3.1 Data Layer

Responsible for reading and transforming embedded data into Cytoscape-compatible format.

**`DataAdapter`** — transforms `DEAL_GRAPH` and `DEAL_ANALYSIS` into Cytoscape elements:

```javascript
class DataAdapter {
    constructor(dealGraph, dealAnalysis) { /* ... */ }

    getCytoscapeElements()
    // Returns { nodes: [...], edges: [...] } formatted for cy.add()
    // Nodes: { data: { id, label, docType, status, ... }, classes: [...] }
    // Edges: { data: { id, source, target, relType, confidence, ... }, classes: [...] }
    // Edge IDs use deterministic format: ${source}::${relType}::${target}::${index}
    // Silently prunes analysis findings that reference non-existent node/edge IDs

    getDocumentDetails(docId)
    // Returns full document object from DEAL_GRAPH for detail panel

    getFindingsForEntity(entityType, entityId)
    // Returns array of findings from DEAL_ANALYSIS affecting this entity

    getExecutionSequence()
    // Returns ordered array of execution steps from execution_sequence analysis

    getRelationshipTypes()
    // Returns array of unique relationship types present in this deal

    getDocumentTypes()
    // Returns array of unique document types present in this deal

    getDefinedTermFlow(termId)
    // Returns { definingDoc, usingDocs } for term highlight visualization

    getFindingsSummary()
    // Returns { critical: N, error: N, warning: N, info: N }
}
```

### 3.2 Graph Renderer

Initializes and manages the Cytoscape instance.

**`GraphRenderer`** — owns the Cytoscape instance and handles layout switching:

```javascript
class GraphRenderer {
    constructor(containerId, elements, styleConfig) { /* ... */ }

    applyLayout(layoutName)
    // Switches between 'dagre', 'cola', 'breadthfirst' with animated transition
    // Preserves selection, filters, and overlay state across layout changes

    highlightNode(nodeId)
    // Highlights node and its neighborhood, dims everything else

    clearHighlight()
    // Restores all elements to default styling

    filterByRelationshipType(types)
    // Shows/hides edges based on array of active relationship types

    filterByDocumentType(types)
    // Shows/hides nodes (and their edges) by document type

    filterByConfidence(minLevel)
    // Hides edges below confidence threshold ('high', 'medium', 'low')

    searchDocuments(query)
    // Dims non-matching nodes, highlights matching ones

    fitToScreen()
    // Calls cy.fit() with padding

    exportSVG()
    // Returns SVG string of current graph state for PDF export
}
```

**Cytoscape Style Configuration:**

Node styles are determined by document type. The 21 document types are grouped into 5-7 broad categories (e.g., Primary, Ancillary, Financial, Corporate, Real Estate, Regulatory, Closing). Each category gets a color from a professional, muted palette. Within a category, document types are differentiated by node shape (rectangle, ellipse, hexagon, diamond) or border style (solid, dashed, double). This approach ensures visual distinguishability even for users with color vision deficiencies, rather than attempting 21 unique colors. Node size scales with relationship count using sqrt scaling (min 40px, max 80px diameter) to prevent hub-dominated layouts. Labels show truncated document names (max 20 characters + ellipsis).

**Visual state precedence** — multiple features affect node/edge appearance. The rules are:
- **Filter** (removes from rendering) > **Search** (dims via opacity) > **Highlight** (changes border/opacity for neighborhood) > **Overlay** (adds badges/rings)
- Implemented via CSS classes on Cytoscape elements: `.filtered-out`, `.search-dimmed`, `.highlighted`, `.finding-critical`, `.finding-error`, etc.
- Filter determines visibility; search dims within the visible set; highlight overrides dimming for the selected neighborhood; overlay adds decorations on top of all other states.

Edge styles are determined by relationship type. The 16 types are grouped into color families:
- **Control/hierarchy** (controls, subordinates_to, supersedes): warm reds/oranges
- **Reference** (references, incorporates): blues
- **Financial** (guarantees, secures, assigns, indemnifies): greens
- **Modification** (amends, restricts, restates): purples
- **Conditional** (triggers, conditions_precedent, consents_to): yellows/amber
- **Term** (defines_terms_for): teal

Confidence affects edge line style: solid (high), dashed (medium), dotted (low).

Edge arrows indicate direction (source → target). Edge labels show relationship type (toggleable).

### 3.3 Analysis Overlay

Manages the "Show Issues" toggle that overlays analysis findings on the graph.

**`AnalysisOverlay`** — applies and removes finding visualizations:

```javascript
class AnalysisOverlay {
    constructor(graphRenderer, dataAdapter) { /* ... */ }

    enable()
    // Adds severity-colored border rings to affected nodes
    // Thickens and colors affected edges
    // Shows finding count badges on nodes
    // Shows summary panel (X critical, Y errors, Z warnings)

    disable()
    // Removes all overlay styling, returns graph to normal

    highlightFinding(findingId)
    // Highlights the specific nodes/edges affected by a finding

    isEnabled()
    // Returns current toggle state
}
```

Severity rendering:
- CRITICAL: thick red border ring, red badge with count
- ERROR: amber border ring, amber badge
- WARNING: blue border ring, blue badge
- INFO: gray border ring (subtle, no badge unless only info findings exist)

### 3.4 Detail Panel

The right sidebar that shows context when a node or edge is clicked.

**`DetailPanel`** — renders document and relationship details:

```javascript
class DetailPanel {
    constructor(panelElementId, dataAdapter) { /* ... */ }

    showDocumentDetail(docId)
    // Renders: name, type badge, status badge, summary, parties, key provisions,
    // obligations, defined terms (clickable for flow highlight), relationships,
    // cross-references, conditions precedent, findings, metadata
    // ALL text rendered via textContent (never innerHTML) to prevent XSS from deal data

    showRelationshipDetail(relationshipId)
    // Renders: source → target header, type badge, evidence quote, confidence,
    // source reference, findings, flags (needs_review, is_manual)

    showTermFlow(termId)
    // Renders: term name, defining document, list of using documents
    // Triggers graph highlight via callback

    hide()
    // Closes the panel
}
```

The panel is a fixed-width (400px) overlay on the right side of the graph. It slides in/out with a CSS transition. Content is scrollable. Clicking the background or an "X" button closes it.

### 3.5 Toolbar

The top control bar with all view controls and actions.

**Layout:**
```
[View: Graph ▾] [Layout: Dagre ▾] [🔍 Search...] [Show Issues ○] [Edge Labels ○] [Filter ▾] [Reset View] [Export PDF]
```

**View switcher** — dropdown or tab bar:
- **Graph** (default): Cytoscape graph view
- **Timeline**: Execution sequence table

**Layout switcher** (only visible in Graph view):
- **Dagre** (default): Top-to-bottom hierarchy
- **Force-directed**: Cola constraint-based layout
- **Tree**: Breadthfirst tree layout

**Search box**: Text input that filters nodes in real-time as user types.

**Show Issues toggle**: Enables/disables the analysis overlay.

**Edge Labels toggle**: Shows/hides relationship type labels on edges.

**Filter dropdown**: Expandable panel with:
- Relationship type checkboxes (with color swatches)
- Document type checkboxes
- Confidence level selector (All / Medium+ / High only)
- "Reset filters" button

**Reset View button**: Clears all highlights, resets zoom/pan, clears search, and re-runs the current layout algorithm. Restores the graph to its initial state without clearing filters or overlay toggles.

**Export PDF button**: Triggers PDF generation.

### 3.6 Timeline View

A data table view replacing the graph canvas when the user switches to Timeline mode.

**`TimelineView`** — renders the execution sequence table:

```javascript
class TimelineView {
    constructor(containerElementId, dataAdapter) { /* ... */ }

    render()
    // Builds HTML table from dataAdapter.getExecutionSequence()
    // Columns: Sequence #, Document Name, Dependencies, Status, Gating Conditions

    onDocumentClick(callback)
    // When user clicks a document name in the table, callback fires
    // Parent switches back to graph view and highlights that document
}
```

The table is styled with alternating row shading, sortable headers, and status badges (pending=yellow, satisfied=green, waived=gray). Documents in the same parallel execution window are visually grouped.

If no execution_sequence analysis exists in DEAL_ANALYSIS, this view shows a message: "Execution sequence analysis not available."

### 3.7 PDF Exporter

Generates a multi-page professional PDF from the current visualization state.

**`PDFExporter`** — orchestrates PDF generation:

```javascript
class PDFExporter {
    constructor(dataAdapter, graphRenderer) { /* ... */ }

    async generate()
    // Creates jsPDF instance (letter size)
    // Page 1: Title + graph snapshot (landscape)
    // Page 2+: Document summary table (portrait)
    // Next pages: Relationship list (portrait)
    // Next pages: Findings report by severity (portrait)
    // Final pages: Closing checklist / execution sequence (portrait)
    // Returns: triggers browser download of PDF file
}
```

**Page details:**

**Page 1 — Graph (landscape):**
- Header: Deal name, "Document Dependency Analysis", date generated
- Body: Vector SVG of current graph state, converted via svg2pdf.js
- The graph captures whatever layout, filters, and overlay state is currently active

**Pages 2+ — Document Summary Table (portrait):**
- Table with columns: Document Name, Type, Status, Parties, Key Provisions Count, Relationships Count
- Built with jspdf-autotable
- Alternating row shading, professional styling

**Next — Relationship List (portrait):**
- Table: Source Document, Target Document, Type, Confidence, Evidence Summary
- Sorted by source document, then relationship type

**Next — Findings Report (portrait):**
- Grouped by severity (CRITICAL first)
- Each finding: severity badge, title, description, affected documents
- Subtotals per severity level

**Final — Closing Checklist (portrait):**
- Same data as timeline view: Sequence #, Document, Dependencies, Status
- Only included if execution_sequence analysis exists

**PDF generation is async** — show a loading indicator ("Generating PDF...") during generation. Use `requestAnimationFrame` before starting PDF generation to ensure the loading UI renders before the main thread is blocked by jsPDF/svg2pdf.js processing.

**Table truncation rules:**
- Document names: max 50 characters + ellipsis
- Evidence summary column: max 120 characters + ellipsis
- Parties: max 80 characters + ellipsis
- Column widths are fixed proportionally to prevent layout explosion from long strings

## 4. CSS & Visual Design

### Layout Structure

```
┌─────────────────────────────────────────────────────────────────────┐
│ Toolbar                                                              │
├─────────────────────────────────────────────┬───────────────────────┤
│                                             │                       │
│                                             │   Detail Panel        │
│           Graph Canvas                      │   (400px, slides in   │
│           (fills remaining space)           │    when node/edge     │
│                                             │    is clicked)        │
│                                             │                       │
│                                             │                       │
└─────────────────────────────────────────────┴───────────────────────┘
```

The toolbar is a fixed-height bar at the top. The graph canvas fills all remaining space. The detail panel overlays the right edge of the graph — it doesn't resize the canvas, just floats on top with a subtle shadow.

### Color Palette

Professional, muted tones appropriate for legal context:

**Document type palette** (21 colors): Derived from a set of distinguishable muted hues. Each type gets a consistent color across all views (graph nodes, detail panel badges, PDF tables).

**Severity palette:**
- CRITICAL: `#dc2626` (red-600)
- ERROR: `#d97706` (amber-600)
- WARNING: `#2563eb` (blue-600)
- INFO: `#6b7280` (gray-500)

**UI chrome:** Light gray background (`#f8f9fa`), white panels, subtle borders (`#e5e7eb`), dark text (`#1f2937`).

### Typography

System font stack: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`

Hierarchy:
- Deal name: 20px, font-weight 700
- Section headers: 16px, font-weight 600
- Document names (in panels): 14px, font-weight 500
- Body text / metadata: 13px, font-weight 400
- Graph node labels: 11px (scales with zoom)

### Print Stylesheet

A `@media print` block hides the toolbar, sidebar, and filter panels. It displays a centered message: "For the best report, use the Export PDF button" with the deal name. This handles the case where users instinctively press Ctrl+P instead of using the PDF export.

### Responsive Behavior

Minimum width: 1024px (legal professionals use desktop monitors). Below that, a horizontal scrollbar appears rather than breaking layout. The detail panel closes automatically if window width drops below 800px.

## 5. Interaction Flows

### Flow 1: Initial Load
1. Browser loads HTML file
2. CDN scripts load (show loading spinner)
3. `DataAdapter` processes `DEAL_GRAPH` and `DEAL_ANALYSIS`
4. `GraphRenderer` initializes Cytoscape with dagre layout
5. If findings exist, show a subtle notification: "X issues found — toggle Show Issues to view"
6. Graph animates into position

### Flow 2: Explore Document
1. User clicks a node
2. Node and its neighborhood highlight
3. Detail panel slides in showing document details
4. User scrolls through provisions, terms, relationships
5. User clicks a defined term → term flow highlight activates on graph
6. User clicks background → panel closes, highlights clear

### Flow 3: Investigate Issues
1. User toggles "Show Issues" on
2. Severity rings appear on affected nodes, badges show counts
3. Summary appears: "3 critical, 5 errors, 12 warnings"
4. User clicks a severity badge on a node → detail panel shows that node's findings
5. User clicks a specific finding → graph highlights all affected entities
6. User toggles off → graph returns to normal

### Flow 4: Switch Views
1. User selects "Timeline" from view switcher
2. Graph canvas fades out, execution sequence table fades in
3. User reviews closing order
4. User clicks a document name in table → view switches back to graph, that node is selected and centered

### Flow 5: Export PDF
1. User clicks "Export PDF"
2. Loading indicator appears
3. Graph SVG is captured, tables are built, findings report compiled
4. Browser download triggers with filename: `{deal_name}-analysis-{date}.pdf`
5. Loading indicator clears

### Flow 6: Change Layout
1. User selects "Force-directed" from layout dropdown
2. Nodes animate from dagre positions to cola positions (~500ms transition)
3. All filters, selections, and overlay state preserved
4. User can drag individual nodes to fine-tune positions

## 6. Error Handling

- **CDN load failure:** Each script tag gets an `onerror` handler that sets a global failure flag. Before app initialization, check that all required globals exist (`cytoscape`, `jspdf`, etc.). If any are missing, display a full-page message: "Required libraries could not be loaded. Please check your internet connection and reload." This handles offline use, corporate proxies, and blocked CDNs gracefully.
- **Invalid data format:** If `DEAL_GRAPH` is malformed or missing required fields, display a diagnostic message showing which fields are missing. Don't crash silently. Validate that `documents` is an array, each document has an `id`, etc.
- **Orphaned analysis findings:** If `DEAL_ANALYSIS` references document or relationship IDs that don't exist in `DEAL_GRAPH`, the DataAdapter silently prunes those findings rather than crashing.
- **No analysis data:** If `DEAL_ANALYSIS` is null, the app works in graph-only mode — disable Show Issues toggle, disable Timeline view, omit findings from detail panels and PDF.
- **Empty deal:** If `DEAL_GRAPH.documents` is empty, show "No documents in this deal" with guidance.
- **Cyclic dependencies:** If the graph contains cycles (Doc A references Doc B, Doc B references Doc A), dagre handles this by arbitrarily reversing an edge. The DataAdapter detects cycles and marks those edges with a special class so they render as bright red dashed lines, making logical loops visible to the user.
- **SVG export failure:** If svg2pdf.js fails, fall back to Cytoscape's built-in `cy.png({scale: 2})` for a high-resolution raster image on the graph page. Log a note in the PDF footer.

## 7. File Structure

Claude Code generates one file:

```
{deal_name}-visualization.html    # Single self-contained HTML file
```

This file contains:
- All CSS in a `<style>` block
- CDN `<script>` tags for dependencies
- Embedded data in a `<script>` block
- Application code in a `<script>` block
- HTML structure for toolbar, graph container, sidebar, timeline container

Claude Code's generation process:
1. Read `deal-graph.json` and `deal-analysis.json`
2. Read the HTML template (the implementation we build)
3. Inject the data as JS variables into the template
4. Write the complete HTML file

The "template" is the HTML file with `<script type="application/json">` data islands. Claude Code replaces the contents of these JSON blocks. Because the data is in a JSON context (not a JavaScript execution context), there is no risk of `</script>` injection from legal text content.

## 8. Implementation Order

The implementation should proceed in this order, with each step buildable and testable independently:

1. **HTML skeleton + CSS layout** — Toolbar, graph container, sidebar panel structure. No functionality, just the visual frame.

2. **Data adapter** — Parse DEAL_GRAPH into Cytoscape elements format. Transform documents to nodes, relationships to edges. Include all metadata in element data properties.

3. **Graph rendering with dagre** — Initialize Cytoscape with the data adapter output. Dagre layout. Node and edge styling by type. Zoom/pan/drag working.

4. **Node/edge interaction + detail panel** — Click handlers on nodes and edges. Detail panel rendering with all document/relationship fields.

5. **Alternative layouts** — Add cola and breadthfirst layouts. Layout switcher in toolbar with animated transitions.

6. **Filtering** — Relationship type filter, document type filter, confidence filter, search box. All affect the graph in real-time.

7. **Analysis overlay** — Show Issues toggle. Severity rings, badges, summary panel. Finding-to-entity highlighting.

8. **Defined term flow** — Click a term in the detail panel to highlight its flow across documents.

9. **Timeline view** — Execution sequence table. View switcher. Click-to-navigate back to graph.

10. **PDF export** — SVG capture, document summary table, relationship list, findings report, closing checklist. Multi-page jsPDF generation with professional styling.

11. **Polish** — Loading states, error handling, edge labels toggle, keyboard shortcuts (Escape to close panel, F to fit screen, R to reset view), tooltips, print stylesheet, final visual refinement.

## 9. Testing Strategy

Since this is a single HTML file with no build system, testing takes a different form:

**Validation testing (Claude Code):**
- Claude Code can read the generated HTML and verify: all expected data is embedded, all script tags are present, HTML structure is well-formed
- Claude Code can verify the data adapter logic by running it against sample deal-graph.json fixtures

**Visual testing (manual):**
- Open the HTML file with sample deal data and verify each view mode renders correctly
- Test with varying deal sizes: 5 documents, 15 documents, 30 documents
- Verify PDF output opens correctly and contains all sections

**Sample data fixtures:**
- Small deal (5 docs, 8 relationships, 2 findings)
- Medium deal (15 docs, 25 relationships, 10 findings across all severity levels)
- Large deal (30 docs, 50 relationships, 20+ findings)
- Edge case: deal with no analysis results (DEAL_ANALYSIS = null)
- Edge case: deal with no relationships (isolated document nodes)
- Edge case: deal with cyclic dependencies between documents
- Edge case: analysis findings referencing non-existent document IDs

**Browser compatibility:**
- Test in Chrome (primary), Edge, Firefox, Safari
- Verify CDN loading, graph rendering, PDF export in each

## 10. Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Library | Cytoscape.js | Built-in interactions, layout ecosystem, CDN-friendly. Replaces D3.js prototype. |
| Default layout | Dagre (hierarchical) | Legal document dependencies are inherently hierarchical. Shows control flow clearly. |
| Data strategy | Embed in HTML | Simplest workflow — no file picker, no server, no browser API limitations. Claude Code regenerates on changes. |
| V1 scope | View-only + export | Editing adds significant complexity. Users describe edits to Claude Code instead. |
| Conflict display | Overlay on graph | User preferred keeping the graph visible while seeing issues, not switching to a separate view. |
| Timeline format | Simple sorted table | User preferred scannable table over complex Gantt visualization. |
| PDF approach | Hybrid (svg2pdf + autotable) | Vector graph quality + native text tables = professional output suitable for outside counsel. |
| Architecture | Single HTML file | Matches prototype pattern. No build step, no server, instant sharing — email the file. |
