_all: setup lint coverage

# Setup the python environment
setup:
  uv sync --frozen --dev
  tests/scripts/setup-sample.sh

# Run tests
test file='':
  uv run pytest -x --pdb --pdbcls=IPython.terminal.debugger:TerminalPdb {{file}}

# Compute test coverage information (formats: term, html, xml)
coverage format='term':
  uv run pytest --cov=bough --cov-branch --cov-report={{format}} --junitxml=junit.xml -o junit_family=legacy

# Run linters and formatters
lint:
  uv run ruff check --fix
  uv run ruff format
  uv run ty check
