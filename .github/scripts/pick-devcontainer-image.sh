#!/usr/bin/env bash
#
# Pick the devcontainers/python base image that .github/workflows/
# update-devcontainer.yml should propose for the devcontainer Dockerfile.
#
# Usage:
#   pick-devcontainer-image.sh DOCKERFILE CATALOG_JSON
#
#   DOCKERFILE    the Dockerfile whose `FROM mcr.microsoft.com/devcontainers/
#                 python:<tag>@<digest>` line is the current pin.
#   CATALOG_JSON  MCR's tag catalog for devcontainers/python, as returned by
#                 https://mcr.microsoft.com/api/v1/catalog/devcontainers/python/tags?reg=mar
#                 (a JSON array of {name, digest, createdDate, ...}).
#
# Environment:
#   MIN_AGE_DAYS  only propose images MCR has listed for at least this many
#                 days (default 14).
#   ALLOW_RECENT  "true" skips the age rule (for an image that fixes a serious
#                 vulnerability).
#   NOW           current time as Unix seconds (default: now); for tests.
#
# Prints key=value lines for $GITHUB_OUTPUT: has_updates, current_version, and
# when has_updates=true also tag, digest and created. Explanations go to
# stderr. Exits non-zero, without output, when the inputs cannot be trusted.
#
# Rules:
#   * Stay on the current image major version and Python minor version, e.g.
#     3.x.y-3.12-bookworm. Moving to a new major or Python version is a
#     deliberate change made by hand together with CI.
#   * Never propose a downgrade: only versions strictly newer than the current
#     pin count. The current version is read from the pinned tag, or, for a
#     floating tag such as 3-3.12-bookworm, from the versioned tag that shares
#     the pinned digest.
#   * The age rule uses MCR's own createdDate for the tag, which the registry
#     records when the tag is pushed. The image config's `created` field is not
#     used: whoever builds the image sets it and can backdate it.

set -euo pipefail

die() {
    echo "error: $*" >&2
    exit 1
}

[[ $# -eq 2 ]] || die "usage: $0 DOCKERFILE CATALOG_JSON"
dockerfile="$1"
catalog="$2"
min_age_days="${MIN_AGE_DAYS:-14}"
allow_recent="${ALLOW_RECENT:-false}"
now="${NOW:-$(date -u +%s)}"

[[ "${min_age_days}" =~ ^[0-9]{1,4}$ ]] || die "MIN_AGE_DAYS='${min_age_days}' is not a whole number of days"
[[ "${allow_recent}" == true || "${allow_recent}" == false ]] || die "ALLOW_RECENT must be true or false"
[[ "${now}" =~ ^[0-9]{1,12}$ ]] || die "NOW='${now}' is not a Unix time"
[[ -r "${dockerfile}" ]] || die "cannot read ${dockerfile}"
[[ -r "${catalog}" ]] || die "cannot read ${catalog}"

from_line="$(grep -m1 '^FROM mcr.microsoft.com/devcontainers/python:' "${dockerfile}" || true)"
from_re='^FROM mcr\.microsoft\.com/devcontainers/python:([A-Za-z0-9._-]+)@(sha256:[a-f0-9]{64})$'
[[ "${from_line}" =~ ${from_re} ]] || die "no pinned devcontainers/python FROM line (tag@sha256 digest) in ${dockerfile}"
current_tag="${BASH_REMATCH[1]}"
current_digest="${BASH_REMATCH[2]}"

# Image major and Python minor, from "3-3.12-bookworm" or "3.0.8-3.12-bookworm".
tag_re='^([0-9]+)(\.[0-9]+)*-(3\.[0-9]+)-bookworm$'
[[ "${current_tag}" =~ ${tag_re} ]] || die "cannot read the image and Python versions from tag '${current_tag}'"
major="${BASH_REMATCH[1]}"
python_minor="${BASH_REMATCH[3]}"
versioned_re="^${major}\\.[0-9]+\\.[0-9]+-${python_minor//./\\.}-bookworm\$"
cutoff=$((now - min_age_days * 86400))

result="$(
    jq -c \
        --arg re "${versioned_re}" \
        --arg current_tag "${current_tag}" \
        --arg current_digest "${current_digest}" \
        --argjson cutoff "${cutoff}" \
        --argjson allow_recent "${allow_recent}" '
        def version: split("-")[0] | split(".") | map(tonumber);
        # MCR dates look like 2026-10-29T02:55:56.0000000+00:00.
        def epoch: sub("\\.[0-9]+"; "") | sub("(\\+00:00|Z)$"; "Z") | fromdateiso8601;
        if type != "array" then error("the catalog is not a JSON array") else . end
        | [ .[]
            | select(type == "object")
            | select((.name | type) == "string" and (.name | test($re)))
            | select((.digest | type) == "string" and (.digest | test("^sha256:[a-f0-9]{64}$")))
            | { tag: .name,
                digest: .digest,
                created: (.createdDate // null),
                epoch: (try (.createdDate | epoch) catch null),
                version: (.name | version) } ] as $tags
        | (if ($current_tag | test($re)) then ($current_tag | version)
           else ([ $tags[] | select(.digest == $current_digest) | .version ] | max)
           end) as $current
        | if $current == null then { current: null }
          else
            [ $tags[]
              | select(.version > $current)
              | select($allow_recent or (.epoch != null and .epoch <= $cutoff)) ] as $eligible
            | { current: ($current | map(tostring) | join(".")),
                newer: ([ $tags[] | select(.version > $current) ] | length),
                pick: ($eligible | max_by(.version)) }
          end
    ' "${catalog}"
)" || die "could not read the MCR catalog in ${catalog}"

current_version="$(jq -r '.current // empty' <<<"${result}")"
if [[ -z "${current_version}" ]]; then
    die "cannot tell which version the pinned digest ${current_digest} (tag ${current_tag}) is; pin a versioned tag such as ${major}.x.y-${python_minor}-bookworm by hand"
fi
echo "current_version=${current_version}"

if [[ "$(jq -r '.pick == null' <<<"${result}")" == true ]]; then
    newer="$(jq -r '.newer' <<<"${result}")"
    if [[ "${newer}" == 0 ]]; then
        echo "Current pin ${current_version} is the newest ${major}.x.y-${python_minor}-bookworm image." >&2
    else
        echo "${newer} newer image(s) exist, none listed for ${min_age_days} days yet; nothing to do." >&2
    fi
    echo "has_updates=false"
    exit 0
fi

tag="$(jq -r '.pick.tag' <<<"${result}")"
digest="$(jq -r '.pick.digest' <<<"${result}")"
created="$(jq -r '.pick.created // "unknown"' <<<"${result}")"
echo "Picked ${tag} (${digest}), listed by MCR at ${created}; current ${current_version}." >&2
echo "has_updates=true"
echo "tag=${tag}"
echo "digest=${digest}"
echo "created=${created}"
