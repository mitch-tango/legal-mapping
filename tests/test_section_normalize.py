"""Tests for Split 02 Section 02 — Section reference normalization."""

from src.semantic_analysis.section_normalize import (
    SectionMatch,
    batch_normalize,
    match_section_ref,
    normalize_section_ref,
)


class TestNormalizeSectionRef:
    def test_strips_section_prefix(self):
        assert normalize_section_ref("Section 4.2") == "4.2"

    def test_case_insensitive_prefix(self):
        assert normalize_section_ref("SECTION 4.2") == "4.2"

    def test_trailing_zeros(self):
        assert normalize_section_ref("1.01") == "1.1"
        assert normalize_section_ref("1.10") == "1.1"

    def test_preserves_parenthetical(self):
        result = normalize_section_ref("1.01(a)")
        assert "(a)" in result

    def test_strips_whitespace(self):
        assert normalize_section_ref("  Section   4.2  ") == "4.2"


class TestMatchSectionRef:
    INVENTORY = ["Section 2.1", "4.2", "Section 5.2(b)", "1.1", "Section 7.1"]

    def test_exact_match(self):
        result = match_section_ref("Section 4.2", ["Section 4.2", "5.1"])
        assert result.match_type == "exact"
        assert result.matched_ref == "Section 4.2"

    def test_strip_section_prefix(self):
        result = match_section_ref("Section 4.2", ["4.2", "5.1"])
        assert result.match_type == "exact"
        assert result.matched_ref == "4.2"

    def test_case_insensitive(self):
        result = match_section_ref("section 4.2", ["Section 4.2"])
        assert result.match_type == "exact"

    def test_normalize_trailing_zeros(self):
        result = match_section_ref("Section 1.01", self.INVENTORY)
        assert result.match_type == "normalized"
        assert result.matched_ref == "1.1"

    def test_no_match(self):
        result = match_section_ref("Section 99.99", self.INVENTORY)
        assert result.match_type in ("suggestion", "none")
        if result.match_type == "none":
            assert result.matched_ref is None

    def test_suggestion_by_edit_distance(self):
        # "7.2" is close to "7.1"
        result = match_section_ref("7.2", self.INVENTORY)
        assert result.match_type == "suggestion"
        assert result.edit_distance is not None
        assert result.edit_distance <= 3

    def test_empty_inventory(self):
        result = match_section_ref("Section 1.1", [])
        assert result.match_type == "none"


class TestBatchNormalize:
    def test_processes_list(self):
        refs = ["Section 2.1", "Section 99.99"]
        inventory = ["2.1", "5.2"]
        results = batch_normalize(refs, inventory)
        assert len(results) == 2
        assert results[0].match_type == "exact"
