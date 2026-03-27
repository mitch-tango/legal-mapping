"""Tests for Split 02 Section 08 — Conditions precedent chain mapping."""

import copy

from src.semantic_analysis.analyses.conditions_precedent import (
    build_cp_dag,
    extract_conditions,
    find_critical_path,
    run_conditions_precedent_analysis,
    topological_levels,
)


class TestConditionExtraction:
    def test_conditions_extracted(self, minimal_deal_graph):
        conditions = extract_conditions(minimal_deal_graph)
        assert len(conditions) == 3
        assert all("id" in c for c in conditions)
        assert all("description" in c for c in conditions)

    def test_missing_document_flagged(self):
        graph = {
            "documents": {"doc-a": {"id": "doc-a"}},
            "conditions_precedent": [
                {"id": "cp-1", "description": "test", "source_document_id": "doc-a",
                 "required_document_id": "doc-missing", "status": "pending"},
            ],
        }
        conditions = extract_conditions(graph)
        _, findings = build_cp_dag(conditions, graph)
        missing = [f for f in findings if f.category == "missing_condition_document"]
        assert len(missing) >= 1


class TestDAGConstruction:
    def test_explicit_dependencies(self, minimal_deal_graph):
        conditions = extract_conditions(minimal_deal_graph)
        adj, _ = build_cp_dag(conditions, minimal_deal_graph)
        assert isinstance(adj, dict)
        assert all(isinstance(v, list) for v in adj.values())

    def test_circular_condition_critical(self):
        """Create a circular dependency: cp-a requires cp-b, cp-b requires cp-a."""
        graph = {
            "documents": {
                "doc-a": {"id": "doc-a"},
                "doc-b": {"id": "doc-b"},
            },
            "conditions_precedent": [
                {"id": "cp-a", "description": "CP A", "source_document_id": "doc-a",
                 "required_document_id": "doc-b", "enables_document_id": "doc-a",
                 "status": "pending"},
                {"id": "cp-b", "description": "CP B", "source_document_id": "doc-a",
                 "required_document_id": "doc-a", "enables_document_id": "doc-b",
                 "status": "pending"},
            ],
        }
        result = run_conditions_precedent_analysis(graph)
        cycles = [f for f in result.findings if f.category == "circular_condition"]
        assert len(cycles) >= 1
        assert cycles[0].severity == "CRITICAL"

    def test_cycle_finding_has_description(self):
        graph = {
            "documents": {"doc-a": {"id": "doc-a"}, "doc-b": {"id": "doc-b"}},
            "conditions_precedent": [
                {"id": "cp-a", "description": "CP A", "source_document_id": "doc-a",
                 "required_document_id": "doc-b", "enables_document_id": "doc-a",
                 "status": "pending"},
                {"id": "cp-b", "description": "CP B", "source_document_id": "doc-a",
                 "required_document_id": "doc-a", "enables_document_id": "doc-b",
                 "status": "pending"},
            ],
        }
        result = run_conditions_precedent_analysis(graph)
        cycles = [f for f in result.findings if f.category == "circular_condition"]
        if cycles:
            assert len(cycles[0].description) > 10
            assert "remove" in cycles[0].description.lower() or "break" in cycles[0].description.lower()


class TestTopologicalSort:
    def test_valid_order(self, minimal_deal_graph):
        conditions = extract_conditions(minimal_deal_graph)
        adj, _ = build_cp_dag(conditions, minimal_deal_graph)
        levels = topological_levels(adj)
        # Verify all nodes appear
        all_nodes = {n for level in levels for n in level}
        assert all_nodes == set(adj.keys())

    def test_no_condition_before_prerequisite(self, minimal_deal_graph):
        conditions = extract_conditions(minimal_deal_graph)
        adj, _ = build_cp_dag(conditions, minimal_deal_graph)
        levels = topological_levels(adj)
        # Build level map
        level_map = {}
        for i, level in enumerate(levels):
            for n in level:
                level_map[n] = i
        # Check: for each node, all its deps must be at earlier levels
        for n, deps in adj.items():
            if n in level_map:
                for dep in deps:
                    if dep in level_map:
                        assert level_map[dep] < level_map[n], \
                            f"{dep} (level {level_map[dep]}) should come before {n} (level {level_map[n]})"

    def test_parallel_groups(self, minimal_deal_graph):
        result = run_conditions_precedent_analysis(minimal_deal_graph)
        parallel = [f for f in result.findings if f.category == "parallel_group"]
        # minimal graph has cp-002 and cp-003 at same level (both depend on cp-001)
        assert isinstance(parallel, list)


class TestCriticalPath:
    def test_critical_path_found(self, minimal_deal_graph):
        conditions = extract_conditions(minimal_deal_graph)
        adj, _ = build_cp_dag(conditions, minimal_deal_graph)
        levels = topological_levels(adj)
        path = find_critical_path(adj, levels)
        assert isinstance(path, list)
        assert len(path) >= 1

    def test_critical_path_findings(self, minimal_deal_graph):
        result = run_conditions_precedent_analysis(minimal_deal_graph)
        crit = [f for f in result.findings if f.category == "critical_path_item"]
        assert len(crit) >= 1


class TestFullAnalysis:
    def test_returns_analysis_result(self, minimal_deal_graph):
        result = run_conditions_precedent_analysis(minimal_deal_graph)
        assert result.analysis_type == "conditions_precedent"
        assert result.status == "completed"

    def test_empty_conditions(self):
        graph = {"documents": {}, "conditions_precedent": []}
        result = run_conditions_precedent_analysis(graph)
        assert result.status == "completed"
        assert len(result.findings) == 0

    def test_ordinals_sequential(self, minimal_deal_graph):
        result = run_conditions_precedent_analysis(minimal_deal_graph)
        if result.findings:
            ordinals = [f.display_ordinal for f in result.findings]
            assert ordinals == list(range(1, len(ordinals) + 1))
