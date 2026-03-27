"""Tests for Section 01 — Foundation (project structure and imports)."""

from pathlib import Path


def test_src_package_importable():
    import src
    assert src is not None


def test_src_models_package_importable():
    import src.models
    assert src.models is not None


def test_src_extraction_package_importable():
    import src.extraction
    assert src.extraction is not None


def test_src_graph_package_importable():
    import src.graph
    assert src.graph is not None


def test_fixtures_directory_exists(fixtures_dir):
    assert fixtures_dir.is_dir(), f"Fixtures directory does not exist: {fixtures_dir}"


def test_pyproject_declares_core_dependencies():
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    assert pyproject_path.exists(), "pyproject.toml not found"
    content = pyproject_path.read_text()
    for dep in ["anthropic", "pydantic", "python-docx", "pypdf"]:
        assert dep in content, f"Missing dependency: {dep}"


def test_pytest_available():
    import pytest
    assert pytest is not None
