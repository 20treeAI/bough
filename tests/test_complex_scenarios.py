"""Test complex repository scenarios using real workspaces and mocked git."""

from pathlib import Path
from unittest.mock import Mock, patch

import tomli_w

from bough.analyzer import BoughAnalyzer


def create_workspace_structure(base_path: Path, structure: dict):
    """Create a real workspace with pyproject.toml files.

    Args:
        base_path: Root directory for the workspace
        structure: Dict mapping package paths to their config
                  e.g. {"libs/core": {"dependencies": []}}
    """
    # Create workspace root pyproject.toml
    workspace_members = list(structure.keys())
    root_config = {
        "tool": {"uv": {"workspace": {"members": workspace_members}}},
        "project": {"name": "test-workspace", "version": "0.1.0"},
    }

    base_path.mkdir(parents=True, exist_ok=True)
    with open(base_path / "pyproject.toml", "wb") as f:
        tomli_w.dump(root_config, f)

    # Create each package
    for package_path, config in structure.items():
        pkg_dir = base_path / package_path
        pkg_dir.mkdir(parents=True, exist_ok=True)

        package_name = config.get("name", package_path.split("/")[-1])

        # Create pyproject.toml for this package
        pyproject_config = {"project": {"name": package_name, "version": "0.1.0"}}

        # Add workspace dependencies if any
        if config.get("dependencies"):
            pyproject_config["tool"] = {"uv": {"sources": {}}}
            for dep in config["dependencies"]:
                pyproject_config["tool"]["uv"]["sources"][dep] = {"workspace": True}

        with open(pkg_dir / "pyproject.toml", "wb") as f:
            tomli_w.dump(pyproject_config, f)

        # Create a simple Python file
        (pkg_dir / f"{package_name.replace('-', '_')}.py").write_text(
            f'"""Package {package_name}."""\n\ndef main():\n    pass\n',
        )


def mock_git_changes(changed_files: list[str]):
    """Create a mock git repo that reports the given files as changed."""
    mock_repo = Mock()
    mock_commit = Mock()
    mock_index = Mock()

    mock_repo.commit.return_value = mock_commit
    mock_repo.head.commit = mock_commit
    mock_repo.index = mock_index
    mock_repo.untracked_files = []

    # Create mock diff items
    mock_diff_items = []
    for file_path in changed_files:
        mock_item = Mock()
        mock_item.a_path = file_path
        mock_item.b_path = file_path
        mock_diff_items.append(mock_item)

    mock_commit.diff.return_value = mock_diff_items
    mock_index.diff.return_value = []
    return mock_repo


@patch("git.Repo")
def test_deep_dependency_chain_core_change(mock_repo_class, tmp_path):
    """When core library changes, all dependent apps should be affected."""
    # Create complex workspace structure
    structure = {
        "libs/core": {"dependencies": []},
        "libs/utils": {"dependencies": ["core"]},
        "libs/database": {"dependencies": ["core", "utils"]},
        "libs/auth": {"dependencies": ["core", "utils", "database"]},
        "services/api": {"dependencies": ["core", "utils", "database", "auth"]},
        "apps/web": {"dependencies": ["api"]},
        "apps/admin": {"dependencies": ["api", "auth"]},
    }

    create_workspace_structure(tmp_path, structure)

    # Mock git to show core library changed
    mock_repo_class.return_value = mock_git_changes(["libs/core/core.py"])

    # Create config that considers apps/* and services/* as buildable
    config_path = tmp_path / ".bough.yml"
    config_path.write_text("""
buildable:
  - "apps/*"
  - "services/*"
ignore:
  - "*.md"
""")

    # Test the public interface
    analyzer = BoughAnalyzer.from_workspace(tmp_path, tmp_path, config_path)
    affected, _ = analyzer.find_affected()

    # Core change should transitively affect all buildable packages
    assert affected == {"api", "web", "admin"}


@patch("git.Repo")
def test_diamond_dependency_pattern(mock_repo_class, tmp_path):
    """Test diamond dependency pattern where multiple paths converge."""
    structure = {
        "libs/base": {"dependencies": []},
        "libs/left": {"dependencies": ["base"]},
        "libs/right": {"dependencies": ["base"]},
        "apps/top": {"dependencies": ["left", "right"]},
    }

    create_workspace_structure(tmp_path, structure)
    mock_repo_class.return_value = mock_git_changes(["libs/base/base.py"])

    config_path = tmp_path / ".bough.yml"
    config_path.write_text("""
buildable:
  - "apps/*"
ignore:
  - "*.md"
""")

    analyzer = BoughAnalyzer.from_workspace(tmp_path, tmp_path, config_path)
    affected, _ = analyzer.find_affected()

    # Base change should affect top through both left and right paths
    assert affected == {"top"}


