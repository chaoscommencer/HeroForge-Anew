#!/usr/bin/env bash
#
# Optional defense-in-depth: enable user-namespace remapping on the Docker
# daemon this dev container talks to (the *inner* dockerd provided by the
# docker-in-docker feature — see .devcontainer/devcontainer.json).
#
# With userns-remap on, the QA containers' in-container UID/GID (the non-root
# `app` user, UID 1000) is mapped to an unprivileged *subordinate* UID on the
# daemon side, so even a process that broke out of a container would not land on
# a privileged user. It complements the per-container `cap_drop: ALL`,
# `no-new-privileges` and read-only-rootfs settings already in docker-compose.yml.
#
# Scope and limits (important):
#   * This configures the INNER daemon inside the dev container. The dev
#     container itself is still a privileged docker-in-docker host on the real
#     machine; remapping the inner containers does NOT harden that outer
#     boundary. The full host-protection benefit of userns-remap is realised
#     when it is set on the REAL host daemon, which this repo cannot reach.
#   * It is global to the inner daemon: every container it runs (the QA stack,
#     the graphify builder, image builds) will be remapped.
#   * Rootless Podman achieves a similar end without daemon configuration — see
#     scripts/setup-podman.sh.
#
# This script is idempotent: re-running it is a no-op once remapping is on.
#
# Usage:
#   scripts/enable-userns-remap.sh           # enable "default" remapping
#   scripts/enable-userns-remap.sh --status  # report current state, change nothing
#   USERNS_REMAP_USER=myuser scripts/enable-userns-remap.sh   # custom remap user
#
# Requires: a Docker daemon you control (the docker-in-docker inner daemon) and
# sudo (the `vscode` dev-container user has passwordless sudo).

set -euo pipefail

DAEMON_JSON="/etc/docker/daemon.json"
REMAP_USER="${USERNS_REMAP_USER:-default}"

err() { printf 'enable-userns-remap: %s\n' "$*" >&2; }

# Report the daemon's current userns-remap state and exit, without modifying it.
print_status() {
    if ! command -v docker >/dev/null 2>&1; then
        err "docker CLI not found on PATH."
        return 1
    fi
    # "Docker Root Dir" gains the remap suffix (e.g. .../100000.100000) when
    # remapping is active; SecurityOptions lists "name=userns" as well.
    if docker info --format '{{json .SecurityOptions}}' 2>/dev/null | grep -q 'userns'; then
        echo "userns-remap: ENABLED on the active Docker daemon."
    else
        echo "userns-remap: not enabled on the active Docker daemon."
    fi
}

if [[ "${1:-}" == "--status" ]]; then
    print_status
    exit 0
fi

if ! command -v docker >/dev/null 2>&1; then
    err "docker CLI not found on PATH. Run inside the dev container (docker-in-docker)."
    exit 1
fi

# Already on? Nothing to do.
if docker info --format '{{json .SecurityOptions}}' 2>/dev/null | grep -q 'userns'; then
    echo "userns-remap already enabled — nothing to do."
    exit 0
fi

# Merge "userns-remap" into any existing /etc/docker/daemon.json without
# clobbering other keys. Prefer python3 (always present in this image) for a
# safe JSON read-modify-write; fall back to writing a fresh file if the existing
# one is absent or unparseable.
echo "Enabling userns-remap=\"${REMAP_USER}\" in ${DAEMON_JSON} ..."

tmp="$(mktemp)"
trap 'rm -f "${tmp}"' EXIT

if sudo test -f "${DAEMON_JSON}"; then
    existing="$(sudo cat "${DAEMON_JSON}")"
else
    existing="{}"
fi

if ! printf '%s' "${existing}" | python3 -c '
import json, sys
try:
    cfg = json.load(sys.stdin)
    if not isinstance(cfg, dict):
        raise ValueError("daemon.json is not a JSON object")
except Exception as exc:  # noqa: BLE001 - surface any parse error to the caller
    sys.stderr.write(f"could not parse existing daemon.json: {exc}\n")
    sys.exit(2)
cfg["userns-remap"] = sys.argv[1]
json.dump(cfg, sys.stdout, indent=2)
sys.stdout.write("\n")
' "${REMAP_USER}" > "${tmp}"; then
    err "Refusing to overwrite an unparseable ${DAEMON_JSON}; fix it by hand."
    exit 2
fi

sudo install -m 0644 "${tmp}" "${DAEMON_JSON}"
echo "Wrote ${DAEMON_JSON}:"
sudo cat "${DAEMON_JSON}"

# Restart the inner daemon so the change takes effect. The docker-in-docker
# feature manages dockerd via the `docker` service script in this image.
echo "Restarting the Docker daemon to apply the change ..."
if command -v service >/dev/null 2>&1 && sudo service docker status >/dev/null 2>&1; then
    sudo service docker restart
elif command -v systemctl >/dev/null 2>&1; then
    sudo systemctl restart docker
else
    err "Could not find a service manager to restart dockerd."
    err "Restart the daemon manually, then re-run with --status to verify."
    exit 1
fi

# Give dockerd a moment to come back, then confirm.
for _ in $(seq 1 10); do
    if docker info >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

print_status
echo
echo "Note: containers and named volumes created BEFORE this change keep their"
echo "old ownership. A fresh QA run (scripts/run-gui.sh) creates remapped ones."
