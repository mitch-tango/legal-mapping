# Section 07 — Graph Operations (Manager, Merger, Validator)

This section implements three modules that manage the `deal-graph.json` file: the graph manager (CRUD and atomic I/O), the graph merger (integrating extraction results into an existing graph), and the graph validator (schema and semantic validation). Together they ensure the graph file is always in a valid, consistent state.

---

## Tests First

### Graph Manager — File: `Mapping/tests/test_graph_manager.py`

```python
# Test: load_graph reads valid deal-graph.json and returns DealGraph
# Test: load_graph with nonexistent file returns None (or creates new)
# Test: load_graph with invalid JSON raises appropriate error
# Test: save_graph writes valid JSON that can be loaded back (round-trip)
# Test: save_graph uses atomic write (temp file + validate + rename)
# Test: save_graph validates schema before writing (rejects invalid graph)
# Test: create_deal creates new deal directory with empty graph
# Test: create_deal sets schema_version, deal metadata, timestamps
```

### Graph Merger — File: `Mapping/tests/test_merger.py`

```python
# Test: merge adds new document to empty graph
# Test: merge adds new document to graph with existing documents
# Test: merge matches existing party by canonical name (fuzzy)
# Test: merge adds new aliases to existing party
# Test: merge adds new raw_names to existing party
# Test: merge creates new party when no match found
# Test: merge handles defined term with same (term, defining_doc_id) — updates existing
# Test: merge handles defined term with same term but different defining_doc — creates new entry
# Test: merge adds document to used_in_document_ids for existing terms
# Test: merge does not duplicate relationships (same source+target+type)
# Test: merge never modifies annotations
# Test: merge writes atomically (temp file + validate + rename)
# Test: merge rolls back on validation failure (original file preserved)
```

### Graph Validator — File: `Mapping/tests/test_graph_manager.py` (or `test_validator.py`)

#### Schema Validation

```python
# Test: valid graph passes schema validation
# Test: graph with missing required field fails validation
# Test: graph with invalid enum value fails validation
# Test: validation runs on every graph write (test via merger)
```

#### Semantic Validation

```python
# Test: relationship referencing nonexistent document_id flagged as error
# Test: party_id in PartyReference referencing nonexistent party flagged as error
# Test: duplicate IDs across entities flagged as error
# Test: supersedes cycle (A supersedes B supersedes A) flagged as error
# Test: relationship directionality sanity check catches known inversions
# Test: CP entity and derived relationship edge are consistent
# Test: valid graph with all references resolved passes semantic validation
```

---

## Implementation — Graph Manager

### File: `Mapping/src/graph/manager.py`

The graph manager handles loading, saving, and creating deal graphs. It is the sole I/O gateway for `deal-graph.json`.

```python
def load_graph(deal_dir: str) -> DealGraph | None:
    """Load a deal graph from disk.

    Reads {deal_dir}/deal-graph.json, parses with Pydantic DealGraph model.
    Returns None if the file does not exist.
    Raises ValueError if the file exists but is invalid JSON or fails schema validation.
    """

def save_graph(graph: DealGraph, deal_dir: str) -> None:
    """Save a deal graph to disk with atomic write.

    Steps:
    1. Serialize DealGraph to JSON (with indentation for readability)
    2. Validate the serialized graph against schema (Pydantic round-trip)
    3. Write to a temporary file in the same directory
    4. Rename temp file to deal-graph.json (atomic on most filesystems)

    If validation fails, the temp file is deleted and the original is preserved.
    This guarantees the graph is never saved in an invalid state.
    """

def create_deal(deal_dir: str, deal_name: str, deal_type: str | None = None) -> DealGraph:
    """Create a new deal directory and empty graph.

    Creates:
    - {deal_dir}/ directory
    - {deal_dir}/documents/ subdirectory
    - {deal_dir}/deal-graph.json with empty collections

    Sets schema_version to current SCHEMA_VERSION constant.
    Sets created_at and updated_at to current ISO timestamp.
    Returns the new DealGraph instance.
    """
```

**Atomic write pattern:** Write to `deal-graph.tmp.json` first, validate the content by loading it back through Pydantic, then rename to `deal-graph.json`. On Windows, `os.replace()` handles the atomic rename. If any step fails, delete the temp file and raise an error — the original file is untouched.

---

## Implementation — Graph Merger

### File: `Mapping/src/graph/merger.py`

The merger takes extraction results and integrates them into an existing graph. It handles deduplication, party matching, and annotation preservation.

