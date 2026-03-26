# Gemini Review

**Model:** gemini-3-pro-preview
**Generated:** 2026-03-26T09:55:19.405964

---

Here is a comprehensive architectural review of your implementation plan. 

Overall, the separation of concerns (schema, extraction, taxonomy) is well thought out, and using Python/Pydantic to enforce Claude’s structured outputs is the correct approach. However, there are several high-impact footguns specifically related to legal tech nuances, context window utilization, and schema design that will cause downstream pain if not addressed now.

---

### 1. Architectural & Pipeline Problems

**Premature Optimization: Document Chunking (§5.5)**
*   **The Issue:** You are planning to chunk documents at ~40 pages (~20k-30k tokens). Claude 3.5 Sonnet/Opus have a 200k token context window (roughly 300-400 pages of dense legal text). Map-reduce extraction on legal documents is notoriously difficult because defined terms, obligations, and conditions precedent often span across the document (e.g., a condition precedent in Article 8 relies on a defined term in Article 1).
*   **Recommendation:** **Drop the chunking entirely for v1.** Pass the entire document to Claude in a single prompt. It yields vastly superior co-reference resolution and accuracy. Only implement chunking if you consistently hit rate limits or encounter 400+ page mega-documents (which are rare; even complex MSAs or Credit Agreements rarely exceed 250 pages).

**The "Summary" Strategy for Linking is Too Weak (§5.3 & §5.4)**
*   **The Issue:** When doing the cross-document relationship pass, you plan to send "summaries of existing documents." Legal cross-references are highly specific (e.g., "subject to Section 4.2(b) of the Guaranty"). A 2-3 sentence AI summary of the Guaranty will not contain Section 4.2(b). The AI will fail to confidently link specific dependencies.
*   **Recommendation:** Instead of just sending a summary, send a generated **"Document Index"** for existing documents. This index should include: Document Name, Aliases, List of Defined Terms, and a Table of Contents (Section numbers and titles). This gives the AI the exact hooks it needs to resolve granular cross-references.

**Read-Time vs. Write-Time Override Logic (§3.8)**
*   **The Issue:** The plan states: *"The visualization reads the annotation's override preferentially... The original AI value remains on the relationship itself."* This is an anti-pattern. If you rely on read-time merging, every single downstream tool (Split 02 Semantic Analysis, Split 03 Visualization, plus any future scripts) will have to perfectly implement this complex override-merging logic before acting on the data.
*   **Recommendation:** Implement **write-time overrides**. When a user creates an override, update the actual entity in `deal-graph.json` immediately. Move the original AI value into a `_provenance` or `ai_original_values` dict on that entity. This ensures the graph is always ready to consume "as-is" by any downstream script.

---

### 2. Document Processing Footguns

**DOCX "Track Changes" Nightmare (§6)**
*   **The Issue:** Legal documents in the draft phase (`status: draft`) heavily utilize Microsoft Word's "Track Changes" feature. By default, `python-docx` extracts deleted text `<w:del>` exactly the same as normal text, meaning Claude will read deleted clauses as if they are active obligations. 
*   **Recommendation:** You must explicitly configure your DOCX parser to either **accept all changes** (ignore `<w:del>` tags and keep `<w:ins>` tags) before extracting the text, or fail and ask the user to provide a clean version.

**Scanned/Non-OCR'd PDFs (§5.2)**
*   **The Issue:** The Anthropic Vision API handles PDFs well, but poorly scanned, non-OCR'd real estate documents (like an old recorded deed or signed signature pages) can result in hallucinations or silently dropped text.
*   **Recommendation:** Add a pre-flight check using a lightweight library like `pypdf` to check if the PDF contains a text layer. If it doesn't, add a warning to the `ExtractionLog` that the document relied entirely on Vision OCR, setting a default `confidence: low` for its extracted data.

---

### 3. Data Model & Schema Edge Cases

