# syntax=docker/dockerfile:1
#
# Singular runtime image for the HeroForge-Anew PyQt6 desktop application.
#
# This image is built and launched via docker-compose.yml (or its podman
# equivalent) for QA "developer-in-the-loop" testing. The GUI is rendered on an
# X server forwarded from the host/devcontainer (see docker-compose.yml and the
# desktop-lite feature in .devcontainer/devcontainer.json).
#
# It is intentionally separate from the development container defined under
# .devcontainer/ — that one is for editing/linting/testing the code, while this
# one exists purely to *run* the application in an isolated, reproducible way.

FROM python:3.12-slim-bookworm

# --- System libraries required by PyQt6 / Qt at runtime ----------------------
# Qt links against a number of shared X11 / OpenGL / XCB / font libraries even
# when it only ever talks to a forwarded X server. They are installed without
# recommended extras to keep the image lean; apt metadata is removed afterwards.
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        libgl1 \
        libegl1 \
        libglib2.0-0 \
        libdbus-1-3 \
        libfontconfig1 \
        libfreetype6 \
        libx11-6 \
        libx11-xcb1 \
        libxcb1 \
        libxcb-cursor0 \
        libxcb-glx0 \
        libxcb-icccm4 \
        libxcb-image0 \
        libxcb-keysyms1 \
        libxcb-randr0 \
        libxcb-render0 \
        libxcb-render-util0 \
        libxcb-shape0 \
        libxcb-shm0 \
        libxcb-sync1 \
        libxcb-util1 \
        libxcb-xfixes0 \
        libxcb-xinerama0 \
        libxcb-xkb1 \
        libxkbcommon0 \
        libxkbcommon-x11-0 \
        libxext6 \
        libxrender1 \
        libsm6 \
        libice6 \
    && rm -rf /var/lib/apt/lists/*

# --- Unprivileged application user -------------------------------------------
# The GUI runs as a non-root user for security. UID/GID are build args so they
# can be aligned with the host/devcontainer user, which keeps ownership of the
# bind-mounted workspace and access to the shared X11 socket sane.
ARG APP_UID=1000
ARG APP_GID=1000
# The login shell is given as the absolute path /bin/bash (not /usr/bin/env
# bash) because useradd --shell writes the value verbatim into /etc/passwd, and
# login/exec runs it directly with no $PATH lookup — so it must be a real path.
# (`/usr/bin/env bash` is only meaningful in a script shebang.) The absolute
# path is both required here and the more deterministic/safer choice.
RUN groupadd --gid "${APP_GID}" app \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" --create-home --shell /bin/bash app

WORKDIR /app

# --- Python dependencies ------------------------------------------------------
# Copy pyproject.toml first and install the third-party runtime dependencies in
# their own layer. Because this layer only depends on pyproject.toml, editing
# application source does NOT bust the cache and re-download the large wheels
# (PyQt6 alone is ~95 MB), which keeps rebuilds fast.
#
# Security: --only-binary=:all: forces pip to install prebuilt wheels and refuse
# to build any downloaded sdist. pip has no npm-style pre/post-install hooks, so
# the ONLY place third-party code can execute during install is an sdist's build
# backend (e.g. setup.py). Refusing sdists removes that arbitrary-code-execution
# surface, making this the closest equivalent to `npm --ignore-scripts`.
#
# The `$(python -c "...")` sub-shell reads project.dependencies out of
# pyproject.toml (via the stdlib tomllib module) and prints them space-separated,
# so the exact same dependency list drives this install — it never has to be
# duplicated or kept in sync here.
COPY pyproject.toml README.md ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir --only-binary=:all: \
        $(python -c "import tomllib; print(' '.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))")

# --- Application source -------------------------------------------------------
# Source changes most often, so copy it last to maximise the cache hits above.
# It is COPYed (not relied on solely via the runtime bind mount) so the image is
# self-contained: a bare `docker run` still has the application code, and the
# editable install below needs the package present at build time to generate its
# metadata. At QA runtime docker-compose.yml bind-mounts src/ over this layer for
# live, developer-in-the-loop edits.
#
# This second pip call installs only our own package, with --no-deps because the
# third-party dependencies were already installed in the cached layer above (so
# this never re-resolves or re-downloads them); -e keeps the project rooted at
# /app so data/ and the auto-seeded heroforge.db resolve relative to it.
COPY src/ ./src/
RUN python -m pip install --no-cache-dir --no-deps -e .

RUN chown -R app:app /app
USER app

# QT_X11_NO_MITSHM disables the MIT-SHM X extension, which does not work across
# the container boundary; PYTHONUNBUFFERED surfaces logs immediately for QA.
ENV QT_X11_NO_MITSHM=1 \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:1

CMD ["python", "-m", "heroforge"]
