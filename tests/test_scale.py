"""Tests for Split 02 Section 11 — Scale handling."""

import json

from src.semantic_analysis.scale import (
    CHARS_PER_TOKEN,
    CLUSTER_THRESHOLD_RATIO,
    MODEL_CONTEXT_WINDOW,
    cluster_graph,
    deduplicate_findings,
    estimate_tokens,
    should_cluster,
)
from src.semantic_analysis.schemas import AffectedEntity, Finding


def _make_finding(fid, confidence="high", cluster_id=None):
    return Finding(
        id=fid, display_ordinal=1, severity="WARNING",
        category="test", title=f"Finding {fid}", description="test",
        affected_entities=[AffectedEntity(entity_type="document", entity_id="d1", document_id="d1")],
        confidence=confidence, source="inferred", verified=False,
        found_in_clusters=[cluster_id] if cluster_id else None,
    )


class TestTokenEstimation:
    def test_small_deal_single_call(self, minimal_deal_graph):
        graph_json = json.dumps(minimal_deal_graph)
        tokens = estimate_tokens(graph_json)
        threshold = int(MODEL_CONTEXT_WINDOW * CLUSTER_THRESHOLD_RATIO)
        assert tokens < threshold
        assert should_cluster(graph_json) is False

    def test_estimation_from_json_size(self):
        # 4000 chars -> ~1000 tokens
        graph_json = "x" * 4000
        tokens = estimate_tokens(graph_json)
        expected = 4000 // CHARS_PER_TOKEN
        assert abs(tokens - expected) / expected < 0.2  # Within 20%

    def test_large_graph_triggers_clustering(self):
        # Create a very large JSON string
        threshold = int(MODEL_CONTEXT_WINDOW * CLUSTER_THRESHOLD_RATIO)
        large_json = "x" * (threshold * CHARS_PER_TOKEN + 1000)
        assert should_cluster(large_json) is True


class TestClustering:
    def test_clustering_returns_clusters(self, minimal_deal_graph):
        clusters = cluster_graph(minimal_deal_graph)
        assert isinstance(clusters, list)
        assert len(clusters) >= 1

    def test_cluster_has_documents(self, minimal_deal_graph):
        clusters = cluster_graph(minimal_deal_graph)
        for cluster in clusters:
            assert "cluster_id" in cluster
            assert "documents" in cluster


class TestDeduplication:
    def test_same_id_deduplicated(self):
        f1 = _make_finding("f001", confidence="high")
        f2 = _make_finding("f001", confidence="medium")
        result = deduplicate_findings([
            ("cluster-a", [f1]),
            ("cluster-b", [f2]),
        ])
        assert len(result) == 1

    def test_keeps_higher_confidence(self):
        f1 = _make_finding("f001", confidence="medium")
        f2 = _make_finding("f001", confidence="high")
        result = deduplicate_findings([
            ("cluster-a", [f1]),
            ("cluster-b", [f2]),
        ])
        assert result[0].confidence == "high"

    def test_provenance_tracks_clusters(self):
        f1 = _make_finding("f001")
        f2 = _make_finding("f001")
        result = deduplicate_findings([
            ("insurance", [f1]),
            ("capital-calls", [f2]),
        ])
        assert result[0].found_in_clusters is not None
        assert "insurance" in result[0].found_in_clusters
        assert "capital-calls" in result[0].found_in_clusters

    def test_unique_findings_not_merged(self):
        f1 = _make_finding("f001")
        f2 = _make_finding("f002")
        result = deduplicate_findings([
            ("cluster-a", [f1, f2]),
        ])
        assert len(result) == 2
