"""Pydantic models for deal-graph.json — the deal document dependency graph."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator

SCHEMA_VERSION = "1.0.0"

RELATIONSHIP_TYPES = frozenset({
    "controls",
    "references",
    "subordinates_to",
    "defines_terms_for",
    "triggers",
    "conditions_precedent",
    "incorporates",
    "amends",
    "assigns",
    "guarantees",
    "secures",
    "supersedes",
    "restricts",
    "consents_to",
    "indemnifies",
    "restates",
})


class DealMetadata(BaseModel):
    name: str
    deal_type: str | None = None
    primary_parties: list[str] = []
    closing_date: str | None = None
    status: Literal["active", "closed", "terminated"]
    notes: str | None = None
    created_at: str
    updated_at: str


class Evidence(BaseModel):
    quote: str | None = None
    page: int | None = None


class ExtractionMetadata(BaseModel):
    extracted_at: str
    model: str
    model_version: str
    temperature: float
    prompt_version: str
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
    provision_type: str | None = None


class Party(BaseModel):
    id: str
    canonical_name: str
    aliases: list[str] = []
    raw_names: list[str] = []
    entity_type: str | None = None
    jurisdiction: str | None = None
    deal_roles: list[str] = []
    confidence: Literal["high", "medium", "low"]


class PartyReference(BaseModel):
    party_id: str
    role_in_document: str

    @field_validator("party_id")
    @classmethod
    def party_id_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("party_id must be a non-empty string")
        return v


class Document(BaseModel):
    id: str
    name: str
    document_type: str
    parties: list[PartyReference] = []
    execution_date_raw: str | None = None
    execution_date_iso: str | None = None
    status: Literal["draft", "executed", "amended"]
    source_file_path: str
    file_hash: str
    key_provisions: list[KeyProvision] = []
    summary: str
    obligations: list[str] = []
    extraction: ExtractionMetadata
    ai_original_values: dict | None = None
    is_manual: bool = False

    @field_validator("file_hash")
    @classmethod
    def file_hash_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("file_hash must be a non-empty string")
        return v


class Relationship(BaseModel):
    id: str
    source_document_id: str
    target_document_id: str
    relationship_type: str
    source_reference: str | None = None
    evidence: Evidence | None = None
    confidence: Literal["high", "medium", "low"]
    needs_review: bool = False
    is_manual: bool = False
    description: str
    ai_original_values: dict | None = None
    extraction: ExtractionMetadata | None = None

    @field_validator("relationship_type")
    @classmethod
    def validate_relationship_type(cls, v: str) -> str:
        if v not in RELATIONSHIP_TYPES:
            raise ValueError(
                f"Invalid relationship_type '{v}'. Must be one of: {sorted(RELATIONSHIP_TYPES)}"
            )
        return v


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
    schema_version: str
    deal: DealMetadata
    parties: dict[str, Party] = {}
    documents: dict[str, Document] = {}
    relationships: list[Relationship] = []
    defined_terms: list[DefinedTerm] = []
    cross_references: list[CrossReference] = []
    conditions_precedent: list[ConditionPrecedent] = []
    annotations: list[Annotation] = []
    extraction_log: list[ExtractionEvent] = []

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, v: str) -> str:
        import re
        if not re.match(r"^\d+\.\d+\.\d+$", v):
            raise ValueError(
                f"schema_version must be valid SemVer (e.g., '1.0.0'), got '{v}'"
            )
        return v
