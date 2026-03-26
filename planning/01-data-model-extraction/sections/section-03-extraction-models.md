# Section 03 — Extraction Models (API Response Models & Taxonomy)

This section defines the Pydantic models used for Claude API extraction results, the 16-type relationship taxonomy as a structured constant, and the normalizer utilities for party name matching and directionality validation. These models are separate from the graph schema (section-02) because they represent transient extraction output that gets merged into the graph, not the persisted graph structure itself.

---

## Tests First

### Extraction Result Models — File: `Mapping/tests/test_extraction.py`

```python
# Test: DocumentExtractionResult with all required fields validates
# Test: DocumentExtractionResult with empty parties list is valid
# Test: ExtractedParty with name and role validates
# Test: ExtractedParty with aliases list preserves order
# Test: ExtractedTerm with term and section_ref validates
# Test: ExtractedTerm with null definition_snippet is valid
# Test: RelationshipExtractionResult with empty relationships list is valid
# Test: ExtractedRelationship with valid relationship_type validates
# Test: ExtractedRelationship with invalid relationship_type raises ValidationError
# Test: extraction result Pydantic model validates against expected schema
# Test: relationship result Pydantic model validates against expected schema
```

### Relationship Taxonomy — File: `Mapping/tests/test_extraction.py` (continued)

```python
# Test: All 16 relationship types are defined in the taxonomy constant
# Test: Each type has direction_semantics, direction_test, and extraction_heuristics
# Test: Direction test sentences follow "The [source] ... [target]" pattern
# Test: Precedence rules: "subject to" maps to subordinates_to, not references
# Test: Precedence rules: "incorporated by reference" maps to incorporates
# Test: Precedence rules: "governed by" maps to controls
```

### Normalizer — File: `Mapping/tests/test_extraction.py` (continued)

```python
# Test: normalize_party_name strips punctuation variations ("LLC" vs "L.L.C.")
# Test: normalize_party_name collapses whitespace
# Test: normalize_party_name casefolding for matching
# Test: party name matching returns high confidence for exact normalized match
# Test: party name matching returns low confidence for uncertain alias match
# Test: common inversion check catches "Note secures Mortgage" (wrong direction)
# Test: common inversion check accepts "Mortgage secures Note" (correct direction)
```

---

## Implementation — Extraction Models

### File: `Mapping/src/models/extraction.py`

These models represent what Claude returns from extraction API calls. They are used with `messages.parse()` for structured output.

```python
class ExtractedParty(BaseModel):
    """A party extracted from a single document."""
    name: str
    role: str                              # Role as stated in this document
    aliases: list[str] = []               # Other names used in the document
    entity_type: str | None = None         # "LLC", "Corporation", "Individual"
    jurisdiction: str | None = None        # "Delaware", "New York"

class ExtractedTerm(BaseModel):
    """A defined term extracted from a document."""
    term: str                              # "Capital Account", "Borrower"
    section_reference: str | None = None   # "Section 1.1"
    definition_snippet: str | None = None  # 1-3 sentence excerpt

class DocumentExtractionResult(BaseModel):
    """Result of extracting metadata from a single document."""
    document_type: str
    name: str
    parties: list[ExtractedParty]
    execution_date_raw: str | None = None
    execution_date_iso: str | None = None
    defined_terms: list[ExtractedTerm] = []
    key_provisions: list[KeyProvision] = []  # Reuses KeyProvision from schema
    obligations: list[str] = []
    document_references: list[str] = []    # Names of other docs mentioned
    summary: str

class ExtractedRelationship(BaseModel):
    """A relationship extracted between two documents."""
    source_reference: str | None = None    # "Section 4.2(b)" in source doc
    target_document_name: str              # Name of the referenced document
    relationship_type: str                 # Must be one of 16 taxonomy types
    direction_test_result: str             # Model's self-check using direction test sentence
    evidence_quote: str | None = None      # Verbatim supporting text
    evidence_page: int | None = None
    confidence: Literal["high", "medium", "low"]
    description: str

class RelationshipExtractionResult(BaseModel):
    """Result of the relationship linking pass."""
    relationships: list[ExtractedRelationship]
```

Add a validator on `ExtractedRelationship.relationship_type` that rejects values not in the 16-type taxonomy (import `RELATIONSHIP_TYPES` from `src.models.schema`).

---

## Implementation — Relationship Taxonomy

### File: `Mapping/src/models/extraction.py` (or a dedicated `taxonomy.py` if preferred)

Define the taxonomy as a module-level constant. Each entry includes the type key, direction semantics, a direction test sentence, and extraction heuristics.

The 16 types:

