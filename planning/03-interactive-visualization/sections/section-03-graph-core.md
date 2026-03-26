# Section 03: Graph Core (AppState + GraphRenderer + Cytoscape Initialization)

## Overview

This section implements the central `AppState` object and the `GraphRenderer` class. Together they initialize a Cytoscape.js graph instance inside the graph container element (created in section-01), populate it with elements from the `DataAdapter` (created in section-02), apply dagre layout, style nodes by document type category and edges by relationship type family, and provide methods for zoom/pan/fit/export.

**Dependencies:**
- **section-01-foundation** -- HTML skeleton must exist with `#graph-container` element, CSS variables for the color palette, and CDN script tags for cytoscape, dagre, and cytoscape-dagre loaded.
- **section-02-data-adapter** -- `DataAdapter` class must be implemented, providing `getCytoscapeElements()` which returns `{ nodes: [...], edges: [...] }` in Cytoscape format.

**File to modify:** The single HTML file (e.g., `{deal_name}-visualization.html`). All code goes into the application `<script>` block.

---

## Tests (Write First)

All tests are inline console assertions behind a `DEBUG` flag. These run on page load when `const DEBUG = true;` and are silent in production.

### Test: Cytoscape instance initializes without errors

```javascript
if (DEBUG) {
    console.assert(
        window.cy instanceof cytoscape,
        'Cytoscape instance should exist on window.cy'
    );
    console.assert(
        document.getElementById('graph-container').children.length > 0,
        'Graph container should have child elements after init'
    );
}
```

### Test: All nodes from DataAdapter are rendered

```javascript
if (DEBUG) {
    const expected = dataAdapter.getCytoscapeElements();
    console.assert(
        cy.nodes().length === expected.nodes.length,
        `Node count mismatch: cy has ${cy.nodes().length}, expected ${expected.nodes.length}`
    );
}
```

### Test: All edges from DataAdapter are rendered

```javascript
if (DEBUG) {
    const expected = dataAdapter.getCytoscapeElements();
    console.assert(
        cy.edges().length === expected.edges.length,
        `Edge count mismatch: cy has ${cy.edges().length}, expected ${expected.edges.length}`
    );
}
```

### Test: Dagre layout positions nodes without overlap

```javascript
if (DEBUG) {
    const positions = new Set();
    let hasOverlap = false;
    cy.nodes().forEach(n => {
        const key = `${Math.round(n.position('x'))},${Math.round(n.position('y'))}`;
        if (positions.has(key)) hasOverlap = true;
        positions.add(key);
    });
    console.assert(!hasOverlap, 'Dagre layout should not produce overlapping node positions');
}
```

### Test: Node size scales with relationship count

```javascript
if (DEBUG) {
    const degrees = cy.nodes().map(n => ({ id: n.id(), deg: n.degree() }));
    if (degrees.length >= 2) {
        const sorted = degrees.sort((a, b) => b.deg - a.deg);
        const highNode = cy.getElementById(sorted[0].id);
        const lowNode = cy.getElementById(sorted[sorted.length - 1].id);
        console.assert(
            highNode.width() >= lowNode.width(),
            'High-degree node should be at least as large as low-degree node'
        );
    }
}
```

### Test: Node size stays within bounds (40-80px)

```javascript
if (DEBUG) {
    cy.nodes().forEach(n => {
        const w = n.width();
        console.assert(w >= 40 && w <= 80,
            `Node ${n.id()} width ${w} out of bounds [40, 80]`
        );
    });
}
```

### Test: Node labels are truncated at 20 characters + ellipsis

```javascript
if (DEBUG) {
    cy.nodes().forEach(n => {
        const label = n.style('label');
        console.assert(label.length <= 23,
            `Node label "${label}" exceeds 20 chars + ellipsis`
        );
    });
}
```

### Test: Edge arrows are visible

```javascript
if (DEBUG) {
    cy.edges().forEach(e => {
        const arrowShape = e.style('target-arrow-shape');
        console.assert(
            arrowShape && arrowShape !== 'none',
            `Edge ${e.id()} should have a target arrow shape`
        );
    });
}
```

### Test: Confidence affects edge line style

```javascript
if (DEBUG) {
    const confidenceStyles = { high: 'solid', medium: 'dashed', low: 'dotted' };
    cy.edges().forEach(e => {
        const conf = e.data('confidence');
        if (conf && confidenceStyles[conf]) {
            const expected = confidenceStyles[conf];
            const actual = e.style('line-style');
            console.assert(actual === expected,
                `Edge ${e.id()} with confidence "${conf}" should be "${expected}" but is "${actual}"`
            );
        }
    });
}
```

