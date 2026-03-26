"""Section reference normalization for fuzzy cross-reference matching."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class SectionMatch:
    """Result of matching a section reference against an inventory."""
    match_type: str  # "exact", "normalized", "suggestion", "none"
    matched_ref: str | None
    normalized_input: str
    edit_distance: int | None = None


def normalize_section_ref(ref: str) -> str:
    """Normalize a section reference string for comparison.

    1. Strip "Section" prefix (case-insensitive)
    2. Strip whitespace
    3. Remove trailing zeros after decimal (1.01 -> 1.1, 1.10 -> 1.1)
    4. Preserve parenthetical sub-sections
    5. Lowercase
    """
    result = ref.strip()
    result = re.sub(r"^section\s+", "", result, flags=re.IGNORECASE)
    result = result.strip()

    # Normalize decimal sub-numbering: strip leading zeros from fractional part
    # (1.01 -> 1.1, 1.10 -> 1.1) but preserve the value
    def normalize_decimal(m):
        integer = m.group(1)
        fractional = m.group(2)
        if fractional.isdigit():
            # Convert to int to strip both leading and trailing zeros
            # 01 -> 1, 10 -> 10... but spec says 1.10 -> 1.1
            # Strip trailing zeros, then leading zeros
            stripped = fractional.rstrip("0") or "0"
            stripped = str(int(stripped)) if stripped.isdigit() else stripped
            return f"{integer}.{stripped}"
        return f"{integer}.{fractional}"

    result = re.sub(r"(\d+)\.(\d+)", normalize_decimal, result)
    result = result.lower()
    return result


def _levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(a) < len(b):
        return _levenshtein(b, a)
    if len(b) == 0:
        return len(a)

    prev_row = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr_row = [i + 1]
        for j, cb in enumerate(b):
            cost = 0 if ca == cb else 1
            curr_row.append(min(
                curr_row[j] + 1,
                prev_row[j + 1] + 1,
                prev_row[j] + cost,
            ))
        prev_row = curr_row
    return prev_row[-1]


def match_section_ref(reference: str, inventory: list[str]) -> SectionMatch:
    """Match a section reference against an inventory of known sections.

    Returns SectionMatch with match_type:
    - "exact": raw strings match (case-insensitive, prefix-stripped)
    - "normalized": match after trailing zero normalization
    - "suggestion": closest by edit distance (if distance <= 3)
    - "none": no match found
    """
    norm_input = normalize_section_ref(reference)

    if not inventory:
        return SectionMatch(match_type="none", matched_ref=None, normalized_input=norm_input)

    # Build normalized inventory
    norm_inventory = [(normalize_section_ref(inv), inv) for inv in inventory]

    # Exact match on normalized forms
    for norm_inv, raw_inv in norm_inventory:
        if norm_input == norm_inv:
            # Check if it was exact before normalization
            raw_stripped = re.sub(r"^section\s+", "", reference.strip(), flags=re.IGNORECASE).strip().lower()
            inv_stripped = re.sub(r"^section\s+", "", raw_inv.strip(), flags=re.IGNORECASE).strip().lower()
            if raw_stripped == inv_stripped:
                return SectionMatch(match_type="exact", matched_ref=raw_inv, normalized_input=norm_input)
            return SectionMatch(match_type="normalized", matched_ref=raw_inv, normalized_input=norm_input)

    # Suggestion by edit distance
    best_dist = float("inf")
    best_ref = None
    for norm_inv, raw_inv in norm_inventory:
        dist = _levenshtein(norm_input, norm_inv)
        if dist < best_dist:
            best_dist = dist
            best_ref = raw_inv

    if best_dist <= 3 and best_ref is not None:
        return SectionMatch(
            match_type="suggestion", matched_ref=best_ref,
            normalized_input=norm_input, edit_distance=best_dist,
        )

    return SectionMatch(match_type="none", matched_ref=None, normalized_input=norm_input)


def batch_normalize(references: list[str], inventory: list[str]) -> list[SectionMatch]:
    """Match a list of section references against an inventory."""
    return [match_section_ref(ref, inventory) for ref in references]
