# shellcheck shell=bash
#
# One-time VNC password helpers shared by scripts/run-gui.sh (Compose stack) and
# scripts/run-gui-local.sh (plain processes in the devcontainer). Source it; it
# defines functions only and has no side effects.
#
# scripts/display-entrypoint.sh does not use this file: Dockerfile.display
# copies that script into the display image on its own, so it keeps its own
# copies of the few lines it needs.

# The noVNC desktop is gated by a VNC password. x11vnc's classic VNC auth only
# honours the first 8 characters, so a longer secret buys nothing here; generate
# exactly 8 from a CSPRNG, fresh for every launch, restricted to [A-Za-z0-9].
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

# Pick a RAM-backed directory for the short-lived secret file, so the password
# never reaches a disk: $XDG_RUNTIME_DIR (per-user tmpfs) when set, else
# /dev/shm. Falls back to $TMPDIR (or /tmp) only when neither exists, with a
# warning.
secret_parent_dir() {
    if [[ -n "${XDG_RUNTIME_DIR:-}" && -d "${XDG_RUNTIME_DIR}" && -w "${XDG_RUNTIME_DIR}" ]]; then
        printf '%s' "${XDG_RUNTIME_DIR}"
    elif [[ -d /dev/shm && -w /dev/shm ]]; then
        printf '%s' /dev/shm
    else
        echo "warning: no tmpfs found for the VNC secret; using ${TMPDIR:-/tmp}." >&2
        printf '%s' "${TMPDIR:-/tmp}"
    fi
}

# write_secret_file PATH VALUE: write VALUE to a new file at PATH that only its
# owner can read (0600). printf is a shell builtin, so VALUE never appears in
# any process's argument list. The explicit chmod backs up the umask: a default
# ACL on the parent directory would otherwise widen the file's permissions.
write_secret_file() {
    local path="$1" value="$2"
    (
        umask 077
        printf '%s' "${value}" >"${path}"
    )
    chmod 600 "${path}"
}

# show_vnc_password PASSWORD PORT: print the one-time password and how to use
# it. It goes to the controlling terminal (/dev/tty), not stdout, so it is not
# captured when the script's output is piped or redirected to a log; with no
# terminal (a non-interactive run) it falls back to stdout. Terminal scrollback
# can still be saved (VS Code restores it across restarts), hence the advice to
# clear it once connected.
show_vnc_password() {
    local password="$1" port="$2" out=/dev/stdout
    if { : >/dev/tty; } 2>/dev/null; then
        out=/dev/tty
    fi
    {
        echo
        echo "  VNC password for this session: ${password}"
        echo "  Open the forwarded port ${port} from the Ports panel (or"
        echo "  https://localhost:${port}/vnc.html) and enter it. It is shown only"
        echo "  here and changes on every launch. Once connected, clear the terminal"
        echo "  (Ctrl+K in VS Code, or 'clear') so it does not stay in the scrollback."
        echo
    } >"${out}"
}

# port_open PORT: true when something accepts TCP connections on
# 127.0.0.1:PORT. Uses bash's /dev/tcp, so it needs no extra tools.
port_open() {
    (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
}
