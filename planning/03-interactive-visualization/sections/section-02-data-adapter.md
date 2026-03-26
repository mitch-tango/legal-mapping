# Section 02: Data Adapter

## Overview

This section implements the `DataAdapter` class, which is the bridge between the embedded JSON deal data and the Cytoscape.js graph library. It transforms `DEAL_GRAPH` (document/relationship data) and `DEAL_ANALYSIS` (findings, execution sequence) into Cytoscape-compatible element format, and exposes query methods used by every other module in the application.

**What this section delivers:**
- `DataAdapter` class with all transformation and query methods
- Document type category mapping (grouping 21 types into 5-7 visual categories)
- Deterministic edge ID generation
- Cycle detection on relationship edges
- Orphaned finding pruning
- Sample data fixtures for testing

**File to modify:**
- `{deal_name}-visualization.html` -- all code goes inside the application `<script>` block, after the data parsing and before the `GraphRenderer` class

**Dependencies (must be implemented first):**
- **Section 01 (Foundation):** HTML skeleton with `<script type="application/json">` data islands for `deal-graph-data` and `deal-analysis-data`, plus the parsing code that produces `DEAL_GRAPH` and `DEAL_ANALYSIS` global constants

---

## Tests (Write First)

All tests are inline console assertions behind a `DEBUG` flag. Add these inside the application `<script>` block. They run on page load when `const DEBUG = true;` and are silenced for production with `const DEBUG = false;`.

The test runner pattern is:

```javascript
function assert(condition, message) {
    if (!condition) {
        console.error('ASSERTION FAILED: ' + message);
    } else {
        console.log('PASS: ' + message);
    }
}
```

### DataAdapter Tests

Write a function `function testDataAdapter()` that exercises the following assertions using a hardcoded inline fixture (do not depend on the embedded deal data for tests). Each bullet is a separate assertion call.

**Core transformation -- `getCytoscapeElements()`:**
- Returns an object with `nodes` array and `edges` array
- Each node has `data.id`, `data.label`, `data.docType`, `data.status` populated from `DEAL_GRAPH.documents`
- Each edge has a deterministic ID in the format `${source}::${relType}::${target}::${index}` where index disambiguates duplicate source/type/target triples
- Every `edge.data.source` and `edge.data.target` matches a valid document ID present in the nodes
- Node `classes` string includes the document type category (e.g., `category-financial`, `category-primary`)
- Edge `classes` string includes the relationship type and confidence level (e.g., `controls high`)

**Query methods:**
- `getDocumentDetails(docId)` returns the full document object for a valid ID
- `getDocumentDetails('nonexistent-id')` returns `null`
- `getRelationshipTypes()` returns a deduplicated array of relationship type strings present in the data
- `getDocumentTypes()` returns a deduplicated array of document type strings present in the data
- `getFindingsForEntity('document', docId)` returns only findings whose `affected_entities` include that document ID; returns empty array when no findings match
- `getFindingsSummary()` returns an object with keys `critical`, `error`, `warning`, `info` and integer values summing correctly
- `getExecutionSequence()` returns the ordered execution steps array from `DEAL_ANALYSIS`, or an empty array if analysis is null
- `getDefinedTermFlow(termId)` returns `{ definingDoc, usingDocs }` where `definingDoc` is a document ID string and `usingDocs` is an array of document ID strings

**Edge cases:**
- When `DEAL_ANALYSIS` is `null`, all analysis methods return empty/default values (`getFindingsForEntity` returns `[]`, `getFindingsSummary` returns all zeros, `getExecutionSequence` returns `[]`)
- When `documents` is an empty object, `getCytoscapeElements()` returns `{ nodes: [], edges: [] }`
- Orphaned findings (referencing document IDs not in `DEAL_GRAPH.documents`) are silently pruned -- they do not appear in `getFindingsForEntity` results or `getFindingsSummary` counts
- Cyclic dependency edges (detected via DFS) are marked with a `cycle` class in their `classes` string

Call `testDataAdapter()` at the end of the DEBUG block, guarded by `if (DEBUG)`.

---

## Fixtures

Create the following JSON fixture files in a `fixtures/` directory alongside the HTML file. These are also embedded inline (as JS object literals) inside the `testDataAdapter()` function for self-contained testing.

### fixture-small.json

5 documents, 8 relationships, 2 findings. Structure:

