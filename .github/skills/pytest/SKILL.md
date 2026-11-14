---
name: pytest
description: >-
  Run the project's test suite with pytest. Use when you need to verify that
  changes do not break existing behaviour before finishing a task.
user-invocable: true
---

# pytest – Python test runner

`pytest` is pre-installed in this environment (via the hash-pinned
`requirements-dev.txt`).

## Run all tests

```bash
pytest
```

Exit code 0 means all tests passed. Any non-zero exit code means at least one
test failed and the failure must be investigated and resolved before the task is
considered complete.

## Run tests with coverage

```bash
pytest --cov=src/heroforge --cov-report=term-missing
```

The project targets ≥ 80 % coverage on `logic/` and `db/` modules.

## Run a specific test file or test

```bash
pytest tests/test_skills.py
pytest tests/test_skills.py::test_calculate_modifier
```

## Configuration

pytest is configured in `pyproject.toml` under `[tool.pytest.ini_options]`.
