# Section 08: PDF Export

## Overview

This section implements the `PDFExporter` class, which generates a multi-page professional PDF report from the current visualization state. The PDF uses jsPDF for document creation, svg2pdf.js for vector graph rendering (with cy.png() fallback), and jspdf-autotable for native PDF tables. The export is triggered by the "Export PDF" toolbar button.

## Dependencies

- **section-01-foundation**: HTML skeleton with the "Export PDF" button in the toolbar, CSS for loading indicator
- **section-02-data-adapter**: `DataAdapter` class providing `getCytoscapeElements()`, `getDocumentDetails()`, `getRelationshipTypes()`, `getDocumentTypes()`, `getFindingsForEntity()`, `getFindingsSummary()`, `getExecutionSequence()`
- **section-03-graph-core**: `GraphRenderer` class providing `exportSVG()` method and access to the Cytoscape instance for `cy.png()` fallback

## CDN Libraries Used

These are loaded in section-01-foundation but consumed here:

- `jspdf.umd.min.js` (~280 KB) -- PDF generation core
- `svg2pdf.js` (~45 KB) -- SVG to PDF vector conversion
- `jspdf.plugin.autotable.min.js` (~50 KB) -- PDF table generation

All accessed via globals: `jspdf.jsPDF` (or `window.jspdf.jsPDF`), `svg2pdf` (auto-registers on jsPDF), and `jspdf-autotable` (auto-registers as `doc.autoTable()`).

## Tests

Write these tests as inline console assertions behind the `DEBUG` flag.

### Test: Clicking "Export PDF" shows loading indicator

Verify that when `PDFExporter.generate()` is called, it sets a loading indicator element to visible before beginning PDF work.

### Test: Loading indicator renders before main thread blocks (requestAnimationFrame used)

Verify that `generate()` uses `requestAnimationFrame` (or a double-rAF pattern) to yield to the browser before starting jsPDF work.

### Test: Generated PDF has page 1 in landscape orientation

After calling `generate()` on a test fixture, page 1 should be created with orientation `'landscape'`.

### Test: Pages 2+ are in portrait orientation

Verify that `addPage` calls for pages after the first use `'portrait'` orientation.

### Test: Page 1 contains deal name header and date

Verify the first page includes text matching the deal name and the current date.

### Test: Page 1 contains graph image (SVG or PNG fallback)

Verify that `exportSVG()` is called first. If it returns null, `cy.png({scale: 2})` is called as fallback.

### Test: Document summary table contains all documents with correct columns

Verify `doc.autoTable()` is called with columns: Document Name, Type, Status, Parties, Key Provisions Count, Relationships Count. Row count equals document count.

### Test: Document name column truncated at 50 chars

Verify document names longer than 50 characters are truncated with ellipsis.

### Test: Evidence summary column truncated at 120 chars

Verify evidence text in the relationship table is truncated at 120 characters.

### Test: Relationship list table is sorted by source document, then type

Verify rows are sorted first by source document name, then by relationship type.

### Test: Findings report groups by severity (CRITICAL first)

Verify findings are grouped in order: CRITICAL, ERROR, WARNING, INFO with count labels.

### Test: Closing checklist included only when execution_sequence exists

When `getExecutionSequence()` returns non-empty, closing checklist table is added. When empty, it is omitted.

### Test: PDF filename follows pattern `{deal_name}-analysis-{date}.pdf`

Verify the filename uses slugified deal name and YYYY-MM-DD date format.

### Test: SVG export failure triggers cy.png() fallback (not html2canvas)

Verify fallback uses `cy.png({scale: 2})` and `html2canvas` is never referenced.

### Test: Loading indicator clears after generation completes

After `generate()` resolves, the loading overlay returns to hidden state.

### Test: PDF generation with null DEAL_ANALYSIS omits findings report and closing checklist

When `DEAL_ANALYSIS` is null, only graph page, document summary, and relationship list are included.