### Test: Zoom, pan, and drag interactions are enabled

```javascript
if (DEBUG) {
    console.assert(cy.userZoomingEnabled(), 'User zooming should be enabled');
    console.assert(cy.userPanningEnabled(), 'User panning should be enabled');
    console.assert(cy.nodes().first().grabbable(), 'Nodes should be grabbable (draggable)');
}
```

### Test: Cyclic dependency edges render with red dashed style

```javascript
if (DEBUG) {
    cy.edges('.cycle').forEach(e => {
        console.assert(
            e.style('line-color') === 'rgb(220, 38, 38)' || e.hasClass('cycle'),
            `Cyclic edge ${e.id()} should have red color or cycle class`
        );
        console.assert(
            e.style('line-style') === 'dashed',
            `Cyclic edge ${e.id()} should be dashed`
        );
    });
}
```

### Fixture needed

- `fixture-medium.json` -- 15 documents, 25 relationships, 10 findings. This is the primary visual test fixture and should already exist from section-02.

---

## Implementation Details

### AppState Object

A central state object that coordinates shared state across all modules. Define it before any class that reads state.

```javascript
const AppState = {
    activeView: 'graph',        // 'graph' | 'timeline'
    layout: 'dagre',            // 'dagre' | 'cola' | 'breadthfirst'
    filters: {
        relationshipTypes: [],  // active types (empty = all)
        documentTypes: [],      // active types (empty = all)
        confidenceLevel: 'all'  // 'all' | 'medium' | 'high'
    },
    searchQuery: '',
    overlayEnabled: false,
    selectedEntity: null        // { type: 'node'|'edge', id: '...' } or null
};
```

This is a plain object, not a class. Other modules read from it directly and update it as needed. No pub/sub framework -- direct mutation is fine for this single-file architecture.

### GraphRenderer Class

The `GraphRenderer` class owns the Cytoscape instance and all direct graph manipulation.

**Constructor signature:**

```javascript
class GraphRenderer {
    constructor(containerId, elements, styleConfig) { ... }
}
```

- `containerId` -- string ID of the DOM element (e.g., `'graph-container'`)
- `elements` -- the output of `dataAdapter.getCytoscapeElements()`
- `styleConfig` -- optional object for overriding default styles (can be omitted initially)

**Constructor responsibilities:**
1. Create the Cytoscape instance with `cytoscape({ container, elements, style, layout })`
2. Apply dagre as the initial layout
3. Enable zoom, pan, and node dragging
4. Store the instance as `this.cy`

**Method stubs:**

```javascript
applyLayout(layoutName) { /* Switches layout, animated. Updates AppState.layout. */ }
highlightNode(nodeId) { /* Dims non-neighbors to opacity ~0.3, highlights selected + neighbors. */ }
clearHighlight() { /* Removes all highlight classes, restores default opacity. */ }
filterByRelationshipType(types) { /* Shows only edges whose relType is in types array. */ }
filterByDocumentType(types) { /* Shows only nodes whose docType is in types array, hides orphaned edges. */ }
filterByConfidence(minLevel) { /* Hides edges below threshold. */ }
searchDocuments(query) { /* Adds .search-dimmed class to non-matching nodes. */ }
fitToScreen() { /* cy.fit() with ~50px padding. */ }
exportSVG() { /* Returns SVG string via cytoscape-svg extension, or null if unavailable. */ }
```

Note: `filterByRelationshipType`, `filterByDocumentType`, `filterByConfidence`, and `searchDocuments` are defined here as stubs. Their full implementation happens in section-05-layouts-filtering. This section only needs to implement the constructor, `applyLayout('dagre')`, `highlightNode`, `clearHighlight`, `fitToScreen`, and `exportSVG`.

### Cytoscape Style Array

The style array passed to the Cytoscape constructor defines how nodes and edges look.

**Node styling by document type category:**

Group the 21 possible document types into 5-7 broad categories. Each category gets a background color and a shape:

| Category | Color (muted) | Shape | Document Types |
|----------|--------------|-------|----------------|
| Primary | `#3b82f6` (blue) | rectangle | purchase_agreement, merger_agreement, loan_agreement |
| Ancillary | `#8b5cf6` (purple) | ellipse | side_letter, joinder, consent |
| Financial | `#10b981` (emerald) | diamond | promissory_note, guaranty, security_agreement, pledge_agreement |
| Corporate | `#f59e0b` (amber) | hexagon | certificate_of_incorporation, bylaws, board_resolution, officers_certificate |
| Real Estate | `#6366f1` (indigo) | round-rectangle | deed, title_policy, survey, lease |
| Regulatory | `#ef4444` (red) | triangle | regulatory_approval, compliance_certificate |
| Closing | `#64748b` (slate) | cut-rectangle | closing_checklist, escrow_agreement, settlement_statement |

