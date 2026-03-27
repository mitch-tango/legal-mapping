"""Party name normalization, relationship directionality validation, and term deduplication."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.schema import Party


# ── Party Name Normalization ─────────────────────────────────────────────

# Common entity suffixes to strip for matching purposes
_ENTITY_SUFFIXES = re.compile(
    r",?\s*(?:"
    r"a\s+\w+\s+(?:limited\s+liability\s+company|corporation|partnership)"
    r"|(?:L\.?L\.?C\.?|Inc\.?|Corp\.?|Ltd\.?|L\.?P\.?|N\.?A\.?)"
    r")\s*$",
    re.IGNORECASE,
)

# Punctuation that varies across documents
_PUNCTUATION = re.compile(r"[.,;:'\"\-]")


def normalize_party_name(name: str) -> str:
    """Normalize a party name for matching purposes.

    Rules:
    - Strip common entity suffixes ("a Delaware limited liability company", "LLC", etc.)
    - Strip punctuation variations (LLC vs L.L.C.)
    - Collapse whitespace
    - Casefold for case-insensitive matching
    """
    result = name.strip()
    result = _ENTITY_SUFFIXES.sub("", result)
    result = _PUNCTUATION.sub("", result)
    result = re.sub(r"\s+", " ", result)
    result = result.strip().casefold()
    return result


def match_party(
    extracted_name: str,
    existing_parties: dict[str, "Party"],
) -> tuple[str | None, str]:
    """Match an extracted party name against existing parties in the graph.

    Returns (party_id, confidence):
    - ("p-xxx", "high") for exact normalized match on canonical_name
    - ("p-xxx", "medium") for match on an alias or raw_name
    - (None, "low") if no match found — caller should create a new party
    """
    norm_extracted = normalize_party_name(extracted_name)

    if not norm_extracted:
        return None, "low"

    for party_id, party in existing_parties.items():
        # Exact match on canonical name
        if normalize_party_name(party.canonical_name) == norm_extracted:
            return party_id, "high"

    for party_id, party in existing_parties.items():
        # Match on aliases
        for alias in party.aliases:
            if normalize_party_name(alias) == norm_extracted:
                return party_id, "medium"
        # Match on raw names
        for raw in party.raw_names:
            if normalize_party_name(raw) == norm_extracted:
                return party_id, "medium"

    return None, "low"


# ── Directionality Validation ────────────────────────────────────────────

# Known wrong direction patterns: (rel_type, source_doc_type, target_doc_type)
# The correct direction is the reverse of these entries.
COMMON_INVERSIONS: dict[tuple[str, str, str], tuple[str, str]] = {
    # "Note secures Mortgage" is wrong; "Mortgage secures Note" is correct
    ("secures", "promissory_note", "deed_of_trust"): ("deed_of_trust", "promissory_note"),
    ("secures", "note", "mortgage"): ("mortgage", "note"),
    ("secures", "note", "deed_of_trust"): ("deed_of_trust", "note"),
    # "Loan Agreement guarantees Guaranty" is wrong; "Guaranty guarantees Loan Agreement"
    ("guarantees", "loan_agreement", "guaranty"): ("guaranty", "loan_agreement"),
    # "Loan Agreement subordinates_to Subordination Agreement" is wrong
    ("subordinates_to", "loan_agreement", "subordination_agreement"): (
        "subordination_agreement", "loan_agreement"
    ),
}


def check_directionality(
    relationship_type: str,
    source_doc_type: str,
    target_doc_type: str,
) -> bool:
    """Check if the directionality of a relationship is correct.

    Returns True if the direction is valid (or not in the known inversions list).
    Returns False if this is a known inversion pattern.
    """
    key = (relationship_type, source_doc_type, target_doc_type)
    return key not in COMMON_INVERSIONS