### Fixtures needed

- `fixture-medium.json` (reuse) -- 15 docs, 25 relationships, 10 findings
- `fixture-large.json` -- 30 docs, 50 relationships, 20+ findings (stress test)
- `fixture-null-analysis.json` (reuse)

## Implementation Details

### File to modify

The single HTML visualization file. All code goes in the application `<script>` block.

### PDFExporter Class

```javascript
class PDFExporter {
    constructor(dataAdapter, graphRenderer) { /* store references */ }

    async generate() {
        /**
         * 1. Show loading overlay
         * 2. Yield via requestAnimationFrame (double-rAF pattern)
         * 3. Create jsPDF instance in landscape for page 1
         * 4. Add title page with graph
         * 5. Switch to portrait for remaining pages
         * 6. Add document summary table
         * 7. Add relationship list table
         * 8. If DEAL_ANALYSIS exists: add findings report
         * 9. If execution_sequence exists: add closing checklist
         * 10. Save with formatted filename
         * 11. Hide loading overlay
         */
    }
}
```

### Page 1: Title and Graph (Landscape)

Create jsPDF with `new jspdf.jsPDF({ orientation: 'landscape', unit: 'pt', format: 'letter' })`.

Add header: deal name (20px bold), "Document Dependency Analysis" subtitle, generation date.

Graph image:
- First attempt: `graphRenderer.exportSVG()` -> parse to SVG element -> `doc.svg(svgElement, options)` for vector PDF
- Fallback: `cy.png({scale: 2, full: true})` -> `doc.addImage(pngDataUrl, 'PNG', x, y, width, height)` with footnote about raster rendering

Scale graph to fit remaining landscape page area while maintaining aspect ratio.

### Pages 2+: Document Summary Table (Portrait)

`doc.addPage('letter', 'portrait')`. Section header: "Document Summary".

```javascript
doc.autoTable({
    head: [['Document Name', 'Type', 'Status', 'Parties', 'Provisions', 'Relationships']],
    body: rows,
    styles: { fontSize: 9, cellPadding: 4 },
    headStyles: { fillColor: [31, 41, 55], textColor: 255 },
    alternateRowStyles: { fillColor: [248, 249, 250] },
    columnStyles: { 0: { cellWidth: 140 } }
});
```

### Relationship List Table (Portrait)

Section header: "Document Relationships". Columns: Source Document, Target Document, Type, Confidence, Evidence Summary. Sorted by source name then type. Truncation applied.

### Findings Report (Portrait, only if DEAL_ANALYSIS exists)

Grouped by severity: CRITICAL, ERROR, WARNING, INFO. Each group has sub-header with name and count, then table with columns: Finding, Affected Documents, Description.

### Closing Checklist (Portrait, only if execution_sequence exists)

Section header: "Closing Checklist / Execution Sequence". Columns: Sequence #, Document, Dependencies, Status, Gating Conditions.

### Truncation Helper

```javascript
function truncateText(text, maxLength) {
    /** Truncate with ellipsis. Returns empty string for null/undefined. */
}
```

Rules: document names 50 chars, evidence 120 chars, parties 80 chars.

### Filename Generation

```javascript
function generatePdfFilename(dealName) {
    /** Slugify deal name, append "-analysis-YYYY-MM-DD.pdf" */
}
```

### Loading Indicator

HTML overlay element shown before PDF work, hidden in finally block. Double-rAF ensures browser paints loading UI before main thread blocks.

### Wiring to Toolbar

```javascript
document.getElementById('export-pdf-btn').addEventListener('click', () => {
    const exporter = new PDFExporter(dataAdapter, graphRenderer);
    exporter.generate().catch(err => console.error('PDF generation failed:', err));
});
```

### Error Handling

- Check jsPDF/autoTable globals before use
- SVG failure handled by PNG fallback
- All deal data converted to strings with `String(value || '')` guard
- autoTable handles page breaks automatically for long tables
