"""Core analysis logic for bough."""

import glob
import tomllib
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
        self.packages = {}
        self.dependency_graph = {}
        self._discover_packages()
        self._build_dependency_graph()
    
    def _discover_packages(self):
        """Discover all workspace packages."""
        # Read workspace root pyproject.toml
        root_pyproject = self.workspace_root / "pyproject.toml"
        with open(root_pyproject, "rb") as f:
            root_config = tomllib.load(f)
        
        # Get workspace members
        members = root_config.get("tool", {}).get("uv", {}).get("workspace", {}).get("members", [])
        
        # Find all package directories
        for member_pattern in members:
            pattern_path = self.workspace_root / member_pattern
            for package_dir in glob.glob(str(pattern_path)):
                package_path = Path(package_dir)
                pyproject_path = package_path / "pyproject.toml"
                
                if pyproject_path.exists():
                    with open(pyproject_path, "rb") as f:
                        package_config = tomllib.load(f)
                    
                    package_name = package_config["project"]["name"]
                    
                    # Parse dependencies from tool.uv.sources
                    uv_sources = package_config.get("tool", {}).get("uv", {}).get("sources", {})
                    dependencies = set()
                    for dep_name, source_config in uv_sources.items():
                        if source_config.get("workspace") is True:
                            dependencies.add(dep_name)
                    
                    self.packages[package_name] = Package(
                        name=package_name,
                        directory=package_path,
                        dependencies=dependencies
                    )
    
    def _build_dependency_graph(self):
        """Build reverse dependency graph (who depends on whom)."""
        # Initialize empty sets for all packages
        for package_name in self.packages:
            self.dependency_graph[package_name] = set()
        
        # Build reverse dependencies
        for package_name, package in self.packages.items():
            for dependency in package.dependencies:
                if dependency in self.dependency_graph:
                    self.dependency_graph[dependency].add(package_name)
