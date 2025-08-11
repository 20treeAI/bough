"""Test dependency graph discovery."""

import shutil
from pathlib import Path

import pytest

from bough.core import BoughAnalyzer


@pytest.fixture
def sample_workspace(tmp_path):
    """Copy sample workspace to temp directory."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample-workspace"
    workspace_path = tmp_path / "workspace"
    shutil.copytree(fixture_path, workspace_path)
    return workspace_path


def test_dependency_graph_discovery(sample_workspace):
    """Test that we correctly discover the dependency graph from workspace."""
    analyzer = BoughAnalyzer(sample_workspace)
    
    # Verify packages were discovered
    expected_packages = {"auth", "database", "shared", "api", "web"}
    assert set(analyzer.packages.keys()) == expected_packages
    
    # Verify dependencies were parsed correctly
    assert analyzer.packages["auth"].dependencies == set()
    assert analyzer.packages["database"].dependencies == set()
    assert analyzer.packages["shared"].dependencies == {"database"}
    assert analyzer.packages["api"].dependencies == {"auth", "database", "shared"}
    assert analyzer.packages["web"].dependencies == {"shared"}
    
    # Verify dependency graph (who depends on whom)
    # database is depended on by shared and api
    assert analyzer.dependency_graph["database"] == {"shared", "api"}
    # shared is depended on by api and web
    assert analyzer.dependency_graph["shared"] == {"api", "web"}
    # auth is only depended on by api
    assert analyzer.dependency_graph["auth"] == {"api"}
    # api and web have no dependents
    assert analyzer.dependency_graph["api"] == set()
    assert analyzer.dependency_graph["web"] == set()
