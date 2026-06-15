#!/usr/bin/env bash
#
# Set up rootless Podman (and podman-compose) inside the dev container so the QA
# stack can be run with Podman instead of docker-in-docker. scripts/run-gui.sh
# already prefers Podman when present (podman-compose -> podman compose ->
# docker compose), so once this script has run, `scripts/run-gui.sh` uses it
# automatically — no flags needed.
#
# Why a script rather than only a devcontainer Feature: running rootless Podman
# *nested* inside a container needs a few prerequisites a stock install does not
# guarantee — subordinate UID/GID ranges for the remote user, the fuse-overlayfs
# storage driver (the kernel `overlay` driver is usually unavailable nested), and
# slirp4netns for user-mode networking. This script installs and configures all
# of them idempotently; re-running it is safe.
#
# Caveats (documented in docs/containerized-runtime.md):
#   * This is rootless Podman nested inside a privileged docker-in-docker dev
#     container — workable for QA, but expect occasional storage/cgroup friction.
#     On a real host (no DinD layer) rootless Podman is cleaner.
#   * If fuse-overlayfs cannot be used (no /dev/fuse), Podman falls back to the
#     slow `vfs` driver; this script configures fuse-overlayfs when available.
#
# Usage:
#   scripts/setup-podman.sh          # install + configure rootless Podman
#   scripts/setup-podman.sh --check  # report whether Podman is set up, change nothing
#
# Requires sudo for the apt install step (the `vscode` dev-container user has
# passwordless sudo).

set -euo pipefail

TARGET_USER="${SUDO_USER:-${USER:-$(id -un)}}"
SUBID_COUNT=65536
SUBID_START=100000

err() { printf 'setup-podman: %s\n' "$*" >&2; }

print_check() {
    if command -v podman >/dev/null 2>&1; then
        echo "podman:         $(podman --version 2>/dev/null || echo present)"
    else
        echo "podman:         not installed"
    fi
    if command -v podman-compose >/dev/null 2>&1; then
        echo "podman-compose: $(podman-compose --version 2>/dev/null | head -n1 || echo present)"
    else
        echo "podman-compose: not installed"
    fi
    if grep -q "^${TARGET_USER}:" /etc/subuid 2>/dev/null; then
        echo "subuid/subgid:  configured for ${TARGET_USER}"
    else
        echo "subuid/subgid:  MISSING for ${TARGET_USER}"
    fi
}

if [[ "${1:-}" == "--check" ]]; then
    print_check
    exit 0
fi

# --- 1. Install Podman and the rootless prerequisites ------------------------
# uidmap provides newuidmap/newgidmap (setuid helpers rootless Podman needs);
# fuse-overlayfs is the nested-friendly storage driver; slirp4netns gives
# rootless user-mode networking.
if ! command -v podman >/dev/null 2>&1; then
    echo "Installing podman, uidmap, fuse-overlayfs, slirp4netns ..."
    sudo apt-get update
    sudo DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y \
        podman \
        uidmap \
        fuse-overlayfs \
        slirp4netns
    sudo apt-get clean
    sudo rm -rf /var/lib/apt/lists/*
else
    echo "podman already installed — skipping apt install."
fi

# --- 2. Ensure subordinate UID/GID ranges for the remote user ----------------
# Rootless Podman maps container UIDs onto this delegated range. The
# devcontainers base image usually seeds these for `vscode`, but make sure.
for f in /etc/subuid /etc/subgid; do
    if ! sudo grep -q "^${TARGET_USER}:" "${f}" 2>/dev/null; then
        echo "Adding ${TARGET_USER}:${SUBID_START}:${SUBID_COUNT} to ${f}"
        echo "${TARGET_USER}:${SUBID_START}:${SUBID_COUNT}" | sudo tee -a "${f}" >/dev/null
    else
        echo "${f} already has a range for ${TARGET_USER} — leaving it."
    fi
done

# --- 3. Configure the fuse-overlayfs storage driver --------------------------
# A nested container typically cannot use the kernel `overlay` driver, so point
# rootless Podman at fuse-overlayfs. Write a per-user storage.conf only if the
# user does not already have one (don't clobber a customised config).
STORAGE_CONF="${HOME}/.config/containers/storage.conf"
if command -v fuse-overlayfs >/dev/null 2>&1 && [[ ! -f "${STORAGE_CONF}" ]]; then
    echo "Writing ${STORAGE_CONF} (overlay via fuse-overlayfs) ..."
    mkdir -p "$(dirname "${STORAGE_CONF}")"
    cat > "${STORAGE_CONF}" <<EOF
[storage]
driver = "overlay"

[storage.options.overlay]
mount_program = "/usr/bin/fuse-overlayfs"
EOF
else
    echo "Leaving existing storage config alone (or fuse-overlayfs absent)."
fi

# --- 4. Install podman-compose ----------------------------------------------
# Prefer pipx (isolated) when available, else a user-site pip install. This
# keeps podman-compose off the system Python.
if ! command -v podman-compose >/dev/null 2>&1; then
    if command -v pipx >/dev/null 2>&1; then
        echo "Installing podman-compose via pipx ..."
        pipx install podman-compose
    else
        echo "Installing podman-compose via pip (--user) ..."
        python3 -m pip install --user podman-compose
    fi
else
    echo "podman-compose already installed — skipping."
fi

# --- 5. Smoke test -----------------------------------------------------------
echo
echo "Verifying rootless Podman can run ..."
if podman info >/dev/null 2>&1; then
    echo "OK: 'podman info' succeeded."
else
    err "'podman info' failed. Rootless Podman nested in DinD can be finicky;"
    err "check /dev/fuse availability and the subuid/subgid ranges above."
fi

echo
print_check
echo
echo "Done. scripts/run-gui.sh will now prefer Podman automatically."