```
DEAL_GRAPH:
  deal: { name: "Test Deal", status: "active", ... }
  documents: {
    "doc-loan": { id: "doc-loan", name: "Loan Agreement", document_type: "loan_agreement", status: "executed", ... },
    "doc-guaranty": { id: "doc-guaranty", name: "Guaranty", document_type: "guaranty", status: "executed", ... },
    "doc-deed": { id: "doc-deed", name: "Deed of Trust", document_type: "deed_of_trust", status: "executed", ... },
    "doc-opco": { id: "doc-opco", name: "Operating Agreement", document_type: "operating_agreement", status: "draft", ... },
    "doc-estoppel": { id: "doc-estoppel", name: "Estoppel Certificate", document_type: "estoppel_certificate", status: "pending", ... }
  }
  relationships: [
    { source_document_id: "doc-guaranty", target_document_id: "doc-loan", relationship_type: "guarantees", confidence: "high", ... },
    { source_document_id: "doc-deed", target_document_id: "doc-loan", relationship_type: "secures", confidence: "high", ... },
    ... (8 total)
  ]
  defined_terms: [
    { id: "term-1", term: "Borrower", defining_document_id: "doc-loan", used_in_document_ids: ["doc-guaranty", "doc-deed"], ... }
  ]

DEAL_ANALYSIS:
  analyses: {
    "conflicts": {
      findings: [
        { severity: "WARNING", affected_entities: [{ entity_type: "document", entity_id: "doc-loan" }], ... },
        { severity: "ERROR", affected_entities: [{ entity_type: "document", entity_id: "doc-guaranty" }], ... }
      ]
    }
  }
```

### fixture-null-analysis.json

Same 5-document graph structure but `DEAL_ANALYSIS = null`. Used to verify graceful degradation of all analysis-dependent methods.

### fixture-orphaned-findings.json

5 documents, 8 relationships, 5 findings where 2 findings reference `entity_id` values ("doc-phantom", "doc-ghost") that do not exist in `DEAL_GRAPH.documents`. Those 2 findings must be pruned from all query results.

### fixture-cycles.json

5 documents with relationships that form a cycle: doc-A references doc-B, doc-B references doc-C, doc-C references doc-A. The adapter must detect these edges and add the `cycle` class.

### fixture-empty.json

`DEAL_GRAPH` with an empty `documents` dict and empty `relationships` array. `DEAL_ANALYSIS = null`.

---

## Implementation Details

### Document Type Category Mapping

The 21 document types from Split 01 are grouped into visual categories for graph coloring. Define a constant map:

```javascript
const DOC_TYPE_CATEGORIES = {
    // Primary deal documents
    'loan_agreement': 'category-primary',
    'purchase_agreement': 'category-primary',
    'credit_agreement': 'category-primary',
    'lease_agreement': 'category-primary',

    // Ancillary / support
    'guaranty': 'category-ancillary',
    'indemnity_agreement': 'category-ancillary',
    'estoppel_certificate': 'category-ancillary',
    'comfort_letter': 'category-ancillary',

    // Financial / security
    'promissory_note': 'category-financial',
    'deed_of_trust': 'category-financial',
    'security_agreement': 'category-financial',
    'assignment': 'category-financial',

    // Corporate / organizational
    'operating_agreement': 'category-corporate',
    'partnership_agreement': 'category-corporate',
    'articles_of_incorporation': 'category-corporate',
    'resolution': 'category-corporate',

    // Regulatory / compliance
    'environmental_report': 'category-regulatory',
    'title_commitment': 'category-regulatory',
    'survey': 'category-regulatory',

    // Closing documents
    'closing_statement': 'category-closing',
    'settlement_statement': 'category-closing',
};
// Fallback for unknown types
const DEFAULT_CATEGORY = 'category-other';
```

This mapping is used when building Cytoscape node classes. The `GraphRenderer` (Section 03) will assign colors based on these category classes.

### DataAdapter Class

```javascript
class DataAdapter {
    constructor(dealGraph, dealAnalysis) {
        /**
         * Store references to raw data.
         * Build internal lookup indexes:
         *   - this._docMap: Map of document ID -> document object (from dealGraph.documents dict)
         *   - this._relMap: Map of relationship ID -> relationship object
         *   - this._termMap: Map of defined term ID -> term object
         *   - this._findingsByEntity: Map of entity ID -> array of findings (pruned of orphans)
         *   - this._cycleEdges: Set of edge IDs that participate in cycles
         *
         * Call this._detectCycles() during construction.
         * Call this._indexFindings() during construction (handles pruning).
         */
    }
}
```

### `getCytoscapeElements()`

Transforms documents into Cytoscape nodes and relationships into Cytoscape edges.

**Node format:**
```javascript
{
    data: {
        id: doc.id,
        label: doc.name,
        docType: doc.document_type,
        status: doc.status,
        relationshipCount: /* count of edges where this doc is source or target */
    },
    classes: DOC_TYPE_CATEGORIES[doc.document_type] || DEFAULT_CATEGORY
}
```

**Edge format:**
```javascript
{
    data: {
        id: `${rel.source_document_id}::${rel.relationship_type}::${rel.target_document_id}::${index}`,
        source: rel.source_document_id,
        target: rel.target_document_id,
        relType: rel.relationship_type,
        confidence: rel.confidence,
        description: rel.description,
        evidence: rel.evidence
    },
    classes: `${rel.relationship_type} ${rel.confidence}${this._cycleEdges.has(edgeId) ? ' cycle' : ''}`
}
```

