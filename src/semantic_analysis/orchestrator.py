"""Main workflow orchestrator for the semantic analysis engine."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.semantic_analysis.analyses.conditions_precedent import run_conditions_precedent_analysis
from src.semantic_analysis.analyses.conflict_detection import run_conflict_detection
from src.semantic_analysis.analyses.defined_terms import run_defined_terms_analysis
from src.semantic_analysis.analyses.execution_sequence import run_execution_sequence_analysis
from src.semantic_analysis.analyses.hierarchy import run_hierarchy_analysis
from src.semantic_analysis.dependency_resolver import resolve_execution_order
from src.semantic_analysis.file_io import read_existing_results, write_results_incremental
from src.semantic_analysis.graph_utils import compute_graph_hash, load_graph
from src.semantic_analysis.schemas import (
    AnalysisMetadata,
    AnalysisResult,
    AnalysisResults,
    AnalysisSummary,
    StalenessRecord,
)
from src.semantic_analysis.staleness import ALL_ANALYSES, check_staleness, format_staleness_report

logger = logging.getLogger(__name__)

ANALYSIS_RUNNERS = {
    "hierarchy": lambda graph, existing, client: run_hierarchy_analysis(graph, client),
    "conflicts": lambda graph, existing, client: run_conflict_detection(
        graph,
        hierarchy_results=existing.analyses.get("hierarchy") if existing else None,
        term_results=existing.analyses.get("defined_terms") if existing else None,
        anthropic_client=client,
    ),
    "defined_terms": lambda graph, existing, client: run_defined_terms_analysis(graph, client),
    "conditions_precedent": lambda graph, existing, client: run_conditions_precedent_analysis(graph),
    "execution_sequence": lambda graph, existing, client: run_execution_sequence_analysis(graph, existing, client),
}


def run_analysis(
    deal_dir: str | Path,
    selected_analyses: list[str] | None = None,
    client=None,
) -> AnalysisResults:
    """Main workflow: load graph, check staleness, resolve order, execute, save."""
    deal_path = Path(deal_dir)
    graph_path = deal_path / "deal-graph.json"

    # 1. Load graph
    graph_data = load_graph(graph_path)
    graph_hash = compute_graph_hash(graph_data)

    # 2. Check staleness
    existing = read_existing_results(deal_path)
    staleness_records = check_staleness(graph_data, existing)
    logger.info(format_staleness_report(staleness_records))

    # 3. Resolve execution order
    if selected_analyses is None:
        selected_analyses = ALL_ANALYSES[:]

    batches = resolve_execution_order(selected_analyses)

    # 4. Execute in batch order
    for batch in batches:
        for analysis_type in batch:
            logger.info(f"Running {analysis_type} analysis...")
            try:
                # Re-read existing results to get latest (previous batch may have written)
                existing = read_existing_results(deal_path)

                runner = ANALYSIS_RUNNERS.get(analysis_type)
                if runner is None:
                    logger.error(f"No runner for analysis type: {analysis_type}")
                    continue

                result = runner(graph_data, existing, client)

                # Write incrementally
                now = datetime.now(timezone.utc).isoformat()
                staleness_rec = StalenessRecord(
                    is_stale=False,
                    last_run=now,
                    stale_reason=None,
                    graph_hash_at_run=graph_hash,
                )
                write_results_incremental(
                    deal_path, analysis_type, result, staleness_rec, graph_hash,
                )
                logger.info(f"  {analysis_type}: {result.summary.total_findings} findings")

            except Exception as e:
                logger.error(f"  {analysis_type} failed: {e}")
                # Write failed result
                failed_result = AnalysisResult(
                    analysis_type=analysis_type,
                    status="failed",
                    completion="failed",
                    run_timestamp=datetime.now(timezone.utc).isoformat(),
                    model_used="N/A",
                    findings=[],
                    summary=AnalysisSummary(
                        total_findings=0, by_severity={}, key_findings=[],
                    ),
                    errors=[str(e)],
                )
                now = datetime.now(timezone.utc).isoformat()
                write_results_incremental(
                    deal_path, analysis_type, failed_result,
                    StalenessRecord(
                        is_stale=True, last_run=now,
                        stale_reason=f"analysis failed: {e}",
                        graph_hash_at_run=graph_hash,
                    ),
                    graph_hash,
                )

    # 5. Return final results
    final = read_existing_results(deal_path)
    if final is None:
        final = AnalysisResults(
            schema_version="1.0.0",
            deal_graph_hash=graph_hash,
            analyses={},
            metadata=AnalysisMetadata(
                last_full_analysis=None,
                documents_included=list(graph_data.get("documents", {}).keys()),
                engine_version="0.1.0",
            ),
            staleness={},
        )
    return final
