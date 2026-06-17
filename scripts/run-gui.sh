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
# For a complete teardown, append --remove-orphans (and --volumes to also drop
# the persistent data/X11 volumes), e.g. `scripts/run-gui.sh down
# --remove-orphans --volumes`. --remove-orphans also removes containers for
# services that were renamed/removed from docker-compose.yml since the stack was
# last started, which a bare `down` would otherwise leave behind.
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

    # .env holds the VNC password in plaintext, so keep it owner-only (it is
    # commonly created world-readable/writable by the default umask or a copied
    # .env.example). This does not weaken anything that depended on a looser
    # mode; nothing reads .env but this script and the compose front-end, both
    # run as the dev user.
    chmod 600 .env
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
#
# Under rootless Podman the file is additionally re-owned (still 0600) to the
# subordinate UID that backs the container's non-root `app` user, so `app` can
# read it WITHOUT the security-weakening `userns_mode: keep-id` (see
# docker-compose.podman.yml). Docker maps the container user 1:1 to the host dev
# user and reads the 0600 file as its owner, so it needs no remap.
write_vnc_secret_file() {
    local pw=""
    if [[ -f .env ]]; then
        pw="$(sed -n 's/^VNC_PASSWORD=//p' .env | tail -n1)"
    fi
    mkdir -p "$(dirname "$SECRET_FILE")"
    # Remove any prior copy first: a previous Podman run may have left the file
    # owned by a subordinate UID (via the unshare-chown below), which this
    # process (the unprivileged dev user) cannot truncate in place but can
    # unlink, because it owns the parent secrets/ directory.
    rm -f "$SECRET_FILE"
    ( umask 077; printf '%s' "$pw" >"$SECRET_FILE" )
    chmod 600 "$SECRET_FILE"

    # Rootless Podman maps the container's `app` user (APP_UID) to a high
    # subordinate UID on the host, so a host-dev-owned 0600 secret appears owned
    # by another user inside the container and is unreadable. The old fix,
    # `userns_mode: keep-id`, mapped `app` straight onto the host dev user and so
    # collapsed the rootless escape isolation that is the main reason we prefer
    # Podman. Instead, re-own the secret to that subuid: `podman unshare` enters
    # the rootless user namespace (where the dev user is root and APP_UID maps to
    # the subuid), so chowning to APP_UID there sets the host file's owner to the
    # subuid. The file stays mode 0600 — now owned by a high subuid, hence
    # unreadable to other *host* users as well — yet appears `app`-owned and
    # readable inside the container.
    if [[ "${COMPOSE[0]}" == podman* ]]; then
        podman unshare chown "$APP_UID:$APP_GID" "$SECRET_FILE"
    fi
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

# Assemble the list of Compose files. docker-compose.yml is the hardened base
# used by every engine. When the engine is Podman, layer docker-compose.podman.yml
# on top: it only disables the healthcheck-based dependency gate (podman-compose
# < 4.4 cannot evaluate `condition: service_healthy`) and substitutes a
# wait-for-X-socket command so the app still starts once the display is ready.
# It deliberately does NOT relax the user namespace, init, or resource limits;
# those are inherited unchanged, with catatonit (init) and crun (runtime)
# supplied by scripts/setup-podman.sh. Docker keeps the base configuration as-is.
COMPOSE_FILES=(-f docker-compose.yml)
if [[ "${COMPOSE[0]}" == podman* ]]; then
    COMPOSE_FILES+=(-f docker-compose.podman.yml)
fi

# Subcommands like "down" / "logs" are passed straight through; otherwise default
# to bringing the stack up with a build. Even these need the secret file to exist
# so Compose can resolve the `vnc_password` secret reference while parsing the
# file, so materialize it (from whatever .env currently holds) first.
#
# Tip: for a thorough `down`, add --remove-orphans (sweeps up containers for
# services no longer defined in docker-compose.yml) and --volumes (also drops the
# persistent heroforge-data and x11-socket volumes); these are forwarded as-is.
if [[ "${1:-}" =~ ^(down|logs|ps|stop|build|config)$ ]]; then
    write_vnc_secret_file
    # `down` emits one line per resource it removes, straight from the compose
    # engine. Each container appears twice (once when stopped, once when
    # removed) and volumes/network follow — clarify that up front so the
    # repeated names are not mistaken for an error. (With the Podman override's
    # `in_pod: false` there is no pod line; under the default pod an extra bare
    # pod ID would also be printed.)
    #
    # Scan every argument for the `down` subcommand rather than assuming it is
    # $1: although the guard above currently matches on $1, the subcommand is
    # not guaranteed to stay positional (e.g. a future global flag could precede
    # it), so detect it by value.
    is_down=0
    for arg in "$@"; do
        if [[ "$arg" == "down" ]]; then
            is_down=1
            echo "Tearing down the QA stack: each container is listed twice (stopped, then removed),"
            echo "followed by any volumes (with --volumes) and the network."
            break
        fi
    done
    # Stop the `app` service before tearing the rest of the stack down so the Qt
    # process exits while its X server is still alive. Without the default Podman
    # pod (removed via `x-podman: in_pod: false` in docker-compose.podman.yml),
    # podman-compose's `down` stops services individually and does NOT honour the
    # app's `depends_on: display` on the teardown path, so the display sidecar's
    # Xvfb can be killed first — removing the shared /tmp/.X11-unix/X99 socket out
    # from under the still-running app. Qt's Xlib reacts to that with a fatal
    # "XIO: ... IO error 2 (No such file or directory) on X server ':99'" on the
    # way down. Quiescing `app` first (Docker already orders this via depends_on;
    # this makes the order explicit for Podman too) lets the GUI close cleanly and
    # suppresses that benign-but-alarming shutdown error. The stop is best-effort:
    # if the app container is already gone (e.g. it crashed earlier) `stop` is a
    # no-op, so a non-zero result here must not abort the real teardown below.
    if [[ "$is_down" == 1 ]]; then
        "${COMPOSE[@]}" "${COMPOSE_FILES[@]}" stop app >/dev/null 2>&1 || true
    fi
    echo "Using: ${COMPOSE[*]} ${COMPOSE_FILES[*]} $*"
    exec "${COMPOSE[@]}" "${COMPOSE_FILES[@]}" "$@"
fi

# Ensure .env carries a usable, strong VNC password before launching the stack
# (generating one when missing/placeholder, or whenever --generate-password is
# given), then write it into the git-ignored secret file that Compose mounts
# into the display sidecar at /run/secrets/vnc_password.
ensure_vnc_password "$GENERATE_PASSWORD"
write_vnc_secret_file

echo "Using: ${COMPOSE[*]}  (UID=$APP_UID, GID=$APP_GID)"
echo "View the GUI at http://localhost:6080 (use your VNC_PASSWORD from .env)."
exec "${COMPOSE[@]}" "${COMPOSE_FILES[@]}" up --build "$@"
