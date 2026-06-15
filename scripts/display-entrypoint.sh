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

# X11 access control via an MIT-MAGIC-COOKIE-1, replacing the old `-ac` flag
# (which disabled host-based access control entirely, letting ANY client on the
# socket connect). Only clients presenting this cookie may now talk to :99.
#
# The cookie file lives on the shared x11-socket volume (/tmp/.X11-unix) so the
# separately-built `app` container can read it too; both services set XAUTHORITY
# to this path (see docker-compose.yml). It is created 0600 and owned by the app
# user (UID 1000 in both images), so only that user can read the secret.
#
# FamilyWild ("ffff") registration is the key cross-container detail: a plain
# `xauth add :99` keys the entry to THIS container's hostname, which would NOT
# match the app container's libXau lookup (it has a different hostname). Rewrite
# the entry's address family to FamilyWild so the one cookie authenticates from
# either container over the shared socket.
#
# The nlist and nmerge steps are serialized through a shell variable rather than
# a single `nlist | sed | nmerge` pipeline: a pipeline runs both xauth processes
# concurrently against the SAME authority file, and the second to grab the file
# lock blocks the first, which then fails with "timeout in locking authority
# file". Capturing nlist's output first lets each xauth invocation take and
# release the lock in turn.
export XAUTHORITY="/tmp/.X11-unix/.Xauthority"
: > "${XAUTHORITY}"
chmod 600 "${XAUTHORITY}"
# mcookie (util-linux) is preferred; fall back to /dev/urandom so cookie
# generation never depends on a single optional binary.
cookie="$(mcookie 2>/dev/null || head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')"
xauth -f "${XAUTHORITY}" add "${DISPLAY}" . "${cookie}" >/dev/null 2>&1
wild_entry="$(xauth -f "${XAUTHORITY}" nlist "${DISPLAY}" | sed -e 's/^..../ffff/')"
printf '%s\n' "${wild_entry}" | xauth -f "${XAUTHORITY}" nmerge - >/dev/null 2>&1

# Virtual framebuffer X server on the shared socket, authenticated by the cookie
# above (-auth) and kept off the network (-nolisten tcp).
Xvfb "${DISPLAY}" -screen 0 "${SCREEN_GEOMETRY}x24" -auth "${XAUTHORITY}" -nolisten tcp &

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
