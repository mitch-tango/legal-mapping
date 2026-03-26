# Section 01 — Foundation (Project Setup)

This section covers the initial project scaffolding: directory structure, dependency configuration, package init files, test fixture placeholders, environment configuration, and deal directory scaffolding. Everything here must be in place before any other section can be implemented.

---

## Tests First

These tests validate that the project structure exists and dependencies are importable. Create the test file at `Mapping/tests/test_foundation.py`.

```python
# Test: src/ package is importable
# Test: src.models package is importable
# Test: src.extraction package is importable
# Test: src.graph package is importable
# Test: tests/fixtures/ directory exists
# Test: pyproject.toml declares all four core dependencies (anthropic, pydantic, python-docx, pypdf)
# Test: pytest is available as test runner
```

### Fixture Files Needed

These fixture files are placeholders created in this section but populated with real content in later sections (02, 03, 06). Create empty or minimal-valid files now so that later tests can import them without path errors.

```
Mapping/tests/fixtures/
├── sample-graph.json          # Complete valid DealGraph with 3-4 documents, relationships, terms
├── empty-graph.json           # Minimal valid DealGraph (deal metadata only, empty collections)
├── extraction-response-loan-agreement.json  # Mock Claude API response for a loan agreement
├── extraction-response-guaranty.json        # Mock Claude API response for a guaranty
├── relationship-response.json               # Mock Claude API response for relationship linking
├── sample.pdf                 # Small test PDF with text layer
├── sample-scanned.pdf         # Small test PDF without text layer (image only)
├── sample.docx                # Simple Word doc with headings and paragraphs
└── sample-track-changes.docx  # Word doc with Track Changes markup
```

For JSON fixtures, create minimal placeholder files (e.g., `{}` or `{"schema_version": "1.0.0"}`) now. They will be replaced with full content when section-02-schema defines the actual models. For binary fixtures (PDF, DOCX), create them manually or with small helper scripts — they cannot be generated as text.

---

## Directory Structure

Create the following directory tree under the `Mapping/` project root:

```
Mapping/
├── src/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schema.py              # Pydantic models for deal-graph.json (section-02)
│   │   └── extraction.py          # Pydantic models for extraction results (section-03)
│   ├── extraction/
│   │   ├── __init__.py
│   │   ├── pipeline.py            # Main extraction orchestrator (section-06)
│   │   ├── pdf_reader.py          # PDF handling (section-04)
│   │   ├── docx_reader.py         # Word document text extraction (section-04)
│   │   ├── prompts.py             # Extraction prompt templates (section-05)
│   │   └── normalizer.py          # Party name normalization, term dedup (section-03)
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── manager.py             # Graph CRUD operations (section-07)
│   │   ├── merger.py              # Merge extraction results into graph (section-07)
│   │   └── validator.py           # Schema + semantic validation (section-07)
│   └── cli.py                     # CLI entry points (section-08)
├── deals/                          # Deal data (one subfolder per deal)
│   └── .gitkeep
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # Shared pytest fixtures
│   ├── fixtures/                  # Sample documents and expected outputs
│   ├── test_foundation.py         # This section's tests
│   ├── test_schema.py             # (section-02)
│   ├── test_extraction.py         # (section-03, 06)
│   ├── test_graph_manager.py      # (section-07)
│   └── test_merger.py             # (section-07)
├── pyproject.toml
└── .env.template                  # Template for API key configuration
```

Every `__init__.py` file should be empty initially. The actual module files (schema.py, pipeline.py, etc.) should be created as empty files or with a single docstring describing their purpose — they will be populated by their respective sections.

---

## pyproject.toml

Create `Mapping/pyproject.toml` with the following configuration:

```toml
[project]
name = "legal-mapping"
version = "0.1.0"
description = "Legal document dependency graph tool"
requires-python = ">=3.11"
dependencies = [
    "anthropic",
    "pydantic>=2.0",
    "python-docx",
    "pypdf",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-asyncio",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

The four core dependencies serve these purposes:
- **anthropic** — Claude API client for extraction calls
- **pydantic** (v2+) — Data models and structured output integration with Claude's `messages.parse()`
- **python-docx** — Word document text extraction with Track Changes awareness
- **pypdf** — PDF preflight checks (text layer detection, page counting) before sending to Claude API

No database, no web framework, no heavy NLP libraries. The Anthropic SDK handles PDF reading natively via document blocks.

---

## Environment Configuration

Create `Mapping/.env.template`:

```
# Copy this file to .env and fill in your API key
# .env is excluded from version control
ANTHROPIC_API_KEY=your-key-here
```

Ensure `.env` is in `.gitignore` (or equivalent exclusion). API keys are loaded from the local `.env` file at runtime. All processing is local plus Anthropic API — no third-party services.

---

## conftest.py

Create `Mapping/tests/conftest.py` with shared fixtures:

```python
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"

@pytest.fixture
def fixtures_dir():
    """Path to the test fixtures directory."""
    return FIXTURES_DIR
```

Additional fixtures will be added by later sections as models are defined.

---

## Dependencies on Other Sections

None. This is the foundation section with no dependencies.

## Blocks

All other sections depend on this one. The directory structure, package layout, and dependency configuration must be complete before any implementation work begins.
