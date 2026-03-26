# Deep Project Interview — Legal Document Mapping Tool

## Date: 2026-03-26

---

## Interview Transcript

### Q1: Primary Users
**Q:** Who are the primary day-to-day users?
**A:** Just me for now. Building for my own workflow first.

### Q2: Document Scale
**Q:** How many documents per deal closing?
**A:** Varies widely — could be 5 to 50+ depending on the deal.

### Q3: Core Pain Points
**Q:** Which of the five core questions cause the most pain?
**A:** Document hierarchy (which doc controls what) and cross-reference conflicts (inconsistencies between docs).

### Q4: Current Workflow
**Q:** How do you currently track cross-reference conflicts and hierarchy issues?
**A:** No systematic approach — issues are caught ad hoc as they're discovered.

### Q5: Automation Importance
**Q:** How important is auto-extraction from PDFs vs. manual entry?
**A:** Auto-extraction is key — manual entry defeats the purpose.

### Q6: Visualization Approach
**Q:** Is the D3 force-directed graph the right metaphor?
**A:** Not sure yet — open to exploring what works best.

### Q7: Deployment & Architecture (Extended Discussion)
**Q:** Where would you want to run this?
**A (expanded):** Claude Code as the analysis engine has tremendous value. But also wants to make edits and notes directly in the application. Two additional critical requirements:
1. **Export capability** — Must be able to export visualization as PDF for sharing with own counsel and internal staff.
2. **Privacy is paramount** — Documents contain confidential terms, confidentiality obligations exist, and nothing can jeopardize attorney-client privilege.

**Discussion:** Walked through privacy implications of various approaches:
- Anthropic API sends content to their servers (zero-retention policy)
- Third-party tools (Heptabase, Miro, legal AI) require cloud upload to another vendor
- Local LLMs keep data private but sacrifice extraction quality
- Metadata-only approach as middle ground

**Resolution:** Anthropic API is acceptable for document processing under their data policies.

### Q8: Interactive Layer Architecture
**Q:** Standalone app or generated HTML file?
**A:** Generated HTML file — Claude Code produces/updates an HTML visualization; user opens in browser, makes edits; Claude Code reads changes back.

### Q9: Document Formats
**Q:** PDFs, Word, or mix?
**A:** Mix of Word and PDF — active drafts in Word plus executed PDFs.

### Q10: Scope
**Q:** MVP or polished v1?
**A:** Polished v1 — build it right, not a quick hack.

---

## Key Decisions Summary

| Decision | Choice |
|----------|--------|
| Primary user | Solo (Maitland / New City Properties) |
| Architecture | Claude Code → generates HTML visualization → browser editing → data syncs back |
| AI processing | Anthropic API (acceptable under confidentiality constraints) |
| Document input | Mix of Word and PDF |
| Core pain points | Document hierarchy, cross-reference conflicts |
| Auto-extraction | Essential — core value proposition |
| Export | PDF export required for counsel/staff sharing |
| Privacy | Critical — but Anthropic API acceptable |
| Visualization | Open — explore best approach |
| Scope | Polished v1 |

## Architectural Model

```
[Word/PDF Documents]
        |
        v
[Claude Code: Extraction & Analysis Engine]
        |
        v
[JSON Data Model (document-graph.json)]
        |
        v
[Interactive HTML Visualization]
   - View/navigate graph
   - Edit relationships, add notes
   - Export to PDF
        |
        v
[Claude Code reads edits back for re-analysis]
```

## Context for Splits

- The **data model** is foundational — everything depends on the JSON schema for the document graph
- **Extraction** (PDF/Word → structured data) is the core value and technically the hardest part
- **Visualization** is a distinct concern — HTML/JS/CSS, interactive graph rendering, export
- **Analysis intelligence** (hierarchy detection, conflict detection, term tracking) could be part of extraction or a separate analytical layer
- The **Claude Code workflow** ties it all together but depends on the other pieces existing
