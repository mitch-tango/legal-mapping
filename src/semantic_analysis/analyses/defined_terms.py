"""Defined term tracking — provenance, usage, and inconsistency detection."""

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


def load_baseline_terms(deal_graph: dict) -> dict:
    """Load defined terms from the deal graph's defined_terms array.

    Returns dict keyed by lowercase term text, each value containing:
    - term: original case term text
    - definitions: list of {document_id, section, snippet}
    """
    terms: dict[str, dict] = {}
    for dt in deal_graph.get("defined_terms", []):
        key = dt["term"].lower()
        if key not in terms:
            terms[key] = {"term": dt["term"], "definitions": []}
        terms[key]["definitions"].append({
            "document_id": dt.get("defining_document_id", ""),
            "section": dt.get("section_reference"),
            "snippet": dt.get("definition_snippet"),
        })
    return terms


def find_enhanced_terms(deal_graph: dict, baseline_terms: dict) -> list[dict]:
    """Find terms that baseline extraction may have missed.

    Scans cross-references, relationship evidence, and key provisions for:
    1. Cross-reference-defined terms ("as defined in...")
    2. Capitalized undefined terms
    """
    enhanced = []
    baseline_keys = set(baseline_terms.keys())
    documents = deal_graph.get("documents", {})

    # Scan for capitalized terms in provisions and evidence
    all_text_sources: list[tuple[str, str]] = []  # (doc_id, text)

    for doc_id, doc in documents.items():
        for prov in doc.get("key_provisions", []):
            all_text_sources.append((doc_id, prov.get("summary", "")))
            all_text_sources.append((doc_id, prov.get("title", "") or ""))

    for rel in deal_graph.get("relationships", []):
        evidence = rel.get("evidence")
        if isinstance(evidence, dict):
            all_text_sources.append((rel.get("source_document_id", ""), evidence.get("quote", "")))
        all_text_sources.append((rel.get("source_document_id", ""), rel.get("description", "")))

    for xref in deal_graph.get("cross_references", []):
        all_text_sources.append((xref.get("source_document_id", ""), xref.get("reference_text", "")))

    # Find capitalized multi-word terms not in baseline
    cap_pattern = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")
    seen = set()
    for doc_id, text in all_text_sources:
        if not text:
            continue
        for match in cap_pattern.finditer(text):
            term = match.group(1)
            key = term.lower()
            if key not in baseline_keys and key not in seen and len(term) > 5:
                seen.add(key)
                enhanced.append({
                    "term": term,
                    "document_id": doc_id,
                    "section": None,
                    "source": "capitalized_usage",
                })

    # Scan cross-references for "as defined in" patterns
    as_defined_pattern = re.compile(r'"([^"]+)"\s+(?:as\s+)?defined\s+in', re.IGNORECASE)
    for xref in deal_graph.get("cross_references", []):
        text = xref.get("reference_text", "")
        for match in as_defined_pattern.finditer(text):
            term = match.group(1)
            key = term.lower()
            if key not in baseline_keys and key not in seen:
                seen.add(key)
                enhanced.append({
                    "term": term,
                    "document_id": xref.get("target_document_id", ""),
                    "section": None,
                    "source": "cross_reference",
                })

    return enhanced


def track_term_usage(deal_graph: dict, all_terms: dict) -> dict[str, set[str]]:
    """For each term, find all documents that use it.

    Returns dict keyed by lowercase term text, value is set of document_ids.
    """
    usage: dict[str, set[str]] = {key: set() for key in all_terms}
    documents = deal_graph.get("documents", {})

    for term_key in all_terms:
        term_text = all_terms[term_key]["term"]
        pattern = re.compile(re.escape(term_text), re.IGNORECASE)

        # Check all document provisions
        for doc_id, doc in documents.items():
            for prov in doc.get("key_provisions", []):
                text = f"{prov.get('title', '')} {prov.get('summary', '')}"
                if pattern.search(text):
                    usage[term_key].add(doc_id)

            # Check summary
            if pattern.search(doc.get("summary", "")):
                usage[term_key].add(doc_id)

            # Check obligations
            for ob in doc.get("obligations", []):
                if pattern.search(ob):
                    usage[term_key].add(doc_id)

        # Check relationships
        for rel in deal_graph.get("relationships", []):
            if pattern.search(rel.get("description", "")):
                usage[term_key].add(rel.get("source_document_id", ""))
                usage[term_key].add(rel.get("target_document_id", ""))

        # Add defining documents
        for defn in all_terms[term_key].get("definitions", []):
            usage[term_key].add(defn["document_id"])

        # Add used_in from graph
        for dt in deal_graph.get("defined_terms", []):
            if dt["term"].lower() == term_key:
                for uid in dt.get("used_in_document_ids", []):
                    usage[term_key].add(uid)

    return usage


def classify_term_status(
    term_key: str,
    definitions: list[dict],
    usage: set[str],
) -> str:
    """Return status: 'defined', 'orphaned', 'undefined', or 'conflicting'."""
    has_definition = bool(definitions)
    # Check for conflicting definitions
    if len(definitions) >= 2:
        snippets = [d.get("snippet") for d in definitions if d.get("snippet")]
        unique_snippets = set(snippets)
        if len(unique_snippets) >= 2:
            return "conflicting"

    defining_docs = {d["document_id"] for d in definitions}
    non_defining_usage = usage - defining_docs

    if has_definition and not non_defining_usage:
        return "orphaned"
    if has_definition:
        return "defined"
    return "undefined"


