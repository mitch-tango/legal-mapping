"""Staleness tracking for semantic analysis results.

Compares graph state against stored analysis hashes and applies
change-type-specific rules to determine which analyses need re-running.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.semantic_analysis.graph_utils import canonicalize, compute_graph_hash

if TYPE_CHECKING:
    from src.semantic_analysis.schemas import AnalysisResults, StalenessRecord

ALL_ANALYSES = [
    "hierarchy", "conflicts", "defined_terms",
    "conditions_precedent", "execution_sequence",
]

STALENESS_RULES: dict[str, list[str]] = {
    "documents": ALL_ANALYSES[:],
    "relationships": ["hierarchy", "conflicts"],
    "defined_terms": ["defined_terms"],
    "cross_references": ["conflicts"],
    "conditions_precedent": ["conditions_precedent", "execution_sequence"],
    "parties": ["execution_sequence", "conditions_precedent", "defined_terms"],
    "annotations": [],
}

# Human-readable reasons per change type
_CHANGE_REASONS: dict[str, str] = {
    "documents": "document added or removed",
    "relationships": "relationship modified",
    "defined_terms": "defined term changed",
    "cross_references": "cross-reference modified",
    "conditions_precedent": "condition precedent changed",
    "parties": "party modified",
    "annotations": "annotation modified",
}


def detect_graph_changes(old_graph: dict, new_graph: dict) -> set[str]:
    """Compare two graphs and return the set of changed section keys.

    Compares each top-level section independently using canonical hashing.
    """
    change_types: set[str] = set()

    # Map graph keys to staleness rule keys
    key_mapping = {
        "documents": "documents",
        "relationships": "relationships",
        "defined_terms": "defined_terms",
        "cross_references": "cross_references",
        "conditions_precedent": "conditions_precedent",
        "parties": "parties",
        "annotations": "annotations",
    }

    for rule_key, graph_key in key_mapping.items():
        old_section = old_graph.get(graph_key, {})
        new_section = new_graph.get(graph_key, {})
        old_canonical = json.dumps(canonicalize(old_section), sort_keys=True, separators=(",", ":"))
        new_canonical = json.dumps(canonicalize(new_section), sort_keys=True, separators=(",", ":"))
        if old_canonical != new_canonical:
            change_types.add(rule_key)

    return change_types


def apply_staleness_rules(change_types: set[str]) -> set[str]:
    """Given change types, return the set of analysis names that should be marked stale."""
    stale_analyses: set[str] = set()
    for change_type in change_types:
        affected = STALENESS_RULES.get(change_type, [])
        stale_analyses.update(affected)
    return stale_analyses


def check_staleness(
    current_graph: dict,
    analysis_results: "AnalysisResults | None",
) -> dict[str, "StalenessRecord"]:
    """Check which analyses are stale given the current graph state.

    Returns a dict mapping analysis type names to StalenessRecord objects.
    """
    from src.semantic_analysis.schemas import StalenessRecord

    current_hash = compute_graph_hash(current_graph)
    now = datetime.now(timezone.utc).isoformat()

    # No prior results — everything is stale
    if analysis_results is None:
        return {
            name: StalenessRecord(
                is_stale=True,
                last_run=now,
                stale_reason="no prior analysis results",
                graph_hash_at_run="",
            )
            for name in ALL_ANALYSES
        }

    records: dict[str, StalenessRecord] = {}

    for name in ALL_ANALYSES:
        existing = analysis_results.staleness.get(name)

        if existing is None:
            records[name] = StalenessRecord(
                is_stale=True,
                last_run=now,
                stale_reason="missing staleness record",
                graph_hash_at_run="",
            )
            continue

        if existing.graph_hash_at_run == current_hash:
            records[name] = StalenessRecord(
                is_stale=False,
                last_run=existing.last_run,
                stale_reason=None,
                graph_hash_at_run=existing.graph_hash_at_run,
            )
        else:
            # Hash differs — need to determine what changed
            records[name] = StalenessRecord(
                is_stale=True,
                last_run=existing.last_run,
                stale_reason="graph changed since last analysis",
                graph_hash_at_run=existing.graph_hash_at_run,
            )

    return records


def check_staleness_with_diff(
    current_graph: dict,
    old_graph: dict | None,
    analysis_results: "AnalysisResults | None",
) -> dict[str, "StalenessRecord"]:
    """Check staleness with granular change detection using old graph.

    When old_graph is available, uses detect_graph_changes + apply_staleness_rules
    for targeted staleness marking instead of marking everything stale.
    """
    from src.semantic_analysis.schemas import StalenessRecord

    current_hash = compute_graph_hash(current_graph)
    now = datetime.now(timezone.utc).isoformat()

    if analysis_results is None or old_graph is None:
        return check_staleness(current_graph, analysis_results)

    change_types = detect_graph_changes(old_graph, current_graph)
    stale_analyses = apply_staleness_rules(change_types)

    # Build reason string
    if len(change_types) > 1:
        reason = f"multiple changes: {', '.join(sorted(change_types))}"
    elif len(change_types) == 1:
        ct = next(iter(change_types))
        reason = _CHANGE_REASONS.get(ct, f"{ct} changed")
    else:
        reason = None

    records: dict[str, StalenessRecord] = {}

    for name in ALL_ANALYSES:
        existing = analysis_results.staleness.get(name)
        last_run = existing.last_run if existing else now
        old_hash = existing.graph_hash_at_run if existing else ""

        if name in stale_analyses:
            records[name] = StalenessRecord(
                is_stale=True,
                last_run=last_run,
                stale_reason=reason,
                graph_hash_at_run=old_hash,
            )
        else:
            # Check if the overall hash still matches
            if existing and existing.graph_hash_at_run == current_hash:
                records[name] = StalenessRecord(
                    is_stale=False,
                    last_run=last_run,
                    stale_reason=None,
                    graph_hash_at_run=existing.graph_hash_at_run,
                )
            elif existing is None:
                records[name] = StalenessRecord(
                    is_stale=True,
                    last_run=now,
                    stale_reason="missing staleness record",
                    graph_hash_at_run="",
                )
            else:
                # Hash differs but this analysis isn't affected by the change types
                records[name] = StalenessRecord(
                    is_stale=False,
                    last_run=last_run,
                    stale_reason=None,
                    graph_hash_at_run=existing.graph_hash_at_run,
                )

    return records


def format_staleness_report(staleness: dict[str, "StalenessRecord"]) -> str:
    """Format staleness status for user display."""
    lines = []
    for name in ALL_ANALYSES:
        record = staleness.get(name)
        if record is None:
            lines.append(f"  {name}: unknown")
        elif record.is_stale:
            reason = record.stale_reason or "unknown reason"
            lines.append(f"  {name}: STALE ({reason})")
        else:
            lines.append(f"  {name}: current")
    return "Analysis staleness:\n" + "\n".join(lines)
