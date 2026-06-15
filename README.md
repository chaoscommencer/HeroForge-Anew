HeroForge-Anew
==============
HeroForge Anew is a D&D 3.5 character builder. Originally implemented in Excel/VBA, it is now being converted to a modern Python application backed by SQLite and a PyQt6 user interface. It makes the process of character generation far simpler, allowing you to create in minutes what would once have taken hours, and in hours what would once have taken days! Powerful and well designed, it can handle the majority of 3.5 content, and more content is being added. Try it, and never look back!

## Features

- Full D&D 3.5 character creation and management
- Support for races, classes, prestige classes, feats, skills, spells, psionics, incarnum, and more
- Reactive UI that automatically recalculates derived stats
- SQLite-backed character save/load
- Session note-taking via the Game Log tab, plus Living Greyhawk legacy logbooks —
  an adventure-record log (LG Game Log) and a magic-item / item-access log
  (LG Item Access / MIL) — retained for legacy characters (deprecated)
- Printable character summaries: a full Character Sheet and a Table Tent (a folded
  name-card you print, fold, and stand on the table), both exportable to text

## Developer Setup

### Prerequisites

- Python 3.11+
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/chaoscommencer/HeroForge-Anew.git
cd HeroForge-Anew

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install the package with development dependencies
pip install -e ".[dev]"
```

### Run the Application

```bash
python src/main.py
```

The application seeds `heroforge.db` automatically on first launch using the source
data files in `data/`. No manual step is required.

If you ever need to re-seed (e.g. after updating a data file), run:

```bash
python -m heroforge.db.seed --db heroforge.db --data-dir data/
```

### Run Tests

```bash
pytest tests/ -v
```

### Lint and Format

```bash
ruff check src/
black src/ tests/
```

### Containerized Development & QA (Codespaces / Docker / Podman)

The project ships an isolated runtime environment so you can develop and QA the
PyQt6 GUI without installing anything locally:

- **Develop** in a ready-to-code Codespace / Dev Container
  (`.devcontainer/`) — Python 3.12, PyQt6 system libraries, and
  Docker-in-Docker.

  > **Note:** The dev container is currently pinned to Python 3.12
  > (`mcr.microsoft.com/devcontainers/python:3-3.12-bookworm@sha256:…`). Consider
  > upgrading to Python 3.14 once it is a generally available devcontainers base
  > image and the project's dependencies (PyQt6, openpyxl, the dev tooling)
  > publish 3.14 wheels; bump `requires-python` and the CI matrix to match.
- **Run the GUI for QA** with a two-container Compose stack
  (`Dockerfile.heroforge-app` + `Dockerfile.display` + `docker-compose.yml`): an
  `app` container running the
  Qt application plus a `display` sidecar that hosts the viewable desktop
  (Xvfb + noVNC). The desktop is gated by a required `VNC_PASSWORD` you set in a
  git-ignored `.env` file:

  ```bash
  cp .env.example .env      # set a strong VNC_PASSWORD (once)
  scripts/run-gui.sh        # build + launch; view at http://localhost:6080
  ```

  The helper auto-detects Podman (preferred) or Docker. See
  [`docs/containerized-runtime.md`](docs/containerized-runtime.md) for details.

### Map the Codebase (Graphify)

The codebase can be mapped into a queryable knowledge graph with
[graphify](https://github.com/safishamsi/graphify) (PyPI package `graphifyy`).
This lets AI coding assistants — and you — answer "how does this fit together?"
questions by querying the graph instead of reading many files, which is faster
and cheaper on tokens. Code is extracted locally with tree-sitter, so no API key
is required.

```bash
pip install graphifyy

# Build / refresh the graph at graphify-out/ (no LLM needed)
graphify update .

# Ask questions instead of grepping
graphify query "how are saving throws calculated"
graphify explain "compute_derived_stats()"
```

The generated `graphify-out/` directory is git-ignored. In Copilot's environment
the tool is pre-installed, the graph is pre-built, and the skill is registered for
Copilot (`graphify install --platform copilot`) by
`.github/workflows/copilot-setup-steps.yml`; see `.github/skills/graphify/SKILL.md`.

To register the graphify skill with your own AI assistant so it uses the graph
automatically, run one of:

```bash
graphify vscode install            # VS Code Copilot Chat
graphify install --platform copilot  # GitHub Copilot CLI
```

## Project Structure

```
src/
├── main.py                    # Application entry point
└── heroforge/
    ├── db/                    # SQLite schema and seed script
    ├── models/                # Dataclass models
    ├── logic/                 # Game rule calculations
    └── ui/                    # PyQt6 user interface
        ├── tabs/              # One widget per character sheet tab
        ├── dialogs/           # Option and custom-entry dialogs
        └── styles/            # Qt stylesheets
tests/                         # pytest test suite
data/                          # Source data files (CSV/XLSX)
docs/
└── conversion-plan.md         # Full conversion plan
```

## WANT TO HELP THIS PROJECT?

I know several of you have offered to help out with this. Well, I finally have something you can do. Now I've put in support for Wild Shape and animal companions, it would be really good if I could get some help with data entry, to add in the stats for more creatures. At the moment, the list of available critters to turn into is pretty limited, and there's barely anything that isn't an animal - so Masters of Many Forms are sad. Anyone up for helping out with that, drop me a message and I'll walk you through the layout and format you need.

