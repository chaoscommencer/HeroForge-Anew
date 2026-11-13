#!/usr/bin/env bash
#
# Install git post-commit and post-checkout hooks that keep the graphify
# knowledge graph (graphify-out/graph.json) current.
#
# graphify's own `graphify hook install` expects the graphify CLI on the host,
# which this project deliberately keeps out of the dev environment (see
# Dockerfile.graphify). These hooks call the isolated, network-free wrapper
# scripts/build-graph.sh instead, so the graph is rebuilt in the throwaway
# container with the repository mounted read-only.
#
# Behaviour:
#   * runs in the background, so commits and checkouts never wait on it;
#   * one rebuild at a time per checkout (flock on graphify-out/.hook.lock);
#   * `update . --force` so the graph also shrinks when code is removed or a
#     branch with less code is checked out;
#   * skipped during rebase, merge and cherry-pick, for file-only checkouts,
#     and when GRAPHIFY_SKIP_HOOK=1;
#   * a no-op in any checkout or worktree whose tree lacks scripts/build-graph.sh;
#   * appended to any existing hook (such as Git LFS's) as a marked block, which
#     re-running replaces and --uninstall removes, leaving the rest untouched.
# The log of the last hook rebuild is graphify-out/.hook.log.
#
# The hooks live in the shared git directory, so they also cover every
# `git worktree` of this clone. Re-run this script after recreating the clone or
# the Codespace; it is idempotent.
#
# Usage: scripts/install-graph-hooks.sh [--uninstall]

set -euo pipefail

BEGIN="# >>> heroforge-graph-hook >>>"
END="# <<< heroforge-graph-hook <<<"
HOOKS_DIR="$(git rev-parse --git-common-dir)/hooks"
mkdir -p "${HOOKS_DIR}"

# The block runs in a subshell, so its early exits never change the exit status
# of whatever the hook already does (for example Git LFS's own hook lines).
hook_block() {
    cat <<EOF
${BEGIN}
# Rebuild graphify-out/ via scripts/build-graph.sh, in the background.
# Managed by scripts/install-graph-hooks.sh; re-run it to update this block.
EOF
    cat <<'EOF'
(
    [ "${GRAPHIFY_SKIP_HOOK:-0}" = "1" ] && exit 0
    # post-checkout passes "<old> <new> <flag>"; flag 0 is a file checkout.
    [ "$(basename "$0")" = "post-checkout" ] && [ "${3:-1}" = "0" ] && exit 0
    GIT_DIR=$(git rev-parse --git-dir 2>/dev/null) || exit 0
    [ -d "$GIT_DIR/rebase-merge" ] && exit 0
    [ -d "$GIT_DIR/rebase-apply" ] && exit 0
    [ -f "$GIT_DIR/MERGE_HEAD" ] && exit 0
    [ -f "$GIT_DIR/CHERRY_PICK_HEAD" ] && exit 0
    TOP=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
    [ -x "$TOP/scripts/build-graph.sh" ] || exit 0
    command -v flock >/dev/null 2>&1 || exit 0
    mkdir -p "$TOP/graphify-out"
    (
        cd "$TOP" &&
        flock -w 900 graphify-out/.hook.lock \
            scripts/build-graph.sh --keep-image graphify update . --force
    ) </dev/null >"$TOP/graphify-out/.hook.log" 2>&1 &
)
EOF
    echo "${END}"
}

for hook in post-commit post-checkout; do
    path="${HOOKS_DIR}/${hook}"
    existing=""
    if [[ -e "${path}" ]]; then
        # Drop any earlier copy of the block, keep everything else verbatim.
        existing="$(sed "/^${BEGIN}\$/,/^${END}\$/d" "${path}")"
    fi
    if [[ "${1:-}" == "--uninstall" ]]; then
        if [[ -z "$(printf '%s' "${existing}" | grep -v '^#!' | tr -d '[:space:]')" ]]; then
            rm -f "${path}"
        else
            printf '%s\n' "${existing}" >"${path}"
        fi
        echo "uninstalled: ${path}"
        continue
    fi
    {
        if [[ -n "${existing}" ]]; then printf '%s\n\n' "${existing}"; else echo '#!/bin/sh'; fi
        hook_block
    } >"${path}.tmp"
    chmod 0755 "${path}.tmp"
    mv "${path}.tmp" "${path}"
    echo "installed: ${path}"
done
