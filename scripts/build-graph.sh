#!/usr/bin/env bash
#
# Build the graphify codebase knowledge graph in a throwaway, network-isolated
# container, writing graphify-out/graph.json back to the host.
#
# Why a container instead of a plain `pip install -e ".[dev]" && graphify
# update .`: it keeps graphifyy and its transitive dependencies out of the local
# dev container's Python environment, and the graph-building run is executed with
# NO network access (`--network none`) in a disposable container that mounts the
# repository READ-ONLY. Only the image build touches the network (to pip-install
# graphifyy); the actual source-tree walk cannot phone home. See Dockerfile.graphify.
#
# The repository is mounted read-only at /src and the writable output directory
# is mounted over /src/graphify-out, so the graph the Copilot agent reads from
# the host dev container is the file this script produces. The container runs as
# the host UID/GID so that file is owned by — and readable to — the host user.
#
# To keep the dev container from accumulating images, the built image and any
# dangling layers it produced are REMOVED automatically when the script exits
# (matched precisely by the com.heroforge.ephemeral=graphify label set in
# Dockerfile.graphify, so unrelated images are never touched). Pass --keep-image
# to retain the image between runs — useful when issuing several queries in a
# row, since it avoids rebuilding (and re-downloading graphifyy) each time.
#
# Usage:
#   scripts/build-graph.sh                 # build the graph, then clean up images
#   scripts/build-graph.sh --build         # force a rebuild of the builder image
#   scripts/build-graph.sh --keep-image    # keep the image after running
#   scripts/build-graph.sh --prune-cache   # also reclaim ALL dangling BuildKit
#                                           # build cache on the host (see notes)
#
# Any extra arguments are forwarded to the container's command, so the same
# isolated image can be reused to query an existing graph, e.g.:
#   scripts/build-graph.sh --keep-image graphify query "how are saving throws calculated"

set -euo pipefail

cd "$(dirname "$0")/.."

IMAGE="heroforge-graphify:dev"
DOCKERFILE="Dockerfile.graphify"
OUT_DIR="graphify-out"
# Label applied to every layer of the image, defined ONCE here and passed into
# the build (Dockerfile.graphify has no hardcoded default). It is split into name
# and value because Dockerfile's `LABEL name=value` cannot parse a single token
# that already contains `=`. Both halves drive the build args and the prune
# filter below, so the LABEL and the cleanup stay in lockstep with no duplication.
# The variable is ...NAME, not ...KEY, so the matching build arg does not trip
# BuildKit's SecretsUsedInArgOrEnv lint (it flags ARG names ending in KEY/TOKEN/
# SECRET/...); this value is a public label name, not a credential.
EPHEMERAL_LABEL_NAME="com.heroforge.ephemeral"
EPHEMERAL_LABEL_VALUE="graphify"

# --- Container engine detection ---------------------------------------------
# podman is preferred per project policy (rootless by default), falling back to
# docker. Both share the CLI surface this script uses (build / image / run).
if command -v podman >/dev/null 2>&1; then
    ENGINE="podman"
elif command -v docker >/dev/null 2>&1; then
    ENGINE="docker"
else
    echo "error: neither podman nor docker is available on PATH." >&2
    exit 1
fi

# --- Parse flags ------------------------------------------------------------
# --build       force a rebuild of the builder image
# --keep-image  retain the image after running (skip the exit-time cleanup)
# --prune-cache also reclaim ALL dangling BuildKit build cache on exit (host-wide;
#               cannot be scoped to this build — see cleanup notes)
FORCE_BUILD=0
KEEP_IMAGE=0
PRUNE_CACHE=0
while [[ "${1:-}" == --* ]]; do
    case "$1" in
        --build) FORCE_BUILD=1 ;;
        --keep-image) KEEP_IMAGE=1 ;;
        --prune-cache) PRUNE_CACHE=1 ;;
        --) shift; break ;;
        *) break ;;
    esac
    shift
done