The implementer should create a `DOC_TYPE_CATEGORIES` mapping object that maps each document type string to its category, then use the category to look up color and shape in the Cytoscape style selectors via CSS classes. The `DataAdapter` (section-02) already places category classes like `category-financial` on each node element.

**Node size scaling:**

Node width and height should scale with the node's degree (number of connected edges) using a square-root function clamped between 40 and 80 pixels:

```javascript
{
    selector: 'node',
    style: {
        'width': function(ele) {
            return Math.min(80, Math.max(40, 40 + Math.sqrt(ele.degree()) * 10));
        },
        'height': function(ele) {
            return Math.min(80, Math.max(40, 40 + Math.sqrt(ele.degree()) * 10));
        },
    }
}
```

**Label truncation:**

```javascript
'label': function(ele) {
    const name = ele.data('label') || ele.data('id');
    return name.length > 20 ? name.substring(0, 20) + '...' : name;
}
```

Font: 11px, the system font stack. Color: dark gray `#1f2937`. Text wrap: `'wrap'`, max-width: `'80px'`.

**Edge styling by relationship type family:**

| Family | Color | Relationship Types |
|--------|-------|--------------------|
| Control/hierarchy | `#ef4444` (red/warm) | controls, subordinates_to, supersedes |
| Reference | `#3b82f6` (blue) | references, incorporates |
| Financial | `#10b981` (green) | guarantees, secures, assigns, indemnifies |
| Modification | `#8b5cf6` (purple) | amends, restricts, restates |
| Conditional | `#f59e0b` (amber) | triggers, conditions_precedent, consents_to |
| Term | `#14b8a6` (teal) | defines_terms_for |

**Confidence-based line style:**

```javascript
{ selector: 'edge[confidence = "high"]',   style: { 'line-style': 'solid' } },
{ selector: 'edge[confidence = "medium"]', style: { 'line-style': 'dashed' } },
{ selector: 'edge[confidence = "low"]',    style: { 'line-style': 'dotted' } },
```

**Edge arrows:** All edges get `'target-arrow-shape': 'triangle'`.

**Cyclic edge styling:**

```javascript
{
    selector: 'edge.cycle',
    style: {
        'line-color': '#dc2626',
        'line-style': 'dashed',
        'target-arrow-color': '#dc2626',
        'width': 3
    }
}
```

### Dagre Layout Configuration

```javascript
{
    name: 'dagre',
    rankDir: 'TB',
    nodeSep: 60,
    rankSep: 80,
    edgeSep: 20,
    animate: true,
    animationDuration: 500,
    fit: true,
    padding: 50
}
```

### Visual State CSS Classes

```javascript
{ selector: '.filtered-out',   style: { 'display': 'none' } },
{ selector: '.search-dimmed',  style: { 'opacity': 0.2 } },
{ selector: '.highlighted',    style: { 'opacity': 1, 'border-width': 3, 'border-color': '#2563eb' } },
{ selector: '.dimmed',         style: { 'opacity': 0.15 } },
```

### fitToScreen Method

```javascript
fitToScreen() {
    this.cy.fit(50);
}
```

### exportSVG Method

```javascript
exportSVG() {
    if (typeof this.cy.svg === 'function') {
        return this.cy.svg({ scale: 1, full: true });
    }
    return null;
}
```

### Initialization Sequence

```javascript
document.addEventListener('DOMContentLoaded', () => {
    const elements = dataAdapter.getCytoscapeElements();
    const graphRenderer = new GraphRenderer('graph-container', elements);
    window.cy = graphRenderer.cy;
    window.graphRenderer = graphRenderer;
});
```

---

## Checklist

1. Define `AppState` object with all shared state fields
2. Define `DOC_TYPE_CATEGORIES` mapping (document type string to category)
3. Define `REL_TYPE_FAMILIES` mapping (relationship type string to color family)
4. Build the Cytoscape style array with all node, edge, and state-class selectors
5. Implement `GraphRenderer` constructor (create Cytoscape instance, apply dagre layout)
6. Implement `fitToScreen()` method
7. Implement `exportSVG()` method
8. Implement `highlightNode(nodeId)` and `clearHighlight()` methods
9. Add stub methods for filter/search (implemented in section-05)
10. Wire initialization in `DOMContentLoaded` handler
11. Add all DEBUG assertion blocks
12. Test visually with `fixture-medium.json` in a browser
