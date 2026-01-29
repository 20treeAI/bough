import json
from pathlib import Path
from unittest.mock import Mock

from hypothesis import given
from hypothesis import strategies as st

import bough.formatters as sut

package_name = st.text(
    min_size=1, max_size=20, alphabet=st.characters(blacklist_characters="\n\r")
)

packages = st.sets(package_name, min_size=1)
files = st.sets(package_name, min_size=1)


@given(packages)
def test_github_matrix_always_valid_json(package_names):
    """GitHub matrix output must always be valid JSON."""
    analyzer = Mock()
    analyzer.packages = {
        name: Mock(directory=Path(f"/root/{name}")) for name in package_names
    }
    analyzer.workspace_root = Path("/root")

    result = sut.github_matrix(analyzer, package_names)
    parsed = json.loads(result)

    assert len(parsed["include"]) == len(package_names)
    assert all("package" in item for item in parsed["include"])


@given(packages)
def test_quiet_output_has_correct_line_count(package_names):
    """Quiet mode outputs exactly one line per package."""
    analyzer = Mock()
    analyzer.packages = {
        name: Mock(directory=Path(f"/root/{name}")) for name in package_names
    }

    result = sut.quiet(analyzer, package_names)

    assert len(result.split("\n")) == len(package_names)


@given(packages, files)
def test_human_readable_contains_all_packages(packages, files):
    """All package names must appear in human readable output."""
    analyzer = Mock()
    analyzer.packages = {
        name: Mock(directory=Path(f"/root/{name}")) for name in packages
    }
    analyzer.workspace_root = Path("/root")

    result = sut.human_readable(analyzer, packages, files)

    for pkg in packages:
        assert pkg in result


@st.composite
def package_graph(draw):
    """Generate a set of packages with dependencies referencing each other."""
    num_packages = draw(st.integers(min_value=1, max_value=10))
    names = [draw(package_name) for _ in range(num_packages)]
    names = list(set(names))

    packages = []
    for name in names:
        deps = draw(st.sets(st.sampled_from(names), max_size=3)) - {name}
        is_buildable = draw(st.booleans())
        packages.append(
            {"name": name, "dependencies": deps, "is_buildable": is_buildable}
        )

    return packages


@given(package_graph())
def test_dependency_graph_contains_all_packages(packages):
    """All package names must appear in dependency graph output."""
    analyzer = Mock()
    analyzer.packages = {
        pkg["name"]: Mock(
            directory=Path(f"/root/{pkg['name']}"), dependencies=pkg["dependencies"]
        )
        for pkg in packages
    }
    analyzer.workspace_root = Path("/root")

    # Build reverse dependency graph
    analyzer.dependency_graph = {name: set() for name in analyzer.packages}
    for pkg in packages:
        for dep in pkg["dependencies"]:
            if dep in analyzer.dependency_graph:
                analyzer.dependency_graph[dep].add(pkg["name"])

    buildable_names = {pkg["name"] for pkg in packages if pkg["is_buildable"]}
    analyzer._is_buildable_package = lambda p: p.directory.name in buildable_names

    result = sut.dependency_graph(analyzer)

    for pkg in packages:
        assert pkg["name"] in result
