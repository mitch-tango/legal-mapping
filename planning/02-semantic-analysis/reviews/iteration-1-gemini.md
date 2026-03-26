# Gemini Review

**Model:** gemini-3-pro-preview
**Generated:** 2026-03-26T12:24:07.036631

---

This is a highly ambitious, well-thought-out plan. The two-pass architecture, the DAG-based execution model, and the strict separation of extraction data (Split 01) from analytical findings (Split 02) are excellent architectural choices. 

However, there are a few **critical architectural flaws**—particularly regarding the runtime environment and source-document retrieval—that will cause this implementation to fail if not addressed. 

Here is a detailed assessment of the footguns, architectural issues, and performance considerations in the plan.

---

### 1. Critical Architectural Problems

**The "Claude Code" Runtime Constraint (Sections 1 & 12)**
* **The Issue:** The plan explicitly states: *"Architecture: Claude Code workflows, not Python CLI."* and *"invoked by Claude Code... The workflow: Loads graph, checks staleness, resolves DAG..."*
* **Why it’s a fatal flaw:** Claude Code is an interactive, autonomous terminal agent designed for developers to write and edit code. It is **not** a reliable, programmatic orchestration engine. If you ask Claude Code to execute a strict, 5-step DAG, read files, calculate SHA-256 hashes, make targeted API calls, and incrementally update a JSON file, it will act non-deterministically. It might summarize the results in markdown instead of JSON, hallucinate Python scripts on the fly, or skip steps to save time.
* **The Fix:** The *orchestration* (DAG logic, file I/O, hash comparisons, staleness checks, and schema validation) **must** be written in code (Python or TypeScript). The *analyses* should be LLM API calls executed by this code. Do not use the `claude` CLI agent as a runtime engine for an end-user tool. 

**Pass 2 Source Text Retrieval (Section 2 & 7)**
* **The Issue:** Pass 2 requires the system to *"pull the specific sections from source documents"* to verify findings. 
* **Why it’s a fatal flaw:** How exactly does the system do this? Split 01 only outputs `deal-graph.json`. Legal documents (especially PDFs) do not have clean, programmatic APIs to "get Section 4.2(b)". If Split 01 did not extract the *entire raw text* mapped to section numbers, Split 02 has no reliable way to fetch the source text for Pass 2 without re-parsing and re-chunking the original PDFs.
* **The Fix:** You must explicitly define how Pass 2 retrieves text. Either:
  1. Split 01 must output a `deal-text-index.json` containing the raw text keyed by section.
  2. Split 02 must include a lightweight text-extraction utility (like `pdfplumber` or `pymupdf`) and use LLMs to perform fuzzy searches over the raw text to find the relevant sections.

**Finding "Missed" Terms using only Extracted Data (Section 8)**
* **The Issue:** The Defined Term Enhancement Pass prompts Claude with the *graph* to find terms that Split 01 *missed*. 
* **Why it’s a fatal flaw:** If Split 01 missed a defined term, it won't be in the graph JSON. You cannot find missing data by exclusively querying the dataset that missed it. You might find "undefined usage" if the term appears in a relationship snippet, but you won't find implicitly defined terms that Split 01 skipped entirely.
* **The Fix:** If you truly want to catch terms missed by Split 01, this specific pass must run against the source document text, not just the extracted `deal-graph.json`.

---

### 2. Performance & Cost Issues

**Missing Prompt Caching (Sections 2 & 11)**
* **The Issue:** You are passing a 50K–100K token JSON graph to the Anthropic API 5 separate times (once for each analysis). For a solo user, this will result in slow execution times (30–60 seconds per analysis) and high API costs.
* **The Fix:** You **must** utilize Anthropic’s Prompt Caching. Load `deal-graph.json` as a cached system prompt, and then run the 5 analysis workflows against that cached context. This will reduce your Pass 1 API costs by ~90% and drop latency to single-digit seconds.

**Model Selection (Section 11)**
* **The Issue:** The plan suggests falling back to *Claude Opus* for complex deals.
* **The Fix:** Do not use Claude 3 Opus for this. Claude 3.5 Sonnet is significantly cheaper, much faster, and empirically outperforms Opus on large-context data retrieval, JSON adherence, and complex logical reasoning. Stick to Claude 3.5 Sonnet for everything. 

---

### 3. Edge Cases & Logic Gaps

**Graph Hashing & Non-Determinism (Section 5)**
* **The Issue:** Staleness uses the SHA-256 hash of `deal-graph.json`. If Split 01 regenerates the graph and the arrays (e.g., `defined_terms`, `relationships`) are in a different order, the hash will change, instantly invalidating all analyses even if the semantic data is identical.
* **The Fix:** Before hashing `deal-graph.json`, the orchestration script must parse the JSON, deeply sort all keys and arrays, and serialize it cleanly. (Alternatively, hash the documents/entities individually to allow granular staleness tracking).

**Cross-Cluster Scale Handling (Section 13)**
* **The Issue:** For large deals, the plan proposes partitioning documents by cluster (e.g., Loan Docs vs. Equity Docs) to fit the context window. 
* **The Footgun:** The primary value of this tool is finding *cross-document* conflicts. If you isolate Loan Docs from Equity Docs, you will entirely miss the critical conflict where an Equity operating agreement violates a Loan covenant.
* **The Fix:** Context windows for Claude 3.5 Sonnet are 200K tokens. A 40-document graph JSON is highly unlikely to exceed this if it's just metadata (no raw text). If you *must* handle massive deals, do not cluster by document type. Instead, cluster by *Issue Area* (derived in Hierarchy analysis) and pass all cross-references related to that issue area, regardless of document origin.

**Missing Dependency in the DAG (Section 3)**
* **The Issue:** Defined Terms is listed as a standalone analysis. However, a "Contradictory Provision" (Conflicts) or an "Ambiguous Hierarchy" often hinges entirely on how a specific term is defined. 
* **The Fix:** Consider making "Defined Terms" a prerequisite for "Conflicts". If a term has a `conflicting_definition`, the Conflicts analysis needs to know that so it can flag cross-references utilizing that term as inherently risky.

---

### 4. Minor Clarifications & Improvements

* **Staleness Tracking (Section 5):** The rule says "Party modified -> None". But what if an Execution Sequence requires the "Guarantor" to sign first, and the "Guarantor" party was removed or replaced in Split 01? Party changes *can* affect Execution Sequence and CPs. Treat party modifications as triggers for CP/Sequence staleness.
* **File Locking (Section 12):** "Check for `.deal-analysis.lock` file... if older than 5 minutes, assume stale". Be careful here. Claude API calls for a 100K token prompt across 5 parallel analyses plus Pass 2 verifications might genuinely take longer than 5 minutes. Use a 15-minute lock expiry, or better yet, touch the lockfile continuously while the process is running.
* **JSON Schema Resiliency (Section 11/12):** You noted retry logic for schema validation failures. Use Anthropic's native **Tool Use (Function Calling)** to enforce the Pydantic schema rather than just asking for JSON in the prompt. Tool Use drastically reduces schema hallucinations.

### Summary Verdict
The core concept (Graph -> Pass 1 Candidates -> Pass 2 Verification) is excellent and accurately mimics how a human lawyer reviews a deal. However, you must replace the "Claude Code" orchestration concept with a standard Python/TS script, explicitly solve how Pass 2 accesses raw source text, and implement Prompt Caching to make this viable for daily use.
