all: setup test lint

setup:
  uv sync --locked --dev
  tests/scripts/setup-sample.sh

test file='':
  uv run pytest -x --pdb --pdbcls=IPython.terminal.debugger:TerminalPdb {{file}}
  uv run tests/scripts/smoke.sh > /dev/null

lint:
  uv run ruff check
  uv run ruff format
