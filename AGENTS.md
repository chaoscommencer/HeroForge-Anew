# AGENTS.md — HeroForge-Anew

The project instructions are in [CLAUDE.md](CLAUDE.md) and
[.github/copilot-instructions.md](.github/copilot-instructions.md); both apply to every agent.

## 1. Graph-first

Query the knowledge graph before broad searches:
`scripts/build-graph.sh --keep-image graphify query "<question>"`. Rebuild it with
`scripts/build-graph.sh --keep-image` after switching branches or making structural changes.
