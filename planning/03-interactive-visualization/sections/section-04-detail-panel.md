# Section 04: Detail Panel

## Overview

This section implements the `DetailPanel` class, which renders document and relationship details in a slide-in sidebar when the user clicks a graph node or edge. It also implements the click handlers that wire graph interactions to the panel, and the term flow detail view. The panel is a 400px fixed-width overlay on the right side of the graph canvas.

**Dependencies:** This section requires sections 01 (HTML skeleton with the detail panel container), 02 (DataAdapter for fetching document/relationship/finding data), and 03 (GraphRenderer for click events and highlight methods) to be complete.

## File to Modify

All code goes in the single HTML file being built:

```
{deal_name}-visualization.html
```

Specifically:
- CSS additions in the `<style>` block for detail panel transitions, badge styles, and content layout
- The `DetailPanel` class in the application `<script>` block
- Cytoscape event handlers wired in the initialization code

## Tests First

These inline console assertions should run when `DEBUG = true`. Place them in a `function testDetailPanel()` called during initialization.

```javascript
function testDetailPanel(detailPanel, dataAdapter, cy) {
    // Test: Clicking a node fires the selection event and populates detail panel
    // Simulate by calling showDocumentDetail with a known doc ID from fixture data
    // Verify panel element is visible (not off-screen or display:none)

    // Test: Detail panel shows document name, type badge, status badge, summary
    // After showDocumentDetail(docId), query panel DOM for expected child elements
    // Verify .detail-doc-name, .detail-type-badge, .detail-status-badge, .detail-summary exist

    // Test: Detail panel shows parties, key provisions, obligations sections
    // Verify .detail-parties, .detail-provisions, .detail-obligations sections exist

    // Test: Detail panel shows defined terms list (each clickable)
    // Verify .detail-terms-list exists and contains clickable items

    // Test: Detail panel shows relationships list for the selected document
    // Verify .detail-relationships section is populated

    // Test: Detail panel shows findings for the selected document (if analysis exists)
    // Call getFindingsForEntity and verify findings section renders when findings present

    // Test: Clicking an edge populates detail panel with relationship details
    // Call showRelationshipDetail with a known edge ID
    // Verify .detail-rel-source, .detail-rel-target, .detail-rel-type, .detail-rel-confidence exist

    // Test: Relationship detail shows source, target, type, confidence, evidence quote
    // Verify .detail-evidence element exists and has text content

    // Test: All text content is rendered via textContent (not innerHTML)
    // Create a doc detail with HTML-like content, verify it appears as literal text
    // e.g., a document name of '<script>alert(1)</script>' should render as visible text

    // Test: Clicking background closes detail panel and clears highlight
    // Verify panel returns to hidden state after hide() is called

    // Test: Clicking X button closes detail panel
    // Verify close button exists and calls hide()

    // Test: Panel slides in/out with CSS transition (has transition property set)
    // Check computed style for transition property on panel element

    // Test: Node highlight dims non-neighbor nodes (opacity < 1)
    // After selecting a node, verify non-neighbor nodes have .search-dimmed or reduced opacity
}
```

### XSS Prevention Test

A critical test that must pass: create a fixture document with malicious content in its name and summary fields, render it in the detail panel, and verify the HTML is not interpreted.

```javascript
function testXSSPrevention(detailPanel) {
    // Use fixture-xss-test.json data:
    // Document name: '<img src=x onerror=alert(1)>'
    // Summary: '<script>document.title="hacked"</script>'
    // After rendering, verify:
    //   1. document.title has NOT changed
    //   2. The panel text content literally shows the angle brackets
    //   3. No <img> or <script> elements were created in the panel
}
```

### Fixture Needed

**`fixture-xss-test.json`** -- 3 documents, 4 relationships, 1 finding. Document names and summaries contain HTML-like strings including `<script>`, `<img onerror=...>`, and `&lt;` entities. Used to verify that `textContent` is used everywhere instead of `innerHTML`.

**`fixture-medium.json`** (reuse from section 03) -- 15 docs, 25 relationships, 10 findings. Primary fixture for verifying all panel sections render with real-ish data.

## Implementation Details

### DetailPanel Class

The `DetailPanel` class manages the right sidebar overlay. It receives a reference to the panel DOM element and the `DataAdapter` instance.

```javascript
class DetailPanel {
    constructor(panelElementId, dataAdapter) { /* ... */ }

    showDocumentDetail(docId)
    // Renders full document information into the panel, then slides it open.
    // Sections rendered (in order):
    //   1. Header: document name (h2), type badge (colored span), status badge
    //   2. Summary: paragraph of document summary text
    //   3. Parties: bulleted list of parties involved
    //   4. Key Provisions: bulleted list of provision summaries
    //   5. Obligations: bulleted list of obligations
    //   6. Defined Terms: list of terms, each clickable to trigger term flow
    //   7. Relationships: list of incoming/outgoing relationships with type badges
    //   8. Conditions Precedent: if present, list of conditions
    //   9. Findings: if analysis exists, list grouped by severity with colored badges
    //  10. Metadata: document metadata (dates, references, etc.)
    //
    // Every text value MUST be set via element.textContent, never innerHTML.
    // Empty/null fields should be omitted entirely, not shown as blank sections.

    showRelationshipDetail(relationshipId)
    // Renders relationship information:
    //   1. Header: "Source -> Target" with document names
    //   2. Type badge (colored by relationship type family)
    //   3. Confidence indicator (high/medium/low with appropriate styling)
    //   4. Evidence quote (blockquote-styled, from the relationship data)
    //   5. Source reference (where in the document this relationship was found)
    //   6. Flags: needs_review, is_manual indicators if present
    //   7. Findings: any analysis findings referencing this relationship

    showTermFlow(termId)
    // Renders term flow detail:
    //   1. Term name header
    //   2. "Defined in:" with the defining document (clickable)
    //   3. "Used in:" with list of using documents (each clickable)
    // Also triggers a callback that the parent code uses to call
    // graphRenderer.highlightNode() or a custom term-flow highlight

    hide()
    // Slides panel off-screen via CSS class toggle
    // Clears panel content after transition completes
}
```

