"""Helper functions for cross-reference conflict detection."""

from __future__ import annotations

from src.semantic_analysis.id_generation import generate_finding_id
from src.semantic_analysis.schemas import AffectedEntity, AnalysisResult, Finding
from src.semantic_analysis.section_normalize import match_section_ref


def _build_section_inventory(graph: dict) -> dict[str, list[str]]:
    """Build a section inventory per document from key provisions."""
    inventory: dict[str, list[str]] = {}
    for doc_id, doc in graph.get("documents", {}).items():
        sections = []
        for prov in doc.get("key_provisions", []):
            ref = prov.get("section_reference")
            if ref:
                sections.append(ref)
        inventory[doc_id] = sections
    return inventory


def detect_dangling_references(
    cross_references: list[dict],
    section_inventory: dict[str, list[str]],
    documents: dict,
) -> list[Finding]:
    """Check each cross-reference target against the section inventory."""
    findings = []

    for xref in cross_references:
        target_doc = xref.get("target_document_id", "")
        target_section = xref.get("target_section")
        source_doc = xref.get("source_document_id", "")

        # Missing document check
        if target_doc not in documents:
            source_name = documents.get(source_doc, {}).get("name", source_doc)
            findings.append(Finding(
                id=generate_finding_id("conflicts", "missing_document",
                                       [xref["id"], target_doc]),
                display_ordinal=0, severity="ERROR",
                category="missing_document",
                title=f"Reference to missing document: {target_doc}",
                description=f"{source_name} references document '{target_doc}' which is not in the deal set.",
                affected_entities=[
                    AffectedEntity(entity_type="cross_reference", entity_id=xref["id"],
                                   document_id=source_doc, section=xref.get("source_section")),
                ],
                confidence="high", source="explicit", verified=True,
            ))
            continue

        if not target_section:
            continue

        inv = section_inventory.get(target_doc, [])
        if not inv:
            continue

        match = match_section_ref(target_section, inv)

        if match.match_type == "exact":
            continue  # Valid reference
        elif match.match_type == "normalized":
            source_name = documents.get(source_doc, {}).get("name", source_doc)
            target_name = documents.get(target_doc, {}).get("name", target_doc)
            findings.append(Finding(
                id=generate_finding_id("conflicts", "ambiguous_section_ref",
                                       [xref["id"], target_doc]),
                display_ordinal=0, severity="WARNING",
                category="ambiguous_section_ref",
                title=f"Ambiguous section reference: {target_section}",
                description=f"{source_name} references '{target_section}' in {target_name}, "
                            f"which matches '{match.matched_ref}' after normalization.",
                affected_entities=[
                    AffectedEntity(entity_type="cross_reference", entity_id=xref["id"],
                                   document_id=source_doc, section=xref.get("source_section")),
                ],
                confidence="medium", source="explicit", verified=True,
            ))
        else:
            source_name = documents.get(source_doc, {}).get("name", source_doc)
            target_name = documents.get(target_doc, {}).get("name", target_doc)
            suggestion = ""
            if match.match_type == "suggestion" and match.matched_ref:
                suggestion = f" Did you mean '{match.matched_ref}'?"
            findings.append(Finding(
                id=generate_finding_id("conflicts", "dangling_reference",
                                       [xref["id"], target_doc]),
                display_ordinal=0, severity="ERROR",
                category="dangling_reference",
                title=f"Dangling reference: {target_section} in {target_name}",
                description=f"{source_name} references '{target_section}' in {target_name}, "
                            f"but this section was not found.{suggestion}",
                affected_entities=[
                    AffectedEntity(entity_type="cross_reference", entity_id=xref["id"],
                                   document_id=source_doc, section=xref.get("source_section")),
                ],
                confidence="high", source="explicit", verified=True,
            ))

    return findings


