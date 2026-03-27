"""Schema contract validator for Split 03 visualization integration."""

from __future__ import annotations

from src.semantic_analysis.schemas import AnalysisResults

KNOWN_ENTITY_TYPES = {"document", "relationship", "defined_term", "cross_reference", "condition_precedent", "condition"}
KNOWN_ANALYSIS_TYPES = {"hierarchy", "conflicts", "defined_terms", "conditions_precedent", "execution_sequence"}
SEVERITY_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO"}

VISUALIZATION_CONTRACT = {
    "conflict_markers": {
        "description": "Red/yellow/blue icons on edges colored by severity",
        "requires": {
            "analysis_key": "conflicts",
            "finding_fields": ["severity", "affected_entities"],
            "entity_types": ["relationship", "document"],
            "severity_to_color": {"CRITICAL": "red", "ERROR": "yellow", "WARNING": "blue"},
        },
    },
    "hierarchy_overlays": {
        "description": "Visual grouping of documents by controlling authority",
        "requires": {
            "analysis_key": "hierarchy",
            "finding_fields": ["category", "affected_entities"],
            "categories": [
                "controlling_authority", "dual_authority_conflict",
                "inferred_hierarchy", "explicit_hierarchy",
            ],
        },
    },
    "term_flow_paths": {
        "description": "Lines showing where defined terms travel across documents",
        "requires": {
            "analysis_key": "defined_terms",
            "finding_fields": ["affected_entities"],
            "entity_types": ["defined_term"],
        },
    },
    "missing_document_indicators": {
        "description": "Dashed-outline nodes for referenced but absent documents",
        "requires": {
            "analysis_key": "conflicts",
            "finding_fields": ["category", "affected_entities"],
            "categories": ["missing_document"],
        },
    },
    "execution_checklist": {
        "description": "Step-by-step closing checklist with conditions and dependencies",
        "requires": {
            "analysis_key": "execution_sequence",
            "finding_fields": ["display_ordinal", "category", "affected_entities"],
        },
    },
}


def validate_for_visualization(analysis_results: AnalysisResults) -> list[str]:
    """Validate that analysis results meet Split 03's requirements.

    Returns list of violation messages (empty = visualization-ready).
    """
    violations = []

    # Check schema version
    if not analysis_results.schema_version:
        violations.append("Missing schema_version")

    # Check analysis keys
    for key in analysis_results.analyses:
        if key not in KNOWN_ANALYSIS_TYPES:
            violations.append(f"Unknown analysis type: {key}")

    # Check findings in each analysis
    for analysis_type, result in analysis_results.analyses.items():
        for i, finding in enumerate(result.findings):
            # Severity check
            if finding.severity not in SEVERITY_LEVELS:
                violations.append(
                    f"{analysis_type} finding {i}: invalid severity '{finding.severity}'"
                )

            # Affected entities check
            if not finding.affected_entities:
                violations.append(
                    f"{analysis_type} finding {i} '{finding.title}': empty affected_entities"
                )

            for entity in finding.affected_entities:
                if entity.entity_type not in KNOWN_ENTITY_TYPES:
                    violations.append(
                        f"{analysis_type} finding {i}: unknown entity_type '{entity.entity_type}'"
                    )
                if not entity.document_id:
                    violations.append(
                        f"{analysis_type} finding {i}: empty document_id on affected entity"
                    )

        # Summary consistency check
        actual_counts: dict[str, int] = {}
        for f in result.findings:
            actual_counts[f.severity] = actual_counts.get(f.severity, 0) + 1

        for sev, count in result.summary.by_severity.items():
            if actual_counts.get(sev, 0) != count:
                violations.append(
                    f"{analysis_type}: summary says {sev}={count} but "
                    f"actual count is {actual_counts.get(sev, 0)}"
                )

    return violations
