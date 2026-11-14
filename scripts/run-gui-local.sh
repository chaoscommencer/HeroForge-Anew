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
# Credentials: the desktop and the app start from an empty environment plus a
# short allowlist (see safe_env below), so the Codespace's GITHUB_TOKEN, any
# Codespaces secrets, the SSH agent and the VS Code IPC socket are not passed
# to them, and cannot leak into their logs, crash reports or child processes.
# This is not a hard boundary: they still run as your user, and Codespaces
# stores the token in files under /workspaces/.codespaces/shared/ that your user
# can read. For real isolation use the Compose stack (QA profile).
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
# An unprivileged port: 1024-65535. 10# reads values like 08080 as decimal.
if [[ ! "${NOVNC_PORT}" =~ ^[0-9]{1,5}$ ]] || ((10#${NOVNC_PORT} < 1024 || 10#${NOVNC_PORT} > 65535)); then
    echo "error: NOVNC_PORT='${NOVNC_PORT}' is invalid (expected 1024-65535)." >&2
    exit 1
fi
NOVNC_PORT=$((10#${NOVNC_PORT}))
# x11vnc's port, reachable only on 127.0.0.1 (x11vnc -localhost); websockify
# bridges noVNC to it. Fixed, so the readiness check below can probe it.
VNC_PORT=5900

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
for port in "${NOVNC_PORT}" "${VNC_PORT}"; do
    if port_open "${port}"; then
        echo "error: port ${port} is already in use (is another GUI session running?)." >&2
        exit 1
    fi
done

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
write_secret_file "${PASSWORD_FILE}" "${VNC_PASSWORD_ONCE}"

# --- Environment allowlist --------------------------------------------------
# Both the desktop and the app start from `env -i` plus these variables only,
# so tokens and sockets in the devcontainer environment (GITHUB_TOKEN,
# GITHUB_CODESPACE_TOKEN, Codespaces secrets, SSH_AUTH_SOCK,
# VSCODE_IPC_HOOK_CLI, ...) never reach them. VNC_PASSWORD is not on the list:
# the entrypoint must take the password from the file only.
safe_env=()
while IFS= read -r -d '' entry; do
    case "${entry%%=*}" in
        PATH | HOME | USER | LOGNAME | SHELL | TERM | TZ | LANG | LANGUAGE | LC_* | \
            XDG_RUNTIME_DIR | QT_* | LOG_LEVEL | HEROFORGE_* | SCREEN_GEOMETRY)
            safe_env+=("${entry}")
            ;;
    esac
done < <(env -0)

# --- Start the desktop ------------------------------------------------------
# Assignments after "${safe_env[@]}" override any allowlisted value.
env -i "${safe_env[@]}" \
    HOME="${RUN_DIR}" \
    DISPLAY="${DISPLAY_NAME}" \
    XAUTHORITY="${RUN_DIR}/Xauthority" \
    VNC_PASSWORD_FILE="${PASSWORD_FILE}" \
    NOVNC_HOST=127.0.0.1 \
    NOVNC_PORT="${NOVNC_PORT}" \
    VNC_PORT="${VNC_PORT}" \
    "${REPO_ROOT}/scripts/display-entrypoint.sh" >"${RUN_DIR}/display.log" 2>&1 &
DISPLAY_PID=$!

# Wait until both x11vnc and noVNC answer. websockify alone is not enough: if
# x11vnc failed, the browser would show a password prompt that can never
# succeed. (The entrypoint reads the password file before it starts anything,
# so by then the file is no longer needed.)
ready=0
for _ in $(seq 1 100); do
    if ! kill -0 "${DISPLAY_PID}" 2>/dev/null; then
        break
    fi
    if port_open "${VNC_PORT}" && port_open "${NOVNC_PORT}"; then
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

show_vnc_password "${VNC_PASSWORD_ONCE}" "${NOVNC_PORT}"
echo "  Close the app or press Ctrl-C to stop."
unset VNC_PASSWORD_ONCE

# --- Run the app ------------------------------------------------------------
# Foreground, not exec, so the EXIT trap tears the desktop down afterwards.
status=0
env -i "${safe_env[@]}" \
    DISPLAY="${DISPLAY_NAME}" XAUTHORITY="${RUN_DIR}/Xauthority" \
    PYTHONPATH="${REPO_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}" \
    python -m heroforge "$@" || status=$?
exit "${status}"
