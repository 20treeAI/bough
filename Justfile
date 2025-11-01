all: setup test lint

setup:
  uv sync --locked --dev

test file='':
  uv run pytest -x --pdb --pdbcls=IPython.terminal.debugger:TerminalPdb {{file}}
  uv run tests/smoke.sh > /dev/null

lint:
  uv run ruff check
  uv run ruff format
