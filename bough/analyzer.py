"""The main module for analyzing uv workspaces."""

import fnmatch
import glob
import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NamedTuple

from packaging.requirements import Requirement

from .config import BoughConfig, load_config
from .git import find_changed_files

logger = logging.getLogger(__name__)

Selection = Literal["buildable", "all"]


@dataclass
class Package:
    """A single package in a uv workspace."""

    name: str
    directory: Path
    dependencies: set[str]


class AnalysisResult(NamedTuple):
    """The packages and files affected for a given analysis."""

    packages: set[str]
    files: set[str]


class BoughAnalyzer:
    """The main analyzer tool -- given a workspace, it discovers the dependency graph and is then ready for analysis."""

    def __init__(
        self,
        repo_root: Path,
        workspace_root: Path,
        config: "BoughConfig",
        packages: dict[str, Package] | None = None,
    ) -> None:
        self.repo_root = repo_root
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
    def from_workspace(
        cls, repo_root: Path, workspace_root: Path, config_path: Path
    ) -> "BoughAnalyzer":
        """Create analyzer by discovering packages from workspace."""
        config = load_config(config_path)
        return cls(repo_root, workspace_root, config)

    def _discover_packages(self) -> None:
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
                        if (
                            isinstance(source_config, dict)
                            and source_config.get("workspace") is True
                        ):
                            dependencies.add(dep_name)

                    # Method 2: Check if regular dependencies are workspace packages
                    project_deps = package_config.get("project", {}).get(
                        "dependencies",
                        [],
                    )
                    for dep_spec in project_deps:
                        try:
                            dep_name = Requirement(dep_spec).name
                            dependencies.add(dep_name)
                        except Exception:
                            logger.debug(
                                f"Skipping invalid dependency spec: {dep_spec}",
                            )

                    self.packages[package_name] = Package(
                        name=package_name,
                        directory=package_path,
                        dependencies=dependencies,
                    )
                    logger.debug(
                        f"Added package {package_name} with dependencies: {dependencies}",
                    )

        # Filter dependencies to only include workspace packages
        all_package_names = set(self.packages.keys())
        logger.debug(f"All workspace packages: {all_package_names}")
        for package in self.packages.values():
            original_deps = package.dependencies.copy()
            workspace_deps = package.dependencies.intersection(all_package_names)
            package.dependencies = workspace_deps
            if original_deps != workspace_deps:
                filtered_out = original_deps - workspace_deps
                logger.debug(
                    f"Package {package.name}: filtered out non-workspace deps {filtered_out}",
                )

    def _build_dependency_graph(self) -> None:
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
        return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)

    def _is_buildable_package(self, package: Package) -> bool:
        package_rel_path = str(package.directory.relative_to(self.workspace_root))
        return self._matches_patterns(package_rel_path, self.config.buildable)

    def _find_direct_packages(
        self,
        changed_files: set[str],
    ) -> set[str]:
        directly_affected = set()
        strip_prefix = self.workspace_root.relative_to(self.repo_root)
        for file_path in changed_files:
            file_path_obj = Path(file_path).relative_to(strip_prefix)

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

            if not package_found:
                logger.debug(f"Root file {file_path} affects all packages")
                directly_affected.update(self.packages.keys())

        logger.debug(f"Directly affected packages: {directly_affected}")
        return directly_affected

    def _find_transitive_packages(self, directly_affected: set[str]) -> set[str]:
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
        return all_affected

    def find_affected(
        self,
        base_commit: str = "HEAD^",
        selection: Selection = "buildable",
    ) -> AnalysisResult:
        """Return the affected packages and files."""
        logger.debug(f"Analyzing changes from {base_commit} to HEAD")

        files = find_changed_files(self.repo_root, base_commit)
        all_affected = self._find_transitive_packages(self._find_direct_packages(files))

        if selection != "buildable":
            return AnalysisResult(all_affected, files)

        buildable_affected = set()
        for package_name in all_affected:
            package = self.packages[package_name]
            if self._is_buildable_package(package):
                buildable_affected.add(package_name)
                logger.debug(f"Package {package_name} is buildable")
            else:
                logger.debug(f"Package {package_name} is not buildable (filtered out)")

        logger.debug(f"Final buildable affected packages: {buildable_affected}")
        return AnalysisResult(buildable_affected, files)
