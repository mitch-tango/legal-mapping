"""Schema and semantic validation for deal-graph.json."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import ValidationError

from src.extraction.normalizer import COMMON_INVERSIONS
from src.models.schema import DealGraph


@dataclass
class ValidationResult:
    """Result of graph validation."""
    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.is_valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


def validate_schema(graph: DealGraph) -> ValidationResult:
    """Validate graph against Pydantic schema via round-trip serialization."""
    result = ValidationResult()
    try:
        json_str = graph.model_dump_json()
        DealGraph.model_validate_json(json_str)
    except ValidationError as e:
        for err in e.errors():
            result.add_error(f"Schema: {err['loc']} — {err['msg']}")
    except Exception as e:
        result.add_error(f"Schema validation error: {e}")
    return result


def validate_semantics(graph: DealGraph) -> ValidationResult:
    """Run semantic validation checks on the graph."""
    result = ValidationResult()
    doc_ids = set(graph.documents.keys())
    party_ids = set(graph.parties.keys())

    # ── Collect all entity IDs for duplicate detection ──
    all_ids: dict[str, list[str]] = {}
    for doc_id in graph.documents:
        all_ids.setdefault(doc_id, []).append("document")
    for party_id in graph.parties:
        all_ids.setdefault(party_id, []).append("party")
    for rel in graph.relationships:
        all_ids.setdefault(rel.id, []).append("relationship")
    for term in graph.defined_terms:
        all_ids.setdefault(term.id, []).append("defined_term")
    for xref in graph.cross_references:
        all_ids.setdefault(xref.id, []).append("cross_reference")
    for cp in graph.conditions_precedent:
        all_ids.setdefault(cp.id, []).append("condition_precedent")
    for ann in graph.annotations:
        all_ids.setdefault(ann.id, []).append("annotation")
    for ev in graph.extraction_log:
        all_ids.setdefault(ev.id, []).append("extraction_event")

    # Duplicate ID check
    for eid, types in all_ids.items():
        if len(types) > 1:
            result.add_error(f"Duplicate ID '{eid}' found in: {', '.join(types)}")

    # ── Relationship referential integrity ──
    for rel in graph.relationships:
        if rel.source_document_id not in doc_ids:
            result.add_error(
                f"Relationship '{rel.id}': source_document_id '{rel.source_document_id}' not found"
            )
        if rel.target_document_id not in doc_ids:
            result.add_error(
                f"Relationship '{rel.id}': target_document_id '{rel.target_document_id}' not found"
            )

    # ── Party reference integrity ──
    for doc_id, doc in graph.documents.items():
        for pref in doc.parties:
            if pref.party_id not in party_ids:
                result.add_error(
                    f"Document '{doc_id}': party_id '{pref.party_id}' not found in parties"
                )

    # ── Defined term references ──
    for term in graph.defined_terms:
        if term.defining_document_id not in doc_ids:
            result.add_error(
                f"DefinedTerm '{term.id}': defining_document_id '{term.defining_document_id}' not found"
            )
        for used_id in term.used_in_document_ids:
            if used_id not in doc_ids:
                result.add_error(
                    f"DefinedTerm '{term.id}': used_in_document_ids contains '{used_id}' not found"
                )

    # ── Cross-reference integrity ──
    for xref in graph.cross_references:
        if xref.source_document_id not in doc_ids:
            result.add_error(
                f"CrossReference '{xref.id}': source_document_id '{xref.source_document_id}' not found"
            )
        if xref.target_document_id not in doc_ids:
            result.add_error(
                f"CrossReference '{xref.id}': target_document_id '{xref.target_document_id}' not found"
            )

    # ── Condition precedent references ──
    for cp in graph.conditions_precedent:
        if cp.source_document_id not in doc_ids:
            result.add_error(
                f"ConditionPrecedent '{cp.id}': source_document_id '{cp.source_document_id}' not found"
            )
        if cp.required_document_id and cp.required_document_id not in doc_ids:
            result.add_error(
                f"ConditionPrecedent '{cp.id}': required_document_id '{cp.required_document_id}' not found"
            )
        if cp.enables_document_id and cp.enables_document_id not in doc_ids:
            result.add_error(
                f"ConditionPrecedent '{cp.id}': enables_document_id '{cp.enables_document_id}' not found"
            )

    # ── Annotation entity references ──
    entity_id_sets = {
        "document": doc_ids,
        "relationship": {r.id for r in graph.relationships},
        "term": {t.id for t in graph.defined_terms},
        "cross_reference": {x.id for x in graph.cross_references},
        "condition": {c.id for c in graph.conditions_precedent},
    }
    for ann in graph.annotations:
        valid_ids = entity_id_sets.get(ann.entity_type, set())
        if ann.entity_id not in valid_ids:
            result.add_warning(
                f"Annotation '{ann.id}': entity_id '{ann.entity_id}' "
                f"not found in {ann.entity_type} entities"
            )

    # ── Extraction log references ──
    for ev in graph.extraction_log:
        if ev.document_id not in doc_ids:
            result.add_warning(
                f"ExtractionEvent '{ev.id}': document_id '{ev.document_id}' not found"
            )

    # ── Supersedes cycle detection ──
    supersedes_edges: dict[str, str] = {}
    for rel in graph.relationships:
        if rel.relationship_type == "supersedes":
            supersedes_edges[rel.source_document_id] = rel.target_document_id

    for start in supersedes_edges:
        visited = set()
        current = start
        while current in supersedes_edges:
            if current in visited:
                result.add_error(
                    f"Supersedes cycle detected involving document '{current}'"
                )
                break
            visited.add(current)
            current = supersedes_edges[current]

    # ── Relationship directionality ──
    for rel in graph.relationships:
        source_doc = graph.documents.get(rel.source_document_id)
        target_doc = graph.documents.get(rel.target_document_id)
        if source_doc and target_doc:
            key = (rel.relationship_type, source_doc.document_type, target_doc.document_type)
            if key in COMMON_INVERSIONS:
                result.add_warning(
                    f"Relationship '{rel.id}': possible direction inversion — "
                    f"'{source_doc.document_type}' {rel.relationship_type} "
                    f"'{target_doc.document_type}' is a known wrong pattern"
                )

    return result


def validate_full(graph: DealGraph) -> ValidationResult:
    """Run both schema and semantic validation."""
    schema_result = validate_schema(graph)
    semantic_result = validate_semantics(graph)

    combined = ValidationResult()
    combined.errors = schema_result.errors + semantic_result.errors
    combined.warnings = schema_result.warnings + semantic_result.warnings
    combined.is_valid = schema_result.is_valid and semantic_result.is_valid
    return combined
