# Bough

A tool to determine which uv workspace packages need rebuilding based on git changes.

## Problem

When using uv workspaces, it's often unclear which packages are affected by a given change. This leads to either rebuilding everything (wasteful) or missing necessary rebuilds (broken deployments).

## Solution

Analyze dependencies and git diffs to identify affected packages, then build only what's needed.

## Usage

```bash
# Default: analyze changes from HEAD^ to HEAD
bough

# Custom base commit
bough --base main

# Output GitHub Actions matrix format
bough --format github-matrix
```

## Configuration

`.bough.toml`:
```toml
# Packages that produce build artifacts (default: ["apps/*"])
buildable = ["apps/*"]

# Files that never trigger rebuilds
ignore = ["*.md", "docs/**"]
```

## How It Works

1. Find all workspace members from `pyproject.toml`
2. Build dependency graph from `tool.uv.sources`
3. Detect changed files with git diff
4. Apply rules:
   - File changed inside package → package affected
   - File changed at root → all packages affected
5. Calculate transitive impacts (if A depends on B and B changes, A is affected)
6. Filter to only buildable packages
7. Output build list

## Example

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

If `packages/database/models.py` changes:
- `database` is directly affected
- `shared` is affected (depends on database)
- `api` is affected (depends on database and shared)
- `web` is affected (depends on shared)
- Output shows only `api` and `web` (they're buildable)

## Output Formats

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

## Non-Goals

This tool is intentionally simple:
- Not a build system (like Bazel or Buck)
- Not a task runner
- Not multi-language aware
- Not trying to optimize build order or parallelization
- Not caching build artifacts

Just answers: "what needs rebuilding?"

## Prior Art

- [una](https://github.com/carderne/una) - Unify Python packaging commands
- [postmodern-mono](https://github.com/carderne/postmodern-mono) - Python monorepo example
- [Nx affected](https://nx.dev) - Similar concept for JS/TS monorepos
- [Turborepo --affected](https://turbo.build) - Git-based filtering for builds