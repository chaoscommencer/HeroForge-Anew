#!/usr/bin/env bash
#
# Launch the HeroForge-Anew PyQt6 application in a container for QA
# "developer-in-the-loop" testing.
#
# It auto-detects a container engine (podman is preferred per project policy,
# falling back to docker), exports the host UID/GID, and brings up the
# docker-compose stack. The viewable desktop is hosted entirely inside the
# `display` sidecar (Xvfb + noVNC); no host X server is involved. The GUI is
# viewable at https://localhost:6080/vnc.html through the forwarded port 6080
# (gated by a one-time VNC password this script prints).
#
# Usage:
#   scripts/run-gui.sh                      # build (if needed) and run the GUI
#   scripts/run-gui.sh --build              # force a rebuild
#   scripts/run-gui.sh down                 # tear the whole stack down
#
# Every launch generates a fresh, random VNC password and prints it once. The
# password is never written to .env or anywhere in the repository: it is handed
# to Compose through a 0600 file in a private directory on a RAM-backed tmpfs,
# and that file is deleted as soon as the display container is up (see
# start_vnc_secret_cleanup below).
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

# --- One-time VNC password ---------------------------------------------------
# gen_password, secret_parent_dir, write_secret_file and port_open are shared
# with scripts/run-gui-local.sh.
# shellcheck source=scripts/lib/vnc-secret.sh
source scripts/lib/vnc-secret.sh

# Write a fresh password to a 0600 file inside a new 0700 directory and export
# its path as HEROFORGE_VNC_SECRET_FILE, which docker-compose.yml uses as the
# source of the `vnc_password` secret (mounted at /run/secrets/vnc_password in
# the display sidecar). write_secret_file keeps the password out of every
# process's argument list.
#
# Under rootless Podman the file is re-owned (still 0600) to the subordinate UID
# that backs the container's non-root `app` user, so `app` can read it WITHOUT
# the security-weakening `userns_mode: keep-id`: `podman unshare` enters the
# rootless user namespace, where chowning to APP_UID sets the host owner to that
# subuid. Docker maps the container user 1:1 to the host dev user, so it needs no
# remap.
#
# The EXIT trap is set straight after mktemp, so the directory is removed if any
# later step fails (the podman chown included). `exec` does not run the trap;
# the background watcher (start_vnc_secret_cleanup) takes over from there.
create_vnc_secret() {
    VNC_SECRET_DIR="$(mktemp -d "$(secret_parent_dir)/heroforge-vnc.XXXXXXXX")"
    trap 'rm -rf "$VNC_SECRET_DIR"' EXIT
    chmod 700 "$VNC_SECRET_DIR"
    export HEROFORGE_VNC_SECRET_FILE="${VNC_SECRET_DIR}/vnc_password"
    VNC_PASSWORD_ONCE="$(gen_password)"
    write_secret_file "$HEROFORGE_VNC_SECRET_FILE" "$VNC_PASSWORD_ONCE"
    if [[ "${COMPOSE[0]}" == podman* ]]; then
        podman unshare chown "$APP_UID:$APP_GID" "$HEROFORGE_VNC_SECRET_FILE"
    fi
}

# display_containers [running]: print the IDs of this project's display
# containers (only running ones with the `running` argument), using the
# com.docker.compose.* labels that both Docker Compose and podman-compose set.
display_containers() {
    local filters=(
        --filter "label=com.docker.compose.project=heroforge-anew"
        --filter "label=com.docker.compose.service=display"
    )
    if [[ "${1:-}" == running ]]; then
        filters+=(--filter status=running)
    fi
    "$ENGINE" ps -aq --no-trunc "${filters[@]}" 2>/dev/null || true
}