### CSS for the Detail Panel

The panel container already exists from section 01. This section adds the transition behavior and interior styling.

Key CSS properties for the panel:

- **Position:** Fixed or absolute, right side, full height below toolbar
- **Width:** 400px
- **Default state:** `transform: translateX(100%)` (off-screen to the right)
- **Open state:** `transform: translateX(0)` via a `.panel-open` class
- **Transition:** `transform 0.3s ease` for smooth slide animation
- **Background:** White with a left box-shadow for depth
- **Content area:** `overflow-y: auto` for scrolling when content exceeds viewport
- **Z-index:** Above the graph canvas but below any modal dialogs
- **Close button:** Absolute positioned top-right "X" button

Interior content styling:

- **Type badges:** Inline colored pills using the same category colors as graph nodes. Background color from CSS variables, white text, small border-radius, 12px font.
- **Status badges:** Similar pill style. Colors: active/green, draft/yellow, executed/blue, terminated/red.
- **Severity badges in findings:** Use the severity palette (critical=red, error=amber, warning=blue, info=gray).
- **Evidence quotes:** Left-bordered blockquote style, slightly indented, italic, lighter text.
- **Section headers:** 14px, font-weight 600, with a subtle bottom border separator.
- **Clickable items (terms, document names in relationships):** Underlined on hover, cursor pointer, colored to indicate interactivity.

### Wiring Click Handlers

In the initialization code (after GraphRenderer is created), wire Cytoscape events to the detail panel:

```javascript
// Node click handler
cy.on('tap', 'node', function(evt) {
    const nodeId = evt.target.id();
    appState.selectedEntity = { type: 'document', id: nodeId };
    graphRenderer.highlightNode(nodeId);
    detailPanel.showDocumentDetail(nodeId);
});

// Edge click handler
cy.on('tap', 'edge', function(evt) {
    const edgeId = evt.target.id();
    appState.selectedEntity = { type: 'relationship', id: edgeId };
    detailPanel.showRelationshipDetail(edgeId);
});

// Background click handler (close panel)
cy.on('tap', function(evt) {
    if (evt.target === cy) {
        appState.selectedEntity = null;
        graphRenderer.clearHighlight();
        detailPanel.hide();
    }
});
```

The close button ("X") in the panel header also calls `detailPanel.hide()` and `graphRenderer.clearHighlight()`.

### DOM Construction Pattern

All panel content is built by creating DOM elements programmatically. This is the XSS-safe pattern to follow throughout:

```javascript
// CORRECT -- safe against XSS
const nameEl = document.createElement('h2');
nameEl.textContent = doc.name; // Even if doc.name contains '<script>...', it renders as text

// WRONG -- vulnerable to XSS, never do this
panel.innerHTML = `<h2>${doc.name}</h2>`; // If doc.name has HTML, it gets interpreted
```

Every single piece of deal data that is rendered in the panel must go through `textContent` or `setAttribute` (for non-event attributes). No exceptions. Legal documents frequently contain angle brackets, ampersands, and other characters that would break or exploit innerHTML.

### Term Flow Callback

When a user clicks a defined term in the detail panel, the panel calls a callback provided during initialization. The parent code uses this callback to:

1. Call `dataAdapter.getDefinedTermFlow(termId)` to get the defining and using documents
2. Highlight the defining document node with a distinct style (e.g., thick teal border)
3. Highlight using document nodes with a lighter teal treatment
4. Dim all other nodes
5. Call `detailPanel.showTermFlow(termId)` to update the panel content to show term flow details

Clicking any document name in the term flow panel view should navigate to that document's detail view (call `showDocumentDetail`).

### Handling Missing Data

The panel must gracefully handle sparse data:

- If a document has no `parties` field or an empty array, omit the Parties section entirely
- If a document has no `defined_terms`, omit the Defined Terms section
- If `DEAL_ANALYSIS` is null, omit the Findings section and do not show "0 findings"
- If a relationship has no `evidence` field, omit the evidence blockquote
- If a relationship has no `flags`, omit the flags section
- Sections with no data are simply not rendered, keeping the panel clean

### AppState Integration

When the detail panel opens or closes, update `appState.selectedEntity`:

- On open: `{ type: 'document'|'relationship'|'term', id: entityId }`
- On close: `null`

Other modules (overlay, filters) check `appState.selectedEntity` to avoid clearing a user's selection during their operations.

### Panel Auto-close on Narrow Viewports

Per the responsive behavior spec, if the window width drops below 800px, the detail panel should auto-close. Add a `resize` event listener that calls `detailPanel.hide()` when `window.innerWidth < 800`.
