# HeroForge-Anew — Claude Instructions

HeroForge-Anew is a D&D 3.5 character builder being converted from an Excel/VBA workbook to a
Python 3 application backed by SQLite with a PyQt6 user interface. The project's conventions,
layout, domain concepts and quality checks live in the Copilot instructions, which apply to every
agent:

@.github/copilot-instructions.md

The conversion strategy is [docs/conversion-plan.md](docs/conversion-plan.md). Read it before
starting feature work.

## graphify (do this first)

The repository is mapped into a knowledge graph at `graphify-out/graph.json` (git-ignored). Query
it before grepping or opening files; a scoped query costs far fewer tokens than reading source.

The `graphify` CLI is not installed in the editor container. Every subcommand runs through the
network-isolated container wrapper, and **always with `--keep-image`**, so the builder image is
reused instead of being deleted and rebuilt on the next call:

```bash
scripts/build-graph.sh --keep-image                                   # build or refresh the graph
scripts/build-graph.sh --keep-image graphify query "<question>" --budget 1500
scripts/build-graph.sh --keep-image graphify path "<A>" "<B>"
scripts/build-graph.sh --keep-image graphify explain "<symbol>"
```

Rules:

- For codebase questions, run `graphify query` first when `graphify-out/graph.json` exists. Use
  `path` for relationships and `explain` for one symbol. Cap output with `--budget`.
- Read `graphify-out/GRAPH_REPORT.md` only for broad architecture review, or when
  query/path/explain don't surface enough.
- Read source files only to modify or debug specific code the graph pointed at, or when the graph
  lacks the detail.
- Git hooks installed by `scripts/install-graph-hooks.sh` rebuild the graph in the background
  after every commit and branch checkout, including in `git worktree` checkouts; the last run's
  log is `graphify-out/.hook.log`. If the hooks are missing (a fresh clone or a rebuilt
  Codespace), run that script once. Rebuild by hand (`scripts/build-graph.sh --keep-image`) when
  the graph is missing or you need it current before your next commit.

## Ownership

The onus is on you to produce a high-quality, functioning product.

- **You own the code.** Treat every file as yours to maintain. Do not leave half-finished code,
  placeholders, or TODOs without a tracking note. Fix the problems you find, even ones you did not
  cause, or flag them clearly.
- **Prove your work.** A change is not done until it is shown to work: tests pass, lint and
  formatting checks are clean, and behaviour changes are run and observed. Say exactly what you ran
  and what it showed. If something could not be verified, say so plainly.
- **Finish the job.** Carry the task through to working, tested, documented code. Do not stop at a
  plan or a partial implementation unless the user asked for that, or you are blocked on a decision
  that belongs to the user.

## Design

- **Single-purpose types**: each type does one job and has one reason to change. When a type
  starts gathering a second responsibility, split it. Prefer small value types and narrow
  interfaces over large classes.

## Commits

- Each commit is a single, functional, atomic change. Each builds and passes tests on its own. Do
  not mix refactors, formatting, and behavior changes in one commit.
- Commit messages follow the Conventional Commits rules in the Copilot instructions and say what
  changed and why, in plain English.
- Add no attribution: no `Co-authored-by` trailer and no line saying a tool generated the message.

## Security

Follow strong security practices at all times.

- **Secrets**: never commit or log credentials, tokens, keys, or personal data. Never send the
  user's details to outside services.
- **Dependencies**: pin every dependency to an exact version (hash-locked requirements, image
  digests, action commit SHAs). Prefer well-maintained packages. Justify every new dependency.
- **Least privilege**: build and asset tools run with no network, no credentials, and the caller's
  uid wherever they can. CI workflows request the minimum token permissions and pin actions by
  commit SHA.
- **Untrusted input**: treat data files, save files, settings, and any downloaded content as
  untrusted. Validate sizes, ranges, and formats before use. A malformed input must fail safely.
- **Sandbox**: never disable or work around the sandbox or permission prompts to finish a task. If
  something is blocked, explain what is missing.

## Working with the user

- **Progress updates**: between steps of work, give one-line updates on what was just done or what
  comes next. A single long-lived summarizer subagent writes them:
  - **Start it once per session.** Before the first update, spawn one Agent with `model: opus`,
    `effort: low`, and `name: summarizer`. Brief it: "You write one-line, plain-English progress
    updates. Each message you receive describes work just executed; reply with exactly one line
    summarizing it for the user. No preamble."
  - **Reuse it.** For every later update, send the executed work (commands run, files changed,
    results) to it with `SendMessage` (`to: "summarizer"`). Do not spawn a new agent per update.
  - **Re-spawn only if needed.** If it is gone (new session, context compacted, or `SendMessage`
    fails), spawn a fresh one with the same brief.
  - **Don't block on it.** Its reply arrives as a notification. Keep working and relay the line
    when it comes. Never invent its reply. If it hasn't answered yet, write the line yourself
    rather than stall.
- **Questions**: when you need the user's input or decision, ask with AskUserQuestion, not with a
  question at the end of a message.
- **Final responses**: concise and practical, in plain, simple English. Say what changed, how it
  was verified, and anything the user needs to do or decide. Skip filler and long recaps.
- **Growing these instructions**: when the user answers a question or states a preference that will
  matter again (style, tooling, scope, priorities), recommend adding it to this file. Propose the
  exact wording.