def detect_circular_references(cross_references: list[dict]) -> list[Finding]:
    """Build directed graph from cross-references and detect cycles."""
    findings = []

    # Build adjacency: source_doc -> set of target_docs
    adj: dict[str, set[str]] = {}
    for xref in cross_references:
        src = xref.get("source_document_id", "")
        tgt = xref.get("target_document_id", "")
        if src and tgt:
            adj.setdefault(src, set()).add(tgt)

    # DFS cycle detection
    WHITE, GRAY, BLACK = 0, 1, 2
    all_nodes = set(adj.keys())
    for targets in adj.values():
        all_nodes.update(targets)
    color = {n: WHITE for n in all_nodes}
    path: list[str] = []

    def dfs(node):
        color[node] = GRAY
        path.append(node)
        for neighbor in adj.get(node, set()):
            if color.get(neighbor) == GRAY:
                # Found cycle
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                chain = " -> ".join(cycle)
                cycle_ids = sorted(set(path[cycle_start:]))
                findings.append(Finding(
                    id=generate_finding_id("conflicts", "circular_reference", cycle_ids),
                    display_ordinal=0, severity="ERROR",
                    category="circular_reference",
                    title="Circular cross-reference chain detected",
                    description=f"Circular reference chain: {chain}",
                    affected_entities=[
                        AffectedEntity(entity_type="document", entity_id=d, document_id=d)
                        for d in cycle_ids
                    ],
                    confidence="high", source="explicit", verified=True,
                ))
            elif color.get(neighbor, WHITE) == WHITE:
                dfs(neighbor)
        path.pop()
        color[node] = BLACK

    for node in all_nodes:
        if color.get(node, WHITE) == WHITE:
            dfs(node)

    return findings


def detect_missing_documents(graph: dict) -> list[Finding]:
    """Find references to documents not in the deal set."""
    findings = []
    doc_ids = set(graph.get("documents", {}).keys())
    documents = graph.get("documents", {})

    # Check relationships
    for rel in graph.get("relationships", []):
        for field in ["source_document_id", "target_document_id"]:
            ref_id = rel.get(field, "")
            if ref_id and ref_id not in doc_ids:
                findings.append(Finding(
                    id=generate_finding_id("conflicts", "missing_document",
                                           [rel["id"], ref_id]),
                    display_ordinal=0, severity="ERROR",
                    category="missing_document",
                    title=f"Missing document: {ref_id}",
                    description=f"Relationship '{rel.get('description', '')}' references "
                                f"document '{ref_id}' which is not in the deal set.",
                    affected_entities=[
                        AffectedEntity(entity_type="relationship", entity_id=rel["id"],
                                       document_id=rel.get("source_document_id", "")),
                    ],
                    confidence="high", source="explicit", verified=True,
                ))

    return findings


def generate_contradiction_candidates(
    graph: dict,
    hierarchy_results: AnalysisResult | None,
    term_results: AnalysisResult | None,
) -> list[dict]:
    """Identify document-section pairs that may contain contradictory provisions."""
    candidates = []
    documents = graph.get("documents", {})
    doc_ids = list(documents.keys())

    for i, doc_a in enumerate(doc_ids):
        for doc_b in doc_ids[i + 1:]:
            score = 0
            reasons = []

            # Check for explicit cross-references between them
            for xref in graph.get("cross_references", []):
                if ((xref.get("source_document_id") == doc_a and xref.get("target_document_id") == doc_b) or
                    (xref.get("source_document_id") == doc_b and xref.get("target_document_id") == doc_a)):
                    score += 2
                    reasons.append("explicit cross-reference")
                    break

            # Check for shared issue area from hierarchy
            if hierarchy_results:
                for f in hierarchy_results.findings:
                    entity_ids = {e.entity_id for e in f.affected_entities}
                    if doc_a in entity_ids and doc_b in entity_ids:
                        score += 3
                        reasons.append("shared issue area")
                        break

            # Check for conflicting term definitions
            if term_results:
                for f in term_results.findings:
                    if f.category == "conflicting_definition":
                        entity_ids = {e.entity_id for e in f.affected_entities}
                        if doc_a in entity_ids and doc_b in entity_ids:
                            score += 3
                            reasons.append("conflicting term definition")
                            break

            if score > 0:
                candidates.append({
                    "doc_a": doc_a,
                    "doc_b": doc_b,
                    "score": score,
                    "reasons": reasons,
                })

    return candidates


def rank_and_cap_candidates(candidates: list[dict], cap: int = 20) -> list[dict]:
    """Sort candidates by score descending, return top `cap` entries."""
    sorted_candidates = sorted(candidates, key=lambda c: c["score"], reverse=True)
    return sorted_candidates[:cap]


def adjust_severity_with_hierarchy(
    finding: Finding,
    hierarchy_results: AnalysisResult | None,
) -> Finding:
    """Upgrade severity if the finding affects a controlling document."""
    if hierarchy_results is None:
        return finding

    controlling_docs = set()
    for f in hierarchy_results.findings:
        if f.category in ("explicit_hierarchy", "controlling_authority"):
            for e in f.affected_entities:
                if e.entity_type == "document":
                    controlling_docs.add(e.entity_id)
                    break  # First entity is typically the controller

    if finding.severity == "WARNING":
        for entity in finding.affected_entities:
            if entity.entity_id in controlling_docs:
                finding.severity = "ERROR"
                break

    return finding
