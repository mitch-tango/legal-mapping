# Section 08: CLI Entry Points

## Overview

This section implements the CLI layer in `src/cli.py` -- the headless, JSON-returning command interface that Claude Code invokes to drive the extraction pipeline. All four commands (`extract-document`, `extract-batch`, `validate-graph`, `show-graph-summary`) are stateless and never prompt for user input via stdin.

**Dependencies:** This section requires all prior sections to be complete:
- **Section 06 (Pipeline):** `extract_document` orchestrator, `link_relationships`, smart matching, API retry logic
- **Section 07 (Graph Ops):** Graph manager (load/save/atomic write), graph merger (merge extraction results), graph validator (schema + semantic validation)
- **Section 02 (Schema):** `DealGraph`, `DealMetadata`, `Document`, `ExtractionEvent` and all other Pydantic models
- **Section 03 (Extraction Models):** `DocumentExtractionResult`, `RelationshipExtractionResult`, party normalizer
- **Section 04 (Document Readers):** PDF preflight, DOCX text extraction

## File to Create

- `C:\Users\maitl\New City Dropbox\Maitland Thompson\Working\Legal Review\Mapping\src\cli.py`

## Tests First

All tests go in `C:\Users\maitl\New City Dropbox\Maitland Thompson\Working\Legal Review\Mapping\tests\test_cli.py`.

### CLI Interface Tests (from plan Section 8)

```python
# Test: extract-document returns JSON (not interactive prompt)
# - Invoke extract_document with a valid file path and deal dir
# - Assert return value is valid JSON string
# - Assert no stdin reads occurred (mock stdin to raise if read)

# Test: extract-document with --resolve replace processes replacement
# - Set up a deal graph with an existing document matching the target file
# - Invoke extract_document with resolve="replace"
# - Assert the document was replaced (same ID preserved), confidence downgraded on edges

# Test: extract-document with --resolve version creates version
# - Set up a deal graph with an existing document
# - Invoke extract_document with resolve="version"
# - Assert old document node preserved, new document node created
# - Assert a supersedes relationship edge was added

# Test: extract-document without --resolve returns conflict JSON when doc exists
# - Set up a deal graph with a document whose file_hash matches
# - Invoke extract_document without resolve flag
# - Assert returned JSON has status="conflict", reason="document_exists"
# - Assert returned JSON includes document_id and options=["replace","version","cancel"]

# Test: extract-batch returns JSON summary
# - Create a temp folder with 2 PDF/DOCX files (mock extraction)
# - Invoke extract_batch
# - Assert returned JSON contains documents_processed count, deal_name, etc.

# Test: validate-graph returns JSON with errors and warnings
# - Create a deal dir with a deal-graph.json that has a referential integrity error
# - Invoke validate_graph
# - Assert returned JSON has "errors" and "warnings" keys

# Test: show-graph-summary returns JSON summary
# - Create a deal dir with a valid deal-graph.json containing 3 documents
# - Invoke show_graph_summary
# - Assert returned JSON has document_count, relationship_count, party_count, etc.

# Test: all CLI commands exit with code 0 on success, non-zero on failure
# - Invoke each command with valid input, assert exit code 0
# - Invoke each command with invalid input (e.g., nonexistent path), assert non-zero exit code
```

### Batch Extraction Tests (from plan Section 5.6)

```python
# Test: batch scans folder and finds all PDF and DOCX files
# - Create temp folder with .pdf, .docx, .txt, .xlsx files
# - Assert only .pdf and .docx are discovered

# Test: batch ignores non-PDF/DOCX files
# - Create folder with .txt, .csv, .png alongside .pdf
# - Assert only .pdf collected

# Test: batch creates new DealGraph with deal metadata
# - Run batch on a folder (mock extraction calls)
# - Assert resulting graph has deal.name set to provided deal_name
# - Assert deal.status is "active", created_at/updated_at are set

# Test: batch processes documents sequentially (order matters for party index)
# - Mock extract to record call order
# - Assert documents processed one at a time, each merged before next

# Test: batch runs relationship linking pass after all documents extracted
# - Mock relationship linking
# - Assert it is called after all individual extractions complete

# Test: batch normalizes parties across full deal
# - Mock extraction to return overlapping party names
# - Assert final graph has deduplicated parties with merged aliases

# Test: batch writes valid deal-graph.json at end
# - Run batch (mocked)
# - Assert deal-graph.json exists in deal_dir and passes schema validation
```

### Re-Extraction Tests (from plan Section 5.7)

