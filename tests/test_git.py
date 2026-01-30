import tempfile
from pathlib import Path

import git
import pytest

import bough.git as sut


@pytest.fixture
def git_repo():
    """Create a temporary git repo for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "guardians"
        repo = git.Repo.init(repo_path)

        (repo_path / "members.txt").write_text("star-lord\n")
        (repo_path / "README.txt").write_text("TODO")
        repo.index.add(["members.txt", "README.txt"])
        repo.index.commit("Initial commit")

        yield repo_path, repo


def test_finds_various_changed_files(git_repo):
    """Test detection of committed, staged, unstaged, and untracked changes."""
    repo_path, repo = git_repo
    base_commit = repo.head.commit.hexsha

    (repo_path / "members.txt").write_text("rocky raccoon\ngroot\n")
    repo.index.add(["members.txt"])
    repo.index.commit("Add members")

    (repo_path / "enemies.txt").write_text("nova core\n")
    (repo_path / "members.txt").write_text("gamora\n")
    repo.index.add(["enemies.txt", "members.txt"])

    (repo_path / "powers.txt").write_text("awesomeness\n")
    (repo_path / "assets.txt").write_text("infinity stone\n")

    files = sut.find_changed_files(repo_path, base_commit)
    assert files == {"members.txt", "enemies.txt", "powers.txt", "assets.txt"}

    repo.index.commit("Add members and enemies")
    (repo_path / "README.txt").write_text("A little bit of both...\n")
    repo.index.add(["powers.txt"])

    files = sut.find_changed_files(repo_path, repo.head.commit.hexsha)
    assert files == {"powers.txt", "assets.txt", "README.txt"}
