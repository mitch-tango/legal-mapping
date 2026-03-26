# TDD Plan — Data Model & Document Extraction

Testing framework: **pytest** with fixtures. Mock API responses for deterministic tests. See `claude-research.md` "Testing Approach" for full setup.

---

## 3. JSON Schema Design

### 3.1 Top-Level Graph Structure

```python
# Test: DealGraph with all required fields validates successfully
# Test: DealGraph with missing required field (e.g., no documents) raises ValidationError
# Test: DealGraph with empty documents dict is valid (new deal, no docs yet)
# Test: schema_version field accepts valid SemVer strings
# Test: schema_version rejects invalid format (e.g., "1.0", "v1.0.0")
# Test: round-trip serialization — create DealGraph, serialize to JSON, deserialize, compare
```

### 3.2 Deal Metadata

```python
# Test: DealMetadata with all fields validates
# Test: DealMetadata with only required fields (name, status, created_at, updated_at) validates
# Test: status field rejects values outside enum ("active", "closed", "terminated")
```

### 3.3 Document Node

```python
# Test: Document with all fields validates
# Test: Document with execution_date_raw but null execution_date_iso is valid (unparseable date)
# Test: Document with both date fields null is valid (draft)
# Test: file_hash is required and must be non-empty string
# Test: status enum rejects invalid values
# Test: ai_original_values stores arbitrary dict when user overrides a field
# Test: PartyReference.party_id must be a non-empty string
```

### 3.4 Key Provision

```python
# Test: KeyProvision with section_reference and summary validates
# Test: KeyProvision with null title and provision_type validates (optional fields)
```

### 3.5 Party Normalization

```python
# Test: Party with canonical_name and empty aliases is valid
# Test: Party with multiple aliases preserves order
# Test: Party with raw_names stores all variations seen
# Test: Party.deal_roles accepts list of role strings
# Test: PartyReference links to party_id with role_in_document
```

### 3.6 Relationship Edge

```python
# Test: Relationship with all required fields validates
# Test: Relationship with null source_reference is valid
# Test: Relationship with Evidence (quote + page) validates
# Test: Relationship with Evidence with null page validates
# Test: relationship_type rejects values not in 16-type taxonomy
# Test: needs_review defaults to false
# Test: ai_original_values stores overridden field values
```

### 3.7 Defined Terms

```python
# Test: DefinedTerm with term + defining_document_id validates
# Test: Two DefinedTerms with same term but different defining_document_id are both valid (collision handling)
# Test: definition_snippet is optional (null allowed)
# Test: used_in_document_ids can be empty list
```

### 3.8 Cross-References

```python
# Test: CrossReference with null target_section is valid (unresolved reference)
# Test: CrossReference with evidence validates
# Test: needs_review defaults to false
```

### 3.9 Conditions Precedent

```python
# Test: ConditionPrecedent with null required_document_id is valid (standalone condition)
# Test: ConditionPrecedent with null enables_document_id is valid
# Test: status enum: "pending", "satisfied", "waived"
```

### 3.10 User Annotations

```python
# Test: Annotation with note and no flag validates
# Test: Annotation with flag and no note validates
# Test: entity_type enum covers all entity types
# Test: created_at and updated_at are required
```

### 3.11 Extraction Metadata

```python
# Test: ExtractionMetadata with temperature=0 validates
# Test: ExtractionMetadata with prompt_version hash validates
# Test: ExtractionEvent action enum covers all three actions
```

---

## 4. Relationship Taxonomy

```python
# Test: All 16 relationship types are defined in the taxonomy constant
# Test: Each type has direction_semantics, direction_test, and extraction_heuristics
# Test: Direction test sentences follow "The [source] ... [target]" pattern
# Test: Precedence rules: "subject to" maps to subordinates_to, not references
# Test: Precedence rules: "incorporated by reference" maps to incorporates
# Test: Precedence rules: "governed by" maps to controls
```

---

## 5. Extraction Pipeline

### 5.2 Single Document Extraction Flow

