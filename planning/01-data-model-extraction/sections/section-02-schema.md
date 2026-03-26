# Section 02 — Schema (Pydantic Models for deal-graph.json)

This section defines all Pydantic models that represent the `deal-graph.json` file — the single source of truth for a deal's document relationships. The file is stored one per deal at `deals/{deal-name}/deal-graph.json`. Every model lives in `Mapping/src/models/schema.py`.

---

## Tests First

Create `Mapping/tests/test_schema.py` with the following test stubs:

### Top-Level Graph Structure

```python
# Test: DealGraph with all required fields validates successfully
# Test: DealGraph with missing required field (e.g., no documents) raises ValidationError
# Test: DealGraph with empty documents dict is valid (new deal, no docs yet)
# Test: schema_version field accepts valid SemVer strings
# Test: schema_version rejects invalid format (e.g., "1.0", "v1.0.0")
# Test: round-trip serialization — create DealGraph, serialize to JSON, deserialize, compare
```

### Deal Metadata

```python
# Test: DealMetadata with all fields validates
# Test: DealMetadata with only required fields (name, status, created_at, updated_at) validates
# Test: status field rejects values outside enum ("active", "closed", "terminated")
```

### Document Node

```python
# Test: Document with all fields validates
# Test: Document with execution_date_raw but null execution_date_iso is valid (unparseable date)
# Test: Document with both date fields null is valid (draft)
# Test: file_hash is required and must be non-empty string
# Test: status enum rejects invalid values
# Test: ai_original_values stores arbitrary dict when user overrides a field
# Test: PartyReference.party_id must be a non-empty string
```

### Key Provision

```python
# Test: KeyProvision with section_reference and summary validates
# Test: KeyProvision with null title and provision_type validates (optional fields)
```

### Party Normalization

```python
# Test: Party with canonical_name and empty aliases is valid
# Test: Party with multiple aliases preserves order
# Test: Party with raw_names stores all variations seen
# Test: Party.deal_roles accepts list of role strings
# Test: PartyReference links to party_id with role_in_document
```

### Relationship Edge

```python
# Test: Relationship with all required fields validates
# Test: Relationship with null source_reference is valid
# Test: Relationship with Evidence (quote + page) validates
# Test: Relationship with Evidence with null page validates
# Test: relationship_type rejects values not in 16-type taxonomy
# Test: needs_review defaults to false
# Test: ai_original_values stores overridden field values
```

### Defined Terms

```python
# Test: DefinedTerm with term + defining_document_id validates
# Test: Two DefinedTerms with same term but different defining_document_id are both valid
# Test: definition_snippet is optional (null allowed)
# Test: used_in_document_ids can be empty list
```

### Cross-References

```python
# Test: CrossReference with null target_section is valid (unresolved reference)
# Test: CrossReference with evidence validates
# Test: needs_review defaults to false
```

### Conditions Precedent

```python
# Test: ConditionPrecedent with null required_document_id is valid (standalone condition)
# Test: ConditionPrecedent with null enables_document_id is valid
# Test: status enum: "pending", "satisfied", "waived"
```

### User Annotations

```python
# Test: Annotation with note and no flag validates
# Test: Annotation with flag and no note validates
# Test: entity_type enum covers all entity types
# Test: created_at and updated_at are required
```

### Extraction Metadata

```python
# Test: ExtractionMetadata with temperature=0 validates
# Test: ExtractionMetadata with prompt_version hash validates
# Test: ExtractionEvent action enum covers all three actions
```

---

## Implementation — File: `Mapping/src/models/schema.py`

This file contains all Pydantic v2 models for the deal graph. The top-level model is `DealGraph`, which composes all other models.

### Schema Version Constant

Define `SCHEMA_VERSION = "1.0.0"` as a module-level constant. This is SemVer:
- MAJOR bump: breaking structural changes
- MINOR bump: new optional fields or entity types
- PATCH bump: documentation or description changes

Use a regex validator on the `schema_version` field to enforce the pattern `^\d+\.\d+\.\d+$`.

### Model Definitions (Signatures and Field Types)

All models use `pydantic.BaseModel`. Use `Literal` types for enum fields. Use `str | None` for optional fields with `default=None`.

