"""HeroForge-Anew application entry point.

Run with: python -m heroforge  (or: python src/main.py)

This is a thin shim. The launch logic lives in :mod:`heroforge.app` so that all
invocation styles share a single source of truth:

* ``heroforge`` console script  -> ``main:main`` (this module)
* ``python -m heroforge``        -> ``heroforge/__main__.py``
* ``python src/main.py``         -> this module
"""

from __future__ import annotations

from heroforge.app import main

if __name__ == "__main__":
    main()