def detect_cross_document_dependencies(
    all_terms: dict,
    usage_map: dict[str, set[str]],
    deal_graph: dict,
) -> list[Finding]:
    """Find terms used across documents without explicit cross-references."""
    findings = []
    xrefs = deal_graph.get("cross_references", [])

    # Build set of (source_doc, target_doc) pairs from cross-references
    xref_pairs = {
        (x["source_document_id"], x["target_document_id"])
        for x in xrefs
    }

    for term_key, info in all_terms.items():
        for defn in info.get("definitions", []):
            defining_doc = defn["document_id"]
            using_docs = usage_map.get(term_key, set()) - {defining_doc}

            for using_doc in using_docs:
                if (using_doc, defining_doc) not in xref_pairs:
                    documents = deal_graph.get("documents", {})
                    using_name = documents.get(using_doc, {}).get("name", using_doc)
                    defining_name = documents.get(defining_doc, {}).get("name", defining_doc)

                    finding = Finding(
                        id=generate_finding_id("defined_terms", "cross_document_dependency",
                                               [defining_doc, using_doc, term_key]),
                        display_ordinal=0,
                        severity="WARNING",
                        category="cross_document_dependency",
                        title=f'"{info["term"]}" used in {using_name} without cross-reference',
                        description=f'The term "{info["term"]}" is defined in {defining_name} and '
                                    f"used in {using_name}, but {using_name} has no cross-reference "
                                    f"to {defining_name} for this term.",
                        affected_entities=[
                            AffectedEntity(entity_type="document", entity_id=defining_doc,
                                           document_id=defining_doc),
                            AffectedEntity(entity_type="document", entity_id=using_doc,
                                           document_id=using_doc),
                        ],
                        confidence="medium",
                        source="inferred",
                        verified=False,
                    )
                    findings.append(finding)

    return findings


def run_defined_terms_analysis(
    deal_graph: dict,
    anthropic_client=None,
    existing_results: dict | None = None,
) -> AnalysisResult:
    """Execute the full defined term tracking analysis."""
    all_findings: list[Finding] = []

    # Phase 1: Baseline
    baseline = load_baseline_terms(deal_graph)

    # Phase 2: Enhancement
    enhanced = find_enhanced_terms(deal_graph, baseline)
    for et in enhanced:
        key = et["term"].lower()
        if key not in baseline:
            baseline[key] = {"term": et["term"], "definitions": []}
        # Add enhanced term finding
        all_findings.append(Finding(
            id=generate_finding_id("defined_terms", "enhanced_term",
                                   [et["document_id"], key]),
            display_ordinal=0,
            severity="INFO",
            category="enhanced_term",
            title=f'Enhanced term found: "{et["term"]}"',
            description=f'Term "{et["term"]}" found via {et["source"]} in document '
                        f'{deal_graph.get("documents", {}).get(et["document_id"], {}).get("name", et["document_id"])}.',
            affected_entities=[
                AffectedEntity(entity_type="document", entity_id=et["document_id"],
                               document_id=et["document_id"]),
            ],
            confidence="medium",
            source="inferred",
            verified=False,
        ))

    # Usage tracking
    usage_map = track_term_usage(deal_graph, baseline)

    # Status classification and findings
    for term_key, info in baseline.items():
        status = classify_term_status(term_key, info.get("definitions", []), usage_map.get(term_key, set()))

        if status == "orphaned":
            doc_id = info["definitions"][0]["document_id"] if info["definitions"] else ""
            all_findings.append(Finding(
                id=generate_finding_id("defined_terms", "orphaned_definition", [doc_id, term_key]),
                display_ordinal=0, severity="WARNING", category="orphaned_definition",
                title=f'Orphaned definition: "{info["term"]}"',
                description=f'"{info["term"]}" is defined but never used in operative provisions.',
                affected_entities=[AffectedEntity(entity_type="defined_term", entity_id=term_key, document_id=doc_id)],
                confidence="medium", source="inferred", verified=False,
            ))
        elif status == "undefined":
            doc_ids = list(usage_map.get(term_key, set()))
            all_findings.append(Finding(
                id=generate_finding_id("defined_terms", "undefined_usage", doc_ids + [term_key]),
                display_ordinal=0, severity="ERROR", category="undefined_usage",
                title=f'Undefined term: "{info["term"]}"',
                description=f'"{info["term"]}" is used but never formally defined.',
                affected_entities=[AffectedEntity(entity_type="document", entity_id=d, document_id=d) for d in doc_ids[:3]],
                confidence="medium", source="inferred", verified=False,
            ))
        elif status == "conflicting":
            doc_ids = [d["document_id"] for d in info.get("definitions", [])]
            all_findings.append(Finding(
                id=generate_finding_id("defined_terms", "conflicting_definition", doc_ids + [term_key]),
                display_ordinal=0, severity="ERROR", category="conflicting_definition",
                title=f'Conflicting definitions: "{info["term"]}"',
                description=f'"{info["term"]}" is defined differently across documents.',
                affected_entities=[AffectedEntity(entity_type="document", entity_id=d, document_id=d) for d in doc_ids],
                confidence="high", source="explicit", verified=False,
            ))

    # Cross-document dependencies
    all_findings.extend(detect_cross_document_dependencies(baseline, usage_map, deal_graph))

    # Deduplicate and assign ordinals
    seen = set()
    unique = []
    for f in all_findings:
        if f.id not in seen:
            seen.add(f.id)
            unique.append(f)
    for i, f in enumerate(unique, 1):
        f.display_ordinal = i

    by_severity: dict[str, int] = {}
    for f in unique:
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1

    return AnalysisResult(
        analysis_type="defined_terms",
        status="completed", completion="complete",
        run_timestamp=datetime.now(timezone.utc).isoformat(),
        model_used="graph-analysis",
        findings=unique,
        summary=AnalysisSummary(
            total_findings=len(unique), by_severity=by_severity,
            key_findings=[f.title for f in unique[:5]],
        ),
        errors=[],
    )
