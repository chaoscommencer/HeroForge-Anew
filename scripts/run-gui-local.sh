#!/usr/bin/env bash
#
# Run the HeroForge-Anew GUI for QA as plain processes inside the devcontainer,
# with no container engine. This is the GUI path for the default (unprivileged)
# devcontainer profile, which has no Docker-in-Docker; the Compose stack
# (scripts/run-gui.sh) is for the opt-in QA profile in .devcontainer/qa/.
#
# It starts the same desktop stack the Compose `display` sidecar runs
# (scripts/display-entrypoint.sh: Xvfb -> fluxbox -> x11vnc -> websockify/noVNC)
# as background processes, then runs the app in the foreground on that display.
# Closing the app (or Ctrl-C) stops the desktop and deletes every per-run file.
#
# View it by opening the forwarded port 6080 from VS Code's Ports panel (or
# https://localhost:6080/vnc.html) and entering the one-time password printed
# below. websockify listens on 127.0.0.1 only, so the port is reachable solely
# through Codespaces / VS Code port forwarding, which is private to you.
#
# Security, compared with the Compose stack: the VNC password, TLS key, X cookie
# and desktop config all live in a private 0700 directory on a RAM-backed tmpfs
# and are deleted on exit, and the password never appears on a command line. The
# app itself, however, runs as your own user with your network access and your
# workspace, rather than in a network-less, read-only container.
#
# Usage:
#   scripts/run-gui-local.sh [app arguments...]
#
# Environment overrides: HEROFORGE_DISPLAY (default :99), NOVNC_PORT (default
# 6080), SCREEN_GEOMETRY (default 1920x1080).

set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$PWD"

# shellcheck source=scripts/lib/vnc-secret.sh
source scripts/lib/vnc-secret.sh

DISPLAY_NAME="${HEROFORGE_DISPLAY:-:99}"
NOVNC_PORT="${NOVNC_PORT:-6080}"
if [[ ! "${DISPLAY_NAME}" =~ ^:[0-9]{1,3}$ ]]; then
    echo "error: HEROFORGE_DISPLAY='${DISPLAY_NAME}' is invalid (expected e.g. :99)." >&2
    exit 1
fi
if [[ ! "${NOVNC_PORT}" =~ ^[0-9]{2,5}$ ]]; then
    echo "error: NOVNC_PORT='${NOVNC_PORT}' is invalid." >&2
    exit 1
fi

# --- Preflight --------------------------------------------------------------
missing=()
for tool in Xvfb fluxbox x11vnc websockify xauth xdpyinfo openssl; do
    command -v "${tool}" >/dev/null 2>&1 || missing+=("${tool}")
done
if ((${#missing[@]})); then
    echo "error: missing desktop tools: ${missing[*]}" >&2
    echo "       They are installed in the default devcontainer image" >&2
    echo "       (.devcontainer/Dockerfile.devcontainer-default). Rebuild or create the" >&2
    echo "       Codespace from .devcontainer/devcontainer.json." >&2
    exit 1
fi
if [[ -e "/tmp/.X11-unix/X${DISPLAY_NAME#:}" ]]; then
    echo "error: display ${DISPLAY_NAME} is already in use; set HEROFORGE_DISPLAY." >&2
    exit 1
fi
if (exec 3<>"/dev/tcp/127.0.0.1/${NOVNC_PORT}") 2>/dev/null; then
    echo "error: port ${NOVNC_PORT} is already in use (is another GUI session running?)." >&2
    exit 1
fi

# --- Per-run private directory ----------------------------------------------
# Everything secret for this run lives here: the password file, the X cookie,
# and (because the entrypoint runs with HOME pointed here) x11vnc's one-shot
# password copy, the TLS key and the fluxbox config.
RUN_DIR="$(mktemp -d "$(secret_parent_dir)/heroforge-gui.XXXXXXXX")"
chmod 700 "${RUN_DIR}"
DISPLAY_PID=""

cleanup() {
    trap - EXIT INT TERM
    if [[ -n "${DISPLAY_PID}" ]] && kill -0 "${DISPLAY_PID}" 2>/dev/null; then
        # The entrypoint's own TERM trap stops Xvfb, fluxbox, x11vnc and websockify.
        kill -TERM "${DISPLAY_PID}" 2>/dev/null || true
        wait "${DISPLAY_PID}" 2>/dev/null || true
    fi
    rm -rf "${RUN_DIR}"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

PASSWORD_FILE="${RUN_DIR}/vnc_password"
VNC_PASSWORD_ONCE="$(gen_password)"
(
    umask 077
    printf '%s' "${VNC_PASSWORD_ONCE}" >"${PASSWORD_FILE}"
)
chmod 600 "${PASSWORD_FILE}"

# --- Start the desktop ------------------------------------------------------
# env -u VNC_PASSWORD: the entrypoint must take the password from the file only.
env -u VNC_PASSWORD \
    HOME="${RUN_DIR}" \
    DISPLAY="${DISPLAY_NAME}" \
    XAUTHORITY="${RUN_DIR}/Xauthority" \
    VNC_PASSWORD_FILE="${PASSWORD_FILE}" \
    NOVNC_HOST=127.0.0.1 \
    NOVNC_PORT="${NOVNC_PORT}" \
    "${REPO_ROOT}/scripts/display-entrypoint.sh" >"${RUN_DIR}/display.log" 2>&1 &
DISPLAY_PID=$!

# Wait until noVNC answers (the entrypoint reads the password file before it
# starts anything, so by then the file is no longer needed).
ready=0
for _ in $(seq 1 100); do
    if ! kill -0 "${DISPLAY_PID}" 2>/dev/null; then
        break
    fi
    if (exec 3<>"/dev/tcp/127.0.0.1/${NOVNC_PORT}") 2>/dev/null; then
        ready=1
        break
    fi
    sleep 0.2
done
rm -f "${PASSWORD_FILE}"
if [[ "${ready}" != 1 ]]; then
    echo "error: the desktop did not start. Its log:" >&2
    sed 's/^/  | /' "${RUN_DIR}/display.log" >&2 || true
    exit 1
fi

echo
echo "  VNC password for this session: ${VNC_PASSWORD_ONCE}"
echo "  Open the forwarded port ${NOVNC_PORT} from the Ports panel (or"
echo "  https://localhost:${NOVNC_PORT}/vnc.html) and enter it. It is shown only"
echo "  here and changes on every launch. Close the app or press Ctrl-C to stop."
echo
unset VNC_PASSWORD_ONCE

# --- Run the app ------------------------------------------------------------
# Foreground, not exec, so the EXIT trap tears the desktop down afterwards.
status=0
DISPLAY="${DISPLAY_NAME}" XAUTHORITY="${RUN_DIR}/Xauthority" \
    PYTHONPATH="${REPO_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}" \
    python -m heroforge "$@" || status=$?
exit "${status}"