| # | Type | Direction Semantics | Direction Test | Extraction Heuristics |
|---|------|---------------------|----------------|----------------------|
| 1 | `controls` | Source governs target on an issue | "The [source] governs [target]" | "governed by", "in accordance with", "subject to the terms of" |
| 2 | `references` | Source cites target | "The [source] cites [target]" | document names, "as set forth in", "described in" |
| 3 | `subordinates_to` | Source is subordinate to target | "The [source] is subordinate to [target]" | "subordinate to", "junior to", "subject and subordinate" |
| 4 | `defines_terms_for` | Source defines terms used in target | "The [source] defines terms used in [target]" | Match defined terms across documents |
| 5 | `triggers` | Events in source activate obligations in target | "Events in [source] activate obligations in [target]" | "upon default", "in the event of", "if [condition] then" |
| 6 | `conditions_precedent` | Source must be satisfied before target is effective | "The [source] must be satisfied for [target]" | "as a condition to", "prior to closing", "shall have delivered" |
| 7 | `incorporates` | Source pulls in provisions from target by reference | "The [source] incorporates provisions from [target]" | "incorporated by reference", "made a part hereof" |
| 8 | `amends` | Source modifies specific provisions of target | "The [source] amends [target]" | "hereby amended", "is amended to read", "Amendment to" in title |
| 9 | `assigns` | Source transfers rights/obligations from target | "The [source] assigns rights from [target]" | "assigns all right", "assignment of", "Assignment" in title |
| 10 | `guarantees` | Source guarantees obligations in target | "The [source] guarantees obligations in [target]" | "guarantees payment", "unconditionally guarantees", "Guaranty" in title |
| 11 | `secures` | Source provides security/collateral for target | "The [source] secures [target]" | "as security for", "grants a security interest", "Deed of Trust" securing a "Note" |
| 12 | `supersedes` | Source entirely replaces target | "The [source] supersedes [target]" | "supersedes and replaces", "in lieu of", "this Agreement replaces" |
| 13 | `restricts` | Source restricts rights/use established in target | "The [source] restricts [target]" | "subject to the restrictions", "shall not", "limited by", easement language |
| 14 | `consents_to` | Source provides consent for action in target | "The [source] consents to [target]" | "hereby consents", "approval of", "Consent" in title |
| 15 | `indemnifies` | Source provides indemnification for claims related to target | "The [source] indemnifies against claims in [target]" | "shall indemnify", "hold harmless", "Indemnity" in title |
| 16 | `restates` | Source restates target (amended and restated) | "The [source] restates [target]" | "Amended and Restated" in title, "restates in its entirety" |

Store this as a dict or list of dataclass/namedtuple entries so that each field (direction_semantics, direction_test, extraction_heuristics) is individually accessible. The prompts module (section-05) will format this into prompt text.

**Precedence rules** (for when multiple types could apply):
- "subject to" maps to `subordinates_to`, not `references`
- "incorporated by reference" maps to `incorporates`, even if also "subject to"
- "governed by" maps to `controls` from the governing document, not `references`
- When in doubt, use the most specific type available

**Notes on usage:**
- An A&R document typically has both `restates` and `supersedes` edges to the original
- `references` is the catch-all — use a more specific type when possible
- The taxonomy is extensible: new types via schema minor version bump

---

## Implementation — Normalizer

### File: `Mapping/src/extraction/normalizer.py`

The normalizer handles two concerns: party name normalization and relationship directionality validation.

### Party Name Normalization

```python
def normalize_party_name(name: str) -> str:
    """Normalize a party name for matching purposes.

    Rules:
    - Strip punctuation variations (LLC vs L.L.C.)
    - Collapse whitespace
    - Casefold for matching
    - Strip common suffixes for comparison ("a Delaware limited liability company")
    """

def match_party(extracted_name: str, existing_parties: dict[str, Party]) -> tuple[str | None, str]:
    """Match an extracted party name against existing parties in the graph.

    Returns (party_id, confidence) where confidence is "high", "medium", or "low".
    Returns (None, "low") if no match found — caller should create a new party.
    """
```

### Directionality Validation

```python
# Common inversion patterns — known wrong directions for specific document type pairs
COMMON_INVERSIONS: dict[tuple[str, str, str], tuple[str, str]] = {
    # (relationship_type, source_doc_type, target_doc_type): (correct_source, correct_target)
    # Example: "Note secures Mortgage" is wrong; "Mortgage secures Note" is right
}

def check_directionality(relationship_type: str, source_doc_type: str, target_doc_type: str) -> bool:
    """Check if the directionality of a relationship is correct.

    Returns True if the direction is valid (or not in the known inversions list).
    Returns False if this is a known inversion pattern.
    """
```

The `COMMON_INVERSIONS` dict should be populated with patterns like:
- `("secures", "note", "mortgage")` -> known wrong (Mortgage secures Note, not the other way)
- `("guarantees", "loan_agreement", "guaranty")` -> known wrong (Guaranty guarantees Loan Agreement)

---

## Fixture Updates

After implementing the models, update these fixture files in `Mapping/tests/fixtures/`:

- **extraction-response-loan-agreement.json** — A mock `DocumentExtractionResult` serialized to JSON, representing a typical loan agreement extraction (parties: Borrower/Lender, defined terms, key provisions).
- **extraction-response-guaranty.json** — A mock `DocumentExtractionResult` for a guaranty document.
- **relationship-response.json** — A mock `RelationshipExtractionResult` with 3-4 relationships of different types.

---

## Dependencies

- **Requires:** section-01-foundation (project structure), section-02-schema (imports `KeyProvision`, `RELATIONSHIP_TYPES`, `Party`)
- **Blocks:** section-05-prompts, section-06-pipeline
