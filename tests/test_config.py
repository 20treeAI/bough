"""Test configuration loading."""

import logging

import bough.config as sut
from bough.analyzer import BoughAnalyzer


def test_default_config_values(tmp_path):
    config_path = tmp_path / ".bough.yml"
    # File doesn't exist

    config = sut.load_config(config_path)

    assert config.buildable == ["apps/*"]
    assert config.ignore == ["*.md"]


def test_custom_buildable_patterns(tmp_path):
    config_path = tmp_path / ".bough.yml"
    config_path.write_text("""
buildable:
  - "services/*"
  - "apps/*"
  - "tools/*"
ignore:
  - "*.md"
  - "docs/**"
""")

    config = sut.load_config(config_path)

    assert config.buildable == ["services/*", "apps/*", "tools/*"]
    assert config.ignore == ["*.md", "docs/**"]


def test_custom_ignore_patterns(tmp_path):
    config_path = tmp_path / ".bough.yml"
    config_path.write_text("""
buildable:
  - "apps/*"
ignore:
  - "*.md"
  - "*.txt"
  - "test/**"
  - "docs/**"
""")

    config = sut.load_config(config_path)

    assert config.buildable == ["apps/*"]
    assert config.ignore == ["*.md", "*.txt", "test/**", "docs/**"]


def test_minimal_config(tmp_path):
    config_path = tmp_path / ".bough.yml"
    config_path.write_text("""
buildable:
  - "microservices/*"
""")

    config = sut.load_config(config_path)

    assert config.buildable == ["microservices/*"]
    assert config.ignore == ["*.md"]  # Should use default


def test_analyzer_loads_config(sample_workspace, tmp_path):
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

    # Should have loaded config from .bough.yml in the workspace
    assert analyzer.config is not None
    assert analyzer.config.buildable == ["apps/*"]
    assert analyzer.config.ignore == ["*.md", "docs/**"]


def test_analyzer_custom_config_path(sample_workspace, tmp_path):
    # Create custom config
    custom_config = tmp_path / "custom.yml"
    custom_config.write_text("""
buildable:
  - "services/*"
ignore:
  - "*.log"
  - "*.tmp"
""")

    analyzer = BoughAnalyzer.from_workspace(
        sample_workspace, sample_workspace, config_path=custom_config
    )

    assert analyzer.config.buildable == ["services/*"]
    assert analyzer.config.ignore == ["*.log", "*.tmp"]


def test_invalid_yaml_uses_defaults_with_warning(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    config_path = tmp_path / ".bough.yml"
    config_path.write_text("""
buildable:
  - "apps/*"
  - invalid: yaml: syntax
""")

    config = sut.load_config(config_path)

    assert config.buildable == ["apps/*"]
    assert config.ignore == ["*.md"]
    assert "Invalid YAML" in caplog.text or "Failed to parse" in caplog.text


def test_missing_keys_use_defaults(tmp_path):
    config_path = tmp_path / ".bough.yml"
    config_path.write_text("""
# Valid YAML but missing both keys
tool:
  something:
    other: "value"
""")

    config = sut.load_config(config_path)

    assert config.buildable == ["apps/*"]
    assert config.ignore == ["*.md"]


def test_partial_config_uses_defaults_for_missing_keys(tmp_path):
    config_path = tmp_path / ".bough.yml"
    config_path.write_text("""
buildable:
  - "services/*"
# ignore key missing
""")

    config = sut.load_config(config_path)

    assert config.buildable == ["services/*"]
    assert config.ignore == ["*.md"]  # Should use default


def test_missing_config_file_uses_defaults_with_log(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    config_path = tmp_path / "nonexistent.yml"

    config = sut.load_config(config_path)

    assert config.buildable == ["apps/*"]
    assert config.ignore == ["*.md"]
    assert "Config file not found" in caplog.text or "Using defaults" in caplog.text