@patch("git.Repo")
def test_layered_architecture_isolation(mock_repo_class, tmp_path):
    """Test that changes in different layers have appropriate scope."""
    structure = {
        # Data layer
        "data/models": {"dependencies": []},
        "data/repositories": {"dependencies": ["models"]},
        # Business layer
        "business/domain": {"dependencies": ["models"]},
        "business/services": {"dependencies": ["domain", "repositories"]},
        # API layer
        "api/controllers": {"dependencies": ["services"]},
        "api/middleware": {"dependencies": ["domain"]},
        # Apps
        "apps/rest-api": {"dependencies": ["controllers", "middleware"]},
        "apps/graphql-api": {"dependencies": ["controllers", "middleware"]},
        "apps/worker": {"dependencies": ["services"]},
    }

    create_workspace_structure(tmp_path, structure)

    config_path = tmp_path / ".bough.yml"
    config_path.write_text("""
buildable:
  - "apps/*"
ignore:
  - "*.md"
""")

    # Test 1: Change in models affects all apps
    mock_repo_class.return_value = mock_git_changes(["data/models/user.py"])
    analyzer = BoughAnalyzer.from_workspace(tmp_path, tmp_path, config_path)
    affected, _ = analyzer.find_affected()

    assert affected == {"rest-api", "graphql-api", "worker"}

    # Test 2: Change in middleware only affects APIs that use it
    mock_repo_class.return_value = mock_git_changes(["api/middleware/auth.py"])
    analyzer = BoughAnalyzer.from_workspace(tmp_path, tmp_path, config_path)
    affected, _ = analyzer.find_affected()

    assert affected == {"rest-api", "graphql-api"}


@patch("git.Repo")
def test_microservices_shared_library_impact(mock_repo_class, tmp_path):
    """Test microservices architecture with shared libraries."""
    structure = {
        # Shared libraries
        "shared/proto": {"dependencies": []},
        "shared/common": {"dependencies": ["proto"]},
        "shared/events": {"dependencies": ["proto", "common"]},
        # Services
        "services/user": {
            "name": "user-service",
            "dependencies": ["proto", "common", "events"],
        },
        "services/order": {
            "name": "order-service",
            "dependencies": ["proto", "common", "events"],
        },
        "services/payment": {
            "name": "payment-service",
            "dependencies": ["proto", "common"],
        },
        "services/notification": {
            "name": "notification-service",
            "dependencies": ["proto", "common", "events"],
        },
        # Gateways
        "gateways/api": {"name": "api-gateway", "dependencies": ["proto", "common"]},
        "gateways/admin": {
            "name": "admin-gateway",
            "dependencies": ["proto", "common"],
        },
    }

    create_workspace_structure(tmp_path, structure)

    config_path = tmp_path / ".bough.yml"
    config_path.write_text("""
buildable:
  - "services/*"
  - "gateways/*"
ignore:
  - "*.md"
""")

    # Test 1: Change in proto affects everything
    mock_repo_class.return_value = mock_git_changes(["shared/proto/user.proto"])
    analyzer = BoughAnalyzer.from_workspace(tmp_path, tmp_path, config_path)
    affected, _ = analyzer.find_affected()

    expected = {
        "user-service",
        "order-service",
        "payment-service",
        "notification-service",
        "api-gateway",
        "admin-gateway",
    }
    assert affected == expected

    # Test 2: Change in events only affects services that use events
    mock_repo_class.return_value = mock_git_changes(["shared/events/order_created.py"])
    analyzer = BoughAnalyzer.from_workspace(tmp_path, tmp_path, config_path)
    affected, _ = analyzer.find_affected()

    expected = {"user-service", "order-service", "notification-service"}
    assert affected == expected


