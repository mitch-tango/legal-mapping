# Section 06 — Pipeline (Extraction Orchestrator)

This section implements the main extraction pipeline that orchestrates document reading, Claude API calls with structured outputs, and result processing. The pipeline handles single document extraction, relationship linking, and smart matching. It is the core integration point that ties together the document readers (section-04), prompts (section-05), and extraction models (section-03).

---

## Tests First

### Single Document Extraction — File: `Mapping/tests/test_extraction.py`

```python
# Test: extract_document with a valid PDF path returns DocumentExtractionResult
# Test: extract_document with a valid DOCX path returns DocumentExtractionResult
# Test: extract_document with unsupported file type returns error JSON
# Test: extract_document with nonexistent file returns error JSON
# Test: extraction result includes all required fields (type, parties, terms, summary)
# Test: extraction uses temperature=0 in API call
# Test: extraction metadata records model, model_version, prompt_version hash, and processing_time_ms
```

### Smart Matching — File: `Mapping/tests/test_extraction.py`

```python
# Test: exact type + name match returns high confidence
# Test: type match only returns medium confidence
# Test: fuzzy name match only returns low confidence
# Test: no match returns no relationship
# Test: matching is case-insensitive for document names
# Test: matching handles common abbreviations ("Agmt" = "Agreement")
```

### Large Document Handling

```python
# Test: documents under 200K tokens processed in single call (no chunking)
# Test: pipeline logs a warning if document is very large but still processes it
```

### API Error Handling

```python
# Test: API error triggers retry with exponential backoff (mock 3 failures)
# Test: after 3 retries, returns error JSON for Claude Code to present
# Test: malformed API response (fails Pydantic parse) returns error JSON
```

Use mock API responses for all tests — never call the real Claude API in tests. The fixture files from section-01 provide the mock responses:
- `tests/fixtures/extraction-response-loan-agreement.json`
- `tests/fixtures/extraction-response-guaranty.json`
- `tests/fixtures/relationship-response.json`

---

## Implementation

### File: `Mapping/src/extraction/pipeline.py`

The pipeline is the main orchestrator. It does not own any data models or prompt text — it imports from the models and prompts modules and coordinates the flow.

### Single Document Extraction Flow

```python
def extract_single_document(file_path: str, existing_graph: DealGraph | None = None) -> DocumentExtractionResult | dict:
    """Extract metadata from a single document via Claude API.

    Flow:
    1. Determine file type (PDF or DOCX) from extension
    2. Read document:
       - PDF: Run preflight with pdf_reader.preflight_pdf()
         - Records has_text_layer, page_count, file_hash
         - Read file bytes for API submission as document block
       - DOCX: Run docx_reader.read_docx()
         - Gets structured text, file_hash, track_changes status
    3. Build extraction prompt via prompts.build_document_extraction_prompt()
    4. Call Claude API with structured outputs:
       - Use anthropic client's messages.parse() with DocumentExtractionResult as the response model
       - Temperature: 0 for deterministic extraction
       - Send PDF as document block, DOCX as text content
    5. Record extraction metadata (model, timestamp, prompt hash, processing time)
    6. If existing_graph provided, run relationship linking
    7. Return DocumentExtractionResult

    On error, returns a dict with error details (not an exception).
    """
```

### Claude API Integration

The pipeline uses the Anthropic Python SDK's structured output feature:

```python
# Conceptual pattern (not full implementation):
client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY from env

# For PDF documents:
message = client.messages.parse(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    temperature=0,
    system=system_prompt,
    messages=[{
        "role": "user",
        "content": [
            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": base64_pdf}},
            {"type": "text", "text": "Extract structured metadata from this document."}
        ]
    }],
    response_model=DocumentExtractionResult,
)

# For DOCX documents (text already extracted):
message = client.messages.parse(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    temperature=0,
    system=system_prompt,
    messages=[{
        "role": "user",
        "content": docx_text
    }],
    response_model=DocumentExtractionResult,
)
```

The `messages.parse()` method uses Pydantic model integration to guarantee valid JSON output matching the model schema.

### Relationship Linking Flow

```python
def extract_relationships(
    file_path: str,
    document_content: str | bytes,
    existing_graph: DealGraph,
) -> RelationshipExtractionResult | dict:
    """Identify relationships between a new document and existing documents.

    Flow:
    1. Build Document Index from existing_graph via prompts.build_document_index()
    2. Build relationship linking prompt via prompts.build_relationship_linking_prompt()
    3. Call Claude API with structured outputs using RelationshipExtractionResult
    4. Post-process: run directionality checks via normalizer.check_directionality()
    5. Return RelationshipExtractionResult

    On error, returns a dict with error details.
    """
```

### Smart Matching

When a new document references other documents by name (e.g., "as defined in the Loan Agreement"), the pipeline scores references against existing documents:

```python
def score_document_match(reference: str, existing_documents: dict[str, Document]) -> list[tuple[str, str, str]]:
    """Score a document reference against existing documents in the graph.

    Scoring:
    - Exact document type match + name overlap -> high confidence
    - Document type match only -> medium confidence
    - Fuzzy name match only -> low confidence

    Returns list of (document_id, document_name, confidence) sorted by confidence.
    Only medium+ confidence matches generate relationship edges.
    Low confidence matches are flagged in the extraction log for user review.
    """
```

Common abbreviation handling: the matcher should recognize standard legal abbreviations:
- "Agmt" = "Agreement"
- "Gty" = "Guaranty"
- "Mtg" = "Mortgage"
- "DOT" = "Deed of Trust"

### Large Document Handling

No chunking for v1. Send the entire document to Claude in a single API call. Claude's 200K token context window handles approximately 300-400 pages of dense legal text. This yields superior extraction quality because:
- Defined terms, obligations, and CPs often span the document
- Cross-reference resolution is dramatically better with full context
- No deduplication complexity from overlapping chunks

If a document exceeds the context window, log a warning and return an error suggesting the user break the document into parts. Chunking is deferred to a future version.

### API Retry Logic

```python
def call_api_with_retry(api_call: Callable, max_retries: int = 3) -> Any:
    """Call the Claude API with exponential backoff retry.

    Retries on:
    - Rate limit errors (429)
    - Server errors (500, 502, 503)
    - Connection errors

    Does NOT retry on:
    - Authentication errors (401)
    - Bad request errors (400)
    - Pydantic validation failures (malformed response)

    Backoff: 1s, 2s, 4s (exponential)
    After max_retries, returns error dict for Claude Code to present.
    """
```

### Post-Parse Validation (Prompt Injection Defense)

After receiving the parsed response from the API, run basic sanity checks:
- Check that string fields don't exceed reasonable lengths (e.g., summary < 2000 chars, term names < 200 chars)
- Check that enum fields contain allowed values (the Pydantic model handles this, but double-check)
- Check that the number of extracted items is reasonable (e.g., not 500 parties from a single document)

This is a defense against prompt injection — if document text contains adversarial instructions, the structured output format limits the attack surface, but field length and count checks provide an additional layer.

---

## Dependencies

- **Requires:** section-03-extraction-models (DocumentExtractionResult, RelationshipExtractionResult, normalizer), section-04-document-readers (pdf_reader, docx_reader), section-05-prompts (prompt builders)
- **Blocks:** section-08-cli (CLI invokes the pipeline)
