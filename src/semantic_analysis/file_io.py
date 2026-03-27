"""Atomic writes, lock file management, and incremental result updates."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from src.semantic_analysis.schemas import (
    AnalysisMetadata,
    AnalysisResult,
    AnalysisResults,
    StalenessRecord,
)

ANALYSIS_FILENAME = "deal-analysis.json"
LOCK_FILENAME = ".deal-analysis.lock"
LOCK_STALE_SECONDS = 15 * 60  # 15 minutes


def read_existing_results(deal_dir: Path | str) -> AnalysisResults | None:
    """Read and parse existing deal-analysis.json. Returns None if not found."""
    path = Path(deal_dir) / ANALYSIS_FILENAME
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    return AnalysisResults.model_validate_json(text)


def _acquire_lock(deal_dir: Path) -> Path:
    """Create lock file. Handles stale locks."""
    lock_path = deal_dir / LOCK_FILENAME
    if lock_path.exists():
        try:
            lock_data = json.loads(lock_path.read_text())
            lock_time = lock_data.get("timestamp", "")
            lock_dt = datetime.fromisoformat(lock_time)
            age = (datetime.now(timezone.utc) - lock_dt).total_seconds()
            if age < LOCK_STALE_SECONDS:
                raise RuntimeError(
                    f"Lock file exists and is recent ({age:.0f}s old). "
                    "Another analysis may be running."
                )
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
        # Stale or corrupt lock — remove it
        lock_path.unlink(missing_ok=True)

    lock_data = {
        "pid": os.getpid(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    lock_path.write_text(json.dumps(lock_data))
    return lock_path


def _release_lock(lock_path: Path) -> None:
    """Remove lock file."""
    lock_path.unlink(missing_ok=True)


def write_results_incremental(
    deal_dir: Path | str,
    analysis_type: str,
    result: AnalysisResult,
    staleness: StalenessRecord,
    graph_hash: str,
) -> None:
    """Update a single analysis in deal-analysis.json atomically."""
    deal_path = Path(deal_dir)
    deal_path.mkdir(parents=True, exist_ok=True)

    lock_path = _acquire_lock(deal_path)
    try:
        # Read or create
        existing = read_existing_results(deal_path)
        if existing is None:
            existing = AnalysisResults(
                schema_version="1.0.0",
                deal_graph_hash=graph_hash,
                analyses={},
                metadata=AnalysisMetadata(
                    last_full_analysis=None,
                    documents_included=[],
                    engine_version="0.1.0",
                ),
                staleness={},
            )

        # Update
        existing.analyses[analysis_type] = result
        existing.staleness[analysis_type] = staleness
        existing.deal_graph_hash = graph_hash

        # Atomic write
        final_path = deal_path / ANALYSIS_FILENAME
        tmp_path = deal_path / f"{ANALYSIS_FILENAME}.tmp"
        tmp_path.write_text(existing.model_dump_json(indent=2), encoding="utf-8")
        os.replace(str(tmp_path), str(final_path))
    finally:
        _release_lock(lock_path)
