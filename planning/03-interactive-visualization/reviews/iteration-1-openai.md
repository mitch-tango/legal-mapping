# Openai Review

**Model:** gpt-5.2
**Generated:** 2026-03-26T14:08:27.128458

---

## High-risk footguns / edge cases

### CDN dependency fragility (Sections 2, 6, 7)
- **Problem:** “Single self-contained HTML” contradicts “all loadable via CDN.” Offline use, corporate proxies, blocked CDNs, CSP policies, or captive portals will break the app. Your error handling says “check internet connection,” but the workflow explicitly implies the user can just open a file.
- **Actionable fix:** Decide explicitly:
  1) **Truly self-contained**: inline/minify vendor libs into the HTML (or embed as `<script>` text blobs), or  
  2) **CDN-required**: rename the deliverable and set expectations (“requires internet access”), and add a “Download dependencies” option.
- **Add:** Subresource Integrity (SRI) + `crossorigin` attributes, and pin exact versions to avoid surprise breaking changes.

### `file://` origin quirks for PDF/export and fonts (Sections 2, 3.7, 9)
- **Problem:** Running from `file://` can behave differently across browsers (especially Safari) for blob downloads, module loading, and some canvas/SVG operations. jsPDF download via `save()` usually works, but not always with strict settings.
- **Actionable fix:** Include a “If export fails, open via a local web server” troubleshooting note, or provide a tiny optional “serve locally” helper script (even if not required).

### Large graphs will break layouts and PDF conversion (Sections 2, 3.2, 3.7, 9)
- **Problem:** Dagre/cola can become slow/unresponsive as nodes/edges grow; svg2pdf can be extremely slow and memory-hungry for dense SVGs. Your “large” test fixture (30 docs / 50 edges) is modest; real deals can be 100–500 docs with many relationships.
- **Actionable fix:**
  - Set explicit **performance budgets** (e.g., target 200 nodes / 600 edges).
  - Add a **“simplify view for export”** option: hide edge labels, hide low-confidence edges, disable overlay badges, reduce shadows, reduce node label rendering.
  - Consider exporting the graph as **high-res PNG** for large graphs as the *primary* path; keep SVG as best-effort for smaller graphs. (Vector is great until it isn’t.)

### Data injection into JS variables is a security + correctness footgun (Sections 2, 7)
- **Problem:** “Simple string replacement” to inject JSON into a `<script>` tag is vulnerable to **script-breaking sequences** (e.g., `</script>` inside evidence quotes) and opens XSS if any data is untrusted (even if “internal,” legal text is arbitrary).
- **Actionable fix:**
  - Embed JSON using `<script type="application/json" id="deal-graph">...</script>` and parse via `JSON.parse(document.getElementById(...).textContent)`.
  - Or at minimum escape `</script>` as `<\/script>` during injection.
  - In the UI, render text via `textContent` not `innerHTML`. Evidence quotes, doc summaries, party names, etc. must be treated as untrusted.

### Requirements mismatch: “self-contained” vs “email the file” vs “confidential legal docs” (Sections 1, 2, 10)
- **Problem:** Emailing a single HTML containing the entire deal graph + analysis + evidence quotes is a **data leakage risk**; opening it loads third-party CDNs which can leak metadata (IP, timing) and possibly referrers. Some firms will disallow this.
- **Actionable fix:** Add an explicit **privacy/security posture** section:
  - Option A: Fully offline bundle (no external calls).
  - Option B: CDN mode but with warning + a “sensitive deal” switch to inline libs.
  - Clarify whether evidence quotes/full text snippets are included and how much.

---

## Missing considerations / ambiguous requirements

### Data schema assumptions are not defined (Section 3.1)
- **Problem:** `DataAdapter` methods assume structures (“documents”, “relationships”, “execution_sequence”, “findings”, “defined terms”) but no schema is specified (required fields, IDs, uniqueness, nullability).
- **Actionable fix:** Add a concise JSON schema (even informal) defining:
  - Document `id` uniqueness, display name fields, type enum, status enum
  - Relationship `id`, `source`, `target`, `relType` enum, `confidence` enum, evidence fields
  - Findings: `findingId`, severity enum, affected entities format
  - Execution sequence: ordering, parallel windows, dependencies representation

