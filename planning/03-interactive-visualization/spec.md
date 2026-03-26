# 03 — Interactive Visualization & Export

## Purpose

Build the HTML/JS application that renders the legal document dependency graph, supports editing and annotation, and exports to PDF. This is the user-facing layer — a generated HTML file that Claude Code produces and the user opens in a browser.

## Context

See `requirements.md` in the project root for full project context. Key points:

- **Architecture:** Claude Code generates/updates this HTML file. The app reads a JSON data file (produced by splits 01 and 02), renders the graph, and writes user edits back to the JSON file. Claude Code can then read the edits for re-analysis.
- **Users:** Solo legal professional — the interface must be polished and usable by a non-technical person, not a developer tool.
- **Export:** Must produce PDF output for sharing with outside counsel and internal staff who won't use the tool directly.
- **Privacy:** Runs locally in the browser. No external service calls from the visualization (all AI processing happens via Claude Code separately).

## Deliverables

### 1. Graph Visualization

The primary view — an interactive dependency graph of deal documents.

- Nodes represent documents, sized/colored by type or importance
- Edges represent relationships, colored/styled by relationship type (controls, references, subordinates_to, etc.)
- Directional arrows showing relationship direction
- Edge labels showing relationship type
- Zoom, pan, drag nodes to rearrange
- Click node → detail panel with document metadata, defined terms, obligations, relationships
- Click edge → detail panel with relationship details, confidence, source citations
- Filter by relationship type (show only "controls" edges, etc.)
- Highlight paths (click a document, see all documents it relates to, with paths highlighted)
- Search/filter documents by name or type

### 2. Additional View Modes

Beyond the force-directed graph, provide views optimized for specific questions:

- **Hierarchy view:** Tree/layered layout showing document control hierarchy (which docs govern which)
- **Timeline/sequence view:** Execution sequence for closing — ordered list or Gantt-style layout showing what gets signed when
- **Conflict view:** Focused view showing only documents with conflicts/risks, with severity indicators

The user should be able to switch between views easily. All views read the same underlying data.

### 3. Editing & Annotation

Users must be able to modify the graph directly in the browser:

- Add/remove/edit relationships between documents
- Add notes/annotations to documents or relationships
- Flag items for review or mark as resolved
- Override AI-extracted data (e.g., change a relationship type, correct a confidence score)
- All edits persist to the JSON data file so Claude Code can read them back

### 4. Analysis Results Display

Render the analysis results from split 02:

- Conflict markers on documents/edges with severity indicators (critical/warning/info)
- Hierarchy overlay showing control chains
- Defined term flow visualization (trace a term from definition to all usage points)
- Conditions precedent chain highlighting
- Risk summary panel or dashboard

### 5. PDF Export

Generate a shareable PDF from the current view:

- Export the graph visualization as a static image/diagram
- Include a document summary table
- Include conflict/risk report
- Include closing checklist (execution sequence)
- Should look professional — this goes to outside counsel

### 6. Data Integration

- Read the JSON data file on load (the file produced by Claude Code)
- Write user edits back to the JSON file (so Claude Code can read changes)
- Handle the case where Claude Code updates the file while the user has it open (reload/merge strategy)
- No server required — pure client-side file handling (File API or a simple local file convention)

## Dependencies

- **Depends on 01-data-model-extraction:** The JSON schema defines what the visualization reads and writes.
- **Depends on 02-semantic-analysis:** The analysis results format defines what conflict markers, hierarchy data, and other analysis overlays the visualization renders.
- **No downstream dependencies** — this is the user-facing endpoint.

## Key Design Decisions for /deep-plan

- **Visualization library:** D3.js (as in prototype), Cytoscape.js, vis.js, or something else? Consider: layout quality for legal document graphs, ease of implementing multiple view modes, export capabilities
- **File I/O strategy:** How does a local HTML file read/write a JSON file? Options: File System Access API (modern browsers), drag-and-drop, copy-paste, or Claude Code regenerates the HTML with embedded data
- **Single HTML file vs. multi-file:** The prototype is a single self-contained HTML file. Should this be the same, or a small set of files (HTML + JS + CSS)?
- **Graph layout algorithm:** Force-directed works for small graphs but gets messy at 30+ nodes. Need a layout strategy that scales.
- **PDF export approach:** Print CSS, html2canvas + jsPDF, or server-side rendering via Claude Code?
- **How to handle large deals:** 50+ documents means the graph needs clustering, collapsing, or progressive disclosure

## Reference

The prototype at `Reference/Legal Mapping Idea.txt` is a working single-file HTML app with D3.js force-directed graph, detail panel, relationship legend, and basic editing. It's a strong starting point but needs:
- Multiple view modes (hierarchy, timeline)
- Analysis results display (conflicts, risks)
- PDF export
- Better UX polish for a legal professional audience
- Scalability for larger document sets
- File-based data persistence (instead of localStorage)
