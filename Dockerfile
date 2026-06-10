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
# This QA image is always run via docker-compose.yml (or scripts/run-gui.sh),
# which bind-mounts the host src/ over /app/src at runtime for live,
# developer-in-the-loop edits. Baking a COPY of src/ into the image would be
# redundant — that copy gets shadowed by the runtime bind mount anyway — so src/
# is NOT copied here.
#
# Instead src/ is supplied to *only* this build step via a BuildKit bind mount.
# That is just enough for the editable install to record the project metadata
# and an entry pointing at /app/src; the editable install never copies the
# sources, it only writes a .pth referencing /app/src (verified: the install
# resolves at runtime once the Compose bind mount restores /app/src). The mount
# is read-write because setuptools' editable build writes a transient egg-info
# into the tree; BuildKit discards those writes (the host src/ is never modified
# and nothing is baked into the image). --no-deps is used because the
# third-party dependencies were already installed in the cached layer above, so
# this step never re-resolves or re-downloads them.
RUN --mount=type=bind,source=src,target=/app/src,rw \
    python -m pip install --no-cache-dir --no-deps -e .

RUN chown -R app:app /app
USER app

# QT_X11_NO_MITSHM disables the MIT-SHM X extension, which does not work across
# the container boundary; PYTHONUNBUFFERED surfaces logs immediately for QA.
ENV QT_X11_NO_MITSHM=1 \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:1

CMD ["python", "-m", "heroforge"]