### ID collisions and stability (Sections 3.1, 3.2)
- **Problem:** Cytoscape requires unique `data.id` for nodes and edges. Relationship IDs often collide or aren’t present; you may generate IDs that change between runs, breaking deep-links or selection restore across layout switches.
- **Actionable fix:** Define deterministic ID rules:
  - Node ID = document ID from source.
  - Edge ID = `${source}::${relType}::${target}::${index}` or hash of stable fields.

### Filtering semantics are unclear (Section 3.2)
- **Problem:** “Shows/hides nodes (and their edges)” when filtering by doc type—what about edges between hidden nodes, or edges connected to hidden nodes from visible nodes?
- **Actionable fix:** Specify rules:
  - If a node is hidden, hide all incident edges.
  - For relationship-type filtering, hide edges only; nodes remain but may become isolated (and optionally visually muted).

### “Preserves selection, filters, and overlay state across layout changes” is non-trivial (Section 3.2)
- **Problem:** Layout re-run can reset positions, selection can be lost if elements are removed/added during filtering. Overlay styles often implemented via classes that can get clobbered by filter classes.
- **Actionable fix:** Define a class/state model:
  - Base classes: `docType-*`, `relType-*`, `confidence-*`
  - State classes: `is-hidden`, `is-dimmed`, `is-highlighted`, `has-finding-critical`, etc.
  - Never rebuild elements on filter; toggle classes instead.

### Timeline “parallel execution window grouping” is underspecified (Section 3.6)
- **Problem:** What is the representation? How is “parallel” determined? What if the analysis doesn’t provide windows?
- **Actionable fix:** Require execution sequence to include either `windowId` or `stage` and define rendering rules; otherwise render flat sorted list.

### “Evidence summary” in PDF relationship table (Section 3.7)
- **Problem:** Evidence text can be long; table will overflow and balloon PDF size.
- **Actionable fix:** Add truncation rules and optionally include an appendix:
  - Summary column: max N chars, single line, ellipsis.
  - Optional “Evidence appendix” pages keyed by relationship ID.

---

## Security vulnerabilities / privacy risks

### XSS via document content rendering (Sections 3.4, 3.7)
- **Risk:** If you render rich text (summaries, quotes, provisions) with `innerHTML`, any embedded `<img onerror=...>` or `<svg onload=...>` becomes code execution.
- **Actionable fix:** Enforce `textContent` everywhere; if you need formatting, use a safe markdown renderer with strict sanitization (but that’s extra complexity—prefer plain text for V1).

### Supply-chain risk via CDN (Sections 2, 6)
- **Risk:** A compromised CDN or dependency update can execute arbitrary code on open.
- **Actionable fix:** Pin versions + SRI. Consider providing an offline/no-network build for sensitive environments.

### Data exfiltration via external loads (Sections 2, 10)
- **Risk:** Even if libraries are benign, opening the HTML causes outbound requests; this is sensitive in legal contexts.
- **Actionable fix:** Provide an “offline mode” deliverable as above; document it prominently.

---

## Performance / UX issues

### Layout performance and UI freezing (Sections 3.2, 5, 3.7)
- **Problem:** Layout and svg2pdf conversion run on the main thread; the UI can freeze, especially during export.
- **Actionable fix:**
  - Use Cytoscape layout events (`layoutstart`, `layoutstop`) to show a spinner.
  - During PDF generation: disable UI, show progress steps (“Capturing graph… Building tables… Writing file…”).
  - Consider chunking long table generation (autotable can also stall).

### Node size scaling by “relationship count” (Section 3.2)
- **Problem:** High-degree hubs become huge and overlap labels, making graph unreadable; low-degree nodes may become too small to click.
- **Actionable fix:** Use a gentler scale (e.g., sqrt/log scale) and cap sizes more tightly; ensure minimum clickable area.

### Search behavior (“dims non-matching nodes”) (Section 3.2)
- **Problem:** If combined with filters/overlay/highlight, the visual state can become confusing.
- **Actionable fix:** Define precedence rules: e.g., filtering determines visibility, search determines dimming within visible set, highlight overrides dimming for neighborhood.

