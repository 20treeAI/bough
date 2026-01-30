"""CLI entry point for bough."""

import argparse
import logging
import sys
from pathlib import Path

import bough.formatters as fmt
from bough.analyzer import BoughAnalyzer


def main() -> None:
    """Parse the CLI options and invoke the analysis tool."""
    default_parser = argparse.ArgumentParser(add_help=False)
    default_parser.add_argument(
        "--config",
        type=Path,
        help="Path to .bough.yml config file (default: .bough.yml in workspace root)",
    )
    default_parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Path to workspace root (default: current directory)",
    )
    default_parser.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="Path to git repository root (default: current directory)",
    )
    default_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    parser = argparse.ArgumentParser(
        description="Determine which uv workspace packages need rebuilding based on git changes.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze git changes to determine affected packages",
        parents=[default_parser],
    )
    _graph_parser = subparsers.add_parser(
        "graph",
        help="Display the dependency graph",
        parents=[default_parser],
    )

    analyze_parser.add_argument(
        "--base",
        default="HEAD^",
        help="Base commit to compare against (default: HEAD^)",
    )
    analyze_parser.add_argument(
        "--format",
        choices=["text", "github-matrix", "quiet"],
        default="text",
        help="Output format (default: text)",
    )
    analyze_parser.add_argument(
        "--selection",
        choices=["buildable", "all"],
        default="buildable",
        help="Return only buildables or all packages (default: buildable)",
    )

    args = parser.parse_args()
    if args.command is None:
        args = parser.parse_args(["analyze"])

    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    config_path = args.config or args.workspace / ".bough.yaml"

    try:
        analyzer = BoughAnalyzer.from_workspace(args.repo, args.workspace, config_path)

        if args.command == "graph":
            output = fmt.dependency_graph(analyzer)
            print(output)
            sys.exit(0)
        else:
            packages, files = analyzer.find_affected(args.base, args.selection)

            if args.format == "github-matrix":
                output = fmt.github_matrix(analyzer, packages)
            elif args.format == "quiet":
                output = fmt.quiet(analyzer, packages)
            else:
                output = fmt.human_readable(analyzer, packages, files)

            print(output)
            sys.exit(0)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
