"""Main extraction orchestrator — single document extraction and relationship linking."""

from __future__ import annotations

import base64
import logging
import time
from pathlib import Path
from typing import Any, Callable

import anthropic
from pydantic import ValidationError

from src.extraction.docx_reader import read_docx
from src.extraction.normalizer import check_directionality
from src.extraction.pdf_reader import preflight_pdf
from src.extraction.prompts import (
    DEFAULT_MODEL,
    build_document_extraction_prompt,
    build_document_index,
    build_relationship_linking_prompt,
    compute_prompt_hash,
)
from src.models.extraction import (
    DocumentExtractionResult,
    ExtractedRelationship,
    RelationshipExtractionResult,
)
from src.models.schema import DealGraph, Document

logger = logging.getLogger(__name__)

# ── Legal abbreviation mappings ──────────────────────────────────────────

_ABBREVIATIONS: dict[str, str] = {
    "agmt": "agreement",
    "agrmt": "agreement",
    "gty": "guaranty",
    "mtg": "mortgage",
    "dot": "deed of trust",
    "asgn": "assignment",
    "amdt": "amendment",
    "subord": "subordination",
}

# ── Post-parse validation limits ─────────────────────────────────────────

_MAX_SUMMARY_LENGTH = 2000
_MAX_TERM_NAME_LENGTH = 200
_MAX_PARTIES = 50
_MAX_TERMS = 200
_MAX_PROVISIONS = 100


# ── API Retry ────────────────────────────────────────────────────────────


def call_api_with_retry(
    api_call: Callable[[], Any],
    max_retries: int = 3,
) -> Any:
    """Call the Claude API with exponential backoff retry.

    Retries on rate limit (429), server errors (500, 502, 503), and connection errors.
    Does NOT retry on auth errors (401), bad requests (400), or validation failures.
    """
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return api_call()
        except anthropic.RateLimitError as e:
            last_error = e
            if attempt < max_retries:
                wait = 2 ** attempt
                logger.warning(f"Rate limited, retrying in {wait}s (attempt {attempt + 1})")
                time.sleep(wait)
        except anthropic.APIStatusError as e:
            if e.status_code in (500, 502, 503):
                last_error = e
                if attempt < max_retries:
                    wait = 2 ** attempt
                    logger.warning(f"Server error {e.status_code}, retrying in {wait}s")
                    time.sleep(wait)
            else:
                return {"error": f"API error: {e.status_code} {e.message}"}
        except anthropic.APIConnectionError as e:
            last_error = e
            if attempt < max_retries:
                wait = 2 ** attempt
                logger.warning(f"Connection error, retrying in {wait}s")
                time.sleep(wait)
        except ValidationError as e:
            return {"error": f"Malformed API response: {e}"}

    return {"error": f"API call failed after {max_retries} retries: {last_error}"}


# ── Post-Parse Validation ────────────────────────────────────────────────


def validate_extraction_result(result: DocumentExtractionResult) -> list[str]:
    """Run sanity checks on extraction result as prompt injection defense.

    Returns list of warning strings (empty if clean).
    """
    warnings = []
    if len(result.summary) > _MAX_SUMMARY_LENGTH:
        warnings.append(f"Summary exceeds {_MAX_SUMMARY_LENGTH} chars")
    if len(result.parties) > _MAX_PARTIES:
        warnings.append(f"Unusually high party count: {len(result.parties)}")
    if len(result.defined_terms) > _MAX_TERMS:
        warnings.append(f"Unusually high term count: {len(result.defined_terms)}")
    if len(result.key_provisions) > _MAX_PROVISIONS:
        warnings.append(f"Unusually high provision count: {len(result.key_provisions)}")
    for term in result.defined_terms:
        if len(term.term) > _MAX_TERM_NAME_LENGTH:
            warnings.append(f"Term name exceeds {_MAX_TERM_NAME_LENGTH} chars: {term.term[:50]}...")
    return warnings


# ── Smart Matching ───────────────────────────────────────────────────────


def _normalize_doc_name(name: str) -> str:
    """Normalize a document name for matching (lowercase, expand abbreviations)."""
    result = name.strip().lower()
    for abbr, full in _ABBREVIATIONS.items():
        result = result.replace(abbr, full)
    return result


