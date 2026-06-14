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
#   scripts/run-gui.sh                      # build (if needed) and run the GUI
#   scripts/run-gui.sh --build              # force a rebuild
#   scripts/run-gui.sh --generate-password  # rotate the VNC password, then run
#   scripts/run-gui.sh down                 # tear the whole stack down
#
# On a normal run this ensures a .env exists (seeded from .env.example) and that
# it carries a strong, randomly-generated VNC_PASSWORD: one is generated when
# .env is missing, empty, or still set to the "change-me" placeholder. Pass
# --generate-password to force a fresh password even if a real one is already
# set. The active password is always stored in .env for you to read.
#
# Any extra arguments are forwarded to the underlying compose command.

set -euo pipefail

cd "$(dirname "$0")/.."

# Path of the git-ignored file that backs the Compose `vnc_password` secret. The
# password is mounted into the display sidecar at /run/secrets/vnc_password from
# here (see docker-compose.yml), rather than injected as an environment
# variable, so it never lands in the container environment.
SECRET_FILE="secrets/vnc_password"

# --- VNC password helpers ----------------------------------------------------
# The noVNC desktop is gated by VNC_PASSWORD. x11vnc's classic VNC auth only
# honours the first 8 characters, so a longer secret buys nothing here; generate
# exactly 8 from a CSPRNG. The alphabet is restricted to [A-Za-z0-9] so the
# value is safe to drop into .env and sed without escaping.
#
# Read a fixed finite chunk of randomness (head exits normally on EOF) and filter
# it, rather than piping the *infinite* /dev/urandom into `head -c 8` — there the
# downstream head closes the pipe early, tr is killed by SIGPIPE, and under
# `set -o pipefail` that aborts the whole script with exit 141.
gen_password() {
    local raw
    raw="$(LC_ALL=C tr -dc 'A-Za-z0-9' < <(head -c 256 /dev/urandom))"
    printf '%s' "${raw:0:8}"
}

# Write VNC_PASSWORD=<pw> into .env, replacing any existing line or appending a
# new one. The password is alphanumeric, so the sed replacement needs no escaping.
set_env_password() {
    local pw="$1"
    if grep -q '^VNC_PASSWORD=' .env; then
        sed -i "s/^VNC_PASSWORD=.*/VNC_PASSWORD=${pw}/" .env
    else
        printf 'VNC_PASSWORD=%s\n' "$pw" >>.env
    fi
}

# Ensure .env exists and holds a usable VNC password. Generates a new one when
# .env is missing, the password is empty/unset, it is still the "change-me"
# placeholder, or *force* is set (the --generate-password flag).
ensure_vnc_password() {
    local force="$1" current=""

    if [[ ! -f .env ]]; then
        if [[ -f .env.example ]]; then
            cp .env.example .env
            echo "Created .env from .env.example."
        else
            : >.env
            echo "Created empty .env."
        fi
    fi

    # Read the password currently recorded in .env (last VNC_PASSWORD wins).
    current="$(sed -n 's/^VNC_PASSWORD=//p' .env | tail -n1)"

    if [[ "$force" == "1" || -z "$current" || "$current" == "change-me" ]]; then
        local pw
        pw="$(gen_password)"
        set_env_password "$pw"
        echo "Generated a new VNC_PASSWORD in .env: ${pw}"
    else
        echo "Using existing VNC_PASSWORD from .env."
    fi
}

# Materialize the file-based Compose secret from the VNC_PASSWORD recorded in
# .env. docker-compose.yml mounts this file at /run/secrets/vnc_password in the
# display sidecar; a file-based secret (rather than an env var) keeps the
# password out of the container environment, and a *file* source specifically is
# required because the display service runs with a read-only root filesystem.
#
# The file is written 0600 (owner-only) under the git-ignored secrets/ directory.
# When .env carries no password the file is created empty so plain compose
# subcommands (config/down/stop) still resolve the secret reference; the
# entrypoint then refuses to start a passwordless desktop at run time.
write_vnc_secret_file() {
    local pw=""
    if [[ -f .env ]]; then
        pw="$(sed -n 's/^VNC_PASSWORD=//p' .env | tail -n1)"
    fi
    mkdir -p "$(dirname "$SECRET_FILE")"
    ( umask 077; printf '%s' "$pw" >"$SECRET_FILE" )
    chmod 600 "$SECRET_FILE"
}

# Align the in-container user with the current user for socket/file permissions.
export APP_UID="$(id -u)"
export APP_GID="$(id -g)"

# Pull the --generate-password flag out of the argument list (it is ours, not
# compose's); everything else is forwarded to the compose command untouched.
GENERATE_PASSWORD=0
args=()
for arg in "$@"; do
    if [[ "$arg" == "--generate-password" ]]; then
        GENERATE_PASSWORD=1
    else
        args+=("$arg")
    fi
done
set -- ${args[@]+"${args[@]}"}

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
# to bringing the stack up with a build. Even these need the secret file to exist
# so Compose can resolve the `vnc_password` secret reference while parsing the
# file, so materialize it (from whatever .env currently holds) first.
if [[ "${1:-}" =~ ^(down|logs|ps|stop|build|config)$ ]]; then
    write_vnc_secret_file
    echo "Using: ${COMPOSE[*]} -f docker-compose.yml $*"
    exec "${COMPOSE[@]}" -f docker-compose.yml "$@"
fi

# Ensure .env carries a usable, strong VNC password before launching the stack
# (generating one when missing/placeholder, or whenever --generate-password is
# given), then write it into the git-ignored secret file that Compose mounts
# into the display sidecar at /run/secrets/vnc_password.
ensure_vnc_password "$GENERATE_PASSWORD"
write_vnc_secret_file

echo "Using: ${COMPOSE[*]}  (UID=$APP_UID, GID=$APP_GID)"
echo "View the GUI at http://localhost:6080 (use your VNC_PASSWORD from .env)."
exec "${COMPOSE[@]}" -f docker-compose.yml up --build "$@"
