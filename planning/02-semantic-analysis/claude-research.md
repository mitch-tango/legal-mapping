# Research Findings: Semantic Analysis Engine (Split 02)

## Part A: Codebase Research

### Project Status

This is a legal document intelligence system in early planning stage. A three-split Claude Code workflow producing an interactive HTML visualization of how deal documents relate to each other.

- **Split 01 (Data Model & Extraction):** Detailed planning complete. 8 implementation sections drafted with TDD test stubs. No source code written yet.
- **Split 02 (Semantic Analysis):** Specification complete. Deep plan starting now.
- **Split 03 (Interactive Visualization):** Specification complete.

### Architecture

- **Python CLI scripts** (headless, return JSON, no stdin prompts)
- **Claude Code orchestrates** user interaction and decision-making
- **One JSON file per deal** (`deals/{deal-name}/deal-graph.json`) is the integration point
- **Dependencies:** anthropic, pydantic (v2+), python-docx, pypdf, pytest

### Split 01 Data Model (What Split 02 Consumes)

**Top-level DealGraph structure:**

```python
class DealGraph:
    schema_version: str              # "1.0.0" (SemVer)
    deal: DealMetadata
    parties: dict[str, Party]        # Canonical party store (keyed by ID)
    documents: dict[str, Document]   # Keyed by ID
    relationships: list[Relationship] # Directional edges
    defined_terms: list[DefinedTerm]
    cross_references: list[CrossReference]
    conditions_precedent: list[ConditionPrecedent]
    annotations: list[Annotation]    # User annotations on any entity
    extraction_log: list[ExtractionEvent]
```

**Key entities the analysis engine will work with:**

- **Document:** Has metadata, parties, key provisions, source file info
- **Relationship:** Directional edge with source/target document IDs, type (16-type taxonomy), confidence, evidence quotes
- **DefinedTerm:** Unique by `(term, defining_document_id)`, has optional definition_snippet
- **CrossReference:** Links between specific sections across documents
- **ConditionPrecedent:** CP entities are the canonical source of truth; `conditions_precedent` relationship type is a derived view

**16-Type Relationship Taxonomy:**

| # | Type | Semantics |
|---|------|-----------|
| 1 | `controls` | Source governs target |
| 2 | `references` | Source cites target |
| 3 | `subordinates_to` | Source is subordinate to target |
| 4 | `defines_terms_for` | Source defines terms used in target |
| 5 | `triggers` | Events in source activate obligations in target |
| 6 | `conditions_precedent` | Source must be satisfied before target is effective |
| 7 | `incorporates` | Source pulls in provisions from target by reference |
| 8 | `amends` | Source modifies provisions of target |
| 9 | `assigns` | Source transfers rights/obligations from target |
| 10 | `guarantees` | Source guarantees obligations in target |
| 11 | `secures` | Source provides security/collateral for target |
| 12 | `supersedes` | Source entirely replaces target |
| 13 | `restricts` | Source restricts rights/use in target |
| 14 | `consents_to` | Source provides consent for action in target |
| 15 | `indemnifies` | Source provides indemnification for claims in target |
| 16 | `restates` | Source restates target (amended and restated) |

**Design patterns relevant to Split 02:**

1. **Confidence levels:** All extracted entities have `confidence: Literal["high", "medium", "low"]` and `needs_review: bool`
2. **Evidence fields:** Optional `evidence: {quote: str, page: int | None}` on relationships and cross-references
3. **User edit coexistence:** User edits stored directly; AI originals in `ai_original_values` dict
4. **Incremental updates:** Re-running one analysis shouldn't lose others
5. **Prompt injection defense:** System message marks document text as untrusted
6. **Document identity:** Matched by SHA-256 hash, source_file_path, or name+type

### Prototype Reference

`Reference/Legal Mapping Idea.txt` is a 719-line working HTML5 single-file app using D3.js and Anthropic API. It has a basic "Analyze All" feature that discovers cross-document relationships with 7 relationship types and confidence scoring. The semantic analysis engine goes deeper: not just finding relationships but analyzing their implications.

