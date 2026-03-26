# Research Findings — Data Model & Document Extraction

## Part 1: Codebase Research (Existing Prototype)

### Project Overview

The existing prototype is a **single-file HTML application** at `Reference/Legal Mapping Idea.txt` — a working proof of concept with D3.js force-directed graph visualization, browser-based Anthropic API integration, and localStorage persistence.

**Key Vision — Five Critical Questions:**
1. Document Control Hierarchy — Which document governs which issues?
2. Defined Term Provenance — Where are terms born and how do they flow?
3. Conditions Precedent Chains — What must be satisfied before what?
4. Cross-Reference Conflicts — Where do documents conflict or create risk?
5. Execution Sequencing — What's the correct closing order?

### Architecture (Prototype → Production)

**Prototype:** Browser-based API calls → localStorage
**Production architecture:**
```
[Word/PDF Documents]
    ↓
[Claude Code: Extraction & Analysis Engine]
    ↓
[deal-graph.json]
    ↓
[Interactive HTML Visualization]
    ├─ View/navigate graph
    ├─ Edit relationships & add notes
    └─ Export to PDF
    ↓
[Claude Code reads edits back for re-analysis]
```

### Relationship Taxonomy (7 types, from prototype)

| Type | Meaning |
|------|---------|
| `controls` | Document A governs/takes precedence over Document B |
| `references` | Document A cites or mentions Document B |
| `subordinates_to` | Document A is contractually subordinate to Document B |
| `defines_terms_for` | Defined terms in Document A flow into Document B |
| `triggers` | Events in Document A activate obligations in Document B |
| `conditions_precedent` | Document A must be satisfied before Document B becomes effective |
| `incorporates` | Document A pulls in provisions by reference from Document B |

### Extraction Prompt Design (from prototype)

The prototype extracts into this JSON structure:
```json
{
  "documentType": "specific type (e.g., Joint Venture Agreement)",
  "parties": ["Party A", "Party B"],
  "keyDefinedTerms": ["up to 10 key defined terms"],
  "obligations": ["2-4 key obligations"],
  "summary": "2-3 sentence summary",
  "referencedDocuments": [
    {
      "inferredName": "document name as cited",
      "relationshipType": "controls|references|subordinates_to|...",
      "description": "how these documents relate",
      "confidence": "high|medium|low"
    }
  ]
}
```

**Key patterns from prototype:**
- System message: "You are a real estate legal document analyst. Return ONLY valid JSON."
- Confidence scoring: high/medium/low for each extracted relationship
- If no PDF provided: marks all confidence as low (infers from document name only)
- Context: Lists existing documents to help matching
- Model: claude-sonnet-4-20250514, max tokens 1500

### Document Type Color Scheme (16 types)

The prototype includes color mappings for: Joint Venture Agreement, Operating Agreement, Construction Loan Agreement, Guaranty (multiple subtypes), Environmental Indemnity, PSA, Ground Lease, Promissory Note, Deed of Trust, Loan Agreement, Intercreditor Agreement, Subordination Agreement, Management Agreement, Development Agreement.

### Existing Gaps / What's Not Yet Built

1. No richer semantic analysis (pairwise relationships only)
2. No Conditions Precedent chain visualization
3. No PDF export
4. No file I/O (uses localStorage)
5. No hierarchy or timeline views
6. No conflict detection
7. No Word document support
8. No multi-user collaboration

### Project Structure

```
Mapping/
├── Reference/
│   └── Legal Mapping Idea.txt          [Working prototype HTML]
├── planning/
│   ├── 01-data-model-extraction/       [This split]
│   ├── 02-semantic-analysis/
│   ├── 03-interactive-visualization/
│   ├── project-manifest.md
│   └── deep_project_interview.md
├── requirements.md
└── .claude/settings.local.json
```

---

## Part 2: Web Research — Best Practices

### 1. JSON Graph Data Modeling