```python
# Test: extract_document with a valid PDF path returns DocumentExtractionResult
# Test: extract_document with a valid DOCX path returns DocumentExtractionResult
# Test: extract_document with unsupported file type returns error JSON
# Test: extract_document with nonexistent file returns error JSON
# Test: extraction result includes all required fields (type, parties, terms, summary)
# Test: extraction uses temperature=0 in API call
```

### 5.3 Extraction Prompts

```python
# Test: document extraction prompt includes untrusted content warning
# Test: relationship linking prompt includes untrusted content warning
# Test: relationship linking prompt includes Document Index (not summaries)
# Test: Document Index includes: name, type, aliases, parties, terms, section headings
# Test: extraction result Pydantic model validates against expected schema
# Test: relationship result Pydantic model validates against expected schema
```

### 5.4 Smart Matching

```python
# Test: exact type + name match returns high confidence
# Test: type match only returns medium confidence
# Test: fuzzy name match only returns low confidence
# Test: no match returns no relationship
# Test: matching is case-insensitive for document names
# Test: matching handles common abbreviations ("Agmt" = "Agreement")
```

### 5.5 Large Document Handling

```python
# Test: documents under 200K tokens processed in single call (no chunking)
# Test: pipeline logs a warning if document is very large but still processes it
```

### 5.6 Batch Extraction

```python
# Test: batch scans folder and finds all PDF and DOCX files
# Test: batch ignores non-PDF/DOCX files
# Test: batch creates new DealGraph with deal metadata
# Test: batch processes documents sequentially (order matters for party index)
# Test: batch runs relationship linking pass after all documents extracted
# Test: batch normalizes parties across full deal
# Test: batch writes valid deal-graph.json at end
```

### 5.7 Re-Extraction

```python
# Test: detects existing document by file_hash match
# Test: detects existing document by source_file_path fallback when hash doesn't match
# Test: detects existing document by name + type fallback
# Test: returns conflict JSON when document exists (not stdin prompt)
# Test: replace mode preserves document ID
# Test: replace mode preserves user annotations and ai_original_values
# Test: replace mode downgrades confidence to "low" on all related edges
# Test: replace mode sets needs_review=true on affected edges
# Test: version mode creates new document node with supersedes edge
# Test: version mode preserves old document node
```

### 5.8 Graph Merge

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

---

## 6. DOCX Processing

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

---

## 7. PDF Preflight

```python
# Test: PDF with text layer detected correctly (pdf_has_text_layer=true)
# Test: scanned PDF without text layer detected (pdf_has_text_layer=false)
# Test: scanned PDF sets default confidence to "low"
# Test: scanned PDF logs warning in extraction event
# Test: corrupted/unreadable PDF returns error JSON
# Test: PDF page count extracted correctly
```

---

## 8. CLI Interface

```python
# Test: extract-document returns JSON (not interactive prompt)
# Test: extract-document with --resolve replace processes replacement
# Test: extract-document with --resolve version creates version
# Test: extract-document without --resolve returns conflict JSON when doc exists
# Test: extract-batch returns JSON summary
# Test: validate-graph returns JSON with errors and warnings
# Test: show-graph-summary returns JSON summary
# Test: all CLI commands exit with code 0 on success, non-zero on failure
```

---

## 9. Validation

### Schema Validation

```python
# Test: valid graph passes schema validation
# Test: graph with missing required field fails validation
# Test: graph with invalid enum value fails validation
# Test: validation runs on every graph write (test via merger)
```

### Semantic Validation

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

## Fixtures Needed

```python
# fixtures/sample-graph.json — complete valid DealGraph with 3-4 documents, relationships, terms
# fixtures/empty-graph.json — minimal valid DealGraph (deal metadata only, empty collections)
# fixtures/extraction-response-loan-agreement.json — mock Claude API response for a loan agreement
# fixtures/extraction-response-guaranty.json — mock Claude API response for a guaranty
# fixtures/relationship-response.json — mock Claude API response for relationship linking
# fixtures/sample.pdf — small test PDF with text layer
# fixtures/sample-scanned.pdf — small test PDF without text layer (image only)
# fixtures/sample.docx — simple Word doc with headings and paragraphs
# fixtures/sample-track-changes.docx — Word doc with Track Changes markup
```