# --- Image cleanup ----------------------------------------------------------
# Remove the built image so repeated runs do not bloat the dev container.
# Registered on EXIT so cleanup happens even if the graph build fails;
# --keep-image skips it entirely. Errors are swallowed (|| true): cleanup is
# best-effort and must not change the script's exit status.
#
# What each step reclaims:
#   * rmi -f "${IMAGE}"  removes the tagged runner image — this is the real
#     cleanup under BuildKit, where the intermediate base/python-builder/
#     git-builder stages never enter the image store (they live in the build
#     cache, see --prune-cache below).
#   * image prune --filter label=...  is a SAFETY NET for the legacy builder
#     (DOCKER_BUILDKIT=0), where untagged intermediate stages DO become dangling
#     images; they inherit the ephemeral label via FROM base, so this removes
#     them. Under BuildKit it is effectively a no-op.
#   * builder prune (only with --prune-cache) reclaims the BuildKit build cache
#     that holds the intermediate stages. It is opt-in because that cache is what
#     makes repeat/--keep-image runs fast. NOTE: it CANNOT be scoped to just this
#     build — BuildKit cache records do not carry the image's LABEL, so a
#     `--filter label=...` matches nothing (verified: reclaims 0B). The prune is
#     therefore unscoped and evicts ALL reclaimable (dangling) build cache on the
#     host, including other projects'. In-use cache is left intact. This is why it
#     is off by default.
cleanup_images() {
    [[ "${KEEP_IMAGE}" -eq 1 ]] && return 0
    "${ENGINE}" rmi -f "${IMAGE}" >/dev/null 2>&1 || true
    "${ENGINE}" image prune -f \
        --filter "label=${EPHEMERAL_LABEL_NAME}=${EPHEMERAL_LABEL_VALUE}" \
        >/dev/null 2>&1 || true
    if [[ "${PRUNE_CACHE}" -eq 1 ]]; then
        "${ENGINE}" builder prune -f >/dev/null 2>&1 || true
    fi
}
trap cleanup_images EXIT

# --- Build the isolated image (only step that needs the network) ------------
# Rebuild when forced or when the image does not yet exist locally. The label
# key/value are passed in as build args so they are defined ONLY in this script
# (Dockerfile.graphify has no hardcoded default), keeping the LABEL and the prune
# filter above in lockstep.
if [[ "${FORCE_BUILD}" -eq 1 ]] || ! "${ENGINE}" image inspect "${IMAGE}" >/dev/null 2>&1; then
    echo "Building ${IMAGE} from ${DOCKERFILE} ..."
    "${ENGINE}" build -f "${DOCKERFILE}" \
        --target graphify-runner \
        --build-arg "EPHEMERAL_LABEL_NAME=${EPHEMERAL_LABEL_NAME}" \
        --build-arg "EPHEMERAL_LABEL_VALUE=${EPHEMERAL_LABEL_VALUE}" \
        -t "${IMAGE}" .
fi

# The output directory must exist on the host before it is bind-mounted, so the
# rw mount has a target and the resulting graph lands in the workspace.
mkdir -p "${OUT_DIR}"

# --- Build the graph with networking severed --------------------------------
# --network none           : no network during the source-tree walk.
# --user <uid>:<gid>        : write the graph as the host user so it is readable
#                             from the dev container (no root-owned artifacts).
# -v "$PWD":/src:ro         : repository mounted read-only.
# -v "$PWD/OUT_DIR":...:rw  : the ONLY writable host mount — where graph.json lands.
# --tmpfs /tmp              : writable, ephemeral HOME (see Dockerfile.graphify).
# "$@"                      : optional command override (defaults to the image CMD,
#                             `graphify update .`).
echo "Building knowledge graph into ${OUT_DIR}/ (network isolated) ..."
"${ENGINE}" run --rm \
    --network none \
    --user "$(id -u):$(id -g)" \
    --tmpfs /tmp \
    -v "${PWD}:/src:ro" \
    -v "${PWD}/${OUT_DIR}:/src/${OUT_DIR}:rw" \
    "${IMAGE}" "$@"

echo "Done. Graph written to ${OUT_DIR}/graph.json"
