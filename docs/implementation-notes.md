# Implementation Notes

## Workspace Parsing

1. Read workspace root `pyproject.toml`
2. Parse `tool.uv.workspace.members` and `exclude` globs
3. Find all matching directories with `pyproject.toml` files
4. Extract package names from each member's `[project]` table

## Dependency Graph

```python
# Build edges from workspace sources
for member in workspace_members:
    deps = member.get("tool.uv.sources", {})
    for dep_name, source in deps.items():
        if source.get("workspace") == True:
            graph.add_edge(member.name, dep_name)
```

## Git Integration

- Use `git diff --name-only BASE..HEAD` for changed files
- Default BASE to `HEAD^` (configurable via `--base`)
- In GitHub Actions, captures merge commit changes

## Change Detection

```python
def get_affected_packages(changed_file, workspace_root, members):
    for member in members:
        if changed_file.startswith(member.relative_path):
            return {member.name}
    
    # Root file affects everything
    return {m.name for m in members}
```

## Transitive Dependencies

```python
def get_all_affected(directly_affected, dependency_graph):
    affected = set(directly_affected)
    queue = list(directly_affected)
    
    while queue:
        pkg = queue.pop(0)
        # Find packages that depend on pkg
        dependents = [p for p, deps in dependency_graph.items() if pkg in deps]
        for dep in dependents:
            if dep not in affected:
                affected.add(dep)
                queue.append(dep)
    
    return affected
```

## Buildable Filtering

- Match affected packages against `buildable` globs
- Default: `["apps/*"]`
- Only these appear in output

## Error Handling

- **Circular dependencies**: Detect during graph build, fail clearly
- **Missing workspace members**: Validate all glob matches have `pyproject.toml`
- **Invalid TOML**: Show file paths in errors
- **Git failures**: Check repo state, handle detached HEAD

## Testing

1. Unit tests for each component
2. Integration tests with sample workspace structures
3. Mock git commands for reproducible tests

## Performance

- Small/medium workspaces (<100 packages) don't need optimization
- O(V+E) graph traversal is fine for typical sizes
- Cache parsed TOML during single run