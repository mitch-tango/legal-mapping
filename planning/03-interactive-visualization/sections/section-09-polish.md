# Section 09: Polish

## Overview

This is the final integration section. It adds error handling for CDN load failures and invalid data, keyboard shortcuts, the Edge Labels toggle, a loading spinner during initialization, toolbar tooltips, the `@media print` stylesheet behavior, and the Reset View button wiring. These are finishing touches that make the application robust and professional.

**File to modify:** The single HTML visualization file (e.g., `{deal_name}-visualization.html`), specifically the application `<script>` block, the `<style>` block, and the HTML skeleton.

## Dependencies

All eight prior sections must be complete before this section is implemented:

- **section-01-foundation**: HTML skeleton, CSS layout, toolbar structure, print stylesheet placeholder
- **section-02-data-adapter**: `DataAdapter` class and constructor validation
- **section-03-graph-core**: `GraphRenderer` with `fitToScreen()`, `clearHighlight()`, `applyLayout()`, `AppState`
- **section-04-detail-panel**: `DetailPanel` with `hide()` method
- **section-05-layouts-filtering**: `FilterManager` with reset capability, Edge Labels toggle element
- **section-06-analysis-overlay**: `AnalysisOverlay` for overlay state awareness
- **section-07-timeline-view**: `TimelineView` for view state awareness
- **section-08-pdf-export**: `PDFExporter` for export button wiring

## Tests

### Test: CDN load failure displays full-page error message

Simulate by checking required globals. If `window.cytoscape` is missing, error message element should be visible with text about loading failure.

```javascript
function testCdnFailureMessage() {
    const saved = window.cytoscape;
    window.cytoscape = undefined;
    const result = checkDependencies();
    console.assert(result === false, 'checkDependencies returns false when cytoscape missing');
    const errorEl = document.getElementById('cdn-error');
    console.assert(errorEl && errorEl.style.display !== 'none', 'Error message visible');
    console.assert(errorEl.textContent.includes('could not be loaded'), 'Mentions loading failure');
    window.cytoscape = saved;
}
```

### Test: Invalid DEAL_GRAPH shows diagnostic message

When data lacks `documents` array, validation fails with clear diagnostic.

```javascript
function testInvalidDataDiagnostic() {
    const invalid = { metadata: { deal_name: 'Test' } };
    const result = validateDealGraph(invalid);
    console.assert(result.valid === false, 'Validation should fail');
    console.assert(result.errors.includes('documents'), 'Identifies missing documents field');
}
```

### Test: Escape key closes detail panel

Simulate `keydown` with `key === 'Escape'`. Panel should be hidden.

### Test: F key triggers fit-to-screen

Simulate `keydown` with `key === 'f'`. Verify `graphRenderer.fitToScreen()` was called.

### Test: R key triggers reset view

Simulate `keydown` with `key === 'r'`. Verify highlights cleared, zoom reset, layout re-run. Filters and overlay NOT cleared.

### Test: Reset View button triggers same behavior as R key

Click Reset View button. Same `resetView()` function is invoked.

### Test: Edge Labels toggle shows/hides edge label text

When off (default), edge labels empty. When on, edges display relType. Check `cy.edges()[0].style('label')`.

### Test: Loading spinner appears during initial Cytoscape setup

Spinner element visible before init, hidden after init completes.

### Test: @media print hides toolbar, sidebar, filter panels

CSS `@media print` block sets `display: none` on toolbar, detail panel, filter panel. Shows centered message.

### Test: Tooltips appear on toolbar buttons on hover

All toolbar buttons have `title` attributes with descriptive strings.

## Fixture

### `fixture-invalid.json`

Malformed data missing required fields:

```json
{
    "metadata": {
        "deal_name": "Invalid Test Deal"
    }
}
```

Missing `documents` array, `relationships` array, and other required fields. Validation function detects omissions.

## Implementation Details

### 1. CDN Load Failure Detection

Each CDN `<script>` tag has an `onerror` handler setting `window.__cdnFailed = true`. Before app init, `checkDependencies()` verifies required globals:

