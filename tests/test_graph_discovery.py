"""Test dependency graph discovery."""

import shutil
from pathlib import Path

import git
import pytest

from bough.core import BoughAnalyzer


@pytest.fixture
def sample_workspace(tmp_path):
    """Copy sample workspace to temp directory."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample-workspace"
    workspace_path = tmp_path / "workspace"
    shutil.copytree(fixture_path, workspace_path)
    return workspace_path


@pytest.fixture
def git_workspace(sample_workspace):
    """Create a git repository with sample workspace and initial commit."""
    # Initialize git repo
    repo = git.Repo.init(sample_workspace)
    
    # Configure git
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")
    
    # Add all files and make initial commit
    repo.git.add(".")
    repo.index.commit("Initial commit")
    
    return sample_workspace


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


@pytest.mark.parametrize("changed_file,expected_affected", [
    # Change auth package -> only api is affected (api depends on auth)
    ("packages/auth/auth.py", {"api"}),
    
    # Change database package -> both api and web affected (both depend on database transitively)
    ("packages/database/database.py", {"api", "web"}),
    
    # Change shared package -> both api and web affected (both depend on shared)
    ("packages/shared/shared.py", {"api", "web"}),
    
    # Change api package -> only api affected (it's the package itself)
    ("apps/api/api.py", {"api"}),
    
    # Change web package -> only web affected (it's the package itself)
    ("apps/web/web.py", {"web"}),
    
    # Change root pyproject.toml -> all buildable packages affected
    ("pyproject.toml", {"api", "web"}),
    
    # Change README.md -> no packages affected (ignored file type)
    ("README.md", set()),
    
    # Change file in package subdirectory -> affects that package
    ("packages/auth/utils/helpers.py", {"api"}),
])
def test_git_change_detection(git_workspace, changed_file, expected_affected):
    """Test that we correctly detect affected packages from git changes."""
    repo = git.Repo(git_workspace)
    
    # Make a change to the specified file
    file_path = git_workspace / changed_file
    
    # Create parent directories if they don't exist
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create or modify the file
    with open(file_path, "a") as f:
        f.write("\n# Added comment\n")
    
    # Commit the change
    repo.git.add(".")
    repo.index.commit(f"Update {changed_file}")
    
    analyzer = BoughAnalyzer(git_workspace)
    
    # This should detect what changed and find affected packages
    affected = analyzer.get_affected_packages()
    
    assert affected == expected_affected
