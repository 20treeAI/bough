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
    name: str
    directory: Path
    dependencies: Set[str]


class BoughAnalyzer:
    def __init__(self, workspace_root: Path, config_path: Path):
        self.workspace_root = workspace_root
        self.config = load_config(config_path)
        self.packages = {}
        self.dependency_graph = {}
        self._discover_packages()
        self._build_dependency_graph()

    def _discover_packages(self):
        root_pyproject = self.workspace_root / "pyproject.toml"
        with open(root_pyproject, "rb") as f:
            root_config = tomllib.load(f)

        members = (
            root_config.get("tool", {})
            .get("uv", {})
            .get("workspace", {})
            .get("members", [])
        )

        for member_pattern in members:
            pattern_path = self.workspace_root / member_pattern
            for package_dir in glob.glob(str(pattern_path)):
                package_path = Path(package_dir)
                pyproject_path = package_path / "pyproject.toml"

                if pyproject_path.exists():
                    with open(pyproject_path, "rb") as f:
                        package_config = tomllib.load(f)

                    package_name = package_config["project"]["name"]
                    dependencies = set()

                    # Method 1: tool.uv.sources (explicit workspace deps)
                    uv_sources = (
                        package_config.get("tool", {}).get("uv", {}).get("sources", {})
                    )
                    for dep_name, source_config in uv_sources.items():
                        if source_config.get("workspace") is True:
                            dependencies.add(dep_name)

                    # Method 2: Check if regular dependencies are workspace packages
                    project_deps = package_config.get("project", {}).get(
                        "dependencies", []
                    )
                    for dep_spec in project_deps:
                        # Extract package name from dependency spec (e.g., "package>=1.0" -> "package")
                        dep_name = (
                            dep_spec.split(">=")[0]
                            .split("==")[0]
                            .split("~=")[0]
                            .split(">")[0]
                            .split("<")[0]
                            .split("!")[0]
                            .split("[")[0]
                            .strip()
                        )
                        dependencies.add(dep_name)

                    self.packages[package_name] = Package(
                        name=package_name,
                        directory=package_path,
                        dependencies=dependencies,
                    )

        # Filter dependencies to only include workspace packages
        all_package_names = set(self.packages.keys())
        for package in self.packages.values():
            workspace_deps = package.dependencies.intersection(all_package_names)
            package.dependencies = workspace_deps

    def _build_dependency_graph(self):
        """Build reverse dependency graph (who depends on whom)."""
        for package_name in self.packages:
            self.dependency_graph[package_name] = set()

        for package_name, package in self.packages.items():
            for dependency in package.dependencies:
                if dependency in self.dependency_graph:
                    self.dependency_graph[dependency].add(package_name)

    def _matches_patterns(self, path: str, patterns: list[str]) -> bool:
        for pattern in patterns:
            if fnmatch.fnmatch(path, pattern):
                return True
        return False

    def _is_buildable_package(self, package: Package) -> bool:
        package_rel_path = str(package.directory.relative_to(self.workspace_root))
        return self._matches_patterns(package_rel_path, self.config.buildable)

    def get_affected_packages(self, base_commit="HEAD^"):
        repo = git.Repo(self.workspace_root)

        changed_files = set()
        for item in repo.commit(base_commit).diff(repo.head.commit):
            if item.a_path:
                changed_files.add(item.a_path)
            if item.b_path:
                changed_files.add(item.b_path)

        directly_affected = set()
        for file_path in changed_files:
            file_path_obj = Path(file_path)

            if self._matches_patterns(file_path, self.config.ignore):
                continue

            package_found = False
            for package_name, package in self.packages.items():
                package_rel_path = package.directory.relative_to(self.workspace_root)
                try:
                    file_path_obj.relative_to(package_rel_path)
                    directly_affected.add(package_name)
                    package_found = True
                    break
                except ValueError:
                    continue

            # Root file affects all packages
            if not package_found:
                directly_affected.update(self.packages.keys())

        # Calculate transitive dependencies
        all_affected = set(directly_affected)
        queue = list(directly_affected)

        while queue:
            pkg = queue.pop(0)
            dependents = self.dependency_graph.get(pkg, set())
            for dependent in dependents:
                if dependent not in all_affected:
                    all_affected.add(dependent)
                    queue.append(dependent)

        buildable_affected = set()
        for package_name in all_affected:
            package = self.packages[package_name]
            if self._is_buildable_package(package):
                buildable_affected.add(package_name)

        return buildable_affected