### Document Types in Scope

Real estate deal documents: Joint Venture Agreements, Operating Agreements, Construction/Permanent Loan Agreements, Guaranties, Environmental Indemnities, Purchase and Sale Agreements, Ground Leases, Promissory Notes, Deeds of Trust, Intercreditor Agreements, Subordination Agreements, Management Agreements, Development Agreements, Title Insurance Policies, Organizational documents.

### Testing Approach

The project uses TDD (Test-Driven Development). Split 01 has `claude-plan-tdd.md` with test stubs for each section. Test framework: pytest + pytest-asyncio. Shared fixtures in `tests/conftest.py`.

---

## Part B: Web Research

### Topic 1: LLM-Driven Legal Document Analysis Patterns

**Architectural patterns:**

1. **Hierarchical segmentation** -- Split documents along semantic boundaries (clause headings, paragraph breaks) rather than arbitrary token limits to prevent meaning fragmentation.
2. **Chain-of-thought prompting** -- Instruct model to "list essential points or obligations" before synthesizing. Reduces omissions and hallucinations.
3. **System role specialization** -- Setting system prompt to domain expert role (e.g., "You are a legal analyst specializing in real estate law") measurably improves output.
4. **XML-structured output** -- Claude responds well to XML tags for input structure and output format, enabling reliable programmatic parsing.
5. **Prefilled assistant responses** -- Constrains output format and reduces preamble.

**Handling large document sets:**

- **Meta-summarization:** Split into ~20K char chunks, summarize each, then synthesize chunk summaries.
- **Summary-indexed documents:** Generate concise summaries per document, rank by relevance. More token-efficient than traditional RAG.
- **Claude's native 1M token context:** Claude Opus 4.6 supports 1M tokens natively. Extended thinking with interleaved tool use enables reasoning between retrieval steps.

**Accuracy and hallucination mitigation:**

| Technique | Description |
|-----------|-------------|
| Temperature control | Set to 0-0.03 for legal analysis |
| Citation grounding | Require model to quote supporting text for every claim |
| Multi-model verification | Use a second LLM pass to fact-check the first |
| "Not specified" default | Instruct Claude to say "Not specified" rather than invent |
| NCKG-enhanced LLMs | Nested Contract Knowledge Graphs achieve F1 of 0.85 in risk identification |

**Sources:** Anthropic legal summarization docs, SCIRP journal, Rankings.io, GetMaxim, Spellbook.legal

### Topic 2: Cross-Reference Validation and Conflict Detection

**Sabetzadeh Framework (99.4% F-measure):**

Cross-reference taxonomy by scope, explicitness, and complexity:
- **Explicit:** Alphanumeric labels ("Article 54", "Section 3.2(a)")
- **Implicit:** Anaphoric ("this section", "the following paragraphs")
- **Delegating:** External references without naming specific text
- **Unspecific:** Vague terms ("the above provision")

Detection pipeline: tokenization -> NER with legal gazetteers -> rule-based pattern matching -> BNF grammar formalization. Achieved 99.7% precision, 97.9% recall.

**Resolution phases:**
1. Schema-based structure recognition (model document hierarchy as DAG)
2. Automated markup generation via topological ordering
3. Context-dependent interpretation rules for implicit references

**Dangling reference categories:** Misclassification errors, well-formedness issues, non-existing targets (0.32% false positive rate).

**Circular reference detection:** RML with Binary Decision Diagram encoding. Real-world testing found 8 length-2 cycles, all mutual cross-references.

**Severity classification:**

| Severity | Criteria | Examples |
|----------|----------|----------|
| CRITICAL | Blocks closing; legal invalidity risk | Missing exhibit; undefined party; circular CP |
| ERROR | Substantive inconsistency; likely requires amendment | Conflicting dates; inconsistent defined terms; dangling xref |
| WARNING | Potential issue; requires human review | Implicit reference ambiguity; unused term; near-duplicate definitions |
| INFO | Cosmetic or informational | Style inconsistencies; simplifiable xref |

