# Section 01: Foundation -- HTML Skeleton, CSS Layout, and CDN Setup

## Overview

This section builds the foundational HTML file that all subsequent sections extend. It produces a single self-contained HTML file with the complete structural skeleton: toolbar, graph container, detail panel, timeline container, embedded data islands, CDN script tags, CSS layout, color palette variables, typography, print stylesheet, and responsive behavior. No JavaScript application logic is included -- only the static frame.

After completing this section, opening the file in a browser should show a professional-looking empty layout: a toolbar bar across the top, a large graph area filling the viewport, and hidden containers for the detail panel and timeline view.

## File to Create

```
{deal_name}-visualization.html
```

This is the single output file for the entire visualization project. All subsequent sections modify this same file.

## Tests (Inline Console Assertions)

These tests run when `const DEBUG = true;` is set at the top of the application script block. They validate the HTML structure programmatically on page load. Place them inside a self-executing function within the application `<script>` block.

The following assertions must pass:

**Toolbar structure:**
- An element with id `toolbar` exists.
- The toolbar contains child containers for: view switcher, layout switcher, search input, show-issues toggle, edge-labels toggle, filter dropdown trigger, reset-view button, and export-pdf button. Each should be findable by a descriptive id or `data-role` attribute.

**Graph container:**
- An element with id `graph-container` exists.
- It fills the remaining viewport height below the toolbar (verify via `getBoundingClientRect` that its height is greater than zero and its top aligns with the toolbar bottom).

**Detail panel:**
- An element with id `detail-panel` exists.
- It starts hidden -- either `display: none`, `visibility: hidden`, or positioned off-screen (e.g., `transform: translateX(100%)`). The test should confirm it is not visible in the initial state.

**Timeline container:**
- An element with id `timeline-container` exists.
- It starts hidden (same check as detail panel).

**CSS class names:**
- All containers use class names consistent with the plan structure: `.toolbar`, `.graph-container`, `.detail-panel`, `.timeline-container`.

**Print stylesheet:**
- Verify that a `<style>` element containing `@media print` exists in the document.

**Minimum width behavior:**
- Confirm no CSS sets `max-width` on the main layout wrapper, so at 1024px the layout does not break.

**Data islands:**
- A `<script type="application/json" id="deal-graph-data">` element exists.
- A `<script type="application/json" id="deal-analysis-data">` element exists.
- Both are parseable with `JSON.parse()` without throwing.

**CDN scripts:**
- At least 7 `<script>` tags with `src` attributes pointing to CDN URLs exist.
- Each CDN script tag has an `integrity` attribute (SRI hash) and `crossorigin="anonymous"`.

The DEBUG assertion block should look roughly like:

```javascript
const DEBUG = true;

if (DEBUG) {
    (function runStructureTests() {
        const assert = (condition, msg) => {
            console.assert(condition, `[FAIL] ${msg}`);
            if (condition) console.log(`[PASS] ${msg}`);
        };

        // ... all assertions listed above ...

        console.log('--- Structure tests complete ---');
    })();
}
```

Keep the test function self-contained. It should not depend on any application classes or external libraries.

## Implementation Details

### HTML Document Structure

The HTML file uses this top-level structure:

```
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{Deal Name} - Document Dependency Analysis</title>
    <style>/* All CSS here */</style>
</head>
<body>
    <!-- Data Islands -->
    <script type="application/json" id="deal-graph-data">{ ... }</script>
    <script type="application/json" id="deal-analysis-data">null</script>

    <!-- Layout -->
    <div id="app">
        <div id="toolbar" class="toolbar">...</div>
        <div id="main-content">
            <div id="graph-container" class="graph-container"></div>
            <div id="timeline-container" class="timeline-container" style="display:none;"></div>
            <div id="detail-panel" class="detail-panel">...</div>
        </div>
    </div>

    <!-- CDN Dependencies -->
    <script src="..." integrity="..." crossorigin="anonymous"></script>
    <!-- ... 7 total CDN scripts ... -->

    <!-- Application Code -->
    <script>
        // DEBUG flag, tests, and later: all application classes
    </script>
</body>
</html>
```

### Data Islands

Two `<script type="application/json">` blocks hold the deal data. For this section, populate them with minimal valid placeholder JSON so the parse tests pass:

- `deal-graph-data`: `{"deal_name": "Sample Deal", "documents": [], "relationships": []}`
- `deal-analysis-data`: `null`

Claude Code replaces these contents when generating a real visualization. The `type="application/json"` ensures the browser does not execute the contents as JavaScript, preventing XSS from legal text that might contain angle brackets.

### CDN Script Tags

Seven CDN scripts, loaded in order, all with pinned versions, SRI hashes, and `crossorigin="anonymous"`:

1. **cytoscape.min.js** -- Core graph library (~112 KB)
2. **dagre.js** -- Dagre layout algorithm (~30 KB)
3. **cytoscape-dagre.js** -- Cytoscape dagre adapter (~5 KB)
4. **cytoscape-cola.js** -- Constraint-based force-directed layout (~50 KB)
5. **jspdf.umd.min.js** -- PDF generation (~280 KB)
6. **svg2pdf.js** -- SVG to PDF conversion (~45 KB)
7. **jspdf.plugin.autotable.min.js** -- PDF table generation (~50 KB)

Use current stable versions from cdnjs or unpkg. Pin exact version numbers (e.g., `cytoscape@3.28.1`, not `@latest`). Generate correct SRI hashes for each. Each script tag should also have an `onerror` handler that sets a global flag (e.g., `window.__cdnFailed = true`) -- the actual error UI is deferred to section-09-polish, but the hook should be present now.

