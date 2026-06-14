#!/usr/bin/env bash
#
# Launch the HeroForge-Anew PyQt6 application in a container for QA
# "developer-in-the-loop" testing.
#
# It auto-detects a container engine (podman is preferred per project policy,
# falling back to docker), exports the host UID/GID, and brings up the
# docker-compose stack. The viewable desktop is hosted entirely inside the
# `display` sidecar (Xvfb + noVNC); no host X server is involved. The GUI is
# viewable at http://localhost:6080 (gated by the VNC password from .env).
#
# Usage:
#   scripts/run-gui.sh             # build (if needed) and run the GUI
#   scripts/run-gui.sh --build     # force a rebuild
#   scripts/run-gui.sh down        # tear the whole stack down (app + display)
#
# Any extra arguments are forwarded to the underlying compose command.

set -euo pipefail

cd "$(dirname "$0")/.."

# Align the in-container user with the current user for socket/file permissions.
export APP_UID="$(id -u)"
export APP_GID="$(id -g)"

# Pick a compose front-end. Podman is preferred (rootless / more secure);
# docker is used as a fallback.
if command -v podman-compose >/dev/null 2>&1; then
    COMPOSE=(podman-compose)
elif command -v podman >/dev/null 2>&1 && podman compose version >/dev/null 2>&1; then
    COMPOSE=(podman compose)
elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE=(docker-compose)
else
    echo "error: no podman/docker compose front-end found on PATH." >&2
    echo "       Inside a Codespace this is provided by the docker-in-docker" >&2
    echo "       feature in .devcontainer/devcontainer.json." >&2
    exit 1
fi

# Subcommands like "down" / "logs" are passed straight through; otherwise default
# to bringing the stack up with a build.
if [[ "${1:-}" =~ ^(down|logs|ps|stop|build|config)$ ]]; then
    echo "Using: ${COMPOSE[*]} -f docker-compose.yml $*"
    exec "${COMPOSE[@]}" -f docker-compose.yml "$@"
fi

# The display sidecar requires a VNC password to gate noVNC access. Compose
# auto-loads it from a git-ignored .env file; fail early with guidance if it is
# defined in neither the environment nor .env.
if [[ -z "${VNC_PASSWORD:-}" ]] && ! { [[ -f .env ]] && grep -q '^VNC_PASSWORD=' .env; }; then
    echo "error: VNC_PASSWORD is not set." >&2
    echo "       Copy .env.example to .env and set a strong VNC_PASSWORD:" >&2
    echo "         cp .env.example .env   # then edit .env" >&2
    echo "       It gates the noVNC desktop at http://localhost:6080." >&2
    exit 1
fi

echo "Using: ${COMPOSE[*]}  (UID=$APP_UID, GID=$APP_GID)"
echo "View the GUI at http://localhost:6080 (use your VNC_PASSWORD from .env)."
exec "${COMPOSE[@]}" -f docker-compose.yml up --build "$@"
