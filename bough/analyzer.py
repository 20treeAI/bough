import fnmatch
import glob
import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Set

import git
from packaging.requirements import Requirement

from .config import BoughConfig, load_config

logger = logging.getLogger(__name__)


@dataclass
class Package:
    name: str
    directory: Path
    dependencies: Set[str]


class BoughAnalyzer:
    def __init__(self, workspace_root: Path, config: 'BoughConfig', packages: Dict[str, Package] = None):
        self.workspace_root = workspace_root
        logger.debug(f"Initializing analyzer for workspace: {workspace_root}")
        self.config = config
        self.packages = packages or {}
        self.dependency_graph = {}
        if packages is None:
            self._discover_packages()
        self._build_dependency_graph()
        logger.debug(f"Discovered {len(self.packages)} packages")

    @classmethod
    def from_workspace(cls, workspace_root: Path, config_path: Path):
        """Create analyzer by discovering packages from workspace."""
        config = load_config(config_path)
        return cls(workspace_root, config)

    def _discover_packages(self):
        root_pyproject = self.workspace_root / "pyproject.toml"
        logger.debug(f"Reading workspace config from {root_pyproject}")
        with open(root_pyproject, "rb") as f:
            root_config = tomllib.load(f)

        members = (
            root_config.get("tool", {})
            .get("uv", {})
            .get("workspace", {})
            .get("members", [])
        )
        logger.debug(f"Found workspace member patterns: {members}")

        for member_pattern in members:
            pattern_path = self.workspace_root / member_pattern
            logger.debug(f"Searching for packages matching: {pattern_path}")
            for package_dir in glob.glob(str(pattern_path)):
                package_path = Path(package_dir)
                pyproject_path = package_path / "pyproject.toml"

                if pyproject_path.exists():
                    logger.debug(f"Found package at {package_path}")
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
                        try:
                            dep_name = Requirement(dep_spec).name
                            dependencies.add(dep_name)
                        except Exception:
                            logger.debug(f"Skipping invalid dependency spec: {dep_spec}")

                    self.packages[package_name] = Package(
                        name=package_name,
                        directory=package_path,
                        dependencies=dependencies,
                    )
                    logger.debug(f"Added package {package_name} with dependencies: {dependencies}")

        # Filter dependencies to only include workspace packages
        all_package_names = set(self.packages.keys())
        logger.debug(f"All workspace packages: {all_package_names}")
        for package in self.packages.values():
            original_deps = package.dependencies.copy()
            workspace_deps = package.dependencies.intersection(all_package_names)
            package.dependencies = workspace_deps
            if original_deps != workspace_deps:
                filtered_out = original_deps - workspace_deps
                logger.debug(f"Package {package.name}: filtered out non-workspace deps {filtered_out}")

    def _build_dependency_graph(self):
        """Build reverse dependency graph (who depends on whom)."""
        logger.debug("Building dependency graph")
        for package_name in self.packages:
            self.dependency_graph[package_name] = set()

        for package_name, package in self.packages.items():
            for dependency in package.dependencies:
                if dependency in self.dependency_graph:
                    self.dependency_graph[dependency].add(package_name)
                    logger.debug(f"Added edge: {dependency} <- {package_name}")

    def _matches_patterns(self, path: str, patterns: list[str]) -> bool:
        for pattern in patterns:
            if fnmatch.fnmatch(path, pattern):
                return True
        return False

    def _is_buildable_package(self, package: Package) -> bool:
        package_rel_path = str(package.directory.relative_to(self.workspace_root))
        return self._matches_patterns(package_rel_path, self.config.buildable)

    def get_affected_packages(self, base_commit="HEAD^"):
        logger.debug(f"Analyzing changes from {base_commit} to HEAD")
        repo = git.Repo(self.workspace_root)

        changed_files = set()
        for item in repo.commit(base_commit).diff(repo.head.commit):
            if item.a_path:
                changed_files.add(item.a_path)
            if item.b_path:
                changed_files.add(item.b_path)
        
        logger.debug(f"Found {len(changed_files)} changed files: {sorted(changed_files)}")

        directly_affected = set()
        for file_path in changed_files:
            file_path_obj = Path(file_path)

            if self._matches_patterns(file_path, self.config.ignore):
                logger.debug(f"Ignoring file {file_path} (matches ignore patterns)")
                continue

            package_found = False
            for package_name, package in self.packages.items():
                package_rel_path = package.directory.relative_to(self.workspace_root)
                try:
                    file_path_obj.relative_to(package_rel_path)
                    directly_affected.add(package_name)
                    logger.debug(f"File {file_path} affects package {package_name}")
                    package_found = True
                    break
                except ValueError:
                    continue

            # Root file affects all packages
            if not package_found:
                logger.debug(f"Root file {file_path} affects all packages")
                directly_affected.update(self.packages.keys())
        
        logger.debug(f"Directly affected packages: {directly_affected}")

        # Calculate transitive dependencies
        logger.debug("Calculating transitive dependencies")
        all_affected = set(directly_affected)
        queue = list(directly_affected)

        while queue:
            pkg = queue.pop(0)
            dependents = self.dependency_graph.get(pkg, set())
            for dependent in dependents:
                if dependent not in all_affected:
                    logger.debug(f"Package {dependent} transitively affected by {pkg}")
                    all_affected.add(dependent)
                    queue.append(dependent)
        
        logger.debug(f"All affected packages (including transitive): {all_affected}")

        buildable_affected = set()
        for package_name in all_affected:
            package = self.packages[package_name]
            if self._is_buildable_package(package):
                buildable_affected.add(package_name)
                logger.debug(f"Package {package_name} is buildable")
            else:
                logger.debug(f"Package {package_name} is not buildable (filtered out)")

        logger.debug(f"Final buildable affected packages: {buildable_affected}")
        return buildable_affected