```python
class DealMetadata(BaseModel):
    name: str
    deal_type: str | None = None
    primary_parties: list[str] = []        # Party IDs
    closing_date: str | None = None        # ISO date
    status: Literal["active", "closed", "terminated"]
    notes: str | None = None
    created_at: str                        # ISO timestamp
    updated_at: str

class Evidence(BaseModel):
    quote: str | None = None
    page: int | None = None

class ExtractionMetadata(BaseModel):
    extracted_at: str                      # ISO timestamp
    model: str                             # e.g., "claude-sonnet-4-20250514"
    model_version: str
    temperature: float                     # 0 for extraction
    prompt_version: str                    # Hash of prompt template
    processing_time_ms: int | None = None
    pdf_has_text_layer: bool | None = None

class ExtractionEvent(BaseModel):
    id: str
    document_id: str
    action: Literal["initial", "re-extract_replace", "re-extract_version"]
    timestamp: str
    model: str
    notes: str | None = None

class KeyProvision(BaseModel):
    section_reference: str
    title: str | None = None
    summary: str
    provision_type: str | None = None      # "covenant", "representation", "default", "closing_condition", etc.

class Party(BaseModel):
    id: str
    canonical_name: str
    aliases: list[str] = []
    raw_names: list[str] = []
    entity_type: str | None = None         # "LLC", "Corporation", "Individual", etc.
    jurisdiction: str | None = None
    deal_roles: list[str] = []
    confidence: Literal["high", "medium", "low"]

class PartyReference(BaseModel):
    party_id: str                          # Must be non-empty
    role_in_document: str

class Document(BaseModel):
    id: str
    name: str
    document_type: str
    parties: list[PartyReference] = []
    execution_date_raw: str | None = None
    execution_date_iso: str | None = None
    status: Literal["draft", "executed", "amended"]
    source_file_path: str
    file_hash: str                         # SHA-256, required non-empty
    key_provisions: list[KeyProvision] = []
    summary: str
    obligations: list[str] = []
    extraction: ExtractionMetadata
    ai_original_values: dict | None = None
    is_manual: bool = False

class Relationship(BaseModel):
    id: str
    source_document_id: str
    target_document_id: str
    relationship_type: str                 # Must be one of the 16-type taxonomy
    source_reference: str | None = None
    evidence: Evidence | None = None
    confidence: Literal["high", "medium", "low"]
    needs_review: bool = False
    is_manual: bool = False
    description: str
    ai_original_values: dict | None = None
    extraction: ExtractionMetadata | None = None

class DefinedTerm(BaseModel):
    id: str
    term: str
    defining_document_id: str
    section_reference: str | None = None
    definition_snippet: str | None = None
    used_in_document_ids: list[str] = []
    confidence: Literal["high", "medium", "low"]

class CrossReference(BaseModel):
    id: str
    source_document_id: str
    source_section: str
    target_document_id: str
    target_section: str | None = None
    reference_text: str
    evidence: Evidence | None = None
    confidence: Literal["high", "medium", "low"]
    needs_review: bool = False

class ConditionPrecedent(BaseModel):
    id: str
    description: str
    source_document_id: str
    source_section: str | None = None
    required_document_id: str | None = None
    enables_document_id: str | None = None
    status: Literal["pending", "satisfied", "waived"]
    confidence: Literal["high", "medium", "low"]

class Annotation(BaseModel):
    id: str
    entity_type: Literal["document", "relationship", "term", "cross_reference", "condition"]
    entity_id: str
    note: str | None = None
    flagged: bool = False
    created_at: str
    updated_at: str

class DealGraph(BaseModel):
    schema_version: str                    # SemVer, validated with regex
    deal: DealMetadata
    parties: dict[str, Party] = {}         # Keyed by party ID
    documents: dict[str, Document] = {}    # Keyed by document ID
    relationships: list[Relationship] = []
    defined_terms: list[DefinedTerm] = []
    cross_references: list[CrossReference] = []
    conditions_precedent: list[ConditionPrecedent] = []
    annotations: list[Annotation] = []
    extraction_log: list[ExtractionEvent] = []
```

### Key Design Decisions

- **Parties are top-level** in a dict keyed by ID. This is the canonical store for all party data across the deal. Documents reference parties by ID via `PartyReference`.
- **Documents are a dict keyed by ID** for fast lookup during relationship resolution, not a list.
- **Relationships are a flat list of edges**, not nested under documents. This enables easier graph traversal and independent editing.
- **Annotations use write-time overrides.** When a user overrides an AI-extracted field, the entity is updated directly and the original AI value is preserved in `ai_original_values`. The graph is always ready to consume as-is.
- **DefinedTerm uniqueness** is by the combination of `(term, defining_document_id)`. The same term text in different documents creates separate entries.
- **CP entities are canonical.** The `conditions_precedent` relationship type in the taxonomy is a derived view; the CP entity is the source of truth for status tracking.

### Relationship Type Validation

The `relationship_type` field on `Relationship` must be one of these 16 values: `controls`, `references`, `subordinates_to`, `defines_terms_for`, `triggers`, `conditions_precedent`, `incorporates`, `amends`, `assigns`, `guarantees`, `secures`, `supersedes`, `restricts`, `consents_to`, `indemnifies`, `restates`.

Define a module-level constant `RELATIONSHIP_TYPES` as a tuple or frozenset of these 16 strings. Use a Pydantic field validator on `Relationship.relationship_type` to reject values not in this set.

### file_hash Validation

The `Document.file_hash` field must be a non-empty string. Add a Pydantic field validator that raises `ValueError` if the string is empty.

### PartyReference Validation

`PartyReference.party_id` must be a non-empty string. Add a validator.

---

## Fixture Updates

After implementing the models, update these fixture files in `Mapping/tests/fixtures/`:

- **sample-graph.json** — A complete valid `DealGraph` with 3-4 documents, several relationships, defined terms, cross-references, and at least one condition precedent. Use realistic real estate deal data (e.g., Loan Agreement, Guaranty, Deed of Trust, Operating Agreement).
- **empty-graph.json** — A minimal valid `DealGraph` with deal metadata only and empty collections for all list/dict fields.

Serialize these from the Pydantic models to guarantee validity.

---

## Dependencies

- **Requires:** section-01-foundation (project structure, pyproject.toml with pydantic dependency)
- **Blocks:** section-03-extraction-models, section-05-prompts, section-07-graph-ops