**Sources:** Sabetzadeh et al. (Springer RE journal, IEEE), arXiv Graph RAG papers, Enterprise RAG community, GRAPH-GRPO-LEX

### Topic 3: Dependency Chain Analysis and Topological Sorting

**Conditions precedent as a DAG:**
- Nodes = conditions, documents, or deliverables
- Edges = "must be satisfied before" relationships
- If DAG, valid execution order exists

**Algorithms (all available in NetworkX):**

| Algorithm | Best For |
|-----------|----------|
| **Kahn's (BFS)** | Produces "generations" -- parallelizable groups at each level |
| **DFS/Tarjan's** | Identifies strongly connected components (mutually dependent conditions) |
| **`topological_generations()`** | Groups of conditions satisfiable in parallel |
| **`dag_longest_path()`** | Critical path computation |
| **`find_cycle()`** | Quick cycle validation |

**Critical path analysis:**
1. Topologically sort conditions
2. For each node: earliest start = max(earliest_finish of predecessors)
3. Earliest finish = earliest start + duration
4. Path with maximum total duration = critical path

**Circular dependency handling:** Tarjan's SCC recommended -- identifies the exact set of mutually dependent conditions, mapping directly to "these conditions need restructuring or simultaneous satisfaction."

**PERT framework mapping:** Milestones=conditions satisfied, Tasks=work to satisfy, Dependencies=CP relationships, Slack/Float=how much non-critical conditions can slip.

**Sources:** NetworkX guides, Wikipedia (topological sorting, dependency graphs), GeeksforGeeks, GitHub examples

### Topic 4: Defined Term Extraction and Tracking

**Extraction techniques:**

Rule-based (high precision):
- Capitalized terms following `"Term" means...`, `"Term" shall mean...`, `as defined in...`
- Parenthetical definitions: `the borrower (the "Borrower")`
- Definitions sections parsing
- LexNLP library: pre-trained for legal entity extraction on SEC EDGAR filings

LLM-based (high recall):
- Prompt Claude for term-definition pairs as structured JSON
- Few-shot examples improve consistency
- Hybrid approach: supervised entity detection for accuracy + generative AI for recommendations

**Term provenance tracking structure:**
```
DefinedTerm {
  term: string           // "Permitted Liens"
  canonical_definition: string
  defined_in: [{document, section, page}]
  used_in: [{document, section, page}]
  related_terms: [DefinedTerm]
  status: "defined" | "undefined" | "orphaned" | "conflicting"
}
```

**Cross-document consistency checking:**
1. Exact match: Same term, same definition -- no issue
2. Semantic equivalence: Different wording, same meaning -- INFO
3. Substantive conflict: Different wording, different meaning -- ERROR
4. Missing incorporation: Document B uses term from A without cross-reference -- WARNING

**Implementation:** Embedding similarity (>0.95 exact match, 0.80-0.95 review zone, <0.80 likely conflict) + LLM semantic comparison for flagged pairs.

**Sources:** LexCheck blog, LegalOn Technologies, LexNLP (arXiv + GitHub), EmergentMind, ScienceDirect, NLP for Legal Domain survey

---

## Cross-Cutting Recommendations

1. **Graph-first architecture:** Model entire document corpus as multi-layer graph (hierarchy, cross-references, defined terms, CPs). Unified representation supports all five analysis capabilities.

2. **Two-pass analysis:** First pass uses deterministic rule-based extraction (high precision); second pass uses LLM analysis (high recall). Merge with confidence scores.

3. **NetworkX as computation backend:** Provides all graph algorithms needed (topological sort, cycle detection, critical path, SCC) with mature Python API.

4. **Claude with extended thinking for reasoning:** Extended thinking for complex tasks (conflict detection, semantic comparison). Standard mode for high-volume extraction.

5. **Severity-classified output:** All findings carry severity levels (CRITICAL/ERROR/WARNING/INFO) to prioritize human review.

6. **Auditable provenance:** Every finding traces back to specific document locations and reasoning chain. Non-negotiable for legal applications.
