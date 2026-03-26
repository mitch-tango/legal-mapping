# Section 07: Timeline View

## Overview

This section implements the `TimelineView` class and the view switcher mechanism that toggles between the Graph canvas and a Timeline table. The Timeline view renders the execution sequence from `DEAL_ANALYSIS` as an HTML table showing closing order, dependencies, status, and gating conditions. It is a standalone alternate view of the deal data -- not a graph visualization but a structured data table.

**Dependencies:** section-01-foundation (HTML skeleton with timeline container and view switcher elements), section-02-data-adapter (DataAdapter providing `getExecutionSequence()` and document lookup methods).

**Does NOT depend on:** section-03-graph-core, though the click-to-navigate feature coordinates with it at integration time (section-09-polish).

---

## Tests

All tests are inline console assertions behind a `DEBUG` flag.

### Test: View switcher shows "Graph" and "Timeline" options

Verify the view switcher element in the toolbar contains exactly two options with values `"graph"` and `"timeline"`.

### Test: Selecting "Timeline" hides graph canvas, shows timeline container

When the view switcher value changes to `"timeline"`, the graph container must be hidden and the timeline container must be visible. The layout switcher should also be hidden.

### Test: Timeline renders an HTML table with correct columns

After calling `TimelineView.render()`, the timeline container must contain a `<table>` with `<thead>` columns: Sequence #, Document Name, Dependencies, Status, Gating Conditions.

### Test: Table rows match the execution sequence order

Using fixture data, confirm row count equals execution sequence length and first row's Sequence # is "1".

### Test: Status badges render correctly (pending=yellow, satisfied=green, waived=gray)

Verify status cells contain `<span>` elements with appropriate CSS classes.

### Test: Documents in same parallel execution window are visually grouped

Rows sharing the same sequence number should have a visual grouping indicator (shared background, merged cell, or CSS class).

### Test: Clicking a document name switches back to graph view

Verify document name cells are clickable and the registered `onDocumentClick` callback fires with the correct document ID.

### Test: Timeline shows "not available" message when no execution_sequence

Using `fixture-null-analysis.json`, verify the message "Execution sequence analysis not available" is displayed and no `<table>` element exists.

### Test: Switching back to Graph preserves previous graph state

Verify the view switcher only toggles container visibility, not reinitializing the graph.

### Fixtures needed

- `fixture-medium.json` (reuse) -- must include execution_sequence in DEAL_ANALYSIS
- `fixture-null-analysis.json` (reuse)

---

## Implementation Details

### File to modify

`{deal_name}-visualization.html` -- the single self-contained HTML file. All code in the application `<script>` block.

### TimelineView Class

```javascript
class TimelineView {
    constructor(containerElementId, dataAdapter) { /* ... */ }

    render()
    // Builds HTML table from dataAdapter.getExecutionSequence()
    // If empty/unavailable, shows fallback message
    // All text via textContent (XSS safe)

    onDocumentClick(callback)
    // Registers callback: (docId) => { ... }

    destroy()
    // Removes event listeners and clears container
}
```

### render() behavior

1. Call `this.dataAdapter.getExecutionSequence()`. If empty/null, render "Execution sequence analysis not available." and return.

2. Build table structure: `<table class="timeline-table">` with `<thead>` (Sequence #, Document Name, Dependencies, Status, Gating Conditions) and `<tbody>`.

3. For each entry:
   - **Sequence #**: step number via `textContent`
   - **Document Name**: clickable element with `data-doc-id`, text via `textContent`
   - **Dependencies**: comma-separated names via `textContent`
   - **Status**: `<span class="status-badge status-{value}">` via `textContent`
   - **Gating Conditions**: text via `textContent`

4. Parallel execution grouping: entries sharing the same sequence number get visual grouping (alternating CSS classes, merged first-column cells).

5. Attach click handlers to document links calling `onDocumentClick` callback.

### View Switcher Wiring

```javascript
viewSwitcher.addEventListener('change', (e) => {
    const view = e.target.value;
    AppState.activeView = view;
    if (view === 'timeline') {
        graphContainer.style.display = 'none';
        timelineContainer.style.display = 'block';
        layoutSwitcher.style.display = 'none';
        timelineView.render();
    } else {
        graphContainer.style.display = 'block';
        timelineContainer.style.display = 'none';
        layoutSwitcher.style.display = '';
        // Do NOT reinitialize graph
    }
});
```

### CSS for Timeline Table

- `.timeline-table` -- full width, border-collapse, professional styling
- Alternating row shading on `tbody tr:nth-child(even)` -- subtle gray `#f3f4f6`
- `.timeline-doc-link` -- blue link style, underline on hover, cursor pointer
- `.status-badge` -- inline-block rounded pill
- `.status-pending` -- yellow/amber background (`#fef3c7`), dark amber text
- `.status-satisfied` -- green background (`#d1fae5`), dark green text
- `.status-waived` -- gray background (`#f3f4f6`), dark gray text
- `.parallel-group-even`, `.parallel-group-odd` -- subtle visual distinction
- Sortable headers: cursor pointer on `<th>`, optional sort arrows
- `#timeline-container` -- starts hidden, internal padding, overflow-y auto

### Click-to-Navigate Integration

```javascript
timelineView.onDocumentClick((docId) => {
    viewSwitcher.value = 'graph';
    viewSwitcher.dispatchEvent(new Event('change'));
    graphRenderer.highlightNode(docId);
    graphRenderer.fitToScreen();
});
```

This wiring happens in main initialization, not inside TimelineView.

### "Not Available" State

When `DEAL_ANALYSIS` is null or has no execution_sequence:
- `getExecutionSequence()` returns empty array
- TimelineView renders centered `<p class="timeline-unavailable">` with the message
- View switcher still allows selection (showing the message is sufficient feedback)
