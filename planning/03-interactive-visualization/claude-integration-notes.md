# Integration Notes — External Review Feedback

## Reviewers
- **Gemini** (gemini-3-pro-preview)
- **OpenAI** (gpt-5.2)

---

## Suggestions INTEGRATED

### 1. Secure JSON Data Embedding (Both reviewers)
**What:** Replace raw JS variable injection (`const DEAL_GRAPH = {...}`) with `<script type="application/json">` data island parsed via `JSON.parse()`.
**Why:** Raw injection breaks if legal text contains `</script>` and creates XSS risk. Both reviewers flagged this as critical.
**Impact:** Sections 2, 7 — changes data embedding architecture.

### 2. Subresource Integrity (SRI) for CDN Scripts (Both)
**What:** Add `integrity` and `crossorigin="anonymous"` attributes to all CDN script tags.
**Why:** Legal professionals handle sensitive M&A data. Supply-chain protection is appropriate.
**Impact:** Section 2 — CDN dependency list.

### 3. Document Type Color Grouping (Gemini)
**What:** Group 21 document types into 5-7 broad categories with colors per category and shapes/borders to differentiate within categories.
**Why:** 21 distinguishable muted colors is not feasible, especially with color vision deficiencies.
**Impact:** Section 3.2, Section 4 — node styling approach.

### 4. Visual State Precedence Rules (Both)
**What:** Define explicit hierarchy: Filter (removes) > Search (dims) > Highlight (borders) > Overlay (badges/rings). Use CSS classes on Cytoscape elements.
**Why:** Multiple features interact (search, filter, highlight, overlay) and without defined precedence the UI becomes confusing.
**Impact:** Section 3.2 — new subsection on state management.

### 5. XSS Prevention via textContent (OpenAI)
**What:** Enforce `textContent` for all user-facing text rendering. Never use `innerHTML` with deal data.
**Why:** Legal document text is arbitrary and could contain HTML-like strings.
**Impact:** Section 3.4 — detail panel rendering.

### 6. Orphaned Analysis Finding Handling (Gemini)
**What:** DataAdapter must silently prune findings referencing non-existent document/relationship IDs.
**Why:** Split 01 and 02 are generated separately; ID mismatches can occur.
**Impact:** Section 3.1 — DataAdapter validation.

### 7. Cyclic Dependency Handling (Gemini)
**What:** Detect and visually mark cyclic edges (red dashed line) so users can spot logical loops.
**Why:** Legal documents can have circular references. Dagre handles these by reversing edges arbitrarily.
**Impact:** Section 3.2, Section 9 — edge case handling.

### 8. Reset View Button (Gemini)
**What:** Add "Reset View" button to toolbar that clears highlights, resets zoom/pan, and re-runs layout.
**Why:** Users can get lost after panning, zooming, dragging nodes. "Fit to screen" isn't enough.
**Impact:** Section 3.5 — toolbar additions.

### 9. @media print Stylesheet (Gemini)
**What:** Add CSS `@media print` block that hides UI controls and shows a message to use Export PDF.
**Why:** Users will instinctively hit Ctrl+P. Better to handle that gracefully.
**Impact:** Section 4 — CSS additions.

### 10. Simplified PDF Export Fallback (OpenAI)
**What:** Use Cytoscape's built-in `cy.png()` as fallback instead of html2canvas.
**Why:** html2canvas adds complexity, CDN payload, and has its own cross-origin issues. cy.png() is simpler and already available.
**Impact:** Section 3.7, Section 6 — error handling.

### 11. Deterministic Edge IDs (OpenAI)
**What:** Define edge ID format: `${source}::${relType}::${target}::${index}`.
**Why:** Prevents ID collisions and ensures stability across regenerations.
**Impact:** Section 3.1 — DataAdapter.

### 12. Central AppState Object (OpenAI)
**What:** Introduce explicit state object tracking activeView, layout, filters, searchQuery, overlayEnabled, selectedEntity with simple event wiring.
**Why:** Many features interact; central state prevents ad-hoc synchronization bugs.
**Impact:** Section 3 — new architectural component.

### 13. Offline Detection + Messaging (Gemini)
**What:** Add inline check for CDN dependency availability; show clear message if libraries didn't load.
**Why:** Legal professionals may open files on restricted networks or offline.
**Impact:** Section 6 — error handling enhancement.

### 14. PDF Evidence Truncation Rules (OpenAI)
**What:** Add column width policies and truncation rules for long strings in PDF tables. Max N chars for evidence summary.
**Why:** Long text in tables can explode page count and look unprofessional.
**Impact:** Section 3.7 — PDF table configuration.

### 15. Async PDF Generation UX (Gemini)
**What:** Use requestAnimationFrame before starting PDF generation to ensure loading UI renders before main thread blocks.
**Why:** CSS spinner freezes if the main thread is immediately locked by jsPDF.
**Impact:** Section 3.7 — PDF generation flow.

---

## Suggestions NOT Integrated

### A. Fully Offline Bundle / Inline All Libraries (Both)
**Why not:** Inlining ~570KB of minified JS into the HTML file would make it enormous and hard for Claude Code to regenerate. CDN with SRI is the right balance for V1. The offline detection message (integrated above) handles the UX gracefully.

### B. Fixed Node Sizes Instead of Auto-sizing (Gemini)
**Why not:** Auto-sizing with truncated labels provides better readability for varying document name lengths. The plan already specifies min/max node sizes (40-80px). Using sqrt/log scaling (integrated via color grouping changes) addresses the hub-dominance concern.

### C. Explicit JSON Schema Contract in This Plan (OpenAI)
**Why not:** The JSON schema is defined in Split 01's data model. This plan should reference it, not duplicate it. Adding a schema here creates a maintenance burden and potential for divergence.

### D. Data Sensitivity Mode / No-CDN Build Path (OpenAI)
**Why not:** This is a V1. The user runs everything locally and shares PDFs (not HTML files) with outside counsel. The CDN libraries are standard open-source packages, not data exfiltration vectors. A no-CDN mode adds significant complexity for minimal V1 benefit.

### E. Font Embedding in PDF (OpenAI)
**Why not:** Helvetica (jsPDF default) is professional and universally readable. Embedding custom fonts as base64 adds significant file size. Not worth the tradeoff for V1.

### F. Performance Budget for 200+ Nodes (OpenAI)
**Why not:** The user's deals are typically 15-50 documents. Testing up to 30 docs (already planned) covers realistic scenarios. Adding a 200-node stress test creates engineering overhead for an unlikely use case.

### G. Per-page Orientation Details for jsPDF (Gemini/OpenAI)
**Why not:** The plan already specifies landscape page 1 and portrait subsequent pages. The specific API call syntax (`doc.addPage('letter', 'portrait')`) is an implementation detail, not a plan-level concern.

### H. Timeline windowId/stage Schema Requirement (OpenAI)
**Why not:** The execution sequence format is defined by Split 02. If parallel windows aren't in the data, the timeline renders a flat sorted list (already specified). We don't need to require a specific field in this plan.
