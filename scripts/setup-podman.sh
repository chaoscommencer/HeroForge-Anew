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

# Resolve the repository root from this script's location so the hash-pinned
# requirements file can be found regardless of the caller's working directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

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
    if command -v crun >/dev/null 2>&1; then
        echo "crun:           $(crun --version 2>/dev/null | head -n1 || echo present)"
    else
        echo "crun:           not installed"
    fi
    if command -v catatonit >/dev/null 2>&1; then
        echo "catatonit:      $(command -v catatonit)"
    else
        echo "catatonit:      not installed"
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
# rootless user-mode networking; crun is the OCI runtime that degrades
# gracefully when no cgroup controllers are delegated (see section 4) — without
# it, runc aborts container start with "rootless needs no limits ... permission
# denied ... /sys/fs/cgroup/..."; catatonit is the container-init binary that
# `init: true` (used by the QA compose stack) needs — bookworm installs it at
# /usr/libexec/podman/catatonit, Podman's default init_path, so PID-1 reaping
# works without disabling init.
if ! command -v podman >/dev/null 2>&1; then
    echo "Installing podman, uidmap, fuse-overlayfs, slirp4netns, crun, catatonit ..."
    sudo apt-get update
    sudo DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y \
        podman \
        uidmap \
        fuse-overlayfs \
        slirp4netns \
        crun \
        catatonit
    sudo apt-get clean
    sudo rm -rf /var/lib/apt/lists/*
else
    echo "podman already installed — skipping apt install."
fi

# crun and catatonit may be missing even when podman is already present (e.g. an
# older setup that only installed runc, or one that disabled init). Ensure both
# are available: the crun runtime config in section 4 depends on crun, and
# `init: true` in the compose stack depends on catatonit.
for pkg in crun catatonit; do
    if ! command -v "${pkg}" >/dev/null 2>&1; then
        echo "Installing ${pkg} ..."
        sudo apt-get update
        sudo DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y "${pkg}"
        sudo apt-get clean
        sudo rm -rf /var/lib/apt/lists/*
    fi
done

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

# --- 4. Select crun as the OCI runtime ---------------------------------------
# Nested rootless Podman in this dev container cannot create per-container cgroup
# v2 subtrees: /sys/fs/cgroup is root-owned and not delegated to the remote user.
# With the default `runc`, starting any container then fails with:
#   "rootless needs no limits + no cgrouppath when no permission is granted for
#    cgroups: mkdir /sys/fs/cgroup/<id>: permission denied".
# crun handles this case gracefully (it starts the container and silently skips
# the cgroup-backed CPU/memory/PID limits it cannot apply instead of aborting),
# so point Podman's engine at it. Written to the per-user containers.conf only
# when crun is installed and the user has no existing [engine].runtime setting,
# so a customised config is never clobbered. Because crun tolerates them, the
# stack's resource limits are inherited unchanged from docker-compose.yml under
# Podman (see docker-compose.podman.yml header point 3); they are enforced under
# Docker and simply not enforced under rootless Podman here.
CONTAINERS_CONF="${HOME}/.config/containers/containers.conf"
if command -v crun >/dev/null 2>&1 \
    && ! grep -qsE '^\s*runtime\s*=' "${CONTAINERS_CONF}" 2>/dev/null; then
    echo "Writing ${CONTAINERS_CONF} ([engine].runtime = crun) ..."
    mkdir -p "$(dirname "${CONTAINERS_CONF}")"
    cat >> "${CONTAINERS_CONF}" <<'EOF'
[engine]
runtime = "crun"
EOF
else
    echo "Leaving existing OCI runtime config alone (or crun absent)."
fi

# --- 5. Install podman-compose (fallback) -----------------------------------
# In the dev container this is already baked into the /opt/venv virtualenv at
# image-build time (.devcontainer/Dockerfile.devcontainer-default, gated by the
# INSTALL_PODMAN_DEPS build arg), so the `command -v` check below short-circuits
# and this block does nothing. It remains as a fallback for STANDALONE use — when
# the script is run on a bare host (no devcontainer image) or after a build with
# INSTALL_PODMAN_DEPS=false. When it does run, the install is hash-pinned from
# requirements-podman-compose.txt (--require-hashes), skips pip's download cache
# (--no-cache-dir) and refuses sdists (--only-binary=:all:) so no build backend
# runs at install time, matching the supply-chain posture used elsewhere in the
# repo. pipx (preferred for isolation) cannot consume a hashed `-r` file via
# `pipx install`, so we create the venv and then re-install the whole closure
# with `pipx runpip ... --require-hashes`, the same two-step integrity gate as
# Dockerfile.graphify.
REQ_PODMAN_COMPOSE="${REPO_ROOT}/requirements-podman-compose.txt"
if ! command -v podman-compose >/dev/null 2>&1; then
    if command -v pipx >/dev/null 2>&1; then
        echo "Installing podman-compose via pipx (hash-pinned) ..."
        pipx install --pip-args='--only-binary=:all:' podman-compose
        pipx runpip podman-compose install --no-cache-dir --only-binary=:all: \
            --require-hashes -r "${REQ_PODMAN_COMPOSE}" --force-reinstall
    else
        echo "Installing podman-compose via pip (--user, hash-pinned) ..."
        python3 -m pip install --user --no-cache-dir --only-binary=:all: \
            --require-hashes -r "${REQ_PODMAN_COMPOSE}"
    fi
else
    echo "podman-compose already installed (baked into the image or present) — skipping."
fi

# --- 6. Smoke test -----------------------------------------------------------
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
