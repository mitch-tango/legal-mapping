"""Merge extraction results into an existing deal graph."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from src.extraction.normalizer import match_party, normalize_party_name
from src.extraction.pipeline import score_document_match
from src.models.extraction import DocumentExtractionResult, RelationshipExtractionResult
from src.models.schema import (
    DefinedTerm,
    Document,
    Evidence,
    ExtractionEvent,
    ExtractionMetadata,
    DealGraph,
    Party,
    PartyReference,
    Relationship,
)


def _gen_id(prefix: str) -> str:
    """Generate a UUID-based ID with a prefix."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def merge_document_extraction(
    graph: DealGraph,
    extraction: DocumentExtractionResult,
    file_path: str,
    file_hash: str,
    extraction_metadata: ExtractionMetadata,
) -> tuple[DealGraph, str]:
    """Merge a document extraction result into the deal graph.

    Returns (updated_graph, new_document_id).
    Does not write to disk — caller handles I/O.
    """
    doc_id = _gen_id("doc")

    # ── Match and merge parties ──
    party_refs: list[PartyReference] = []
    for ext_party in extraction.parties:
        matched_id, confidence = match_party(ext_party.name, graph.parties)

        if matched_id:
            # Merge into existing party
            existing = graph.parties[matched_id]
            # Add new aliases
            for alias in ext_party.aliases:
                if alias not in existing.aliases:
                    existing.aliases.append(alias)
            # Add raw name
            if ext_party.name not in existing.raw_names:
                existing.raw_names.append(ext_party.name)
            # Add role if not already present
            if ext_party.role not in existing.deal_roles:
                existing.deal_roles.append(ext_party.role)
            party_id = matched_id
        else:
            # Create new party
            party_id = _gen_id("party")
            graph.parties[party_id] = Party(
                id=party_id,
                canonical_name=ext_party.name,
                aliases=ext_party.aliases[:],
                raw_names=[ext_party.name],
                entity_type=ext_party.entity_type,
                jurisdiction=ext_party.jurisdiction,
                deal_roles=[ext_party.role],
                confidence="medium",
            )

        party_refs.append(PartyReference(
            party_id=party_id,
            role_in_document=ext_party.role,
        ))

    # ── Create document ──
    doc = Document(
        id=doc_id,
        name=extraction.name,
        document_type=extraction.document_type,
        parties=party_refs,
        execution_date_raw=extraction.execution_date_raw,
        execution_date_iso=extraction.execution_date_iso,
        status="executed" if extraction.execution_date_iso else "draft",
        source_file_path=file_path,
        file_hash=file_hash,
        key_provisions=extraction.key_provisions[:],
        summary=extraction.summary,
        obligations=extraction.obligations[:],
        extraction=extraction_metadata,
    )
    graph.documents[doc_id] = doc

    # ── Merge defined terms ──
    for ext_term in extraction.defined_terms:
        # Check for existing term with same (term, defining_document_id)
        existing_term = None
        for t in graph.defined_terms:
            if t.term == ext_term.term and t.defining_document_id == doc_id:
                existing_term = t
                break

        if existing_term:
            existing_term.section_reference = ext_term.section_reference
            existing_term.definition_snippet = ext_term.definition_snippet
        else:
            term = DefinedTerm(
                id=_gen_id("term"),
                term=ext_term.term,
                defining_document_id=doc_id,
                section_reference=ext_term.section_reference,
                definition_snippet=ext_term.definition_snippet,
                used_in_document_ids=[],
                confidence="medium",
            )
            graph.defined_terms.append(term)

    # Update used_in_document_ids for terms defined elsewhere but referenced here
    for term in graph.defined_terms:
        if term.defining_document_id != doc_id:
            for ext_term in extraction.defined_terms:
                if term.term == ext_term.term and doc_id not in term.used_in_document_ids:
                    term.used_in_document_ids.append(doc_id)

    # ── Add extraction event ──
    graph.extraction_log.append(ExtractionEvent(
        id=_gen_id("ev"),
        document_id=doc_id,
        action="initial",
        timestamp=datetime.now(timezone.utc).isoformat(),
        model=extraction_metadata.model,
    ))

    # ── Update timestamp ──
    graph.deal.updated_at = datetime.now(timezone.utc).isoformat()

    return graph, doc_id


def merge_relationships(
    graph: DealGraph,
    relationships: RelationshipExtractionResult,
    source_document_id: str,
    document_matches: dict[str, str],
    extraction_metadata: ExtractionMetadata,
) -> DealGraph:
    """Merge extracted relationships into the deal graph.

    document_matches maps target_document_name -> document_id.
    Returns updated DealGraph.
    """
    existing_edges = {
        (r.source_document_id, r.target_document_id, r.relationship_type)
        for r in graph.relationships
    }

    for ext_rel in relationships.relationships:
        target_doc_id = document_matches.get(ext_rel.target_document_name)
        if not target_doc_id:
            # Try smart matching
            matches = score_document_match(ext_rel.target_document_name, graph.documents)
            if matches and matches[0][2] in ("high", "medium"):
                target_doc_id = matches[0][0]

        if not target_doc_id:
            continue  # Cannot resolve target, skip

        # Check for duplicate
        edge_key = (source_document_id, target_doc_id, ext_rel.relationship_type)
        if edge_key in existing_edges:
            continue

        evidence = None
        if ext_rel.evidence_quote:
            evidence = Evidence(
                quote=ext_rel.evidence_quote,
                page=ext_rel.evidence_page,
            )

        rel = Relationship(
            id=_gen_id("rel"),
            source_document_id=source_document_id,
            target_document_id=target_doc_id,
            relationship_type=ext_rel.relationship_type,
            source_reference=ext_rel.source_reference,
            evidence=evidence,
            confidence=ext_rel.confidence,
            description=ext_rel.description,
            extraction=extraction_metadata,
        )
        graph.relationships.append(rel)
        existing_edges.add(edge_key)

    return graph
