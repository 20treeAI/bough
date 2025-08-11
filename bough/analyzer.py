"""Core analysis logic for bough."""

import fnmatch
import glob
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Set

import git

from .config import load_config


@dataclass
class Package:
    """Represents a workspace package."""

    name: str
    directory: Path
    dependencies: Set[str]


class BoughAnalyzer:
    """Analyzes workspace dependencies and git changes."""

    def __init__(self, workspace_root: Path, config_path: Path):
        self.workspace_root = workspace_root
        self.config = load_config(config_path)
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
        members = (
            root_config.get("tool", {})
            .get("uv", {})
            .get("workspace", {})
            .get("members", [])
        )

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
                    uv_sources = (
                        package_config.get("tool", {}).get("uv", {}).get("sources", {})
                    )
                    dependencies = set()
                    for dep_name, source_config in uv_sources.items():
                        if source_config.get("workspace") is True:
                            dependencies.add(dep_name)
                    
                    # Debug: print what we found
                    print(f"DEBUG: Package {package_name} at {package_path}")
                    print(f"DEBUG: uv_sources = {uv_sources}")
                    print(f"DEBUG: dependencies = {dependencies}")

                    self.packages[package_name] = Package(
                        name=package_name,
                        directory=package_path,
                        dependencies=dependencies,
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

    def _matches_patterns(self, path: str, patterns: list[str]) -> bool:
        """Check if a path matches any of the given glob patterns."""
        for pattern in patterns:
            if fnmatch.fnmatch(path, pattern):
                return True
        return False

    def _is_buildable_package(self, package: Package) -> bool:
        """Check if a package matches buildable patterns."""
        package_rel_path = str(package.directory.relative_to(self.workspace_root))
        return self._matches_patterns(package_rel_path, self.config.buildable)

    def get_affected_packages(self, base_commit="HEAD^"):
        """Get packages affected by git changes since base_commit."""
        repo = git.Repo(self.workspace_root)

        # Get changed files
        changed_files = set()
        for item in repo.commit(base_commit).diff(repo.head.commit):
            if item.a_path:
                changed_files.add(item.a_path)
            if item.b_path:
                changed_files.add(item.b_path)

        # Map changed files to affected packages
        directly_affected = set()
        for file_path in changed_files:
            file_path_obj = Path(file_path)

            # Skip ignored files
            if self._matches_patterns(file_path, self.config.ignore):
                continue

            # Check if file belongs to a specific package
            package_found = False
            for package_name, package in self.packages.items():
                package_rel_path = package.directory.relative_to(self.workspace_root)
                try:
                    file_path_obj.relative_to(package_rel_path)
                    directly_affected.add(package_name)
                    package_found = True
                    break
                except ValueError:
                    # File is not in this package directory
                    continue

            # If file doesn't belong to any package, it's a root file
            if not package_found:
                directly_affected.update(self.packages.keys())

        # Calculate transitive dependencies
        all_affected = set(directly_affected)
        queue = list(directly_affected)

        while queue:
            pkg = queue.pop(0)
            # Find packages that depend on this one
            dependents = self.dependency_graph.get(pkg, set())
            for dependent in dependents:
                if dependent not in all_affected:
                    all_affected.add(dependent)
                    queue.append(dependent)

        # Filter to buildable packages only
        buildable_affected = set()
        for package_name in all_affected:
            package = self.packages[package_name]
            if self._is_buildable_package(package):
                buildable_affected.add(package_name)

        return buildable_affected
