<!-- PROJECT_CONFIG
runtime: html-static
test_command: echo "Open HTML file in browser to test"
END_PROJECT_CONFIG -->

<!-- SECTION_MANIFEST
section-01-foundation
section-02-data-adapter
section-03-graph-core
section-04-detail-panel
section-05-layouts-filtering
section-06-analysis-overlay
section-07-timeline-view
section-08-pdf-export
section-09-polish
END_MANIFEST -->

# Implementation Sections Index

## Dependency Graph

| Section | Depends On | Blocks | Parallelizable |
|---------|------------|--------|----------------|
| section-01-foundation | - | all | Yes (standalone) |
| section-02-data-adapter | 01 | 03-09 | No |
| section-03-graph-core | 01, 02 | 04-09 | No |
| section-04-detail-panel | 01, 02, 03 | 09 | Yes (with 05) |
| section-05-layouts-filtering | 01, 02, 03 | 09 | Yes (with 04) |
| section-06-analysis-overlay | 01, 02, 03 | 09 | Yes (with 07) |
| section-07-timeline-view | 01, 02 | 09 | Yes (with 06) |
| section-08-pdf-export | 01, 02, 03 | 09 | No |
| section-09-polish | 01-08 | - | No (final) |

## Execution Order

1. **Batch 1:** section-01-foundation (no dependencies)
2. **Batch 2:** section-02-data-adapter (after 01)
3. **Batch 3:** section-03-graph-core (after 02)
4. **Batch 4:** section-04-detail-panel, section-05-layouts-filtering (parallel, both need 03)
5. **Batch 5:** section-06-analysis-overlay, section-07-timeline-view (parallel, need 03 and 02 respectively)
6. **Batch 6:** section-08-pdf-export (needs graph core + data adapter)
7. **Batch 7:** section-09-polish (final integration, needs everything)

## Section Summaries

### section-01-foundation
HTML skeleton, CSS layout structure, CDN script tags with SRI, `<script type="application/json">` data islands, toolbar HTML, graph container, detail panel container, timeline container, print stylesheet, system font stack, color palette CSS variables, responsive behavior.

**From plan:** Sections 2 (Architecture), 4 (CSS & Visual Design), 7 (File Structure)
**From TDD:** Section 1 (HTML Skeleton + CSS Layout)

### section-02-data-adapter
DataAdapter class: transforms DEAL_GRAPH and DEAL_ANALYSIS into Cytoscape elements format. Deterministic edge IDs, document type category mapping, orphaned finding pruning, cycle detection, all query methods (getDocumentDetails, getFindingsForEntity, getExecutionSequence, getRelationshipTypes, getDocumentTypes, getDefinedTermFlow, getFindingsSummary). Sample data fixtures.

**From plan:** Section 3.1 (Data Layer)
**From TDD:** Section 2 (Data Adapter)

### section-03-graph-core
AppState central state object. GraphRenderer class: Cytoscape initialization, dagre layout, node styling by document type category (5-7 color groups + shapes), edge styling by relationship type family, confidence-based line styles, edge arrows, node size scaling (sqrt, 40-80px), label truncation, zoom/pan/drag, fitToScreen, exportSVG. Cyclic edge rendering.

**From plan:** Sections 3.2 (Graph Renderer), 3 intro (AppState)
**From TDD:** Section 3 (Graph Rendering with Dagre)

### section-04-detail-panel
DetailPanel class: document detail rendering (name, type badge, status badge, summary, parties, provisions, obligations, defined terms, relationships, findings, metadata), relationship detail rendering (source/target, type, evidence, confidence), term flow detail. All text via textContent (XSS prevention). Slide-in/out CSS transitions, 400px overlay, scrollable content, close on background click or X button.

**From plan:** Section 3.4 (Detail Panel)
**From TDD:** Section 4 (Node/Edge Interaction + Detail Panel)

### section-05-layouts-filtering
Alternative layouts (cola force-directed, breadthfirst tree), layout switcher dropdown with animated transitions. FilterManager: relationship type checkboxes, document type checkboxes, confidence level selector, search box with real-time dimming, reset filters button. Visual state precedence (Filter > Search > Highlight > Overlay) via CSS classes.

**From plan:** Sections 3.2 (filter/layout methods), 3.5 (Toolbar filter/layout controls)
**From TDD:** Sections 5 (Alternative Layouts) + 6 (Filtering)

### section-06-analysis-overlay
AnalysisOverlay class: Show Issues toggle, severity-colored border rings (critical=red, error=amber, warning=blue, info=gray), finding count badges, summary panel with severity counts, finding-to-entity highlighting. Enable/disable without affecting filter state. Overlay decorations persist across layout changes.

**From plan:** Section 3.3 (Analysis Overlay)
**From TDD:** Section 7 (Analysis Overlay)

### section-07-timeline-view
TimelineView class: execution sequence HTML table (Sequence #, Document Name, Dependencies, Status, Gating Conditions). View switcher (Graph/Timeline). Alternating row shading, sortable headers, status badges (pending=yellow, satisfied=green, waived=gray). Parallel execution window grouping. Click document name to switch back to graph and highlight. "Not available" message when no execution_sequence.

**From plan:** Section 3.6 (Timeline View), Section 3.5 (view switcher)
**From TDD:** Section 9 (Timeline View)

### section-08-pdf-export
PDFExporter class: multi-page jsPDF generation. Page 1 landscape (title + graph SVG via svg2pdf.js, or cy.png() fallback). Pages 2+ portrait (document summary table via autotable, relationship list table, findings report grouped by severity, closing checklist). Truncation rules for table columns. requestAnimationFrame for loading UI. Filename pattern. Async generation with loading indicator.

**From plan:** Section 3.7 (PDF Exporter)
**From TDD:** Section 10 (PDF Export)

### section-09-polish
Error handling (CDN load failure detection, invalid data diagnostics, empty deal message). Keyboard shortcuts (Escape=close panel, F=fit screen, R=reset view). Reset View button wiring. Edge Labels toggle. Loading spinner during init. Tooltips on toolbar buttons. @media print stylesheet behavior. Final visual refinement and cross-browser testing notes.

**From plan:** Sections 5 (Interaction Flows), 6 (Error Handling), 8 step 11 (Polish)
**From TDD:** Section 11 (Polish)