```python
# Test: detects existing document by file_hash match
# - Load graph with doc having file_hash "abc123"
# - Attempt extract on a file that hashes to "abc123"
# - Assert conflict detected

# Test: detects existing document by source_file_path fallback when hash doesn't match
# - Load graph with doc at path "documents/loan.pdf"
# - Attempt extract on file at same relative path but different hash
# - Assert conflict detected

# Test: detects existing document by name + type fallback
# - Load graph with doc named "Loan Agreement" of type "loan_agreement"
# - Mock extraction returning same name+type but different hash/path
# - Assert conflict detected

# Test: returns conflict JSON when document exists (not stdin prompt)
# - Assert returned JSON has the conflict structure, never calls input()

# Test: replace mode preserves document ID
# - Run extract with resolve="replace"
# - Assert document ID in graph is unchanged

# Test: replace mode preserves user annotations and ai_original_values
# - Set up doc with annotations and ai_original_values
# - Run replace
# - Assert annotations still present, ai_original_values preserved

# Test: replace mode downgrades confidence to "low" on all related edges
# - Set up doc with high-confidence relationships
# - Run replace
# - Assert all relationships touching this doc now have confidence="low"

# Test: replace mode sets needs_review=true on affected edges
# - Run replace
# - Assert needs_review=true on relationships involving the replaced doc

# Test: version mode creates new document node with supersedes edge
# - Run extract with resolve="version"
# - Assert graph has one new document node
# - Assert a relationship with type="supersedes" from new to old exists

# Test: version mode preserves old document node
# - Run version
# - Assert old document still in graph.documents with its original data intact
```

## Implementation Details

### Command-Line Entry Point

The CLI is invoked as `python -m src.cli <command> [args]`. Use Python's `argparse` module (no external CLI framework needed). The module-level `main()` function parses the command and dispatches to the appropriate handler.

**Subcommands and their arguments:**

1. **`extract-document`**
   - `file_path` (positional): Path to the PDF or DOCX file
   - `deal_dir` (positional): Path to the deal directory
   - `--resolve` (optional): One of `"replace"`, `"version"`. Omit for initial extraction.

2. **`extract-batch`**
   - `folder_path` (positional): Folder containing documents to process
   - `deal_dir` (positional): Path to the deal directory (created if needed)
   - `--deal-name` (required): Human-readable deal name for metadata

3. **`validate-graph`**
   - `deal_dir` (positional): Path to deal directory containing `deal-graph.json`

4. **`show-graph-summary`**
   - `deal_dir` (positional): Path to deal directory

### Function Signatures

```python
# src/cli.py

def extract_document(file_path: str, deal_dir: str, resolve: str | None = None) -> str:
    """Extract a single document and merge into deal graph.

    If document already exists in graph, returns JSON conflict status.
    Claude Code handles user interaction and re-invokes with --resolve flag.
    If no graph exists, creates a new one.

    Returns: JSON string with extraction results or conflict status.
    """

def extract_batch(folder_path: str, deal_dir: str, deal_name: str) -> str:
    """Process all PDF/DOCX files in a folder. Creates new deal graph.

    Processes documents sequentially, building the graph incrementally.
    Runs relationship linking pass after all documents are extracted.

    Returns: JSON string with batch results summary.
    """

def validate_graph(deal_dir: str) -> str:
    """Validate deal-graph.json against schema and semantic rules.

    Returns: JSON string with validation results (errors, warnings).
    """

def show_graph_summary(deal_dir: str) -> str:
    """Return a JSON summary of the deal graph for display."""

def main():
    """Argparse-based entry point. Dispatches to command handlers."""
```

### extract_document Flow

1. Validate that `file_path` exists and has a supported extension (`.pdf`, `.docx`). If not, return error JSON and exit non-zero.
2. Compute `file_hash` (SHA-256) of the input file.
3. Attempt to load existing graph from `deal_dir/deal-graph.json` via graph manager. If no graph exists, initialize a new empty `DealGraph`.
4. **Conflict detection** (re-extraction check):
   - Search existing documents by `file_hash` match.
   - If no hash match, search by `source_file_path` (relative path within deal dir).
   - If no path match, run extraction first to get the document name and type, then search by `name + document_type`.
   - If a match is found and `resolve` is `None`, return conflict JSON:
     ```json
     {"status": "conflict", "reason": "document_exists", "document_id": "...", "match_method": "file_hash", "options": ["replace", "version", "cancel"]}
     ```
   - If `resolve="replace"`: proceed with replacement logic (preserve ID, annotations, `ai_original_values`; downgrade confidence on related edges to `"low"`; set `needs_review=true` on affected edges; log `"re-extract_replace"` event).
   - If `resolve="version"`: keep old document node, create new document node, add `supersedes` relationship edge, log `"re-extract_version"` event.
