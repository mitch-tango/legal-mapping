# Section 04 — Document Readers (PDF Preflight & DOCX Extraction)

This section implements two document readers that prepare files for the Claude API extraction step. The PDF reader performs preflight checks (text layer detection, page counting) and prepares the file for submission as a document block. The DOCX reader extracts structured text from Word documents with Track Changes awareness. Both readers produce output suitable for the extraction prompts (section-05) and pipeline (section-06).

---

## Tests First

### PDF Preflight — File: `Mapping/tests/test_extraction.py` (or `test_document_readers.py`)

```python
# Test: PDF with text layer detected correctly (pdf_has_text_layer=true)
# Test: scanned PDF without text layer detected (pdf_has_text_layer=false)
# Test: scanned PDF sets default confidence to "low"
# Test: scanned PDF logs warning in extraction event
# Test: corrupted/unreadable PDF returns error JSON
# Test: PDF page count extracted correctly
```

### DOCX Processing — File: `Mapping/tests/test_extraction.py` (or `test_document_readers.py`)

```python
# Test: extract text from simple DOCX preserving heading hierarchy
# Test: extract text preserves numbered list items
# Test: extract text preserves table content
# Test: detect Track Changes in DOCX with <w:del> tags
# Test: accept all changes strips deleted text, keeps inserted text
# Test: DOCX without Track Changes processes normally
# Test: extraction log notes when Track Changes were detected
# Test: malformed DOCX returns error (not crash)
```

These tests should use the fixture files created in section-01:
- `tests/fixtures/sample.pdf` — small PDF with a text layer
- `tests/fixtures/sample-scanned.pdf` — small PDF without a text layer (image only)
- `tests/fixtures/sample.docx` — simple Word doc with headings and paragraphs
- `tests/fixtures/sample-track-changes.docx` — Word doc with Track Changes markup

---

## Implementation — PDF Reader

### File: `Mapping/src/extraction/pdf_reader.py`

The PDF reader uses `pypdf` for preflight checks only. The actual PDF content is sent to the Claude API as a document block (the Anthropic SDK handles PDF reading natively). The reader's job is to determine how the PDF should be handled.

```python
from dataclasses import dataclass

@dataclass
class PdfPreflightResult:
    """Result of PDF preflight analysis."""
    file_path: str
    page_count: int
    has_text_layer: bool
    file_hash: str                         # SHA-256 of file contents
    error: str | None = None

def preflight_pdf(file_path: str) -> PdfPreflightResult:
    """Run preflight checks on a PDF file.

    Checks:
    1. File is readable and valid PDF
    2. Count pages
    3. Detect text layer by attempting text extraction on first few pages
       - If extracted text is minimal/empty, classify as scanned (no text layer)
    4. Compute SHA-256 file hash for identity tracking

    Returns PdfPreflightResult with findings.
    On error (corrupt file, unreadable), returns result with error field set.
    """
```

**Text layer detection logic:** Use `pypdf.PdfReader` to open the file, iterate over the first 3-5 pages, and call `page.extract_text()`. If the total extracted text across sampled pages is less than ~50 characters, classify as scanned/no text layer.

**How the PDF gets to Claude:** The pipeline (section-06) reads the file bytes and sends them as a document block in the Claude API message. The preflight result informs the pipeline about confidence defaults and whether to log OCR warnings.

**File hash:** Compute SHA-256 of the entire file contents using `hashlib.sha256`. This hash is stored in the `Document.file_hash` field for rename detection — if a user renames a file, the CLI can match by hash to auto-heal the `source_file_path`.

---

## Implementation — DOCX Reader

### File: `Mapping/src/extraction/docx_reader.py`

The DOCX reader extracts text from Word documents using `python-docx`, with special handling for Track Changes and structural preservation.

```python
from dataclasses import dataclass

@dataclass
class DocxReadResult:
    """Result of reading a DOCX file."""
    text: str                              # Structured text ready for extraction
    file_hash: str                         # SHA-256 of file contents
    had_track_changes: bool                # Whether Track Changes were detected
    page_count_estimate: int | None = None # Rough estimate (DOCX doesn't have real pages)
    error: str | None = None

def read_docx(file_path: str) -> DocxReadResult:
    """Extract structured text from a Word document.

    Steps:
    1. Open with python-docx
    2. Detect and resolve Track Changes
    3. Extract text preserving structure
    4. Compute SHA-256 file hash

    Returns DocxReadResult with structured text or error.
    """
```

### Track Changes Handling

Word documents may contain Track Changes markup (insertions and deletions). If not resolved, Claude would read deleted clauses as active obligations — a critical error for legal analysis.

**Detection:** Check for `<w:del>` and `<w:ins>` XML tags in the document's underlying XML. Access via `python-docx`'s `element` property on paragraphs/runs.

**Resolution:** Accept all changes by default:
- Strip `<w:del>` elements (deleted text) — remove entirely
- Keep `<w:ins>` content (inserted text) — unwrap the `<w:ins>` tag but keep the text content
- Log a note in the extraction event that Track Changes were detected and resolved

This requires working at the XML level since `python-docx` does not natively expose Track Changes. Access paragraph XML via `paragraph._element` and process the lxml elements directly.

### Structural Preservation

Convert the document to a structured text format that maintains:

1. **Heading hierarchy** — Detect heading styles (`Heading 1`, `Heading 2`, etc.) and render with markdown-style markers:
   ```
   # ARTICLE I — DEFINITIONS
   ## Section 1.1 Defined Terms
   ### (a) "Borrower" means...
   ```

2. **Numbered/lettered list items** — Preserve list numbering from the document's numbering definitions. Render as indented text with the original numbering.

3. **Table content** — Convert tables to a readable text format. For each table, output rows with pipe-delimited columns or a simple text representation.

4. **Bold/italic markers** — Mark bold text with `**bold**` and italic with `*italic*`. This helps Claude identify defined terms (often bolded or quoted in legal documents).

5. **Paragraph separation** — Use blank lines between paragraphs to maintain readability.

**Why python-docx over PDF conversion:** Legal Word documents rely heavily on heading styles for section structure. `python-docx` preserves this semantic structure, while PDF conversion would flatten it into visual formatting. The heading hierarchy is critical for Claude to understand document organization and resolve section references.

### Error Handling

If `python-docx` cannot parse the file (corrupt, password-protected, not actually a DOCX), return a `DocxReadResult` with the `error` field set describing the issue. The pipeline will surface this as an error JSON suggesting the user convert to PDF.

---

## Dependencies

- **Requires:** section-01-foundation (project structure, python-docx and pypdf dependencies)
- **Blocks:** section-06-pipeline (pipeline calls these readers to prepare document content)
- **No dependency on section-02 or section-03** — the readers are independent of the data models. They produce raw text/preflight data, not Pydantic model instances.
