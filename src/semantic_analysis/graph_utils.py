"""Graph loading, canonicalization, and hashing utilities."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def load_graph(path: str | Path) -> dict:
    """Load deal-graph.json and return parsed dict.

    Raises FileNotFoundError if file doesn't exist.
    Raises ValueError if JSON is invalid.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Graph file not found: {p}")

    text = p.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {p}: {e}") from e


def canonicalize(data):
    """Recursively sort all dict keys and arrays for deterministic representation."""
    if isinstance(data, dict):
        return {k: canonicalize(v) for k, v in sorted(data.items())}
    elif isinstance(data, list):
        canonical_items = [canonicalize(item) for item in data]
        # Sort arrays: by "id" field if all items are dicts with "id",
        # otherwise by JSON serialization
        if canonical_items and all(isinstance(item, dict) for item in canonical_items):
            if all("id" in item for item in canonical_items):
                canonical_items.sort(key=lambda x: x["id"])
            else:
                canonical_items.sort(key=lambda x: json.dumps(x, sort_keys=True, separators=(",", ":")))
        elif canonical_items:
            try:
                canonical_items.sort()
            except TypeError:
                # Mixed types or uncomparable — sort by string repr
                canonical_items.sort(key=lambda x: json.dumps(x, sort_keys=True, separators=(",", ":")))
        return canonical_items
    else:
        return data


def compute_graph_hash(graph: dict) -> str:
    """Canonicalize graph and return SHA-256 hex digest."""
    canonical = canonicalize(graph)
    json_str = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()
