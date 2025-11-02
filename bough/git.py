"""Handles git-based utility functions."""

from logging import getLogger
from pathlib import Path

import git

logger = getLogger(__name__)


def find_changed_files(root: Path, base_commit: str) -> set[str]:
    """Given the root of a repo and a base commit, finds all the files that have changed since that base commit."""
    repo = git.Repo(root)

    files = set()
    for item in repo.commit(base_commit).diff(repo.head.commit):
        if item.a_path:
            files.add(item.a_path)
        if item.b_path:
            files.add(item.b_path)

    for item in repo.untracked_files:
        files.add(item)

    for item in repo.index.diff(None):
        files.add(item.a_path)

    for item in repo.index.diff("HEAD"):
        files.add(item.a_path)

    logger.debug(
        f"Found {len(files)} changed files: {sorted(files)}",
    )
    return files