5. Run single document extraction via the pipeline (Section 06).
6. Merge results into graph via graph merger (Section 07).
7. Save graph via graph manager (atomic write with validation).
8. Return success JSON with document ID, extracted metadata summary, and any warnings.

### extract_batch Flow

1. Scan `folder_path` for all `.pdf` and `.docx` files (case-insensitive extension matching). Ignore all other file types.
2. Create the deal directory structure if it does not exist.
3. Initialize a new `DealGraph` with `DealMetadata`:
   - `name` = provided `deal_name`
   - `status` = `"active"`
   - `created_at` and `updated_at` = current ISO timestamp
4. Process each document sequentially:
   - Run single document extraction via the pipeline.
   - Merge result into the growing graph via graph merger.
   - Log an `ExtractionEvent` with action `"initial"`.
5. After all documents are extracted:
   - Run relationship linking pass across all documents (invoke the relationship linking pipeline from Section 06 for each document against the full Document Index).
   - Normalize parties across the full deal (merge duplicates found across documents using the normalizer from Section 03).
   - Flag uncertain matches (`confidence: "low"`) for user review.
6. Validate the final graph (schema + semantic validation via graph validator).
7. Write `deal-graph.json` atomically to `deal_dir`.
8. Return JSON summary:
   ```json
   {"status": "success", "deal_name": "...", "documents_processed": 5, "relationships_found": 12, "parties_found": 8, "warnings": [...]}
   ```

### validate_graph Flow

1. Load `deal-graph.json` from `deal_dir` via graph manager.
2. Run schema validation (Pydantic model parse).
3. Run semantic validation via graph validator (referential integrity, duplicate IDs, acyclic supersedes, directionality sanity, CP consistency).
4. Return JSON:
   ```json
   {"status": "valid", "errors": [], "warnings": ["Party 'ABC' has low confidence match"]}
   ```
   Or on failure:
   ```json
   {"status": "invalid", "errors": ["Relationship r-001 references nonexistent document doc-999"], "warnings": [...]}
   ```

### show_graph_summary Flow

1. Load `deal-graph.json` from `deal_dir`.
2. Compute summary statistics:
   - `deal_name`, `deal_status`
   - `document_count`, list of document names and types
   - `relationship_count`, breakdown by type
   - `party_count`, list of canonical party names
   - `defined_term_count`
   - `condition_count` with status breakdown (pending/satisfied/waived)
   - `needs_review_count` (entities flagged for review)
   - `last_updated` timestamp
3. Return JSON summary object.

### Exit Codes and Error Handling

- Exit code 0: Command completed successfully (even if validation found errors -- the command itself succeeded).
- Exit code 1: Command failed (file not found, unsupported file type, corrupted graph, API error after retries).
- All output goes to stdout as JSON. Logging (warnings, debug info) goes to stderr so it does not pollute the JSON output.
- Never call `input()` or read from stdin. The CLI is fully headless.

### JSON Output Convention

Every command returns a JSON object with at minimum a `"status"` field:
- `"success"` -- operation completed
- `"conflict"` -- re-extraction conflict detected, awaiting resolution
- `"error"` -- operation failed

Error responses include a `"message"` field with a human-readable description and optionally a `"details"` field.

### Module Invocation

The `if __name__ == "__main__"` block calls `main()`, which uses `argparse` to parse the command line and dispatch. The module is invoked as:

```bash
python -m src.cli extract-document /path/to/file.pdf /path/to/deal/dir
python -m src.cli extract-document /path/to/file.pdf /path/to/deal/dir --resolve replace
python -m src.cli extract-batch /path/to/folder /path/to/deal/dir --deal-name "123 Main St"
python -m src.cli validate-graph /path/to/deal/dir
python -m src.cli show-graph-summary /path/to/deal/dir
```

### Testing Strategy

Tests should mock the pipeline and graph operations heavily. The CLI layer is a thin orchestration layer -- the logic being tested is:
- Correct argument parsing and dispatch
- Conflict detection logic (hash, path, name+type matching)
- Re-extraction handling (replace vs. version mode side effects)
- Batch file discovery and sequential processing order
- JSON output format correctness
- Exit code correctness

Use `unittest.mock.patch` to mock:
- `pipeline.extract_document` (return fixture `DocumentExtractionResult`)
- `pipeline.link_relationships` (return fixture `RelationshipExtractionResult`)
- Graph manager load/save
- Graph merger merge
- Graph validator validate
- File I/O (use `tmp_path` pytest fixture for deal directories)

Use the fixtures from `tests/fixtures/` (defined in Section 01):
- `sample-graph.json` for pre-populated graph scenarios
- `empty-graph.json` for new deal scenarios
- `extraction-response-loan-agreement.json` and `extraction-response-guaranty.json` for mock API responses
