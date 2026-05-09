HeroForge-Anew
==============
HeroForge Anew is a D&D 3.5 character builder. Originally implemented in Excel/VBA, it is now being converted to a modern Python application backed by SQLite and a PyQt6 user interface. It makes the process of character generation far simpler, allowing you to create in minutes what would once have taken hours, and in hours what would once have taken days! Powerful and well designed, it can handle the majority of 3.5 content, and more content is being added. Try it, and never look back!

## Features

- Full D&D 3.5 character creation and management
- Support for races, classes, prestige classes, feats, skills, spells, psionics, incarnum, and more
- Reactive UI that automatically recalculates derived stats
- SQLite-backed character save/load

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

### Generate the Database

```bash
# Seed the SQLite database from the data/ directory
python -m heroforge.db.seed --db heroforge.db --data-dir data/
```

### Run the Application

```bash
python src/main.py
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

