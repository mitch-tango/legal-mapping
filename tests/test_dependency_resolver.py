"""Tests for Split 02 Section 04 — Dependency resolver."""

import pytest

from src.semantic_analysis.dependency_resolver import resolve_execution_order


class TestResolveExecutionOrder:
    def test_single_standalone(self):
        batches = resolve_execution_order(["hierarchy"])
        assert batches == [["hierarchy"]]

    def test_hard_dependency_auto_included(self):
        batches = resolve_execution_order(["conflicts"])
        # hierarchy must come before conflicts
        assert len(batches) == 2
        assert "hierarchy" in batches[0]
        assert "conflicts" in batches[1]

    def test_chain_dependency(self):
        batches = resolve_execution_order(["execution_sequence"])
        assert len(batches) == 2
        assert "conditions_precedent" in batches[0]
        assert "execution_sequence" in batches[1]

    def test_all_analyses(self):
        batches = resolve_execution_order([
            "hierarchy", "conflicts", "defined_terms",
            "conditions_precedent", "execution_sequence",
        ])
        # Batch 0: hierarchy, defined_terms, conditions_precedent (no deps)
        # Batch 1: conflicts (needs hierarchy), execution_sequence (needs CP)
        #   But conflicts also has soft dep on defined_terms, so it goes to batch 1
        assert len(batches) == 2
        assert set(batches[0]) == {"hierarchy", "defined_terms", "conditions_precedent"}
        assert set(batches[1]) == {"conflicts", "execution_sequence"}

    def test_includes_missing_prerequisites(self):
        batches = resolve_execution_order(["conflicts"])
        all_analyses = [a for batch in batches for a in batch]
        assert "hierarchy" in all_analyses
        assert "conflicts" in all_analyses

    def test_soft_dependency_included_when_available(self):
        # conflicts soft-depends on defined_terms
        # When both are selected, conflicts comes after defined_terms
        batches = resolve_execution_order(["conflicts", "defined_terms"])
        all_analyses = [a for batch in batches for a in batch]
        # defined_terms should appear in an earlier batch than conflicts
        dt_batch = next(i for i, b in enumerate(batches) if "defined_terms" in b)
        c_batch = next(i for i, b in enumerate(batches) if "conflicts" in b)
        assert dt_batch < c_batch

    def test_soft_dependency_skipped_when_unavailable(self):
        # Only selecting conflicts — defined_terms should NOT be auto-added
        batches = resolve_execution_order(["conflicts"])
        all_analyses = [a for batch in batches for a in batch]
        assert "defined_terms" not in all_analyses

    def test_no_duplicates(self):
        batches = resolve_execution_order(["hierarchy", "conflicts"])
        all_analyses = [a for batch in batches for a in batch]
        assert len(all_analyses) == len(set(all_analyses))
        assert all_analyses.count("hierarchy") == 1

    def test_empty_selection(self):
        assert resolve_execution_order([]) == []

    def test_invalid_name_raises(self):
        with pytest.raises(ValueError, match="Unknown"):
            resolve_execution_order(["nonexistent"])

    def test_deduplicates_input(self):
        batches = resolve_execution_order(["hierarchy", "hierarchy"])
        all_analyses = [a for batch in batches for a in batch]
        assert all_analyses.count("hierarchy") == 1
