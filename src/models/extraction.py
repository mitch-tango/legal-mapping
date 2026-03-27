"""Pydantic models for Claude API extraction responses and the 16-type relationship taxonomy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, field_validator

from src.models.schema import RELATIONSHIP_TYPES, KeyProvision


# ── Extraction Result Models ─────────────────────────────────────────────


class ExtractedParty(BaseModel):
    """A party extracted from a single document."""
    name: str
    role: str
    aliases: list[str] = []
    entity_type: str | None = None
    jurisdiction: str | None = None


class ExtractedTerm(BaseModel):
    """A defined term extracted from a document."""
    term: str
    section_reference: str | None = None
    definition_snippet: str | None = None


class DocumentExtractionResult(BaseModel):
    """Result of extracting metadata from a single document."""
    document_type: str
    name: str
    parties: list[ExtractedParty]
    execution_date_raw: str | None = None
    execution_date_iso: str | None = None
    defined_terms: list[ExtractedTerm] = []
    key_provisions: list[KeyProvision] = []
    obligations: list[str] = []
    document_references: list[str] = []
    summary: str


class ExtractedRelationship(BaseModel):
    """A relationship extracted between two documents."""
    source_reference: str | None = None
    target_document_name: str
    relationship_type: str
    direction_test_result: str
    evidence_quote: str | None = None
    evidence_page: int | None = None
    confidence: Literal["high", "medium", "low"]
    description: str

    @field_validator("relationship_type")
    @classmethod
    def validate_relationship_type(cls, v: str) -> str:
        if v not in RELATIONSHIP_TYPES:
            raise ValueError(
                f"Invalid relationship_type '{v}'. Must be one of: {sorted(RELATIONSHIP_TYPES)}"
            )
        return v


class RelationshipExtractionResult(BaseModel):
    """Result of the relationship linking pass."""
    relationships: list[ExtractedRelationship]


# ── Relationship Taxonomy ────────────────────────────────────────────────


@dataclass(frozen=True)
class RelationshipTypeInfo:
    """Metadata for a single relationship type in the taxonomy."""
    type_key: str
    direction_semantics: str
    direction_test: str
    extraction_heuristics: list[str]


RELATIONSHIP_TAXONOMY: dict[str, RelationshipTypeInfo] = {
    "controls": RelationshipTypeInfo(
        type_key="controls",
        direction_semantics="Source governs target on an issue",
        direction_test="The [source] governs [target]",
        extraction_heuristics=["governed by", "in accordance with", "subject to the terms of"],
    ),
    "references": RelationshipTypeInfo(
        type_key="references",
        direction_semantics="Source cites target",
        direction_test="The [source] cites [target]",
        extraction_heuristics=["as set forth in", "described in", "referred to in"],
    ),
    "subordinates_to": RelationshipTypeInfo(
        type_key="subordinates_to",
        direction_semantics="Source is subordinate to target",
        direction_test="The [source] is subordinate to [target]",
        extraction_heuristics=["subordinate to", "junior to", "subject and subordinate"],
    ),
    "defines_terms_for": RelationshipTypeInfo(
        type_key="defines_terms_for",
        direction_semantics="Source defines terms used in target",
        direction_test="The [source] defines terms used in [target]",
        extraction_heuristics=["as defined in", "capitalized terms have the meanings"],
    ),
    "triggers": RelationshipTypeInfo(
        type_key="triggers",
        direction_semantics="Events in source activate obligations in target",
        direction_test="Events in [source] activate obligations in [target]",
        extraction_heuristics=["upon default", "in the event of", "if [condition] then"],
    ),
    "conditions_precedent": RelationshipTypeInfo(
        type_key="conditions_precedent",
        direction_semantics="Source must be satisfied before target is effective",
        direction_test="The [source] must be satisfied for [target]",
        extraction_heuristics=["as a condition to", "prior to closing", "shall have delivered"],
    ),
    "incorporates": RelationshipTypeInfo(
        type_key="incorporates",
        direction_semantics="Source pulls in provisions from target by reference",
        direction_test="The [source] incorporates provisions from [target]",
        extraction_heuristics=["incorporated by reference", "made a part hereof"],
    ),
    "amends": RelationshipTypeInfo(
        type_key="amends",
        direction_semantics="Source modifies specific provisions of target",
        direction_test="The [source] amends [target]",
        extraction_heuristics=["hereby amended", "is amended to read", "Amendment to"],
    ),
    "assigns": RelationshipTypeInfo(
        type_key="assigns",
        direction_semantics="Source transfers rights/obligations from target",
        direction_test="The [source] assigns rights from [target]",
        extraction_heuristics=["assigns all right", "assignment of", "Assignment"],
    ),
    "guarantees": RelationshipTypeInfo(
        type_key="guarantees",
        direction_semantics="Source guarantees obligations in target",
        direction_test="The [source] guarantees obligations in [target]",
        extraction_heuristics=["guarantees payment", "unconditionally guarantees", "Guaranty"],
    ),
    "secures": RelationshipTypeInfo(
        type_key="secures",
        direction_semantics="Source provides security/collateral for target",
        direction_test="The [source] secures [target]",
        extraction_heuristics=["as security for", "grants a security interest", "Deed of Trust"],
    ),
    "supersedes": RelationshipTypeInfo(
        type_key="supersedes",
        direction_semantics="Source entirely replaces target",
        direction_test="The [source] supersedes [target]",
        extraction_heuristics=["supersedes and replaces", "in lieu of", "this Agreement replaces"],
    ),
    "restricts": RelationshipTypeInfo(
        type_key="restricts",
        direction_semantics="Source restricts rights/use established in target",
        direction_test="The [source] restricts [target]",
        extraction_heuristics=["subject to the restrictions", "shall not", "limited by"],
    ),
    "consents_to": RelationshipTypeInfo(
        type_key="consents_to",
        direction_semantics="Source provides consent for action in target",
        direction_test="The [source] consents to [target]",
        extraction_heuristics=["hereby consents", "approval of", "Consent"],
    ),
    "indemnifies": RelationshipTypeInfo(
        type_key="indemnifies",
        direction_semantics="Source provides indemnification for claims related to target",
        direction_test="The [source] indemnifies against claims in [target]",
        extraction_heuristics=["shall indemnify", "hold harmless", "Indemnity"],
    ),
    "restates": RelationshipTypeInfo(
        type_key="restates",
        direction_semantics="Source restates target (amended and restated)",
        direction_test="The [source] restates [target]",
        extraction_heuristics=["Amended and Restated", "restates in its entirety"],
    ),
}

# Precedence rules for ambiguous relationship type resolution
PRECEDENCE_RULES: dict[str, str] = {
    "subject to": "subordinates_to",
    "incorporated by reference": "incorporates",
    "governed by": "controls",
}
