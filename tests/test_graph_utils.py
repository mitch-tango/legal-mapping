"""Tests for Split 02 Section 02 — Graph loading, canonicalization, and hashing."""

import json

import pytest

from src.semantic_analysis.graph_utils import canonicalize, compute_graph_hash, load_graph


class TestLoadGraph:
    def test_load_graph_returns_dict(self, tmp_path):
        graph_data = {"documents": {}, "relationships": []}
        (tmp_path / "deal-graph.json").write_text(json.dumps(graph_data))
        result = load_graph(tmp_path / "deal-graph.json")
        assert isinstance(result, dict)
        assert "documents" in result

    def test_load_graph_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="not found"):
            load_graph("/nonexistent/deal-graph.json")

    def test_load_graph_invalid_json(self, tmp_path):
        (tmp_path / "bad.json").write_text("not valid json {{{")
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_graph(tmp_path / "bad.json")


class TestCanonicalize:
    def test_sorts_object_keys(self):
        data = {"z": 1, "a": 2, "m": 3}
        result = canonicalize(data)
        assert list(result.keys()) == ["a", "m", "z"]

    def test_sorts_arrays_by_id(self):
        data = [{"id": "c", "x": 1}, {"id": "a", "x": 2}, {"id": "b", "x": 3}]
        result = canonicalize(data)
        assert [item["id"] for item in result] == ["a", "b", "c"]

    def test_sorts_primitive_arrays(self):
        data = [3, 1, 2]
        result = canonicalize(data)
        assert result == [1, 2, 3]

    def test_handles_nested_structures(self):
        data = {
            "z": {"b": 2, "a": 1},
            "a": [{"id": "2"}, {"id": "1"}],
        }
        result = canonicalize(data)
        assert list(result.keys()) == ["a", "z"]
        assert list(result["z"].keys()) == ["a", "b"]
        assert result["a"][0]["id"] == "1"


class TestComputeGraphHash:
    def test_stable_hash_despite_reordering(self):
        graph1 = {
            "documents": {"doc-b": {"id": "doc-b"}, "doc-a": {"id": "doc-a"}},
            "relationships": [{"id": "r2"}, {"id": "r1"}],
        }
        graph2 = {
            "relationships": [{"id": "r1"}, {"id": "r2"}],
            "documents": {"doc-a": {"id": "doc-a"}, "doc-b": {"id": "doc-b"}},
        }
        assert compute_graph_hash(graph1) == compute_graph_hash(graph2)

    def test_different_data_different_hash(self):
        graph1 = {"documents": {"doc-a": {"id": "doc-a"}}}
        graph2 = {"documents": {"doc-b": {"id": "doc-b"}}}
        assert compute_graph_hash(graph1) != compute_graph_hash(graph2)

    def test_returns_hex_string(self):
        h = compute_graph_hash({"test": True})
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic(self):
        graph = {"a": 1, "b": [3, 1, 2]}
        assert compute_graph_hash(graph) == compute_graph_hash(graph)
