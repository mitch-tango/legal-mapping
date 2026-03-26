# Section 05: Layouts and Filtering

## Overview

This section adds alternative graph layouts (force-directed via Cola, tree via Breadthfirst) with an animated layout switcher, and a comprehensive filtering system (relationship type, document type, confidence level, text search, reset). It also establishes the visual state precedence model that governs how Filter, Search, Highlight, and Overlay interact via CSS classes on Cytoscape elements.

**Dependencies:** Sections 01 (HTML skeleton with toolbar containers), 02 (DataAdapter providing `getRelationshipTypes()`, `getDocumentTypes()`), and 03 (GraphRenderer with Cytoscape instance, AppState, dagre layout already working).

**Output file:** The single HTML visualization file (same file created in sections 01-03). All code goes into the existing `<script>` block and `<style>` block.

---

## Tests

All tests are inline console assertions behind the `DEBUG` flag, added to the self-test block established in earlier sections.

### 5. Alternative Layouts

```javascript
// Test: Layout switcher dropdown contains Dagre, Force-directed, Tree options
(function testLayoutSwitcherOptions() {
    const select = document.getElementById('layout-switcher');
    console.assert(select, 'Layout switcher element exists');
    const options = Array.from(select.options).map(o => o.value);
    console.assert(options.includes('dagre'), 'Has dagre option');
    console.assert(options.includes('cola'), 'Has cola/force-directed option');
    console.assert(options.includes('breadthfirst'), 'Has breadthfirst/tree option');
})();

// Test: Selecting layout updates AppState
(function testLayoutSwitching() {
    graphRenderer.applyLayout('cola');
    console.assert(appState.layout === 'cola', 'AppState tracks cola layout');
})();

// Test: Layout transition is animated (animation duration > 0)
(function testLayoutAnimated() {
    console.assert(
        graphRenderer._getLayoutOptions('dagre').animate !== false,
        'Layout animation is enabled'
    );
})();

// Test: State persists across layout switch
(function testStatePersistsAcrossLayout() {
    const savedFilters = { ...appState.filters };
    const savedOverlay = appState.overlayEnabled;
    graphRenderer.applyLayout('dagre');
    console.assert(
        JSON.stringify(appState.filters) === JSON.stringify(savedFilters),
        'Filters persist across layout change'
    );
    console.assert(appState.overlayEnabled === savedOverlay, 'Overlay persists across layout change');
})();
```

### 6. Filtering