def score_document_match(
    reference: str,
    existing_documents: dict[str, Document],
) -> list[tuple[str, str, str]]:
    """Score a document reference against existing documents in the graph.

    Returns list of (document_id, document_name, confidence) sorted by confidence.
    """
    norm_ref = _normalize_doc_name(reference)
    matches: list[tuple[str, str, str, int]] = []

    for doc_id, doc in existing_documents.items():
        norm_name = _normalize_doc_name(doc.name)
        norm_type = doc.document_type.lower().replace("_", " ")

        # Exact name match
        if norm_ref == norm_name:
            matches.append((doc_id, doc.name, "high", 3))
            continue

        # Name contained in reference or vice versa
        if norm_name in norm_ref or norm_ref in norm_name:
            matches.append((doc_id, doc.name, "high", 2))
            continue

        # Document type appears in reference
        if norm_type in norm_ref:
            matches.append((doc_id, doc.name, "medium", 1))
            continue

        # Word overlap (fuzzy)
        ref_words = set(norm_ref.split())
        name_words = set(norm_name.split())
        overlap = ref_words & name_words
        # Need at least 2 significant words in common
        significant = {w for w in overlap if len(w) > 2}
        if len(significant) >= 2:
            matches.append((doc_id, doc.name, "low", 0))

    # Sort by score descending
    matches.sort(key=lambda m: m[3], reverse=True)
    return [(m[0], m[1], m[2]) for m in matches]


# ── Single Document Extraction ───────────────────────────────────────────


def extract_single_document(
    file_path: str,
    existing_graph: DealGraph | None = None,
    model: str = DEFAULT_MODEL,
    client: anthropic.Anthropic | None = None,
) -> DocumentExtractionResult | dict:
    """Extract metadata from a single document via Claude API.

    On error, returns a dict with error details (not an exception).
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix not in (".pdf", ".docx"):
        return {"error": f"Unsupported file type: {suffix}. Only .pdf and .docx are supported."}

    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    # Read document
    if suffix == ".pdf":
        preflight = preflight_pdf(file_path)
        if preflight.error:
            return {"error": f"PDF read error: {preflight.error}"}
        file_bytes = path.read_bytes()
        file_hash = preflight.file_hash
        has_text_layer = preflight.has_text_layer
    else:
        docx_result = read_docx(file_path)
        if docx_result.error:
            return {"error": f"DOCX read error: {docx_result.error}"}
        file_hash = docx_result.file_hash
        has_text_layer = None

    # Build prompt
    system_prompt = build_document_extraction_prompt()
    prompt_hash = compute_prompt_hash(system_prompt)

    # Build API message content
    if suffix == ".pdf":
        b64_data = base64.standard_b64encode(file_bytes).decode("ascii")
        user_content = [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": b64_data,
                },
            },
            {"type": "text", "text": "Extract structured metadata from this document."},
        ]
    else:
        user_content = (
            f"Extract structured metadata from this document:\n\n{docx_result.text}"
        )

    # Call API
    if client is None:
        client = anthropic.Anthropic()

    start_time = time.time()

    def api_call():
        return client.messages.parse(
            model=model,
            max_tokens=4096,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
            response_model=DocumentExtractionResult,
        )

    result = call_api_with_retry(api_call)

    elapsed_ms = int((time.time() - start_time) * 1000)

    if isinstance(result, dict):
        return result  # Error dict from retry logic

    # Post-parse validation
    warnings = validate_extraction_result(result)
    if warnings:
        logger.warning(f"Extraction warnings for {file_path}: {warnings}")

    # Store metadata on the result for the caller to use when building Document
    result._extraction_meta = {  # type: ignore[attr-defined]
        "model": model,
        "prompt_version": prompt_hash,
        "processing_time_ms": elapsed_ms,
        "file_hash": file_hash,
        "has_text_layer": has_text_layer,
    }

    return result


# ── Relationship Linking ─────────────────────────────────────────────────


def extract_relationships(
    file_path: str,
    document_content: str | bytes,
    existing_graph: DealGraph,
    model: str = DEFAULT_MODEL,
    client: anthropic.Anthropic | None = None,
) -> RelationshipExtractionResult | dict:
    """Identify relationships between a new document and existing documents.

    On error, returns a dict with error details.
    """
    if not existing_graph.documents:
        return RelationshipExtractionResult(relationships=[])

    # Build prompt
    doc_index = build_document_index(existing_graph)
    system_prompt = build_relationship_linking_prompt(doc_index)

    if isinstance(document_content, bytes):
        b64_data = base64.standard_b64encode(document_content).decode("ascii")
        user_content = [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": b64_data,
                },
            },
            {"type": "text", "text": "Identify all relationships between this document and the existing documents listed in the Document Index."},
        ]
    else:
        user_content = (
            f"Identify all relationships between this document and the existing "
            f"documents listed in the Document Index:\n\n{document_content}"
        )

    if client is None:
        client = anthropic.Anthropic()

    def api_call():
        return client.messages.parse(
            model=model,
            max_tokens=4096,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
            response_model=RelationshipExtractionResult,
        )

    result = call_api_with_retry(api_call)

    if isinstance(result, dict):
        return result

    # Post-process: check directionality warnings
    for rel in result.relationships:
        # Try to find the target document to get its type for directionality check
        matches = score_document_match(rel.target_document_name, existing_graph.documents)
        if matches:
            target_doc = existing_graph.documents.get(matches[0][0])
            if target_doc:
                # We'd need the source doc type too; log if known inversion
                pass  # Full directionality check happens during merge

    return result
