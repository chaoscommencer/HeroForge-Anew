#!/usr/bin/env bash
#
# Isolated runtime entrypoint for HeroForge Anew.
#
# Starts a self-contained virtual desktop inside the container and exposes it
# over the network so QA can view and interact with the PyQt application from a
# web browser (noVNC) or any VNC client. This is what makes "user-in-the-loop"
# testing possible without any host display or X11 forwarding.
#
# Pipeline:
#   Xvfb        -> virtual framebuffer (a headless X server)
#   fluxbox     -> lightweight window manager so windows can be moved/resized
#   x11vnc      -> shares the virtual display over the VNC protocol
#   websockify  -> serves noVNC (VNC-over-websockets) for browser access
#   the app     -> the HeroForge Anew PyQt application
#
set -euo pipefail

DISPLAY_NUM="${DISPLAY_NUM:-1}"
export DISPLAY=":${DISPLAY_NUM}"
SCREEN_GEOMETRY="${SCREEN_GEOMETRY:-1280x800x24}"
VNC_PORT="${VNC_PORT:-5900}"
NOVNC_PORT="${NOVNC_PORT:-6080}"
# Optional VNC password. When unset the desktop is open (fine for local/CI QA).
VNC_PASSWORD="${VNC_PASSWORD:-}"

NOVNC_DIR="${NOVNC_DIR:-/usr/share/novnc}"

pids=()

cleanup() {
    for pid in "${pids[@]:-}"; do
        if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
            kill "${pid}" 2>/dev/null || true
        fi
    done
}
trap cleanup EXIT INT TERM

echo "[entrypoint] Starting Xvfb on ${DISPLAY} (${SCREEN_GEOMETRY})"
Xvfb "${DISPLAY}" -screen 0 "${SCREEN_GEOMETRY}" -ac +extension GLX +render -noreset &
pids+=("$!")

# Wait for the X server to accept connections before starting clients.
for _ in $(seq 1 50); do
    if xdpyinfo -display "${DISPLAY}" >/dev/null 2>&1; then
        break
    fi
    sleep 0.2
done

echo "[entrypoint] Starting fluxbox window manager"
fluxbox >/tmp/fluxbox.log 2>&1 &
pids+=("$!")

x11vnc_args=(-display "${DISPLAY}" -rfbport "${VNC_PORT}" -forever -shared -nopw)
if [[ -n "${VNC_PASSWORD}" ]]; then
    mkdir -p "${HOME:-/tmp}/.vnc"
    x11vnc -storepasswd "${VNC_PASSWORD}" "${HOME:-/tmp}/.vnc/passwd" >/dev/null 2>&1
    x11vnc_args=(-display "${DISPLAY}" -rfbport "${VNC_PORT}" -forever -shared \
        -rfbauth "${HOME:-/tmp}/.vnc/passwd")
fi

echo "[entrypoint] Starting x11vnc on port ${VNC_PORT}"
x11vnc "${x11vnc_args[@]}" >/tmp/x11vnc.log 2>&1 &
pids+=("$!")

echo "[entrypoint] Starting noVNC (websockify) on port ${NOVNC_PORT}"
websockify --web "${NOVNC_DIR}" "${NOVNC_PORT}" "localhost:${VNC_PORT}" \
    >/tmp/websockify.log 2>&1 &
pids+=("$!")

echo "[entrypoint] Desktop ready:"
echo "[entrypoint]   noVNC (browser): http://localhost:${NOVNC_PORT}/vnc.html"
echo "[entrypoint]   VNC client:      localhost:${VNC_PORT}"

# With no arguments, launch the application. Otherwise run whatever was passed
# (e.g. `bash` for an interactive shell, or `pytest` for tests).
if [[ "$#" -eq 0 ]]; then
    echo "[entrypoint] Launching HeroForge Anew"
    exec python -m heroforge
else
    echo "[entrypoint] Running: $*"
    exec "$@"
fi