**Defined Term Collisions (§3.5)**
*   **The Issue:** In real estate deals, the same exact word can mean two different things in two different documents. For example, "Note" defined in the Loan Agreement means the $10M Promissory Note. "Note" defined in the Mezzanine Loan means the $2M Mezzanine Note. Your schema merges them: `defining_document_id: str` and `used_in_document_ids: list[str]`. If "Note" is defined twice, this schema breaks.
*   **Recommendation:** Change `defining_document_id` to a list, OR make the `DefinedTerm` ID a composite of `[Term_Name]_[Defining_Doc_ID]`. Allow multiple `DefinedTerm` objects for the same string, resolved by which document the string is being used in.

**Stale Edges on Document Replacement (§5.8)**
*   **The Issue:** If a user re-extracts/replaces v1 of a Loan Agreement with v2, the `Document` ID stays the same. However, Sections move. A `source_reference` on a relationship edge pointing to "Section 4.2" might now be pointing to the wrong clause. 
*   **Recommendation:** When a document is updated via "Replace", any incoming or outgoing `Relationship` or `CrossReference` edges linked to that document must automatically have their `confidence` downgraded to `low` or flagged as `needs_review: true` so the user knows to check if the section references shifted.

**Execution Date Formatting (§3.2)**
*   **The Issue:** Enforcing an ISO string (`YYYY-MM-DD`) for `execution_date` will cause the LLM to hallucinate or the pipeline to crash. Legal documents often say things like "Dated as of May __, 2024" or "Effective as of the date first written above." 
*   **Recommendation:** Split this into `execution_date_raw: str` (exactly as written in the doc) and `execution_date_iso: str | None` (LLM's best attempt to parse it, null if incomplete).

**Source File Path Fragility (§3.2)**
*   **The Issue:** Storing `source_file_path` as the primary link to the document means if a user renames the file from "JV_Agmt_v1.pdf" to "JV_Agmt_Final.pdf", the graph breaks. 
*   **Recommendation:** Use a hash of the file contents (SHA-256) as an additional field `file_hash: str`. When the CLI runs, it can use the hash to find moved/renamed files within the deal directory and auto-heal the `source_file_path`.

---

### 4. CLI & Orchestration UX

**Claude Code CLI Interaction (§5.7 & §8)**
*   **The Issue:** You state Claude Code will invoke the CLI, and the CLI will `input()` prompt the user for Re-extraction options (Replace/Version/Cancel). Claude Code operates as an LLM agent; if a Python script hangs on a standard `stdin` prompt, Claude Code might get confused, timeout, or try to forcefully kill the process.
*   **Recommendation:** Make the Python CLI purely headless and stateless. Instead of the Python script prompting the user, the Python script should return an exit code or JSON payload: `{"status": "conflict", "reason": "document_exists", "options": ["replace", "version"]}`. Claude Code reads this, asks the user via its own chat interface, and then re-invokes the CLI with a flag: `python -m cli extract-document --resolve replace`.

---

### 5. Missing Considerations / Security

**API Privacy & Data Retention (§1)**
*   **The Issue:** You mention "zero-retention policy." Be aware that Anthropic's standard commercial API retains data for 30 days for abuse monitoring unless you are on a specific Enterprise tier or have explicitly requested zero-retention (HIPAA/SOC2 compliance mode). 
*   **Recommendation:** Document the exact Anthropic header or account setting required to guarantee zero-retention for the solo practitioner. Additionally, explicitly state that API keys should be loaded via a local `.env` file that is in `.gitignore` to prevent accidental commits of credentials.

**Missing Dependencies (§7)**
*   **Recommendation:** You will need `tiktoken` (or Anthropic's token counting equivalent) to monitor prompt sizes before dispatching, preventing expensive API errors. You should also add a lightweight PDF checker (like `pypdf` or `pdfplumber`) to handle page counting and text-layer detection *before* sending heavy payloads to the API.
