#!/usr/bin/env bash
#
# Entrypoint for the HeroForge-Anew display sidecar (see Dockerfile.display).
#
# It sequences the viewable desktop stack and then hands PID 1 to websockify:
#
#   Xvfb (:99, shared /tmp/.X11-unix socket)
#     -> fluxbox          (window manager)
#       -> x11vnc         (exports :99 over VNC, bound to loopback only)
#         -> websockify   (noVNC web client + WebSocket<->VNC bridge on :6080)
#
# The companion `app` container draws into the same :99 display via the shared
# socket volume. Human access to the desktop is gated by a REQUIRED VNC password
# sourced from the git-ignored .env file (see .env.example); this script refuses
# to start a passwordless desktop.

set -euo pipefail

: "${DISPLAY:=:99}"
: "${SCREEN_GEOMETRY:=1920x1080}"
: "${NOVNC_PORT:=6080}"
: "${VNC_PORT:=5900}"

if [[ -z "${VNC_PASSWORD:-}" ]]; then
    echo "error: VNC_PASSWORD is not set — refusing to start a passwordless desktop." >&2
    echo "       Copy .env.example to .env and set a strong VNC_PASSWORD." >&2
    exit 1
fi

# Terminate the background X/WM/VNC processes when this script exits so the
# container shuts down cleanly on Ctrl-C / `compose down`.
cleanup() {
    pkill -P $$ >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

# Virtual framebuffer X server on the shared socket. -ac disables host-based
# access control (safe: the server only listens on the in-container unix socket,
# -nolisten tcp keeps it off the network, and noVNC access is password-gated),
# which lets the differently-owned `app` process connect without an X cookie.
Xvfb "${DISPLAY}" -screen 0 "${SCREEN_GEOMETRY}x24" -ac -nolisten tcp &

# Wait for the X server to accept connections before starting clients.
for _ in $(seq 1 50); do
    if xdpyinfo -display "${DISPLAY}" >/dev/null 2>&1; then
        break
    fi
    sleep 0.2
done
if ! xdpyinfo -display "${DISPLAY}" >/dev/null 2>&1; then
    echo "error: Xvfb did not become ready on ${DISPLAY}." >&2
    exit 1
fi

# Minimal window manager so the Qt window gets decorations and focus.
fluxbox >/dev/null 2>&1 &

# Store the VNC password in a private file, then export the display over VNC
# bound to loopback only — the sole client is the in-container websockify bridge.
vnc_pass_file="${HOME}/.vnc/passwd"
mkdir -p "$(dirname "${vnc_pass_file}")"
x11vnc -storepasswd "${VNC_PASSWORD}" "${vnc_pass_file}" >/dev/null 2>&1
x11vnc -display "${DISPLAY}" -rfbauth "${vnc_pass_file}" \
    -localhost -rfbport "${VNC_PORT}" -forever -shared -noxdamage -quiet &

# Serve the noVNC web client and bridge its WebSocket traffic to x11vnc. This is
# the foreground process (PID 1 via `init`) and the only published port.
exec websockify --web=/usr/share/novnc "${NOVNC_PORT}" "localhost:${VNC_PORT}"
