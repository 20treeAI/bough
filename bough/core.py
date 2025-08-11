"""Core analysis logic for bough."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Set


@dataclass
class Package:
    """Represents a workspace package."""
    name: str
    directory: Path
    dependencies: Set[str]


class BoughAnalyzer:
    """Analyzes workspace dependencies and git changes."""
    
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        # These will fail the test until implemented
        self.packages = {}
        self.dependency_graph = {}
