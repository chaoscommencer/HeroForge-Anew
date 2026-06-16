---
name: ruff
description: >-
  Lint Python source files with Ruff. Use when you need to check for or fix
  linting violations in src/ before finishing a task.
user-invocable: true
---

# Ruff – Python linter

`ruff` is pre-installed in this environment (via the hash-pinned
`requirements-dev.txt`).

## Check for lint violations

```bash
ruff check src/
```

Exit code 0 means no violations. Any non-zero exit code means there are issues
that must be fixed before the task is complete. This is the exact command run
by the **Lint with Ruff** step in `.github/workflows/ci.yml`.

## Auto-fix violations

```bash
ruff check --fix src/
```

Ruff can automatically fix many violations. Always verify the fixes look correct
before committing.

## Configuration

Ruff is configured in `pyproject.toml` under `[tool.ruff]` and `[tool.ruff.lint]`.
The project enables the `E`, `W`, `F`, `I`, `UP`, and `N` rule sets (ignoring
`N802` and `N803`).
