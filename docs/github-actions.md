# GitHub Actions Integration

## Basic Workflow

```yaml
name: Build Affected Packages

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  detect-changes:
    runs-on: ubuntu-latest
    outputs:
      matrix: ${{ steps.changes.outputs.matrix }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      - name: Setup uv
        uses: astral-sh/setup-uv@v3
      
      - name: Install bough
        run: uv tool install bough
      
      - name: Detect affected packages
        id: changes
        run: |
          matrix=$(bough analyze --format github-matrix --base ${{ github.event.before || 'HEAD~1' }})
          echo "matrix=$matrix" >> $GITHUB_OUTPUT

  build:
    needs: detect-changes
    strategy:
      matrix: 
        include: ${{ fromJson(needs.detect-changes.outputs.matrix) }}
    steps:
      - name: Build Frontend
        if: matrix.package == 'frontend'
        uses: ./.github/workflows/build_frontend.yml
        secrets: inherit

      - name: Build Admin
        if: matrix.package == 'admin'  
        uses: ./.github/workflows/build_admin.yml
        secrets: inherit

      - name: Build Service
        if: matrix.package != 'frontend' && matrix.package != 'admin'
        uses: ./.github/workflows/build_service.yml
        with:
          package-name: ${{ matrix.package }}
          package-directory: ${{ matrix.directory }}
        secrets: inherit
```

## Matrix Output Format

The `--format github-matrix` option outputs JSON suitable for GitHub Actions matrix builds:

```json
{
  "include": [
    {"package": "frontend", "directory": "apps/frontend"},
    {"package": "billing", "directory": "apps/billing"}
  ]
}
```

While `bough graph` shows the human-readable dependency visualization with emojis and detailed relationships.

## Reusable Workflows

```yaml
# .github/workflows/build_frontend.yml
name: Build Frontend

on:
  workflow_call:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Frontend
        run: |
          cd apps/frontend
          # Your build steps here
```

## References

- [GitHub Actions Matrix Strategy](https://docs.github.com/en/actions/using-jobs/using-a-matrix-for-your-jobs)
- [Reusable Workflows](https://docs.github.com/en/actions/using-workflows/reusing-workflows)
