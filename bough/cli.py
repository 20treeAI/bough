"""Command line interface for bough."""

import argparse
import sys
from pathlib import Path

from .analyzer import BoughAnalyzer


def format_human_readable(analyzer: BoughAnalyzer, affected_packages: set[str], changed_files: set[str]) -> str:
    """Format output for human consumption."""
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


def get_changed_files(analyzer: BoughAnalyzer, base_commit: str) -> set[str]:
    """Get the list of changed files for display purposes."""
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
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Determine which uv workspace packages need rebuilding based on git changes."
    )
    parser.add_argument(
        "--base",
        default="HEAD^",
        help="Base commit to compare against (default: HEAD^)"
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to .bough.yml config file (default: .bough.yml in workspace root)"
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Path to workspace root (default: current directory)"
    )
    
    args = parser.parse_args()
    
    # Determine config path
    if args.config:
        config_path = args.config
    else:
        config_path = args.workspace / ".bough.yml"
    
    try:
        analyzer = BoughAnalyzer(args.workspace, config_path)
        affected_packages = analyzer.get_affected_packages(args.base)
        changed_files = get_changed_files(analyzer, args.base)
        
        output = format_human_readable(analyzer, affected_packages, changed_files)
        print(output)
        
        # Exit with non-zero if packages need rebuilding (useful for CI)
        sys.exit(0 if not affected_packages else 1)
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
