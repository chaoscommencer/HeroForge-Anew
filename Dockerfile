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
#
# It is a multi-stage build:
#   * the `builder` stage runs pip (and its build/cache machinery) to install the
#     third-party wheels AND the application's own package into an isolated
#     prefix, then
#   * the final stage copies ONLY those installed packages onto a fresh runtime
#     image.
# This keeps pip's caches/metadata and the resolver out of the shipped image, so
# the runtime layer carries just the Qt system libraries and the installed
# Python packages — a smaller image and a smaller attack surface.

# =============================================================================
# Stage 1 — builder: install third-party deps and the app package into /install
# =============================================================================
FROM python:3.12-slim-bookworm AS builder

WORKDIR /app

# Step 1 — third-party dependencies.
# Only pyproject.toml is needed to install the third-party dependencies. The
# app is launched with `python -m heroforge` against PYTHONPATH in the final
# stage, and the source is provided at runtime by the docker-compose bind mount.
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
# duplicated or kept in sync here. They are installed under --prefix=/install so
# the whole dependency tree can be copied into the final stage in one layer.
COPY pyproject.toml ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir --only-binary=:all: --prefix=/install \
        $(python -c "import tomllib; print(' '.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))")

# Step 2 — the application's own package.
# Install heroforge into the same /install prefix so it ships as a proper
# installed distribution (dist-info metadata + the `heroforge` console script)
# that is copied into the final image alongside the dependencies — not merely
# importable via a PYTHONPATH env var. The editable (-e) install records ONLY a
# .pth pointing at /app/src; it never copies the sources, so the actual code is
# still supplied at runtime by the docker-compose bind mount over /app/src (a
# bare run without that mount has no app code, by design).
#
# src/ is provided to just this build step via a transient BuildKit bind mount.
# The mount is read-write because setuptools' egg_info step writes a
# src/heroforge.egg-info directory into the source tree during the editable build
# (a read-only mount fails with "Cannot update time stamp of directory"). Those
# writes land only in BuildKit's ephemeral mount, which it discards — the host
# src/ is untouched and no source is baked into the image. --no-deps is used
# because the third-party dependencies were already installed in step 1.
RUN --mount=type=bind,source=src,target=/app/src,rw \
    python -m pip install --no-cache-dir --no-deps -e . --prefix=/install

# =============================================================================
# Stage 2 — final runtime image
# =============================================================================
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

# --- Installed Python packages (deps + the app) ------------------------------
# Copy ONLY what was installed into /install in the builder stage onto this fresh
# image (merging into /usr/local, where this base image's Python looks): the
# third-party dependencies plus the heroforge editable distribution (its .pth and
# dist-info metadata and the `heroforge` console script). pip itself, its caches
# and the resolver stay behind in the builder and never ship in the runtime image.
COPY --from=builder /install /usr/local

# WORKDIR creates /app owned by root; chown it to the unprivileged app user so
# the application can write heroforge.db there on first launch. The database is
# seeded at runtime into the project root, which is /app inside the container
# (see src/heroforge/app.py); without this the non-root user could not create it.
WORKDIR /app
RUN chown app:app /app
USER app

# QT_X11_NO_MITSHM disables the MIT-SHM X extension, which does not work across
# the container boundary; PYTHONUNBUFFERED surfaces logs immediately for QA.
# No PYTHONPATH is needed: the editable install copied from the builder writes a
# .pth that puts /app/src on the import path, so `python -m heroforge` resolves
# once the docker-compose bind mount populates /app/src at runtime.
ENV QT_X11_NO_MITSHM=1 \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:1

# CMD (not ENTRYPOINT) is used so this QA image stays easy to poke at: a bare
# `docker run heroforge-anew:dev <cmd>` overrides it to drop into a shell or run
# the test suite for debugging, while docker-compose.yml still launches the GUI
# by default. docker-compose can override it with `command:` if ever needed.
CMD ["python", "-m", "heroforge"]
