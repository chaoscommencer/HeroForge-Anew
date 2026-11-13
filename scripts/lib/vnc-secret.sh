# shellcheck shell=bash
#
# One-time VNC password helpers shared by scripts/run-gui.sh (Compose stack) and
# scripts/run-gui-local.sh (plain processes in the devcontainer). Source it; it
# defines functions only and has no side effects.

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
