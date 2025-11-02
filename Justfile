_all: setup lint coverage

# Setup the python environment
setup:
  uv sync --frozen --dev
  tests/scripts/setup-sample.sh

# Run tests
test file='':
  uv run pytest -x --pdb --pdbcls=IPython.terminal.debugger:TerminalPdb {{file}}

# Compute test coverage information
coverage:
  uv run coverage run --branch -m pytest
  uv run coverage html --omit=tests/**/*.py
  uv run coverage report --omit=tests/**/*.py

# Run linters and formatters
lint:
  uv run ruff check --fix
  uv run ruff format
  uv run ty check
