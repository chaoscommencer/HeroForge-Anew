#!/usr/bin/env bash
#
# Entrypoint for the HeroForge-Anew display sidecar (see Dockerfile.display).
#
# It sequences the viewable desktop stack and then runs websockify in the
# foreground, tearing the whole stack down on shutdown via a signal trap:
#
#   Xvfb (:99, shared /tmp/.X11-unix socket)
#     -> fluxbox          (window manager)
#       -> x11vnc         (exports :99 over VNC, bound to loopback only)
#         -> websockify   (noVNC web client + WebSocket<->VNC bridge on :6080)
#
# The companion `app` container draws into the same :99 display via the shared
# socket volume. Human access to the desktop is gated by a REQUIRED VNC password
# delivered as a Compose secret (a file mounted at /run/secrets/vnc_password) so
# it never appears in this container's environment; for a plain `docker run`
# without the secret it falls back to a VNC_PASSWORD environment variable. Either
# way this script refuses to start a passwordless desktop.

set -euo pipefail

: "${DISPLAY:=:99}"
: "${SCREEN_GEOMETRY:=1920x1080}"
: "${NOVNC_PORT:=6080}"
: "${VNC_PORT:=5900}"

# Resolve the VNC password from the Compose secret file if present, otherwise
# from the VNC_PASSWORD environment variable (plain `docker run` fallback). The
# secret file is the preferred source because it keeps the password out of the
# container environment.
vnc_secret_file="${VNC_PASSWORD_FILE:-/run/secrets/vnc_password}"
if [[ -r "${vnc_secret_file}" ]]; then
    # Strip a single trailing newline if the secret file has one; leave any
    # other characters (including internal whitespace) untouched.
    VNC_PASSWORD="$(<"${vnc_secret_file}")"
fi

if [[ -z "${VNC_PASSWORD:-}" ]]; then
    echo "error: VNC_PASSWORD is not set — refusing to start a passwordless desktop." >&2
    echo "       Copy .env.example to .env and set a strong VNC_PASSWORD." >&2
    exit 1
fi

if [[ "${VNC_PASSWORD}" == "change-me" ]]; then
    echo "error: VNC_PASSWORD is still the placeholder 'change-me' — refusing to start." >&2
    echo "       Set a strong VNC_PASSWORD in .env (or run scripts/run-gui.sh," >&2
    echo "       which generates one automatically)." >&2
    exit 1
fi

# Validate caller-supplied geometry before interpolating it into the Xvfb
# command line, so a malformed value cannot inject extra arguments.
if [[ ! "${SCREEN_GEOMETRY}" =~ ^[0-9]{3,4}x[0-9]{3,4}$ ]]; then
    echo "error: SCREEN_GEOMETRY='${SCREEN_GEOMETRY}' is invalid (expected WIDTHxHEIGHT, e.g. 1920x1080)." >&2
    exit 1
fi

# Terminate the background X/WM/VNC processes when this script is asked to stop
# (Ctrl-C / `compose down` sends SIGTERM to this script via the `init` reaper).
#
# websockify serves each connected noVNC browser client in a multiprocessing
# worker. If its main process receives SIGTERM while a client is attached it
# terminates that worker with SIGTERM too, and websockify's own handler then
# raises an (uncaught) exception inside the worker — a benign but alarming
# traceback on shutdown. We avoid it by SIGKILLing the whole websockify process
# tree first (SIGKILL cannot be trapped, so no handler runs and nothing is
# printed), then stopping the remaining background jobs.
shutdown() {
    trap - EXIT INT TERM
    # Silence the shell's own teardown chatter (e.g. the "Killed" job-control
    # notice for the SIGKILLed websockify job below); real runtime errors were
    # already emitted while the services were running.
    exec 2>/dev/null
    if [[ -n "${websockify_pid:-}" ]]; then
        pkill -KILL -P "${websockify_pid}" >/dev/null 2>&1 || true
        kill -KILL "${websockify_pid}" >/dev/null 2>&1 || true
    fi
    pkill -P $$ >/dev/null 2>&1 || true
    exit 0
}
trap shutdown EXIT INT TERM

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

# Minimal window manager so the Qt window gets decorations and focus. fluxbox
# would otherwise spawn a blocking "I can't find an app to set the wallpaper
# with" xmessage dialog at startup (the slim image has no wallpaper setter); the
# fbsetbg binary is replaced with a solid-colour shim at image build time (see
# Dockerfile.display), so no dialog appears and no runtime workaround is needed.
fluxbox >/dev/null 2>&1 &

# Store the VNC password in a private file, then export the display over VNC
# bound to loopback only — the sole client is the in-container websockify bridge.
vnc_pass_file="${HOME}/.vnc/passwd"
mkdir -p "$(dirname "${vnc_pass_file}")"
x11vnc -storepasswd "${VNC_PASSWORD}" "${vnc_pass_file}" >/dev/null 2>&1
x11vnc -display "${DISPLAY}" -rfbauth "${vnc_pass_file}" \
    -localhost -rfbport "${VNC_PORT}" -forever -shared -noxdamage -quiet &

# Serve the noVNC web client and bridge its WebSocket traffic to x11vnc. Run it
# in the background (rather than `exec`) so the shutdown trap above stays
# installed and can tear the process tree down cleanly; `wait` blocks here until
# websockify exits or a signal fires the trap.
websockify --web=/usr/share/novnc "${NOVNC_PORT}" "localhost:${VNC_PORT}" &
websockify_pid=$!
wait "${websockify_pid}"
