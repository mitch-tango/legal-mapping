# Section 06: Analysis Overlay

## Overview

This section implements the `AnalysisOverlay` class, which manages the "Show Issues" toggle that overlays analysis findings on the graph. When enabled, it adds severity-colored border rings to affected nodes, shows finding count badges, displays a summary panel with severity counts, and allows clicking a finding to highlight its affected entities. The overlay operates independently of filter and search state and persists across layout changes.

**File to modify:** The single HTML visualization file (e.g., `{deal_name}-visualization.html`), specifically the application `<script>` block.

## Dependencies

- **section-01-foundation**: HTML skeleton must include the "Show Issues" toggle button in the toolbar and a container element for the summary panel.
- **section-02-data-adapter**: `DataAdapter` must provide `getFindingsForEntity(entityType, entityId)`, `getFindingsSummary()`, and access to all findings data.
- **section-03-graph-core**: `GraphRenderer` must expose the Cytoscape instance and support adding/removing CSS classes on elements. The `AppState` object must have an `overlayEnabled` property.

## Tests

All tests are inline console assertions behind the `DEBUG` flag.

### Test: "Show Issues" toggle is disabled when DEAL_ANALYSIS is null

When `DEAL_ANALYSIS` is null, the "Show Issues" toggle button in the toolbar must have the `disabled` attribute set. Verify by checking `toggleElement.disabled === true`.

### Test: Enabling overlay adds severity-colored border rings to affected nodes

After calling `overlay.enable()`, every node that has at least one associated finding must have a Cytoscape CSS class applied corresponding to its highest severity finding. Verify by checking that `node.hasClass('finding-critical')` or similar returns true.

### Test: Critical findings get red rings, error gets amber, warning gets blue, info gets gray

Verify the Cytoscape stylesheet entries map the overlay classes to the correct border colors:
- `.finding-critical` -> border-color `#dc2626` (red-600)
- `.finding-error` -> border-color `#d97706` (amber-600)
- `.finding-warning` -> border-color `#2563eb` (blue-600)
- `.finding-info` -> border-color `#6b7280` (gray-500)

### Test: Finding count badges appear on nodes with findings

When overlay is enabled, nodes with findings should display a badge showing the count. Verify that the badge text matches the actual finding count for each affected node.

### Test: Summary panel shows correct counts

When overlay is enabled, a summary panel element should become visible and display text matching `dataAdapter.getFindingsSummary()`.

### Test: Disabling overlay removes all rings, badges, and summary

After calling `overlay.disable()`, verify `cy.nodes('.finding-critical, .finding-error, .finding-warning, .finding-info').length === 0` and summary panel is hidden.

### Test: Clicking a finding in the detail panel highlights affected entities

Verify `highlightFinding(findingId)` highlights affected elements and dims others.

### Test: Overlay state is independent of filter state

Enable overlay, apply filter. Overlay rings should remain on visible nodes. Disable overlay -- filters remain unchanged.

### Test: Overlay decorations persist across layout changes

Enable overlay, switch layout. Verify `finding-*` classes remain on same nodes after layout animation.

### Fixtures needed

- **fixture-medium.json** (reuse) -- has 10 findings across severity levels.
- **fixture-null-analysis.json** (reuse) -- verifies toggle is disabled.

## Implementation Details

### AnalysisOverlay Class

```javascript
class AnalysisOverlay {
    constructor(graphRenderer, dataAdapter, appState) { /* ... */ }

    enable()
    // 1. Set appState.overlayEnabled = true
    // 2. Get all findings from dataAdapter
    // 3. For each affected node, determine highest severity finding
    // 4. Add appropriate CSS class: 'finding-critical', 'finding-error', etc.
    // 5. Add finding count badges to affected nodes
    // 6. Show the summary panel with severity counts
    // 7. Thicken and color affected edges (if findings reference edges)

    disable()
    // 1. Set appState.overlayEnabled = false
    // 2. Remove all 'finding-*' classes from all nodes and edges
    // 3. Remove all badge elements/overlays
    // 4. Hide the summary panel

    highlightFinding(findingId)
    // 1. Look up finding by ID
    // 2. Highlight affected elements, dim others

    isEnabled()
    // Returns appState.overlayEnabled
}
```

### Cytoscape Style Entries

```javascript
{ selector: '.finding-critical', style: { 'border-color': '#dc2626', 'border-width': 5 } },
{ selector: '.finding-error',    style: { 'border-color': '#d97706', 'border-width': 4 } },
{ selector: '.finding-warning',  style: { 'border-color': '#2563eb', 'border-width': 4 } },
{ selector: '.finding-info',     style: { 'border-color': '#6b7280', 'border-width': 3 } },
```

### Severity Priority

When a node has multiple findings of different severities, the highest severity determines the ring color (CRITICAL > ERROR > WARNING > INFO). Badge count reflects total findings regardless of severity.

### Finding Count Badges

Recommended: Use Cytoscape node data + label overlay (approach 1) rather than DOM overlay elements. This keeps everything within Cytoscape's rendering pipeline and survives layout changes automatically.

### Summary Panel

An HTML element positioned at the top of the graph area showing severity counts with color-coded dots. Appears on `enable()`, hides on `disable()`. All text via `textContent`.

### Show Issues Toggle Wiring

1. Check if `DEAL_ANALYSIS` is null -- if so, disable toggle with tooltip "No analysis data available"
2. Otherwise, wire click/change event to toggle overlay

### Visual State Precedence

The overlay operates at the lowest visual priority:
- Filtered-out nodes do not show overlay decorations (not rendered)
- Search-dimmed nodes still show overlay rings but at reduced opacity
- Highlighted nodes show overlay rings at full opacity
- Overlay classes add border styling that coexists with other states

### Integration with Layout Changes

Cytoscape classes survive layout re-computation. `applyLayout()` only changes positions, not classes. Overlay decorations persist automatically via Cytoscape classes.

### Integration with Detail Panel

When overlay is enabled and user clicks a node, detail panel (section-04) shows findings. Each finding should be clickable, triggering `overlay.highlightFinding(findingId)`.