---

## Architectural problems / maintainability

### “All within a single `<script>` block” will become brittle (Section 3)
- **Problem:** Even in a single HTML file, stuffing everything into one block makes it hard to test and reason about.
- **Actionable fix:** Still keep single-file output, but structure code with:
  - IIFE modules or ES module pattern (if you avoid `type="module"` due to file:// issues)
  - Clear separation: `state`, `render`, `events`, `export`
  - A single `AppController` orchestrating module interactions and state

### State synchronization between modules is not described (Sections 3.2–3.7)
- **Problem:** Many features interact: selection, highlight, overlay, filters, view switcher, timeline click-to-focus, edge label toggle, export capturing “current state.”
- **Actionable fix:** Introduce an explicit state object:
  - `activeView`, `layout`, `filters`, `searchQuery`, `overlayEnabled`, `selectedEntity`
  - One event bus or simple callback wiring documented in the plan

---

## Error handling gaps

### “Catch script tag load failure” is not straightforward (Section 6)
- **Problem:** `<script src=...>` failures don’t throw in a way you can “catch” globally unless you attach `onerror` handlers per script or use a loader.
- **Actionable fix:** Implement a tiny dependency loader:
  - Programmatically create scripts with `onload/onerror`, or add `onerror="window.__depFail('cytoscape')"` to each script tag.
  - Gate app initialization on all deps loaded.

### “Invalid data format” diagnostics (Section 6)
- **Problem:** Without a schema validator you’ll end up with vague runtime errors.
- **Actionable fix:** Add a lightweight validation step with explicit checks + user-friendly messages (“Missing documents array”, “Relationship source id not found: X”).

### “SVG export failure → html2canvas fallback” is underspecified (Section 6)
- **Problem:** html2canvas is not listed as a dependency; adding it via CDN increases payload and adds its own cross-origin/canvas pitfalls.
- **Actionable fix:** Decide now:
  - Either include html2canvas explicitly (pinned + SRI), or
  - Use Cytoscape’s built-in `cy.png({scale: ...})` as fallback (simpler than html2canvas).

---

## PDF export quality issues to address

### Page orientation mixing in jsPDF (Section 3.7)
- **Problem:** jsPDF supports per-page orientation, but you must manage size/orientation carefully; “Page 1 landscape, Page 2+ portrait” can lead to wrong dimensions if not done correctly.
- **Actionable fix:** Define exact page sizes and how you’ll switch:
  - Create doc in portrait, add landscape page with `doc.addPage([height,width], 'landscape')` (or create landscape then add portrait pages).
  - Test in all target browsers.

### Font embedding and professional output (Section 3.7, 4)
- **Problem:** jsPDF default fonts are limited; “system font stack” doesn’t apply to PDF. Output may look less “professional” than the HTML.
- **Actionable fix:** Decide whether to embed a font (e.g., Source Sans/Inter) as base64 in the HTML for jsPDF, or accept standard Helvetica. Document the tradeoff.

### Table overflow and long strings (Section 3.7)
- **Problem:** Long document names, parties, provisions, evidence will wrap unpredictably and can explode page count.
- **Actionable fix:** Add truncation + column width policies and consistent wrapping rules; include an appendix or export options (“Include evidence: Yes/No”).

---

## Additional recommendations to add to the plan

1. **Add a “Data Sensitivity Mode”** (new section):  
   - Offline bundle option; no external requests; explicit statement about what data is embedded.
2. **Define a minimal JSON schema contract** for Split 01/02 outputs, including enums and required fields.
3. **Add deterministic ID and escaping rules** for injection + rendering.
4. **Introduce a central AppState + event wiring** to prevent feature interactions from becoming ad hoc.
5. **Expand performance testing** beyond 30 docs: include at least one “stress” fixture (e.g., 200 docs/600 edges) and define graceful degradation (hide labels by default, default filter to high-confidence, etc.).
6. **Pin and integrity-check all CDN libs**, or provide a no-CDN build path.

If you want, I can propose a concrete “state/class model” (CSS classes + Cytoscape stylesheet rules) that makes filters/search/highlight/overlay composable without conflicts.
