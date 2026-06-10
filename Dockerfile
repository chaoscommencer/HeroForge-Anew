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
RUN groupadd --gid "${APP_GID}" app \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" --create-home --shell /bin/bash app

WORKDIR /app

# --- Python dependencies ------------------------------------------------------
# Copy pyproject.toml first and install the third-party runtime dependencies in
# their own layer. Because this layer only depends on pyproject.toml, editing
# application source does NOT bust the cache and re-download the large wheels
# (PyQt6 alone is ~95 MB), which keeps rebuilds fast.
#
# --only-binary=:all: forces pip to install prebuilt wheels and never build a
# downloaded sdist. pip has no npm-style post-install hooks, so the only place
# third-party code could run during install is an sdist's build backend; this
# flag removes that, making it the closest equivalent to `npm --ignore-scripts`.
COPY pyproject.toml README.md ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir --only-binary=:all: PyQt6>=6.6 openpyxl>=3.1

# --- Application source -------------------------------------------------------
# Source changes most often, so copy it last to maximise cache hits above. The
# editable install (--no-deps: dependencies are already installed above) keeps
# the project root at /app so data/ and the auto-seeded heroforge.db resolve.
# At QA runtime, docker-compose.yml bind-mounts src/, data/ and the workbooks
# over this layer for live, developer-in-the-loop editing.
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