### Toolbar HTML

The toolbar is a single horizontal bar containing these controls, laid out with flexbox:

- **View switcher**: A `<select>` or button group with options "Graph" and "Timeline". Id or data-role: `view-switcher`.
- **Layout switcher**: A `<select>` with options "Dagre", "Force-directed", "Tree". Id or data-role: `layout-switcher`.
- **Search box**: An `<input type="text" placeholder="Search documents...">`. Id or data-role: `search-box`.
- **Show Issues toggle**: A toggle button or checkbox labeled "Show Issues". Id or data-role: `toggle-issues`.
- **Edge Labels toggle**: A toggle button or checkbox labeled "Edge Labels". Id or data-role: `toggle-edge-labels`.
- **Filter button**: A button that will trigger a dropdown panel. Id or data-role: `filter-trigger`.
- **Reset View button**: A button labeled "Reset View". Id or data-role: `btn-reset-view`.
- **Export PDF button**: A button labeled "Export PDF". Id or data-role: `btn-export-pdf`.

No event handlers are wired in this section. The controls are purely structural HTML. Subsequent sections attach behavior.

### CSS Layout

Use CSS flexbox for the overall layout:

- `body` and `html`: full height, no margin, no scroll.
- `#app`: flex column, full viewport height.
- `.toolbar`: fixed height (~48-56px), flex row, items centered, gap between controls. Light background, subtle bottom border.
- `#main-content`: flex 1 (fills remaining height), position relative (for detail panel overlay).
- `.graph-container`: fills the main-content area completely. This is where Cytoscape will mount.
- `.timeline-container`: same dimensions as graph-container, hidden by default (`display: none`). Shown when Timeline view is selected (handled in section-07).
- `.detail-panel`: fixed width 400px, position absolute, right 0, top 0, height 100%, off-screen by default via `transform: translateX(100%)`. Has `transition: transform 0.3s ease`. When active, transform becomes `translateX(0)`. Has a subtle left box-shadow, white background, overflow-y auto for scrollable content. Contains a close button (X) in the top-right corner.

### CSS Custom Properties (Color Palette)

Define CSS custom properties on `:root` for the full color system:

```css
:root {
    /* UI Chrome */
    --bg-primary: #f8f9fa;
    --bg-panel: #ffffff;
    --border-color: #e5e7eb;
    --text-primary: #1f2937;
    --text-secondary: #6b7280;

    /* Severity */
    --severity-critical: #dc2626;
    --severity-error: #d97706;
    --severity-warning: #2563eb;
    --severity-info: #6b7280;

    /* Document Type Categories (5-7 groups) */
    --cat-primary: #3b82f6;
    --cat-ancillary: #8b5cf6;
    --cat-financial: #10b981;
    --cat-corporate: #f59e0b;
    --cat-real-estate: #ef4444;
    --cat-regulatory: #6366f1;
    --cat-closing: #14b8a6;

    /* Edge Type Families */
    --edge-control: #ef4444;
    --edge-reference: #3b82f6;
    --edge-financial: #10b981;
    --edge-modification: #8b5cf6;
    --edge-conditional: #f59e0b;
    --edge-term: #14b8a6;
}
```

These variables are consumed by Cytoscape style configuration (section-03), detail panel badges (section-04), and overlay rings (section-06).

### Typography

Apply the system font stack globally:

```css
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: var(--text-primary);
    background: var(--bg-primary);
}
```

The type hierarchy (20px/700 for deal name, 16px/600 for section headers, 14px/500 for doc names, 13px/400 for body, 11px for graph labels) should be established as CSS classes or defined inline where used. At minimum define utility classes for the major levels.

### Print Stylesheet

Include a `@media print` block within the `<style>` element:

```css
@media print {
    .toolbar, .detail-panel, .filter-panel {
        display: none !important;
    }
    .graph-container {
        display: none !important;
    }
    body::after {
        content: "For the best report, use the Export PDF button.";
        display: block;
        text-align: center;
        font-size: 18px;
        padding: 40px;
        color: var(--text-secondary);
    }
}
```

This prevents users from getting a useless Ctrl+P printout and directs them to the PDF export.

### Responsive Behavior

- Minimum supported width: 1024px. Do not set `max-width` on the layout wrapper.
- Below 1024px, a horizontal scrollbar appears (set `min-width: 1024px` on `#app`).
- The detail panel should auto-close if viewport width drops below 800px (handled in section-04, but the CSS foundation should not prevent this behavior).

## Dependencies

This section has no dependencies on other sections. It is the foundation that all other sections build upon.

## What Subsequent Sections Expect

- **Section 02 (Data Adapter):** Expects the `deal-graph-data` and `deal-analysis-data` script elements to exist and be parseable.
- **Section 03 (Graph Core):** Expects `#graph-container` to exist and fill the viewport below the toolbar.
- **Section 04 (Detail Panel):** Expects `#detail-panel` to exist with the slide-in/out CSS transition and close button.
- **Section 05 (Layouts/Filtering):** Expects the layout switcher `<select>`, filter trigger button, search input, and reset button to exist in the toolbar.
- **Section 06 (Analysis Overlay):** Expects the show-issues toggle to exist in the toolbar. Expects severity CSS variables.
- **Section 07 (Timeline View):** Expects `#timeline-container` to exist and be hidden by default. Expects the view switcher control.
- **Section 08 (PDF Export):** Expects the export-pdf button to exist in the toolbar.
- **Section 09 (Polish):** Expects the edge-labels toggle and reset-view button to exist. Expects the `@media print` block to be in place.
