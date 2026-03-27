"""Graph CRUD operations — load, save, and atomic I/O for deal-graph.json."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from src.models.schema import SCHEMA_VERSION, DealGraph, DealMetadata

GRAPH_FILENAME = "deal-graph.json"


def load_graph(deal_dir: str) -> DealGraph | None:
    """Load a deal graph from disk.

    Returns None if the file does not exist.
    Raises ValueError if the file exists but is invalid.
    """
    graph_path = Path(deal_dir) / GRAPH_FILENAME
    if not graph_path.exists():
        return None

    text = graph_path.read_text(encoding="utf-8")
    try:
        return DealGraph.model_validate_json(text)
    except Exception as e:
        raise ValueError(f"Invalid deal graph at {graph_path}: {e}") from e


def save_graph(graph: DealGraph, deal_dir: str) -> None:
    """Save a deal graph to disk with atomic write.

    1. Serialize to JSON
    2. Validate via Pydantic round-trip
    3. Write to temp file
    4. Atomic rename to deal-graph.json

    If validation fails, temp file is deleted and original is preserved.
    """
    deal_path = Path(deal_dir)
    deal_path.mkdir(parents=True, exist_ok=True)
    graph_path = deal_path / GRAPH_FILENAME

    # Serialize
    json_str = graph.model_dump_json(indent=2)

    # Validate round-trip
    try:
        DealGraph.model_validate_json(json_str)
    except Exception as e:
        raise ValueError(f"Graph failed validation, not saving: {e}") from e

    # Atomic write: temp file in same directory, then rename
    fd, tmp_path = tempfile.mkstemp(
        dir=str(deal_path), suffix=".tmp.json", prefix="deal-graph-"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json_str)
            f.write("\n")
        os.replace(tmp_path, str(graph_path))
    except Exception:
        # Clean up temp file on failure
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def create_deal(
    deal_dir: str,
    deal_name: str,
    deal_type: str | None = None,
) -> DealGraph:
    """Create a new deal directory and empty graph.

    Creates the directory structure and saves an empty deal-graph.json.
    Returns the new DealGraph instance.
    """
    deal_path = Path(deal_dir)
    deal_path.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()

    graph = DealGraph(
        schema_version=SCHEMA_VERSION,
        deal=DealMetadata(
            name=deal_name,
            deal_type=deal_type,
            status="active",
            created_at=now,
            updated_at=now,
        ),
    )

    save_graph(graph, deal_dir)
    return graph
