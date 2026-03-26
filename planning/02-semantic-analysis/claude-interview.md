# Interview Transcript: Semantic Analysis Engine (Split 02)

## Q1: Analysis Workflow — Run all together or select individually?

**Options presented:** All-at-once with dependencies, all-at-once independent, user selects (independent), user selects with smart dependencies.

**Recommendation given:** User selects with smart dependencies. Let user pick which analyses to run, but auto-trigger prerequisites (e.g., conflict detection auto-runs hierarchy first).

**Dependency chain:**
1. Document Hierarchy (standalone)
2. Cross-Reference Conflicts (uses hierarchy results)
3. Defined Term Tracking (standalone)
4. Conditions Precedent (standalone)
5. Execution Sequence (requires conditions precedent)

**Answer:** Agreed with recommendation — user selects, with smart dependencies.

## Q2: Deal Scale — How many documents, how large?

**Options presented:** 5-10 docs, 10-20 docs, 20-40 docs, varies widely.

**Recommendation given:** Handle all sizes, optimize for medium (10-20 docs). Simple acquisitions may be 5-10 docs, JV with construction financing could hit 30+.

**Answer:** Agreed — handle all sizes, optimize for 10-20 docs.

## Q3: Confidence/Severity — How to present uncertain findings?

**Options presented:** 4-level severity, 3-level risk, binary issue/note.

**Recommendation given:** 4-level severity (CRITICAL/ERROR/WARNING/INFO) maps to legal materiality concepts.

**Answer:** Agreed — 4-level severity system.

## Q4: Missing Documents — When a referenced document isn't in the deal set?

**Options presented:** Flag as missing document, note as dangling reference, flag + suggest what to look for.

**Answer:** Flag as missing document (prominently surface so user knows to upload or acknowledge out of scope).

## Q5: Re-analysis Triggers — What happens after graph edits?

**Options presented:** Track staleness + user triggers, fully automatic, fully manual.

**Answer:** Track staleness, user triggers. System marks which analyses are stale after edits, user decides when to re-run.

## Q6: Citation Granularity — How specific should references be?

**Options presented:** Section + quote, section-level only, document-level only.

**Answer:** Section-level only (e.g., "Operating Agreement, Section 4.2(b)" without quoting text). Keeps output clean.

## Q7: Analysis Results Storage — Where to store results?

**Options presented:** Companion file, embedded in deal-graph.json, both.

**Answer:** Companion file (deal-analysis.json). Keeps extraction data clean, analysis can be re-run without touching the graph.

## Q8: Hierarchy Detection — Explicit language only or also inferred?

**Options presented:** Both explicit and inferred, explicit only, explicit first with inferred as suggestions.

**Answer:** Both explicit and inferred. Use explicit language AND document type conventions (e.g., Guaranty is inherently subordinate to guaranteed obligation), but flag inferred hierarchies with lower confidence.

## Q9: Execution Sequence Format

**Options presented:** Ordered list with conditions, simple ordered list, full closing checklist.

**Answer:** Ordered list with conditions — document execution order + what conditions must be met before each step, grouped by parallel execution windows.

## Q10: API Strategy — Single prompt vs. sub-tasks for large deals?

**Context discussion:** User asked whether 20+ documents would cause degradation. Clarification provided: Split 02 analyzes the structured graph JSON (~50K-100K tokens for 20 docs), not raw documents. Claude's 1M token context handles this easily. For verification of flagged issues, targeted follow-up calls pull just the relevant sections.

**Answer:** Two-pass approach — analyze full graph first (single call), then targeted verification calls for flagged issues against source document text.

## Q11: Architecture — Python CLI or Claude Code workflows?

**Options presented:** Claude Code workflows, Python CLI commands, hybrid.

**Answer:** Claude Code workflows. Claude Code reads graph, constructs analysis prompts, calls Claude API, writes results. No separate Python CLI for analysis.

## Q12: Defined Term Tracking Scope

**Options presented:** Start with Split 01 + enhance, only Split 01 terms, full independent extraction.

**Answer:** Start with Split 01 extracted terms as baseline, then do a focused deeper pass to catch missed terms and fill in usage tracking.