```python
def merge_document_extraction(
    graph: DealGraph,
    extraction: DocumentExtractionResult,
    file_path: str,
    file_hash: str,
    extraction_metadata: ExtractionMetadata,
) -> DealGraph:
    """Merge a document extraction result into the deal graph.

    Steps:
    1. Create Document node from extraction result
       - Generate UUID for document ID
       - Set source_file_path relative to deal folder
       - Set file_hash from preflight/reader result
       - Attach extraction metadata
    2. Match and merge parties:
       - For each extracted party, normalize name and match against existing parties
       - If match found: merge aliases, add new raw_names, update deal_roles
       - If no match: create new Party node with generated UUID
       - Create PartyReference linking document to party with role_in_document
    3. Merge defined terms:
       - Check for existing term with same (term, defining_document_id) pair
       - If found: update section_reference and definition_snippet
       - If same term but different defining document: create new DefinedTerm entry
       - Add the new document to used_in_document_ids where applicable
    4. Add extraction event to extraction_log
    5. Update deal.updated_at timestamp

    Returns updated DealGraph (does not write to disk — caller handles I/O).
    """

def merge_relationships(
    graph: DealGraph,
    relationships: RelationshipExtractionResult,
    source_document_id: str,
    document_matches: dict[str, str],  # target_doc_name -> document_id mapping
    extraction_metadata: ExtractionMetadata,
) -> DealGraph:
    """Merge extracted relationships into the deal graph.

    Steps:
    1. For each extracted relationship:
       a. Resolve target_document_name to a document_id using document_matches
       b. Check for duplicate (same source + target + type) — skip if exists
       c. Create Relationship edge with generated UUID
       d. Attach evidence, confidence, extraction metadata
    2. Attempt to resolve previously unresolved cross-references
       (a new document may be the target of an earlier unresolved reference)
    3. For conditions_precedent relationships, create corresponding CP entities

    Returns updated DealGraph.
    """

def merge_cross_references(graph: DealGraph, ...) -> DealGraph:
    """Merge extracted cross-references into the graph.

    Attempts to resolve target sections against existing documents.
    Unresolved references are added with target_section=None and needs_review=True.
    """
```

### Merge Rules Summary

| Entity Type | Match Key | If Match Found | If No Match |
|-------------|-----------|---------------|-------------|
| Document | file_hash, then source_file_path, then name+type | Update (see re-extraction in section-08) | Add new node |
| Party | Normalized canonical_name (fuzzy) | Merge aliases, raw_names, roles | Add new party |
| Defined Term | (term, defining_document_id) | Update section_ref, snippet | Add new entry |
| Relationship | (source_id, target_id, type) | Skip (no duplicate) | Add new edge |
| Cross-Reference | No dedup (each is unique by context) | N/A | Add new entry |
| Condition Precedent | No dedup (each is unique by description) | N/A | Add new entry |
| Annotation | Never touched | N/A | N/A |

**Critical rule:** Annotations are user-owned and never modified during merge. When re-extracting (handled in section-08), AI-extracted fields update but annotations persist.

---

## Implementation — Graph Validator

### File: `Mapping/src/graph/validator.py`

The validator runs schema validation (via Pydantic) and semantic validation (referential integrity, consistency checks). Schema validation runs on every write. Semantic validation can be triggered explicitly or as part of a full validation pass.

```python
@dataclass
class ValidationResult:
    """Result of graph validation."""
    is_valid: bool
    errors: list[str]                      # Hard failures
    warnings: list[str]                    # Soft issues (won't prevent save)

def validate_schema(graph: DealGraph) -> ValidationResult:
    """Validate graph against Pydantic schema.

    This is implicitly done by Pydantic during deserialization, but this function
    provides explicit validation with detailed error messages.
    Runs on every graph write via save_graph().
    """

def validate_semantics(graph: DealGraph) -> ValidationResult:
    """Run semantic validation checks on the graph.

    Checks:
    1. All *_document_id fields reference existing documents in graph.documents
    2. All party_id fields in PartyReferences reference existing parties in graph.parties
    3. No duplicate IDs across any entity type (documents, parties, relationships, terms, etc.)
    4. Relationship directionality sanity checks using known inversion patterns
       (imports COMMON_INVERSIONS from normalizer)
    5. Supersedes chains are acyclic (follow supersedes edges, detect cycles)
    6. CP entities and their derived relationship edges are consistent
       (if a CP links two documents, a corresponding conditions_precedent relationship should exist)
    7. All used_in_document_ids in DefinedTerms reference existing documents

    Returns ValidationResult with errors (hard failures) and warnings (soft issues).
    """

def validate_full(graph: DealGraph) -> ValidationResult:
    """Run both schema and semantic validation.

    Combines results from validate_schema and validate_semantics.
    """
```

### Supersedes Cycle Detection

Follow `supersedes` relationship edges and detect cycles using a simple DFS or visited-set approach. If document A supersedes B and B supersedes A (directly or transitively), flag as an error. This prevents infinite loops in version chains.

### Referential Integrity Checks

For every ID reference in the graph, verify the target exists:
- `Relationship.source_document_id` and `target_document_id` must be keys in `graph.documents`
- `PartyReference.party_id` must be a key in `graph.parties`
- `DefinedTerm.defining_document_id` must be a key in `graph.documents`
- `DefinedTerm.used_in_document_ids` entries must be keys in `graph.documents`
- `CrossReference.source_document_id` and `target_document_id` must be keys in `graph.documents`
- `ConditionPrecedent.source_document_id`, `required_document_id`, `enables_document_id` must be keys in `graph.documents` (when not None)
- `Annotation.entity_id` must reference an existing entity of the specified `entity_type`
- `ExtractionEvent.document_id` must be a key in `graph.documents`

### Duplicate ID Detection

Collect all IDs across all entity types. If any ID appears more than once (even across different entity types), flag as an error. UUIDs should be unique globally, but this check catches bugs in ID generation.

---

## Dependencies

- **Requires:** section-02-schema (all Pydantic models, RELATIONSHIP_TYPES, SCHEMA_VERSION), section-03-extraction-models (extraction result models, normalizer for party matching and directionality checks)
- **Blocks:** section-08-cli (CLI uses manager for I/O, merger for processing, validator for validation commands)
