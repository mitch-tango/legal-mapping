"""Stable content-derived ID generation for analysis findings."""

from __future__ import annotations

import hashlib


def generate_finding_id(
    analysis_type: str,
    category: str,
    affected_entity_ids: list[str],
) -> str:
    """Generate a stable, content-derived ID for a finding.

    Concatenate analysis_type + category + sorted(affected_entity_ids),
    then compute SHA-256 hex digest (first 16 chars for readability).

    Same inputs always yield the same ID regardless of discovery order.
    """
    sorted_ids = sorted(affected_entity_ids)
    content = f"{analysis_type}:{category}:{','.join(sorted_ids)}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
