import sys

import pytest

from bough import cli


def test_smoke_cli_graph():
    sys.argv = ["bough", "graph", "--workspace", "tests/fixtures/sample-workspace"]
    with pytest.raises(SystemExit, match="0"):
        cli.main()


def test_smoke_cli_analyze():
    sys.argv = [
        "bough",
        "analyze",
        "--workspace",
        "tests/fixtures/sample-workspace",
        "--repo",
        "tests/fixtures/sample-workspace",
    ]
    with pytest.raises(SystemExit, match="0"):
        cli.main()