The `index` in the edge ID is a counter that disambiguates when the same source/type/target triple appears more than once. Track counts with a temporary map keyed by `${source}::${type}::${target}`.

### Cycle Detection

Use a standard DFS-based cycle detection on the directed graph formed by relationships:

1. Build an adjacency list from all relationships (source -> [targets])
2. Track node states: unvisited, in-progress, visited
3. When a DFS traversal from node X encounters an in-progress node Y, all edges on the path from Y back to Y form a cycle
4. Store the IDs of edges that participate in cycles in `this._cycleEdges` (a `Set`)

The cycle detection runs once during construction. Edges in cycles get the `cycle` CSS class, which Section 03 renders as red dashed lines.

### Finding Indexing and Orphan Pruning

`_indexFindings()` iterates over all findings from all analysis types in `DEAL_ANALYSIS.analyses`. For each finding:

1. Iterate its `affected_entities` array
2. If `entity.entity_id` exists in `this._docMap` (for document entities) or in the relationship list (for relationship entities), index it
3. If the entity ID does not exist in the graph, skip it silently (orphan pruning)
4. Build `this._findingsByEntity` as a `Map<string, Finding[]>` keyed by entity ID

### Query Methods

All query methods are straightforward lookups against the indexes built in the constructor:

- **`getDocumentDetails(docId)`** -- Return `this._docMap.get(docId) || null`
- **`getFindingsForEntity(entityType, entityId)`** -- Return `this._findingsByEntity.get(entityId) || []`. The `entityType` parameter is available for future filtering but currently all entity types share the same index.
- **`getExecutionSequence()`** -- Navigate into `DEAL_ANALYSIS.analyses.execution_sequence` and return its findings sorted by `display_ordinal`. Return `[]` if `DEAL_ANALYSIS` is null or execution_sequence analysis does not exist.
- **`getRelationshipTypes()`** -- Deduplicate `relationship_type` across all relationships using a `Set`, return as array.
- **`getDocumentTypes()`** -- Deduplicate `document_type` across all documents using a `Set`, return as array.
- **`getDefinedTermFlow(termId)`** -- Look up term in `this._termMap`. Return `{ definingDoc: term.defining_document_id, usingDocs: term.used_in_document_ids }`. Return `null` if term not found.
- **`getFindingsSummary()`** -- Iterate all indexed (non-orphaned) findings, count by severity. Return `{ critical: N, error: N, warning: N, info: N }`.

### Data Schema Reference

The `DataAdapter` consumes two data structures embedded in the HTML. Here are the relevant shapes for implementer reference:

**DEAL_GRAPH structure (from Split 01 schema):**
```
{
  schema_version: "1.0.0",
  deal: { name, deal_type, status, ... },
  parties: { [partyId]: { id, canonical_name, aliases, ... } },
  documents: { [docId]: { id, name, document_type, status, parties, summary, key_provisions, obligations, ... } },
  relationships: [ { id, source_document_id, target_document_id, relationship_type, confidence, evidence, description, ... } ],
  defined_terms: [ { id, term, defining_document_id, used_in_document_ids, ... } ],
  cross_references: [ { id, source_document_id, target_document_id, ... } ],
  conditions_precedent: [ { id, description, status, ... } ]
}
```

**DEAL_ANALYSIS structure (from Split 02 schema), or null:**
```
{
  schema_version: "1.0.0",
  analyses: {
    [analysisType]: {
      analysis_type: "hierarchy" | "conflicts" | "defined_terms" | "conditions_precedent" | "execution_sequence",
      status: "completed" | "failed" | "partial",
      findings: [ { id, severity, category, title, description, affected_entities: [{ entity_type, entity_id, document_id }], confidence, ... } ],
      summary: { total_findings, by_severity: { CRITICAL: N, ... }, key_findings: [...] }
    }
  }
}
```

**Relationship type taxonomy (16 types):** `controls`, `references`, `subordinates_to`, `defines_terms_for`, `triggers`, `conditions_precedent`, `incorporates`, `amends`, `assigns`, `guarantees`, `secures`, `supersedes`, `restricts`, `consents_to`, `indemnifies`, `restates`.

---

## Acceptance Criteria

The DataAdapter is complete when:

1. All `testDataAdapter()` assertions pass in the console with `DEBUG = true`
2. `getCytoscapeElements()` produces valid Cytoscape format that Section 03 can consume directly via `cy.add()`
3. Null analysis, empty documents, orphaned findings, and cyclic edges are all handled without errors
4. The class exposes all seven query methods with correct return types
5. Fixtures are created and can be embedded as data islands for manual visual verification
