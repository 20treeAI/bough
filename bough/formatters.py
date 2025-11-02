"""Formatter functions for use in various tools."""

import json

from bough.analyzer import BoughAnalyzer


def human_readable(
    analyzer: BoughAnalyzer,
    affected_packages: set[str],
    changed_files: set[str],
) -> str:
    """Output the analysis results in a textual format suitable for CLI usage."""
    lines = []

    if affected_packages:
        lines.append("Packages to rebuild:")
        for package_name in sorted(affected_packages):
            package = analyzer.packages[package_name]
            rel_path = package.directory.relative_to(analyzer.workspace_root)
            lines.append(f"  {package_name} ({rel_path})")
    else:
        lines.append("No packages need rebuilding.")

    if changed_files:
        lines.append("")
        lines.append("Changed files:")
        lines.extend(f"  {file_path}" for file_path in sorted(changed_files))

    return "\n".join(lines)


def quiet(
    analyzer: BoughAnalyzer,
    affected_packages: set[str],
) -> str:
    """Output each package directory root on a separate line, suitable for useage in scripting."""
    return "\n".join(
        str(analyzer.packages[package].directory) for package in affected_packages
    )


def github_matrix(analyzer: BoughAnalyzer, affected_packages: set[str]) -> str:
    """Output the analysis results in a format suitable for use with GitHub actions."""
    matrix_items = []

    for package_name in sorted(affected_packages):
        package = analyzer.packages[package_name]
        rel_path = str(package.directory.relative_to(analyzer.workspace_root))
        matrix_items.append({"package": package_name, "directory": rel_path})

    matrix = {"include": matrix_items}
    return json.dumps(matrix, indent=2)


def _render_graph(packages: list[dict], title: str, warning: bool = False) -> list[str]:
    lines = [title]
    lines.append("=" * 50)
    for pkg in packages:
        lines.append(f"📦 {pkg['name']} ({pkg['path']})")
        if pkg["dependencies"]:
            lines.append(
                f"   └─ depends on: {', '.join(sorted(pkg['dependencies']))}",
            )
        else:
            lines.append("   └─ depends on: (none)")

        if pkg["dependents"]:
            if warning:
                lines.append(
                    f"   ⚠️  WARNING: depended on by {', '.join(sorted(pkg['dependents']))} (buildables shouldn't have dependents)",
                )
            else:
                lines.append(
                    f"   └─ depended on by: {', '.join(sorted(pkg['dependents']))}",
                )

        else:
            lines.append("   └─ depended on by: (none)")
        lines.append("")
    return lines


def dependency_graph(analyzer: BoughAnalyzer) -> str:
    """Output the dependency graph for the CLI."""
    lines = []

    buildable_packages = set()
    for package_name, package in analyzer.packages.items():
        if analyzer._is_buildable_package(package):
            buildable_packages.add(package_name)

    buildable = []
    libraries = []

    for package_name in sorted(analyzer.packages.keys()):
        package = analyzer.packages[package_name]
        rel_path = package.directory.relative_to(analyzer.workspace_root)

        package_info = {
            "name": package_name,
            "path": rel_path,
            "dependencies": package.dependencies,
            "dependents": analyzer.dependency_graph.get(package_name, set()),
        }

        if package_name in buildable_packages:
            buildable.append(package_info)
        else:
            libraries.append(package_info)

    if buildable:
        lines.extend(_render_graph(buildable, "🚀 Buildable Packages:", warning=True))

    if libraries:
        lines.extend(_render_graph(libraries, "📚 Library Packages:"))

    if not buildable and not libraries:
        lines.append("No packages found in workspace.")

    return "\n".join(lines)