- `window.cytoscape`
- `window.jspdf` (or `window.jspdf.jsPDF`)
- `window.svg2pdf`

If missing, create full-page overlay (`id="cdn-error"`) with: "Required libraries could not be loaded. Please check your internet connection and reload." Do not initialize the app.

### 2. Data Validation

`validateDealGraph(data)` checks:
- `data` is non-null object
- `data.documents` is an array
- Each document has an `id` string
- `data.relationships` is an array
- `data.metadata` exists with `deal_name` string

Returns `{ valid: boolean, errors: string[] }`. On failure, show diagnostic div with bulleted list. For empty deals (valid but `documents.length === 0`), show "No documents in this deal" with guidance.

### 3. Keyboard Shortcuts

Single `document.addEventListener('keydown', handleKeyboard)` handler. Ignores keypresses when focus is on `INPUT`, `TEXTAREA`, or `SELECT`.

| Key | Action |
|-----|--------|
| `Escape` | Close detail panel, clear highlights |
| `f` / `F` | Fit graph to screen |
| `r` / `R` | Reset view |

### 4. Reset View Function

Shared by R key and Reset View button:

1. `graphRenderer.clearHighlight()`
2. Clear search box text and search state
3. `cy.fit()` with padding
4. `graphRenderer.applyLayout(appState.currentLayout)`

Does NOT reset filter toggles or overlay toggle.

### 5. Edge Labels Toggle

Default: off (clean graph). Toggle wires to `GraphRenderer.toggleEdgeLabels(visible)` which updates Cytoscape edge style `label` to `data.relType` (on) or empty string (off).

### 6. Loading Spinner

HTML element visible by default, overlaying graph container with centered spinner and "Loading..." text. CSS-only animation (rotating border). Hidden after Cytoscape init and layout animation complete.

### 7. Toolbar Tooltips

| Element | `title` |
|---------|---------|
| View switcher | "Switch between Graph and Timeline views" |
| Layout switcher | "Change graph layout algorithm" |
| Search box | "Search documents by name" |
| Show Issues toggle | "Toggle analysis findings overlay" |
| Edge Labels toggle | "Show/hide relationship labels on edges" |
| Filter button | "Filter by document type, relationship type, or confidence" |
| Reset View button | "Reset zoom, clear highlights, re-run layout (R)" |
| Export PDF button | "Export deal analysis as PDF report" |

### 8. Print Stylesheet

Complete the `@media print` block:

```css
@media print {
    .toolbar { display: none !important; }
    .detail-panel { display: none !important; }
    .filter-panel { display: none !important; }
    .timeline-container { display: none !important; }
    #graph-container { display: none !important; }
    .print-message {
        display: block !important;
        text-align: center;
        padding: 2rem;
        font-size: 18px;
    }
}
```

`.print-message` element hidden by default, contains "For the best report, use the Export PDF button" with deal name.

### 9. App Initialization Flow

```javascript
function initializeApp() {
    // 1. Check CDN dependencies -> show error and stop if missing
    // 2. Parse DEAL_GRAPH and DEAL_ANALYSIS from data islands
    // 3. Validate with validateDealGraph() -> show diagnostics and stop if invalid
    // 4. Empty documents check -> show message and stop
    // 5. Create DataAdapter
    // 6. Create GraphRenderer (spinner visible)
    // 7. Create DetailPanel, FilterManager, AnalysisOverlay, TimelineView, PDFExporter
    // 8. Register keyboard shortcut handler
    // 9. Wire Reset View button
    // 10. Wire Edge Labels toggle
    // 11. Add tooltips to toolbar elements
    // 12. Hide loading spinner
    // 13. If findings exist, show notification: "X issues found -- toggle Show Issues to view"
}
```

Wrapped in try/catch for graceful error display.

### 10. Cross-Browser Notes

- Test in Chrome (primary), Edge, Firefox, Safari
- All modern browsers supported (no IE11)
- CSS custom properties supported everywhere
- System font stack renders appropriately cross-platform
