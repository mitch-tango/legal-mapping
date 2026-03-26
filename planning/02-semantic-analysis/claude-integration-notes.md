# Integration Notes — External Review Feedback

## Reviewers
- **Gemini (gemini-3-pro-preview):** Detailed architectural critique
- **OpenAI (gpt-5.2):** Comprehensive edge case and security analysis

---

## Changes INTEGRATING

### 1. Pass 2 Source Text Retrieval — MUST be explicitly defined
**Both reviewers flagged this.** The plan says "pull specific sections from source documents" but never specifies how. Split 01 outputs `deal-graph.json` which is metadata, not raw text.

**Fix:** Add explicit requirement that Split 01 must provide a text index or that source documents are accessible by path. Define the retrieval mechanism: source documents remain in the deal directory, and Pass 2 reads the relevant files directly using document paths stored in the graph.

### 2. Party Changes DO Affect Analyses
**Both reviewers flagged the staleness rule "Party modified → None" as incorrect.** Party changes can affect execution sequence (signing party), CPs (guarantor requirements), and defined terms (party-referencing definitions).

**Fix:** Update staleness table — party changes mark Execution Sequence, CPs, and Defined Terms as stale.

### 3. Stable Finding IDs
**OpenAI flagged** that `hierarchy-001` style sequential IDs break across reruns, disrupting UI deep links and diffing.

**Fix:** Use content-derived stable IDs: hash of (analysis_type + category + sorted affected_entity_ids). Keep a display ordinal separate from the stable ID.

### 4. Graph Hash Determinism
**Gemini flagged** that JSON array ordering non-determinism means identical semantic data produces different hashes.

**Fix:** Add requirement to canonicalize (deep sort keys + arrays) before hashing.

### 5. Section Reference Canonicalization
**OpenAI flagged** that section references (1.01 vs 1.1 vs Section 1.1) need normalization for dangling reference detection.

**Fix:** Add normalization rules and fuzzy matching tiers for section references in conflict detection.

### 6. Prompt Injection Defense for Pass 2
**OpenAI flagged** that raw contract text sent to the API could contain adversarial instructions.

**Fix:** Add explicit instruction in Pass 2 prompts to treat provided text as data only. Wrap source text in clear delimiters.

### 7. Atomic File Writes
**OpenAI flagged** that the current lock file approach risks corruption.

**Fix:** Write to `.tmp` then rename (atomic). Increase lock timeout to 15 minutes.

### 8. Pass 2 Explosion Control
**OpenAI flagged** that contradictory provision candidates can be O(n²).

**Fix:** Add ranking by likelihood (shared terms + same issue area + explicit cross-ref) and cap at top K candidates per run. Allow user opt-in to exhaustive mode.

### 9. Issue Area Stability
**OpenAI flagged** that LLM-discovered issue areas are non-repeatable across runs.

**Fix:** Add requirement for issue areas to include stable identifiers anchored to specific defined terms and clause types. Provide a base taxonomy with allowed extensions.

### 10. Prompt Caching
**Gemini flagged** the cost/performance of sending 50K-100K graph tokens 5 separate times.

**Fix:** Add requirement to use Anthropic's prompt caching — load graph as cached system prompt, run analyses against cached context.

### 11. Cross-Cluster Partitioning Should Be by Issue Area, Not Document Type
**Gemini flagged** that clustering by document type (loan docs vs equity docs) would miss the most valuable cross-document conflicts.

**Fix:** If clustering is needed, cluster by issue area and include all cross-references related to that issue, regardless of document origin.

### 12. Defined Terms as Prerequisite for Conflicts
**Gemini noted** that conflicting definitions directly affect conflict detection quality.

**Fix:** Add Defined Terms as optional enrichment input for Conflicts (not hard dependency, but used if available).

### 13. Status Model Enhancement
**OpenAI suggested** adding completion/coverage fields to distinguish "stale but completed" vs "current but partial."

**Fix:** Add `completion` field (complete/partial/failed) and `errors` array to AnalysisResult.

---

## Changes NOT Integrating

### 1. "Replace Claude Code with Python/TS orchestration"
**Gemini's strongest recommendation.** However, this contradicts the project's core architecture decision. The user is a solo legal professional building tools with Claude Code — not a software engineering team maintaining a Python CLI. Claude Code IS the runtime for this project. The orchestration logic (DAG resolution, hash comparison) is simple enough to implement as part of the workflow. We'll add guardrails (structured output via tool use, explicit schemas) rather than abandon the architecture.

### 2. "Don't use Opus, use Sonnet for everything"
**Gemini's model recommendation.** The plan already defaults to Sonnet with Opus only as a fallback for unusually complex deals. The user can choose based on their experience. Not changing.

### 3. "Enhancement pass can't find missed terms from graph data alone"
**Gemini flagged** that you can't find terms Split 01 missed by only looking at the graph. This is partially correct but overstated — the enhancement pass CAN find undefined usage (capitalized terms appearing in relationship evidence/descriptions that aren't in the defined_terms array). It can't find completely unextracted terms, but that's acceptable. The plan already scopes this appropriately.

### 4. "Pin model versions explicitly"
**OpenAI suggested** pinning exact model versions. This is an operational detail for implementation, not a plan-level decision. Implementation will handle this.

### 5. "Add PII redaction before Pass 2"
**OpenAI suggested** redacting sensitive data. The user's deal documents are already confidential — they're being sent to Anthropic API which is the approved channel. Adding a redaction layer adds complexity without meaningful privacy improvement given the existing constraint (Anthropic API only).

### 6. "Rate limiting / concurrency controller"
**OpenAI suggested** adaptive throttling. For a solo user running analyses on one deal at a time, this is over-engineering. If rate limits are hit, the existing retry logic handles it.

### 7. "Amendments/restatements modeling"
**OpenAI suggested** modeling amendment relationships. This is a Split 01 schema concern, not a Split 02 analysis concern. If Split 01 provides amendment data, Split 02 can use it. Not adding this requirement here.

### 8. "Regression tests with canned graphs"
**OpenAI suggested** fixture-based testing. Good idea but belongs in the TDD plan, not the implementation plan.
