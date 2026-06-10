#!/usr/bin/env bash
#
# Launch the HeroForge-Anew PyQt6 application in a container for QA
# "developer-in-the-loop" testing.
#
# It auto-detects a container engine (podman is preferred per project policy,
# falling back to docker), grants the local X server access, exports the
# host UID/GID and DISPLAY, and brings up the docker-compose stack. Inside a
# Codespace/devcontainer the GUI renders on the desktop-lite desktop, viewable
# at http://localhost:6080 (password: vscode).
#
# Usage:
#   scripts/run-gui.sh             # build (if needed) and run the GUI
#   scripts/run-gui.sh --build     # force a rebuild
#   scripts/run-gui.sh down        # tear the stack down
#
# Any extra arguments are forwarded to the underlying compose command.

set -euo pipefail

cd "$(dirname "$0")/.."

# Display forwarded from the host/devcontainer (desktop-lite uses :1).
export DISPLAY="${DISPLAY:-:1}"
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

# Best-effort: allow local container clients to talk to the X server. Failures
# are non-fatal (e.g. when xhost is absent or access control is already off).
if command -v xhost >/dev/null 2>&1; then
    xhost +local: >/dev/null 2>&1 || true
fi

# Subcommands like "down" / "logs" are passed straight through; otherwise default
# to bringing the stack up with a build.
if [[ "${1:-}" =~ ^(down|logs|ps|stop|build|config)$ ]]; then
    echo "Using: ${COMPOSE[*]} -f docker-compose.yml $*  (DISPLAY=$DISPLAY)"
    exec "${COMPOSE[@]}" -f docker-compose.yml "$@"
fi

echo "Using: ${COMPOSE[*]}  (DISPLAY=$DISPLAY, UID=$APP_UID, GID=$APP_GID)"
echo "View the GUI at http://localhost:6080 (password: vscode)."
exec "${COMPOSE[@]}" -f docker-compose.yml up --build "$@"