# Delete the secret directory in the background once it is no longer needed.
# Compose bind-mounts the file into the display container when the container
# starts; the mount keeps the file readable inside the container after the host
# path is unlinked, so the host copy can go as soon as the container is up. The
# watcher removes it when the first of these happens:
#   * a display container that did not exist when this launch began is running,
#     so it was created from this launch's secret and has it mounted (a
#     listener on port 6080 proves nothing: it may be another process, or a
#     container from an earlier launch);
#   * the compose process (this script's PID, after `exec`) exits; or
#   * 30 minutes pass (a stuck or very slow first build).
start_vnc_secret_cleanup() {
    local owner_pid=$$ dir="$VNC_SECRET_DIR" existing
    existing=" $(display_containers | tr '\n' ' ') "
    (
        trap 'rm -rf "$dir"' EXIT
        deadline=$((SECONDS + 1800))
        while ((SECONDS < deadline)) && kill -0 "$owner_pid" 2>/dev/null; do
            for id in $(display_containers running); do
                if [[ "$existing" != *" ${id} "* ]]; then
                    exit 0
                fi
            done
            sleep 1
        done
    ) </dev/null >/dev/null 2>&1 &
}

# Older versions of this script stored the password in .env and in
# secrets/vnc_password. Remove that generated file, and point out the now-unused
# .env line (the user's .env itself is left alone).
clean_legacy_vnc_secret() {
    if [[ -e secrets/vnc_password ]]; then
        rm -f secrets/vnc_password
        rmdir secrets 2>/dev/null || true
        echo "Removed the old stored VNC password file secrets/vnc_password."
    fi
    if [[ -f .env ]] && grep -q '^VNC_PASSWORD=' .env; then
        echo "note: .env still has a VNC_PASSWORD line. It is no longer used (each launch"
        echo "      gets a fresh one-time password); delete that line from .env."
    fi
}

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
    echo "       In a Codespace, Docker comes with the QA profile" >&2
    echo "       (.devcontainer/qa/devcontainer.json). In the default profile use" >&2
    echo "       scripts/run-gui-local.sh instead." >&2
    exit 1
fi
# The container engine CLI behind the compose front-end, for `ps` queries.
if [[ "${COMPOSE[0]}" == podman* ]]; then
    ENGINE=podman
else
    ENGINE=docker
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
# to bringing the stack up with a build. These need no password: with
# HEROFORGE_VNC_SECRET_FILE unset, docker-compose.yml points the secret at
# /dev/null, which is enough for Compose to parse the file.
#
# Tip: for a thorough `down`, add --remove-orphans (sweeps up containers for
# services no longer defined in docker-compose.yml) and --volumes (also drops the
# persistent heroforge-data and x11-socket volumes); these are forwarded as-is.
if [[ "${1:-}" =~ ^(down|logs|ps|stop|build|config)$ ]]; then
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

# The display publishes noVNC on 127.0.0.1:6080. If something already listens
# there (scripts/run-gui-local.sh, a stack from an earlier launch, or any other
# process), the new display cannot bind it, and the password printed below
# would not belong to whatever answers. Stop here instead.
if port_open 6080; then
    echo "error: port 6080 is already in use. Stop the other GUI first:" >&2
    echo "       scripts/run-gui.sh down, or close scripts/run-gui-local.sh." >&2
    exit 1
fi

# Create this launch's one-time password, schedule its file for deletion, and
# show it once.
clean_legacy_vnc_secret
create_vnc_secret
start_vnc_secret_cleanup

echo "Using: ${COMPOSE[*]}  (UID=$APP_UID, GID=$APP_GID)"
echo
echo "  VNC password for this session: ${VNC_PASSWORD_ONCE}"
echo "  Open the forwarded port 6080 from the Ports panel (or"
echo "  https://localhost:6080/vnc.html) and enter it. It is shown only here and"
echo "  changes on every launch."
echo
unset VNC_PASSWORD_ONCE
# --force-recreate: every launch has a new secret file path, and the watcher
# deletes the old one. Compose's change detection does not look at a secret's
# host path, so without this it could restart a container left over from an
# earlier launch (stopped by Ctrl-C, or still running) with that deleted file:
# a "bind source path does not exist" failure, or a desktop that rejects the
# password printed above. Recreating also gives the watcher the new container
# it waits for. The app keeps its data on the heroforge-data volume.
exec "${COMPOSE[@]}" "${COMPOSE_FILES[@]}" up --build --force-recreate "$@"