```javascript
// Test: Relationship type filter checkboxes are generated from actual data
(function testRelTypeCheckboxesFromData() {
    const types = dataAdapter.getRelationshipTypes();
    const checkboxes = document.querySelectorAll('.filter-rel-type input[type="checkbox"]');
    console.assert(checkboxes.length === types.length,
        `Rel type checkboxes (${checkboxes.length}) match data types (${types.length})`);
})();

// Test: Document type filter checkboxes are generated from actual data
(function testDocTypeCheckboxesFromData() {
    const types = dataAdapter.getDocumentTypes();
    const checkboxes = document.querySelectorAll('.filter-doc-type input[type="checkbox"]');
    console.assert(checkboxes.length === types.length,
        `Doc type checkboxes (${checkboxes.length}) match data types (${types.length})`);
})();

// Test: Unchecking a relationship type hides those edges
(function testRelTypeFilterHidesEdges() {
    const types = dataAdapter.getRelationshipTypes();
    if (types.length > 0) {
        const typeToHide = types[0];
        graphRenderer.filterByRelationshipType(types.filter(t => t !== typeToHide));
        const hiddenEdges = cy.edges().filter(e =>
            e.data('relType') === typeToHide && e.hasClass('filtered-out')
        );
        console.assert(hiddenEdges.length > 0, `Edges of type "${typeToHide}" are filtered out`);
        graphRenderer.filterByRelationshipType(types);
    }
})();

// Test: Hiding all edges of a type doesn't hide connected nodes
(function testRelFilterDoesNotHideNodes() {
    const types = dataAdapter.getRelationshipTypes();
    if (types.length > 0) {
        graphRenderer.filterByRelationshipType([]);
        const visibleNodes = cy.nodes().filter(n => !n.hasClass('filtered-out'));
        console.assert(visibleNodes.length === cy.nodes().length,
            'All nodes remain visible when all edges are filtered');
        graphRenderer.filterByRelationshipType(types);
    }
})();

// Test: Unchecking a document type hides those nodes AND their incident edges
(function testDocTypeFilterHidesNodesAndEdges() {
    const types = dataAdapter.getDocumentTypes();
    if (types.length > 0) {
        const typeToHide = types[0];
        graphRenderer.filterByDocumentType(types.filter(t => t !== typeToHide));
        const hiddenNodes = cy.nodes().filter(n =>
            n.data('docType') === typeToHide && n.hasClass('filtered-out')
        );
        console.assert(hiddenNodes.length > 0, `Nodes of type "${typeToHide}" are filtered out`);
        hiddenNodes.forEach(n => {
            n.connectedEdges().forEach(e => {
                console.assert(e.hasClass('filtered-out'),
                    `Edge ${e.id()} connected to filtered node is also filtered`);
            });
        });
        graphRenderer.filterByDocumentType(types);
    }
})();

// Test: Confidence filter at "High only" hides medium and low confidence edges
(function testConfidenceFilter() {
    graphRenderer.filterByConfidence('high');
    const medLowEdges = cy.edges().filter(e =>
        ['medium', 'low'].includes(e.data('confidence'))
    );
    medLowEdges.forEach(e => {
        console.assert(e.hasClass('filtered-out'),
            `Edge ${e.id()} with confidence "${e.data('confidence')}" filtered at high-only`);
    });
    graphRenderer.filterByConfidence('all');
})();

// Test: Search box dims non-matching nodes in real-time
(function testSearchDimming() {
    const firstNodeLabel = cy.nodes()[0]?.data('label');
    if (firstNodeLabel) {
        graphRenderer.searchDocuments(firstNodeLabel.substring(0, 3).toLowerCase());
        const dimmed = cy.nodes().filter(n => n.hasClass('search-dimmed'));
        const notDimmed = cy.nodes().filter(n => !n.hasClass('search-dimmed'));
        console.assert(notDimmed.length > 0, 'At least one node matches search');
        graphRenderer.searchDocuments('');
    }
})();

// Test: Reset filters button exists
(function testResetFilters() {
    const resetBtn = document.getElementById('reset-filters');
    console.assert(resetBtn, 'Reset filters button exists');
})();

// Test: Combining filters is additive
(function testCombinedFilters() {
    const docTypes = dataAdapter.getDocumentTypes();
    const relTypes = dataAdapter.getRelationshipTypes();
    if (docTypes.length > 1 && relTypes.length > 0) {
        graphRenderer.filterByDocumentType(docTypes.slice(1));
        graphRenderer.filterByConfidence('high');
        const filteredNodes = cy.nodes('.filtered-out');
        const filteredEdges = cy.edges('.filtered-out');
        console.assert(filteredNodes.length > 0 || filteredEdges.length > 0,
            'Combined filters produce filtered elements');
        graphRenderer.filterByDocumentType(docTypes);
        graphRenderer.filterByConfidence('all');
    }
})();
```

### Fixture needed

Reuse `fixture-medium.json` (15 docs, 25 relationships, 10 findings) created in section 02. No new fixtures required.

---

## Implementation Details

### A. CDN Dependency: cytoscape-cola

Section 01 includes CDN script tags for Cytoscape core, dagre, and cytoscape-dagre. This section requires the Cola layout plugin. Add the `<script>` tag after `cytoscape-dagre.js` and before the jsPDF scripts. The breadthfirst layout is built into Cytoscape core and requires no additional script.

### B. Layout Switcher UI

