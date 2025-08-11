"""Shared test fixtures."""

import shutil
from pathlib import Path

import git
import pytest


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


@pytest.fixture
def empty_config(tmp_path):
    """Create an empty config file for testing."""
    config_path = tmp_path / ".bough.yml"
    config_path.write_text("")
    return config_path