**JSON Graph Specification** ([jsongraph/json-graph-specification](https://github.com/jsongraph/json-graph-specification)) is the most mature open standard:

```json
{
  "graph": {
    "directed": true,
    "type": "legal-dependency-graph",
    "metadata": { "schemaVersion": "1.0.0" },
    "nodes": {
      "doc-id": {
        "label": "Purchase and Sale Agreement",
        "metadata": { "docType": "agreement", "parties": ["Buyer", "Seller"] }
      }
    },
    "edges": [
      {
        "source": "doc-purchase-agreement",
        "target": "doc-title-commitment",
        "relation": "requires",
        "metadata": { "clause": "Section 5.2" }
      }
    ]
  }
}
```

**Node types to consider:** Document, Clause/Section, DefinedTerm, Party, Obligation, Milestone/Event

**Incremental updates + user annotations — layered approach:**
- Separate `ai_extracted` and `user_annotations` sub-objects on each node/edge
- Tag each extracted field with `confidence`, `extractedAt`, `modelVersion`
- Store `status` field (`draft`, `needs_review`, `confirmed`) for user validation

**Schema versioning:** Use SemVer (MAJOR.MINOR.PATCH). Always include `additionalProperties: true` in JSON Schema for forward compatibility. Keep migration functions for version transitions.

Sources: [JSON Graph Spec](https://github.com/jsongraph/json-graph-specification), [Memgraph](https://memgraph.com/docs/data-modeling/graph-data-model), [SchemaVer](https://snowplow.io/blog/introducing-schemaver-for-semantic-versioning-of-schemas)

### 2. PDF and .docx Extraction via Claude API

**PDF capabilities (Anthropic docs):**
- Max 32 MB, 600 pages (100 for 200k models)
- Each page: ~1,500-3,000 text tokens + image tokens
- Three methods: URL reference, Base64 encoding, Files API (recommended for repeated use)
- Best practice: Place PDFs before text in request; enable prompt caching for repeated analysis

**DOCX handling:** Claude does not natively support .docx. Two approaches:
1. Extract text with `python-docx` (preserves heading hierarchy, section structure) → send as plain text
2. Convert to PDF first if images matter

**Structured outputs (now GA):**
- `messages.parse()` with Pydantic models — guarantees valid JSON matching your schema
- `strict: true` on tool use — guarantees tool call parameters match schema
- Use `enum` for restricted values (relationship types, doc categories)
- ~100-300ms overhead on first request (cached 24h)

Sources: [Claude PDF Support](https://platform.claude.com/docs/en/build-with-claude/pdf-support), [Claude Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), [Claude Files API](https://platform.claude.com/docs/en/build-with-claude/files)

### 3. Large Document Chunking Strategies

**Token budget for 200k context window:**
- System prompt: ~3K (1.5%)
- Document content: ~120K (60%)
- Working space: ~50K (25%)
- Output buffer: ~27K (13.5%)

**When to chunk:** Documents over ~40-60 pages depending on density.

**Best strategies for legal documents:**
1. **Structure-aware chunking** — split on articles, sections, numbered clauses using heading detection
2. **Recursive character splitting** — for oversized sections without clear structure
3. **Semantic chunking** — groups by meaning, detects topic shifts

**Overlap for cross-references:** Use 20-25% overlap at clause boundaries (legal cross-references often appear there).

**Map-Reduce pattern for extraction:**
1. **MAP:** Per-chunk extraction → defined terms, party names, document references, obligations, cross-references (tagged with chunk_id and position)
2. **COLLAPSE:** Group related extractions, deduplicate, merge
3. **REDUCE:** Synthesize into unified graph — deduplicated nodes, resolved cross-references, merged edges, conflict resolution

**Key insight (LLMxMapReduce):** Pass summary of extracted entities from adjacent chunks as context when processing each chunk to handle inter-chunk dependencies.

Sources: [Firecrawl](https://www.firecrawl.dev/blog/best-chunking-strategies-rag), [LangCopilot](https://langcopilot.com/posts/2025-10-11-document-chunking-for-rag-practical-guide), [Redis](https://redis.io/blog/context-window-overflow/), [LLMxMapReduce](https://arxiv.org/html/2410.09342v1)

### 4. Legal Document NLP/Extraction Patterns

**Defined terms extraction:**
1. LLM-based with structured output (recommended): Prompt Claude to identify capitalized terms + definitions
2. Pattern matching pre-filter + LLM validation: Regex for `"Term" means ...`, `"Term" shall mean ...`, etc. → feed to Claude
3. NER-based (John Snow Labs): 600+ pretrained legal models, but requires Spark infrastructure

**Cross-reference detection (open challenge in literature):**
1. Build term/entity index from all documents in the deal
2. Pattern-match references: "as defined in the Purchase Agreement", "pursuant to Section 5.2 of the Loan Agreement"
3. Match against index; use Claude for ambiguous references
4. Two-pass approach: local (within-section) coreference first, then cross-section

**Obligation extraction — signal words:**

| Signal | Type |
|--------|------|
| "shall", "must", "is required to" | Mandatory obligation |
| "shall not", "must not" | Prohibition |
| "may", "is entitled to" | Permission/right |
| "subject to", "conditioned upon", "provided that" | Condition precedent |
| "notwithstanding" | Exception/override |

**Party identification:**
1. Extract from preamble first (highest accuracy zone)
2. Map aliases: "XYZ Corp" introduced as "Borrower"
3. Classify roles: Buyer/Seller, Borrower/Lender, Landlord/Tenant, Guarantor, etc.

Sources: [Springer Legal Terms LLM](https://link.springer.com/article/10.1007/s10506-025-09448-8), [John Snow Labs Legal NLP](https://medium.com/john-snow-labs/contract-understanding-with-legal-nlp-pretrained-pipelines-84da2346af17), [ACL 2025 ACORD](https://aclanthology.org/2025.acl-long.1206.pdf)

---

## Synthesized Recommendations

1. **Data model:** Adopt JSON Graph Specification as the base format with custom metadata schemas. Version from day one (SemVer). Separate AI-extracted data from user annotations in node/edge metadata.

2. **Document ingestion:**
   - PDFs: Send directly to Claude API (Files API for repeated use, prompt caching enabled)
   - DOCX: Extract with `python-docx` (preserves structure) → send as plain text to Claude
   - Use structured outputs (`messages.parse()` with Pydantic) for all extraction

3. **Large document handling:** Structure-aware chunking (sections/articles first, then recursive splitting). 512-token chunks with 20% overlap. Map-reduce: extract per-chunk, synthesize in reduce step.

4. **Legal extraction:** LLM-based with Claude structured outputs. Pattern-matching pre-filter for defined terms. Build cross-document term index. Question-answering prompts for obligation extraction.

5. **Privacy:** Claude API only (Anthropic zero-retention policy). No third-party services. All data stored locally.

---

## Testing Approach

**New project** — no existing test framework.

**Chosen setup:** pytest with fixtures
- Test files in `tests/` directory, named `test_*.py`
- Fixtures in `tests/conftest.py` and `tests/fixtures/`
- JSON fixture files for mock API responses (deterministic testing of merger/validator without API calls)
- `pytest-mock` for mocking Anthropic API calls in extraction tests
- Separate test categories:
  - **Unit tests** (deterministic): schema validation, normalization, merging, graph operations
  - **Integration tests** (mocked API): extraction pipeline with recorded API responses
  - **Acceptance tests** (live API, manual): run against real documents, snapshot-based validation
- Run command: `pytest` (or `pytest tests/ -v` for verbose)
- Configuration in `pyproject.toml` under `[tool.pytest.ini_options]`
