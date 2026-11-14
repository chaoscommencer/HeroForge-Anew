---
name: black
description: >-
  Format Python source files with Black. Use when you need to format or verify
  formatting of src/ and tests/ before finishing a task.
user-invocable: true
---

# Black – Python code formatter

`black` is pre-installed in this environment (via the hash-pinned
`requirements-dev.txt`).

## Format files

```bash
black src/ tests/
```

Rewrites files in place to match Black's style (line length 88, targeting
Python 3.12). Always run this before the formatting check.

## Verify formatting (CI check)

```bash
black --check src/ tests/
```

Exit code 0 means all files are already formatted correctly. Any non-zero exit
code means at least one file would be reformatted — run `black src/ tests/`
first and then re-run the check. This is the exact command run by the
**Check formatting with Black** step in `.github/workflows/ci.yml`.

## Configuration

Black is configured in `pyproject.toml` under `[tool.black]`:
- `line-length = 88`
- `target-version = ["py312"]`
