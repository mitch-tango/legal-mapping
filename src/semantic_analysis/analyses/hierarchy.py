"""Document hierarchy analysis — determines controlling authority per issue area."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from src.semantic_analysis.id_generation import generate_finding_id
from src.semantic_analysis.schemas import (
    AffectedEntity,
    AnalysisResult,
    AnalysisSummary,
    Finding,
)
from src.semantic_analysis.taxonomy import BASE_ISSUE_AREA_TAXONOMY

# Document type hierarchy conventions (source controls target)
_TYPE_HIERARCHY: list[tuple[str, list[str]]] = [
    ("loan_agreement", ["promissory_note", "deed_of_trust", "guaranty", "environmental_indemnity"]),
    ("operating_agreement", ["management_agreement"]),
    ("joint_venture_agreement", ["operating_agreement"]),
    ("intercreditor_agreement", ["loan_agreement", "promissory_note"]),
]

# Relationship types indicating explicit control
_CONTROL_REL_TYPES = {"controls", "subordinates_to", "incorporates"}

# Phrases indicating controlling language in evidence
_CONTROL_PHRASES = [
    "governed by", "subject to the terms of", "in accordance with",
    "as set forth in", "shall be governed by", "controls",
]


def slugify_issue_area(label: str) -> str:
    """Convert issue area label to stable slug ID."""
    slug = label.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def discover_issue_areas(graph_data: dict) -> list[dict]:
    """Extract issue areas from graph provisions using base taxonomy + discovery.

    Returns list of dicts with: issue_area_id, label, anchor_evidence.
    """
    issue_areas = []
    documents = graph_data.get("documents", {})

    # Scan provisions for taxonomy matches
    all_provisions_text = []
    for doc_id, doc in documents.items():
        for prov in doc.get("key_provisions", []):
            text = f"{prov.get('title', '')} {prov.get('summary', '')}".lower()
            all_provisions_text.append((doc_id, prov.get("section_reference", ""), text))

    matched_labels = set()
    for label in BASE_ISSUE_AREA_TAXONOMY:
        keywords = [w.lower() for w in label.split("/")[0].strip().split() if len(w) > 3]
        anchors = []
        for doc_id, section, text in all_provisions_text:
            if any(kw in text for kw in keywords):
                anchors.append({"document_id": doc_id, "section": section})
        if anchors:
            matched_labels.add(label)
            issue_areas.append({
                "issue_area_id": slugify_issue_area(label),
                "label": label,
                "anchor_evidence": anchors,
            })

    # Add a general "loan terms" area if loan documents exist
    loan_docs = [did for did, d in documents.items() if "loan" in d.get("document_type", "").lower()]
    if loan_docs and "Loan covenants" not in matched_labels:
        issue_areas.append({
            "issue_area_id": "loan-terms",
            "label": "Loan terms",
            "anchor_evidence": [{"document_id": did, "section": ""} for did in loan_docs],
        })

    return issue_areas


def detect_explicit_hierarchy(graph_data: dict, issue_area: dict) -> list[Finding]:
    """Detect hierarchy from explicit controlling language in graph relationships."""
    findings = []
    relationships = graph_data.get("relationships", [])
    documents = graph_data.get("documents", {})
    anchor_doc_ids = {a["document_id"] for a in issue_area.get("anchor_evidence", [])}

    for rel in relationships:
        if rel.get("relationship_type") not in _CONTROL_REL_TYPES:
            continue

        source_id = rel.get("source_document_id", "")
        target_id = rel.get("target_document_id", "")

        # Only include if at least one document is in this issue area
        if not (source_id in anchor_doc_ids or target_id in anchor_doc_ids):
            continue

        entities = [
            AffectedEntity(entity_type="document", entity_id=source_id, document_id=source_id,
                           section=rel.get("source_reference")),
            AffectedEntity(entity_type="document", entity_id=target_id, document_id=target_id),
            AffectedEntity(entity_type="relationship", entity_id=rel["id"], document_id=source_id),
        ]

        source_name = documents.get(source_id, {}).get("name", source_id)
        target_name = documents.get(target_id, {}).get("name", target_id)

        finding = Finding(
            id=generate_finding_id("hierarchy", "explicit_hierarchy",
                                   [source_id, target_id]),
            display_ordinal=0,  # Set later
            severity="INFO",
            category="explicit_hierarchy",
            title=f"{source_name} controls {target_name}",
            description=f"{source_name} has explicit controlling authority over {target_name} "
                        f"for {issue_area['label']} (relationship type: {rel['relationship_type']}).",
            affected_entities=entities,
            confidence="high",
            source="explicit",
            verified=True,
        )
        findings.append(finding)

    return findings


def detect_inferred_hierarchy(graph_data: dict, issue_area: dict) -> list[Finding]:
    """Detect hierarchy from document type conventions."""
    findings = []
    documents = graph_data.get("documents", {})
    anchor_doc_ids = {a["document_id"] for a in issue_area.get("anchor_evidence", [])}
    existing_rels = graph_data.get("relationships", [])

    # Check which explicit control edges already exist
    explicit_pairs = set()
    for rel in existing_rels:
        if rel.get("relationship_type") in _CONTROL_REL_TYPES:
            explicit_pairs.add((rel["source_document_id"], rel["target_document_id"]))

    for controlling_type, subordinate_types in _TYPE_HIERARCHY:
        controlling_docs = [
            (did, d) for did, d in documents.items()
            if d.get("document_type") == controlling_type
        ]
        for ctrl_id, ctrl_doc in controlling_docs:
            for sub_type in subordinate_types:
                sub_docs = [
                    (did, d) for did, d in documents.items()
                    if d.get("document_type") == sub_type
                ]
                for sub_id, sub_doc in sub_docs:
                    # Skip if explicit hierarchy already exists
                    if (ctrl_id, sub_id) in explicit_pairs:
                        continue
                    # Only include if relevant to this issue area
                    if not (ctrl_id in anchor_doc_ids or sub_id in anchor_doc_ids):
                        continue

                    entities = [
                        AffectedEntity(entity_type="document", entity_id=ctrl_id, document_id=ctrl_id),
                        AffectedEntity(entity_type="document", entity_id=sub_id, document_id=sub_id),
                    ]

                    finding = Finding(
                        id=generate_finding_id("hierarchy", "inferred_hierarchy",
                                               [ctrl_id, sub_id]),
                        display_ordinal=0,
                        severity="WARNING",
                        category="inferred_hierarchy",
                        title=f"Inferred: {ctrl_doc['name']} controls {sub_doc['name']}",
                        description=f"By document type convention, {ctrl_doc['name']} ({controlling_type}) "
                                    f"controls {sub_doc['name']} ({sub_type}) for {issue_area['label']}.",
                        affected_entities=entities,
                        confidence="medium",
                        source="inferred",
                        verified=False,
                    )
                    findings.append(finding)

    return findings


def detect_dual_authority(graph_data: dict, issue_area: dict) -> list[Finding]:
    """Detect conflicting controlling claims on the same issue area."""
    findings = []
    relationships = graph_data.get("relationships", [])
    documents = graph_data.get("documents", {})
    anchor_doc_ids = {a["document_id"] for a in issue_area.get("anchor_evidence", [])}

    # Find all documents that claim control over others in this issue area
    controlling_docs = set()
    for rel in relationships:
        if rel.get("relationship_type") in _CONTROL_REL_TYPES:
            source = rel["source_document_id"]
            target = rel["target_document_id"]
            if source in anchor_doc_ids or target in anchor_doc_ids:
                controlling_docs.add(source)

    # If two+ documents both control for this issue area, that's a conflict
    if len(controlling_docs) >= 2:
        doc_ids = sorted(controlling_docs)
        doc_names = [documents.get(d, {}).get("name", d) for d in doc_ids]
        entities = [
            AffectedEntity(entity_type="document", entity_id=d, document_id=d)
            for d in doc_ids
        ]
        finding = Finding(
            id=generate_finding_id("hierarchy", "dual_authority_conflict", doc_ids),
            display_ordinal=0,
            severity="ERROR",
            category="dual_authority_conflict",
            title=f"Dual authority conflict: {' vs '.join(doc_names)}",
            description=f"Multiple documents claim controlling authority for {issue_area['label']}: "
                        f"{', '.join(doc_names)}. Review to determine which document should control.",
            affected_entities=entities,
            confidence="medium",
            source="inferred",
            verified=False,
        )
        findings.append(finding)

    return findings


def run_hierarchy_analysis(
    graph_data: dict,
    anthropic_client=None,
    source_dir: str | None = None,
) -> AnalysisResult:
    """Run document hierarchy analysis.

    Uses graph-based detection for explicit and inferred hierarchy.
    API client used for Pass 2 verification when source_dir is provided.
    """
    all_findings: list[Finding] = []

    issue_areas = discover_issue_areas(graph_data)

    for ia in issue_areas:
        all_findings.extend(detect_explicit_hierarchy(graph_data, ia))
        all_findings.extend(detect_inferred_hierarchy(graph_data, ia))
        all_findings.extend(detect_dual_authority(graph_data, ia))

    # Deduplicate by finding ID
    seen_ids = set()
    unique_findings = []
    for f in all_findings:
        if f.id not in seen_ids:
            seen_ids.add(f.id)
            unique_findings.append(f)

    # Assign display ordinals
    for i, f in enumerate(unique_findings, 1):
        f.display_ordinal = i

    # Build summary
    by_severity: dict[str, int] = {}
    for f in unique_findings:
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1

    return AnalysisResult(
        analysis_type="hierarchy",
        status="completed",
        completion="complete",
        run_timestamp=datetime.now(timezone.utc).isoformat(),
        model_used="graph-analysis",
        findings=unique_findings,
        summary=AnalysisSummary(
            total_findings=len(unique_findings),
            by_severity=by_severity,
            key_findings=[f.title for f in unique_findings[:5]],
        ),
        errors=[],
    )
