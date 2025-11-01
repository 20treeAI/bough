# Bough

[`bough`](https://en.wiktionary.org/wiki/bough) is a tool to determine which uv workspace packages need rebuilding based on git changes.

## Problem

When using uv workspaces, it's often unclear which packages are affected by a given change. This leads to either rebuilding everything (wasteful) or missing necessary rebuilds (broken deployments).

## Solution

Analyze dependencies and git diffs to identify affected packages, then build only what's needed.

## Usage

```bash
bough

# Custom base commit
bough --base main analyze

# Display dependency graph
bough graph

# Output GitHub Actions matrix format
bough --format github-matrix analyze
```

## Examples

```
my-app/
├── pyproject.toml
├── packages/
│   ├── auth/          # library (no deps)
│   ├── database/      # library (no deps)
│   └── shared/        # library (depends on: database)
└── apps/
    ├── api/           # buildable (depends on: auth, database, shared)
    └── web/           # buildable (depends on: shared)
```

### Graph

The `bough graph` command shows the dependency relationships between packages:

```
🚀 Buildable Packages:
==================================================
📦 api (apps/api)
   └─ depends on: auth, database, shared

📦 web (apps/web)
   └─ depends on: shared

📚 Library Packages:
==================================================
📖 auth (packages/auth)
   ├─ depends on: (none)
   └─ depended on by: api

📖 database (packages/database)
   ├─ depends on: (none)
   └─ depended on by: api, shared, web

📖 shared (packages/shared)
   ├─ depends on: database
   └─ depended on by: api, web
```

### Analyze

The `bough analyze` command shows what packages should be built based on what files have changed.

**GitHub Matrix** (for parallel CI jobs):
```json
{
  "include": [
    {"package": "api", "directory": "apps/api"},
    {"package": "web", "directory": "apps/web"}
  ]
}
```

**Text** (default):
```
Packages to rebuild:
  api (apps/api)
  web (apps/web)

Changed files:
  packages/database/models.py
```

## Configuration

`.bough.yml`:
```yaml
# Packages that produce build artifacts (default: ["apps/*"])
buildable:
  - "apps/*"

# Files that never trigger rebuilds
ignore:
  - "*.md"
  - "docs/**"
```

## GitHub Actions Integration

See [GitHub Actions Integration Guide](docs/github-actions.md) for examples of using Bough in CI/CD pipelines.

## How It Works

1. Find all workspace members from `pyproject.toml`
2. Build dependency graph from `tool.uv.sources`
3. Detect changed files with git diff
4. Apply change detection rules:
   - File changed inside package → package directly affected
   - File changed at workspace root → all packages affected
5. Calculate transitive impacts (if A depends on B and B changes, A is affected)
6. Filter to only buildable packages
7. Output build list


If `packages/database/models.py` changes:
- `database` is directly affected
- `shared` is affected (depends on database)
- `api` is affected (depends on database and shared)
- `web` is affected (depends on shared)
- Output shows only `api` and `web` (they're buildable)


## Non-Goals

This tool is intentionally simple:
- Not a build system (like Bazel or Buck)
- Not a task runner
- Not multi-language aware
- Not trying to optimize build order or parallelization
- Not caching build artifacts

## Prior Art

- [una](https://github.com/carderne/una) - Unify Python packaging commands
- [postmodern-mono](https://github.com/carderne/postmodern-mono) - Python monorepo example
- [Nx affected](https://nx.dev) - Similar concept for JS/TS monorepos
- [Turborepo --affected](https://turbo.build) - Git-based filtering for builds

## Roadmap

- [ ] provide an option that outputs all affected packages, not just buildable ones (useful for selectively running tests)
- [ ] check in a sample configuration file and document the defaults better
- [ ] improve or remove the github actions examples
- [ ] setup a release workflow to pypi
- [ ] add a contributing guide
