---
name: graphify
description: >-
  Map and query the HeroForge-Anew codebase as a knowledge graph with graphify.
  Use this FIRST for any question about how the code fits together — architecture,
  where a calculation lives, what calls or imports a module, or how data flows —
  instead of grepping or reading many files. Querying the graph costs far fewer
  tokens than opening source files one by one.
user-invocable: true
---

# graphify – queryable codebase knowledge graph

`graphify` (PyPI package **`graphifyy`**, CLI command `graphify`) maps this
codebase into a queryable knowledge graph. **Availability differs by environment:**

- In the GitHub Copilot **coding agent** environment it is pre-installed via
  `.github/workflows/copilot-setup-steps.yml`, which also registers this skill
  (`graphify install --platform copilot`) and pre-builds the graph at
  `graphify-out/graph.json` before the task starts, so the `graphify` CLI is on
  `PATH` and the commands below run as written.
- In the **local dev container** the CLI is intentionally NOT installed into the
  environment. Instead, run every `graphify` subcommand through the isolated,
  network-free container wrapper `scripts/build-graph.sh`, which forwards its
  arguments to a `graphify` CLI living inside a throwaway container (repository
  mounted read-only, `--network none`). Prefix the commands below with
  `scripts/build-graph.sh`, e.g. `scripts/build-graph.sh graphify query "..."`.

Code is extracted **locally** with tree-sitter (AST) — **no API key and no network
call is required** for `update`, `query`, `path`, or `explain`. The graph and its
report under `graphify-out/` are generated artifacts and are git-ignored.

## When to use it

Reach for graphify *before* `grep`/`glob` or opening files when you need to
understand the codebase. A single `graphify query` returns the relevant
functions, classes, files, and their relationships in a compact form, which keeps
token usage low. Fall back to reading specific files only after the query points
you at them.

## Make sure the graph exists / is fresh

```bash
# coding agent (CLI on PATH):
graphify update .
# local dev container (isolated, network-free container):
scripts/build-graph.sh
```

This re-extracts code files and (re)writes `graphify-out/graph.json` with no LLM
needed. Run it once at the start of a task if `graphify-out/graph.json` is
missing, and again after you make significant code changes so later queries
reflect your edits.

## Query the graph (preferred)

```bash
graphify query "how are saving throws calculated"
graphify query "what computes derived combat stats" --budget 1500
```

Returns a breadth-first slice of the graph (nodes + edges) answering the question.
Use `--budget N` to cap the output at roughly N tokens, and `--dfs` to trace a
single path rather than gather broad context.

## Trace a path between two concepts

```bash
graphify path "AttacksTab" "GameDataRepository"
```

Prints the shortest dependency/relationship path between two named nodes.

## Explain a single node

```bash
graphify explain "compute_derived_stats()"
```

Gives a plain-language summary of a node and its immediate neighbours.

## Read the architecture overview

`graphify-out/GRAPH_REPORT.md` lists the most-connected ("god") nodes, surprising
cross-module connections, and suggested questions. Skim it for a high-level map;
use targeted `graphify query` calls for specifics.
