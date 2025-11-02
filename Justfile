_all: setup test lint

# Setup the python environment
setup:
  uv sync --frozen --dev
  tests/scripts/setup-sample.sh

# Run tests
test file='':
  uv run pytest -x --pdb --pdbcls=IPython.terminal.debugger:TerminalPdb {{file}}
  uv run tests/scripts/smoke.sh > /dev/null

# Run linters and formatters
lint:
  uv run ruff check --fix
  uv run ruff format
  uv run ty check
