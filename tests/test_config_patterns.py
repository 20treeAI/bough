"""Test configurable pattern matching for buildable and ignore patterns."""

import git

from bough.analyzer import BoughAnalyzer


def test_custom_buildable_patterns_filter_correctly(sample_workspace, tmp_path):
    """Test that custom buildable patterns correctly filter packages."""
    # Create config that only considers packages/* as buildable
    config_path = tmp_path / ".bough.yml"
    config_path.write_text("""
buildable:
  - "packages/*"
ignore:
  - "*.md"
""")

    analyzer = BoughAnalyzer.from_workspace(
        sample_workspace, sample_workspace, config_path
    )

    # Modify a file that affects everything

    repo = git.Repo.init(sample_workspace)
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")

    repo.git.add(".")
    repo.index.commit("Initial commit")

    # Change root file to affect all packages
    root_file = sample_workspace / "pyproject.toml"
    with open(root_file, "a") as f:
        f.write("\n# Test change\n")

    repo.git.add(".")
    repo.index.commit("Update root config")

    affected, _ = analyzer.find_affected()

    # Should only return packages under packages/*, not apps/*
    expected = {"auth", "database", "shared"}  # packages/* only
    assert affected == expected


def test_multiple_buildable_patterns(sample_workspace, tmp_path):
    """Test multiple buildable patterns work together."""
    config_path = tmp_path / ".bough.yml"
    config_path.write_text("""
buildable:
  - "apps/*"
  - "packages/shared"  # specific package
ignore:
  - "*.md"
""")

    analyzer = BoughAnalyzer.from_workspace(
        sample_workspace, sample_workspace, config_path
    )

    repo = git.Repo.init(sample_workspace)
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")

    repo.git.add(".")
    repo.index.commit("Initial commit")

    # Change root file
    root_file = sample_workspace / "pyproject.toml"
    with open(root_file, "a") as f:
        f.write("\n# Test change\n")

    repo.git.add(".")
    repo.index.commit("Update root config")

    affected, _ = analyzer.find_affected()

    # Should include apps/* and packages/shared
    expected = {"api", "web", "shared"}
    assert affected == expected


def test_custom_ignore_patterns_work(sample_workspace, tmp_path):
    """Test that custom ignore patterns prevent triggering builds."""
    config_path = tmp_path / ".bough.yml"
    config_path.write_text("""
buildable:
  - "apps/*"
ignore:
  - "*.md"
  - "*.txt"
  - "docs/**"
""")

    analyzer = BoughAnalyzer.from_workspace(
        sample_workspace, sample_workspace, config_path
    )

    repo = git.Repo.init(sample_workspace)
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")

    repo.git.add(".")
    repo.index.commit("Initial commit")

    # Create and change an ignored file
    ignored_file = sample_workspace / "CHANGELOG.txt"
    ignored_file.write_text("Version 1.0.0")

    repo.git.add(".")
    repo.index.commit("Add changelog")

    affected, _ = analyzer.find_affected()

    # Should be empty since .txt files are ignored
    assert affected == set()


def test_nested_ignore_patterns(sample_workspace, tmp_path):
    """Test that nested ignore patterns like docs/** work correctly."""
    config_path = tmp_path / ".bough.yml"
    config_path.write_text("""
buildable:
  - "apps/*"
ignore:
  - "*.md"
  - "docs/**"
""")

    analyzer = BoughAnalyzer.from_workspace(
        sample_workspace, sample_workspace, config_path
    )

    repo = git.Repo.init(sample_workspace)
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")

    repo.git.add(".")
    repo.index.commit("Initial commit")

    # Create nested docs structure
    docs_dir = sample_workspace / "docs" / "api"
    docs_dir.mkdir(parents=True)
    docs_file = docs_dir / "endpoints.md"
    docs_file.write_text("# API Endpoints")

    repo.git.add(".")
    repo.index.commit("Add docs")

    affected, _ = analyzer.find_affected()

    # Should be empty since docs/** is ignored
    assert affected == set()