The `<select>` with `id="layout-switcher"` in the toolbar (from section 01) should have options:
- `<option value="dagre" selected>Dagre (Hierarchical)</option>`
- `<option value="cola">Force-directed</option>`
- `<option value="breadthfirst">Tree</option>`

Wire the `change` event to call `graphRenderer.applyLayout(select.value)` and update `appState.layout`.

### C. GraphRenderer Layout Methods

Extend the `GraphRenderer` class (from section 03) with layout switching.

**`_getLayoutOptions(layoutName)`** -- private method returning Cytoscape layout options:

- `dagre`: `{ name: 'dagre', rankDir: 'TB', nodeSep: 50, rankSep: 80, animate: true, animationDuration: 500 }`
- `cola`: `{ name: 'cola', animate: true, maxSimulationTime: 2000, nodeSpacing: 30, edgeLength: 150, randomize: false }`
- `breadthfirst`: `{ name: 'breadthfirst', directed: true, spacingFactor: 1.5, animate: true, animationDuration: 500 }`

**`applyLayout(layoutName)`** -- stops any running layout, applies the new one. Must NOT clear filters, selections, highlights, or overlay state. Updates `appState.layout`. Calls `cy.layout(options).run()`.

### D. Filter Panel UI

A collapsible panel triggered by the "Filter" toolbar button, containing:

1. **Relationship Type Checkboxes** (container class: `filter-rel-type`) -- generated from `dataAdapter.getRelationshipTypes()`, with color swatches matching edge colors. All checked by default.
2. **Document Type Checkboxes** (container class: `filter-doc-type`) -- generated from `dataAdapter.getDocumentTypes()`, with color swatches. All checked by default.
3. **Confidence Level Selector** -- three radio buttons: "All", "Medium+", "High only". Default: "All".
4. **Reset Filters Button** (`id="reset-filters"`) -- re-checks all, resets confidence, clears search.

### E. FilterManager Class

```javascript
class FilterManager {
    constructor(graphRenderer, dataAdapter, appState) { /* ... */ }

    init()
    // Generates checkbox HTML, wires event listeners, wires search debounce

    _applyFilters()
    // Reads all filter controls, calls graphRenderer methods, updates appState.filters

    _onSearchInput(query)
    // Calls graphRenderer.searchDocuments(query), updates appState.searchQuery

    resetAll()
    // Resets all controls to defaults, calls _applyFilters(), clears search
}
```

### F. GraphRenderer Filter/Search Methods

Implement the stubs from section 03:

**`filterByRelationshipType(activeTypes)`** -- Edges not in `activeTypes` get `filtered-out` class. Does NOT affect nodes.

**`filterByDocumentType(activeTypes)`** -- Nodes not in `activeTypes` get `filtered-out` class. Their incident edges also get `filtered-out`.

**`filterByConfidence(minLevel)`** -- Edges below threshold get `filtered-out`.

**Recommended approach: Recompute all filters from scratch.** Each time any filter changes, `_applyFilters()` iterates all elements once, applies all three criteria, and sets/removes `filtered-out` accordingly. This avoids class management bugs.

**`searchDocuments(query)`** -- Empty query removes `search-dimmed` from all nodes. Non-empty query dims non-matching nodes (case-insensitive substring match on `data.label`). Independent of filtering.

### G. Visual State Precedence

Cytoscape style selectors ordered by priority:

```javascript
{ selector: '.filtered-out',   style: { display: 'none' } },
{ selector: '.search-dimmed',  style: { opacity: 0.15 } },
{ selector: '.highlighted',    style: { opacity: 1.0 } },
```

Precedence: Filter (removes) > Search (dims) > Highlight (restores) > Overlay (adds decorations).

### H. Search Box

Wire the `<input>` search box `input` event to `filterManager._onSearchInput()` with 200ms debounce.

### I. CSS for Filter Panel

- Dropdown positioned absolutely below the "Filter" button
- White background, subtle border/shadow, max-height with overflow scroll
- Checkbox labels with small color swatch squares (10x10px)
- Subsection headers as small uppercase labels
- Closes when clicking outside
