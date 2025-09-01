import argparse
import json
import logging
import sys
from pathlib import Path

from .analyzer import BoughAnalyzer


def format_human_readable(
    analyzer: BoughAnalyzer, affected_packages: set[str], changed_files: set[str]
) -> str:
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
        for file_path in sorted(changed_files):
            lines.append(f"  {file_path}")

    return "\n".join(lines)


def format_github_matrix(analyzer: BoughAnalyzer, affected_packages: set[str]) -> str:
    matrix_items = []

    for package_name in sorted(affected_packages):
        package = analyzer.packages[package_name]
        rel_path = str(package.directory.relative_to(analyzer.workspace_root))
        matrix_items.append({"package": package_name, "directory": rel_path})

    matrix = {"include": matrix_items}
    return json.dumps(matrix, indent=2)


def format_dependency_graph(analyzer: BoughAnalyzer) -> str:
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
        lines.append("🚀 Buildable Packages:")
        lines.append("=" * 50)
        for pkg in buildable:
            lines.append(f"📦 {pkg['name']} ({pkg['path']})")
            if pkg["dependencies"]:
                lines.append(
                    f"   └─ depends on: {', '.join(sorted(pkg['dependencies']))}"
                )
            else:
                lines.append("   └─ depends on: (none)")

            # Warn if buildable packages have dependents (architectural issue)
            if pkg["dependents"]:
                lines.append(
                    f"   ⚠️  WARNING: depended on by {', '.join(sorted(pkg['dependents']))} (buildables shouldn't have dependents)"
                )
            lines.append("")

    if libraries:
        lines.append("📚 Library Packages:")
        lines.append("=" * 50)
        for pkg in libraries:
            lines.append(f"📖 {pkg['name']} ({pkg['path']})")
            if pkg["dependencies"]:
                lines.append(
                    f"   ├─ depends on: {', '.join(sorted(pkg['dependencies']))}"
                )
            else:
                lines.append("   ├─ depends on: (none)")

            if pkg["dependents"]:
                lines.append(
                    f"   └─ depended on by: {', '.join(sorted(pkg['dependents']))}"
                )
            else:
                lines.append("   └─ depended on by: (none)")
            lines.append("")

    if not buildable and not libraries:
        lines.append("No packages found in workspace.")

    return "\n".join(lines)


def get_changed_files(analyzer: BoughAnalyzer, base_commit: str) -> set[str]:
    import git

    repo = git.Repo(analyzer.workspace_root)

    changed_files = set()
    for item in repo.commit(base_commit).diff(repo.head.commit):
        if item.a_path:
            changed_files.add(item.a_path)
        if item.b_path:
            changed_files.add(item.b_path)

    return changed_files


def main():
    parser = argparse.ArgumentParser(
        description="Determine which uv workspace packages need rebuilding based on git changes."
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to .bough.yml config file (default: .bough.yml in workspace root)",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Path to workspace root (default: current directory)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    analyze_parser = subparsers.add_parser(
        "analyze", help="Analyze git changes to determine affected packages"
    )
    analyze_parser.add_argument(
        "--base",
        default="HEAD^",
        help="Base commit to compare against (default: HEAD^)",
    )
    analyze_parser.add_argument(
        "--format",
        choices=["text", "github-matrix"],
        default="text",
        help="Output format (default: text)",
    )

    _ = subparsers.add_parser("graph", help="Display the dependency graph")

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    if args.command is None:
        args.command = "analyze"
        args.base = "HEAD^"
        args.format = "text"

    if args.config:
        config_path = args.config
    else:
        config_path = args.workspace / ".bough.yml"

    try:
        analyzer = BoughAnalyzer.from_workspace(args.workspace, config_path)

        if args.command == "graph":
            output = format_dependency_graph(analyzer)
            print(output)
            sys.exit(0)
        else:
            affected_packages = analyzer.get_affected_packages(args.base)

            if args.format == "github-matrix":
                output = format_github_matrix(analyzer, affected_packages)
                print(output)
                sys.exit(0)
            else:
                changed_files = get_changed_files(analyzer, args.base)
                output = format_human_readable(
                    analyzer, affected_packages, changed_files
                )
                print(output)
                sys.exit(0 if not affected_packages else 1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