@patch("git.Repo")
def test_isolated_packages_no_unnecessary_rebuilds(mock_repo_class, tmp_path):
    """Test that isolated packages don't trigger unnecessary rebuilds."""
    structure = {
        "tools/standalone-a": {"dependencies": []},
        "tools/standalone-b": {"dependencies": []},
        "apps/main": {"dependencies": ["standalone-a"]},
    }

    create_workspace_structure(tmp_path, structure)

    config_path = tmp_path / ".bough.yml"
    config_path.write_text("""
buildable:
  - "apps/*"
  - "tools/*"
ignore:
  - "*.md"
""")

    # Change standalone-b should only affect itself
    mock_repo_class.return_value = mock_git_changes(
        ["tools/standalone-b/standalone_b.py"],
    )
    analyzer = BoughAnalyzer.from_workspace(tmp_path, tmp_path, config_path)
    affected, _ = analyzer.find_affected()

    assert affected == {"standalone-b"}

    # Change standalone-a should affect main too
    mock_repo_class.return_value = mock_git_changes(
        ["tools/standalone-a/standalone_a.py"],
    )
    analyzer = BoughAnalyzer.from_workspace(tmp_path, tmp_path, config_path)
    affected, _ = analyzer.find_affected()

    assert affected == {"standalone-a", "main"}


@patch("git.Repo")
def test_root_file_affects_all_buildable_packages(mock_repo_class, tmp_path):
    """Test that root file changes affect all buildable packages."""
    structure = {
        "libs/utils": {"dependencies": []},
        "apps/web": {"dependencies": ["utils"]},
        "apps/api": {"dependencies": ["utils"]},
        "tools/cli": {"dependencies": []},
    }

    create_workspace_structure(tmp_path, structure)

    config_path = tmp_path / ".bough.yml"
    config_path.write_text("""
buildable:
  - "apps/*"
ignore:
  - "*.md"
""")

    # Root pyproject.toml change should affect all buildable packages
    mock_repo_class.return_value = mock_git_changes(["pyproject.toml"])
    analyzer = BoughAnalyzer.from_workspace(tmp_path, tmp_path, config_path)
    affected, _ = analyzer.find_affected()

    assert affected == {"web", "api"}  # Only buildable packages


@patch("git.Repo")
def test_ignored_files_trigger_no_rebuilds(mock_repo_class, tmp_path):
    """Test that ignored files don't trigger any rebuilds."""
    structure = {
        "apps/web": {"dependencies": []},
        "apps/api": {"dependencies": []},
    }

    create_workspace_structure(tmp_path, structure)

    config_path = tmp_path / ".bough.yml"
    config_path.write_text("""
buildable:
  - "apps/*"
ignore:
  - "*.md"
  - "docs/**"
  - "*.txt"
""")

    # Changes to ignored files should not trigger rebuilds
    mock_repo_class.return_value = mock_git_changes(
        ["README.md", "docs/api.md", "CHANGELOG.txt"],
    )
    analyzer = BoughAnalyzer.from_workspace(tmp_path, tmp_path, config_path)
    affected, _ = analyzer.find_affected()

    assert affected == set()


@patch("git.Repo")
def test_complex_buildable_patterns(mock_repo_class, tmp_path):
    """Test complex buildable pattern matching."""
    structure = {
        "libs/common": {"dependencies": []},
        "services/user": {"name": "user-service", "dependencies": ["common"]},
        "services/order": {"name": "order-service", "dependencies": ["common"]},
        "gateways/api": {"name": "api-gateway", "dependencies": ["common"]},
        "gateways/admin": {"name": "admin-gateway", "dependencies": ["common"]},
        "apps/web": {"dependencies": ["common"]},
    }

    create_workspace_structure(tmp_path, structure)

    # Only specific services and gateways are buildable
    config_path = tmp_path / ".bough.yml"
    config_path.write_text("""
buildable:
  - "services/user"
  - "gateways/api"
  - "apps/*"
ignore:
  - "*.md"
""")

    # Change common library to affect everything
    mock_repo_class.return_value = mock_git_changes(["libs/common/common.py"])
    analyzer = BoughAnalyzer.from_workspace(tmp_path, tmp_path, config_path)
    affected, _ = analyzer.find_affected()

    # Should only include packages matching buildable patterns
    assert affected == {"user-service", "api-gateway", "web"}


@patch("git.Repo")
def test_divergent_git_vs_workspace_roots(mock_repo_class, tmp_path):
    """Test that root file changes affect all buildable packages."""
    structure = {
        "libs/utils": {"dependencies": []},
        "apps/web": {"dependencies": ["utils"]},
        "apps/api": {"dependencies": ["utils"]},
        "tools/cli": {"dependencies": []},
    }

    create_workspace_structure(tmp_path / "src", structure)

    config_path = tmp_path / ".bough.yml"
    config_path.write_text("""
buildable:
  - "apps/*"
ignore:
  - "*.md"
""")

    mock_repo_class.return_value = mock_git_changes(["src/apps/web/foo"])
    analyzer = BoughAnalyzer.from_workspace(tmp_path, tmp_path / "src", config_path)
    affected, _ = analyzer.find_affected()

    assert affected == {"web"}
