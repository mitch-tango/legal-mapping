"""Token estimation, clustering, and finding deduplication for large deals."""

from __future__ import annotations

import json

from src.semantic_analysis.analyses.hierarchy import discover_issue_areas
from src.semantic_analysis.schemas import Finding

MODEL_CONTEXT_WINDOW = 200_000
CLUSTER_THRESHOLD_RATIO = 0.60
CHARS_PER_TOKEN = 4

_CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}


def estimate_tokens(graph_json: str) -> int:
    """Estimate token count from graph JSON string length."""
    return len(graph_json) // CHARS_PER_TOKEN


def should_cluster(graph_json: str) -> bool:
    """Return True if graph is large enough to require clustering."""
    threshold = int(MODEL_CONTEXT_WINDOW * CLUSTER_THRESHOLD_RATIO)
    return estimate_tokens(graph_json) > threshold


def cluster_graph(graph_data: dict) -> list[dict]:
    """Partition a deal graph into issue-area clusters.

    Each cluster contains documents, relationships, terms, cross-references,
    and conditions precedent related to a single issue area.
    """
    issue_areas = discover_issue_areas(graph_data)

    if not issue_areas:
        # No issue areas found — return single cluster with everything
        return [{
            "cluster_id": "all",
            "documents": graph_data.get("documents", {}),
            "relationships": graph_data.get("relationships", []),
            "defined_terms": graph_data.get("defined_terms", []),
            "cross_references": graph_data.get("cross_references", []),
            "conditions_precedent": graph_data.get("conditions_precedent", []),
        }]

    clusters = []
    all_docs = graph_data.get("documents", {})
    all_rels = graph_data.get("relationships", [])
    all_terms = graph_data.get("defined_terms", [])
    all_xrefs = graph_data.get("cross_references", [])
    all_cps = graph_data.get("conditions_precedent", [])

    for ia in issue_areas:
        cluster_doc_ids = {a["document_id"] for a in ia.get("anchor_evidence", [])}

        # Pull documents
        cluster_docs = {did: all_docs[did] for did in cluster_doc_ids if did in all_docs}

        # Pull relationships where both endpoints are in the cluster
        cluster_rels = [
            r for r in all_rels
            if r.get("source_document_id") in cluster_doc_ids
            or r.get("target_document_id") in cluster_doc_ids
        ]

        # Pull terms defined in or used by cluster documents
        cluster_terms = [
            t for t in all_terms
            if t.get("defining_document_id") in cluster_doc_ids
            or any(uid in cluster_doc_ids for uid in t.get("used_in_document_ids", []))
        ]

        # Pull cross-references involving cluster documents
        cluster_xrefs = [
            x for x in all_xrefs
            if x.get("source_document_id") in cluster_doc_ids
            or x.get("target_document_id") in cluster_doc_ids
        ]

        # Pull CPs involving cluster documents
        cluster_cps = [
            cp for cp in all_cps
            if cp.get("source_document_id") in cluster_doc_ids
            or cp.get("required_document_id") in cluster_doc_ids
            or cp.get("enables_document_id") in cluster_doc_ids
        ]

        clusters.append({
            "cluster_id": ia["issue_area_id"],
            "documents": cluster_docs,
            "relationships": cluster_rels,
            "defined_terms": cluster_terms,
            "cross_references": cluster_xrefs,
            "conditions_precedent": cluster_cps,
        })

    return clusters


def deduplicate_findings(
    clustered_findings: list[tuple[str, list[Finding]]],
) -> list[Finding]:
    """Merge findings from multiple clusters, deduplicating by stable ID.

    Rules:
    - Same ID: keep higher confidence version
    - Record all source cluster IDs in found_in_clusters
    """
    merged: dict[str, tuple[Finding, list[str]]] = {}

    for cluster_id, findings in clustered_findings:
        for finding in findings:
            if finding.id in merged:
                existing_f, existing_clusters = merged[finding.id]
                existing_clusters.append(cluster_id)
                # Keep higher confidence
                if _CONFIDENCE_RANK.get(finding.confidence, 0) > _CONFIDENCE_RANK.get(existing_f.confidence, 0):
                    merged[finding.id] = (finding, existing_clusters)
            else:
                merged[finding.id] = (finding, [cluster_id])

    result = []
    for finding, clusters in merged.values():
        finding.found_in_clusters = clusters if len(clusters) > 1 else None
        result.append(finding)

    return result
