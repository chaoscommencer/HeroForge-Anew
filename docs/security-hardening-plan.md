# Container security hardening plan (continuation)

This document tracks a sequential, review-gated security-hardening campaign on
the HeroForge-Anew containerized QA stack (the `app` + `display` Compose
services). It exists so the work can be paused and resumed later without losing
context.

## Process rules

- **One change per step.** Implement a single step, then stop for review and an
  explicit go-ahead before starting the next.
- **Each step stands alone** and is committed by itself before the next begins.
- When a step touches Python, it must pass `pytest`, then `black`, then `ruff`
  (in that order, each exiting 0) before commit. Steps so far have been
  container/script/doc only, so that gate has not yet applied.
- Container changes are verified with `docker compose config -q` plus a live
  `up --build` → check → `stop` (both services must exit 0 with no tracebacks) →
  `down`. Doc-only steps need only review.
- Branch: `chaoscommencer/harden-vnc`. Commits follow Conventional Commits.

## Live-test recipe

```bash
docker compose up -d --build
# ...verify the specific change (mounts, env, window, etc.)...
docker compose stop
docker inspect -f '{{.Name}} exit={{.State.ExitCode}}' \
  heroforge-anew-app-1 heroforge-anew-display-1   # expect 0 for both
docker compose logs <service> | tail   # expect no tracebacks
docker compose down
```

---

## Completed steps

| Step | Commit | Summary |
|------|--------|---------|
| 1 | `cd0eaa7` | Mount `/tmp` and `/home/app` tmpfs `noexec,nosuid,nodev` on both services (converted `/home/app` to short-form `tmpfs:` with `mode=1707`). |
| 2 | `1d48f17` | Drop the `./tests` bind mount from the runtime `app` service. |
| 3 | `49e245b` | Deliver the VNC password as a Compose **file-based** secret (`/run/secrets/vnc_password`) instead of a `VNC_PASSWORD` env var. `scripts/run-gui.sh` materializes `secrets/vnc_password` (0600, git-ignored) from `.env`. |

---

## Remaining steps

### Step 4 — Authenticate X11 with a magic cookie instead of `-ac`

**Decision: Option A (xauth magic cookie).**

Replace the `Xvfb ... -ac` flag (which disables all host-based X access control)
with `xauth` magic-cookie authentication, so only processes holding the cookie
can connect to the `:99` display.

- `scripts/display-entrypoint.sh`: generate a cookie (`mcookie` →
  `xauth -f "$XAUTHORITY" add :99 . <cookie>`) **before** x11vnc and the app
  connect; drop `-ac` from the `Xvfb` line.
- The cookie file must live on a path **both containers** can read. `/home/app`
  is a *per-container* tmpfs (NOT shared), so it cannot be used. Use the shared
  `x11-socket` volume directory (or a new small shared volume) for the cookie.
- Both containers run as UID 1000 (same `useradd` in both Dockerfiles), so a
  0600 cookie owned by `app` is readable from both.
- Set `XAUTHORITY` in both services' `environment:` pointing at the shared cookie
  file.
- **Gotcha:** the cookie must exist before any client connects; sequence the
  entrypoint so generation happens before x11vnc starts, and the app's
  `depends_on: service_healthy` already gates it behind the display.

**Verify:** app window still renders over noVNC; `xauth list` shows the cookie;
connecting without it is refused. Both services exit 0.

**Commit:** `feat(security): authenticate X11 with a magic cookie instead of -ac`

---

### Step 5 — Supply-chain integrity (lockfile + CI scan)

**Decision: hash-pinned lockfile + CI vulnerability scan. NO SBOM** (overkill for
this single-tenant QA stack). Dependabot already covers pip, docker, actions, and
devcontainers — no Dependabot change needed.

- **5a:** Generate a hash-pinned lockfile from the `pyproject.toml` deps
  (`pip-compile --generate-hashes` from pip-tools, or `uv`); install it in the
  `Dockerfile` builder stage with `--require-hashes`. Keep dev extras out of the
  runtime image.
- **5b:** Add a CI step in `.github/workflows/ci.yml` running `pip-audit`
  (CVEs in resolved deps) as the primary scan. Optional: a Trivy image scan for
  OS-level CVEs in the Debian base + Qt libs. (CI today runs only ruff/black/
  pytest — no security scan yet.)
- May be split into separate `5a` (build) and `5b` (ci) commits.

**Verify:** image still builds with `--require-hashes`; pytest unaffected; CI
green.

**Commits:** `build(security): hash-pin dependencies with --require-hashes` and
`ci(security): add pip-audit (and optional Trivy) scanning`

---

### Step 6 — Document seccomp/AppArmor posture (docs-only)

**Decision: document only**, do not author a custom profile.

A custom seccomp profile would mean authoring a JSON syscall allowlist (traced
via `strace`/`oci-seccomp-bpf-hook`), attached via
`security_opt: [seccomp:./security/seccomp.json]` — brittle and prone to breaking
on Qt updates. AppArmor profiles are loaded into the **host** kernel and
referenced by name, so they are not portable inside a devcontainer.

- Document reliance on Docker's **default** seccomp profile (already active) plus
  `cap_drop: ALL` and `no-new-privileges`. Note that a custom profile is possible
  but out of scope as high-maintenance for single-tenant QA.

**Commit:** `docs(security): document seccomp/AppArmor posture`

---

### Step 7 — Add a healthcheck to the `app` service

Availability (not strictly security, but requested). Add a `healthcheck:` to the
`app` service in `docker-compose.yml` (e.g. a liveness check for the Python
process, or a lightweight probe). The `display` service already has one
(`xdpyinfo`).

**Verify:** `docker compose config -q`; `up`; `docker inspect` shows the app
`health=healthy`.

**Commit:** `feat(compose): add healthcheck to the app service`

---

### Step 8 — Document residual/accepted risks (docs-only)

In `docs/containerized-runtime.md`, record the knowingly accepted residual risks:

- `ws://` plaintext on the loopback hop (the VS Code tunnel itself is TLS).
- VNC's DES-based password is capped at 8 significant characters
  (protocol-inherent).
- Dependabot **security alerts** are a repository-settings toggle, not something
  in `.github/dependabot.yml`.

**Commit:** `docs(security): record accepted residual risks`

---

### Step 9 — Document `userns-remap` (docs-only)

In `docs/containerized-runtime.md`, document `userns-remap` as a **host
daemon-level** hardening option:

- Configured in `/etc/docker/daemon.json` as `{"userns-remap": "default"}`, it
  maps the container's UID 1000 to an unprivileged subordinate UID on the host —
  extra defense in depth if the host is shared.
- It cannot be enforced from this repo (not a per-compose setting), so document
  it as a recommended host step, including the volume-ownership remapping caveat.

**Commit:** `docs(security): document userns-remap host-level hardening option`

---

### Step 10 — Remove this plan document (cleanup)

Once Steps 4–9 are all implemented and committed, this file has served its
purpose. Delete `docs/security-hardening-plan.md` so the tracking scaffold does
not linger in the repository.

**Verify:** the file is gone and nothing references it (e.g.
`grep -r security-hardening-plan` returns no hits).

**Commit:** `docs(security): remove completed hardening plan`

---

## Status

- Steps 1–3 complete and committed (see table above).
- **Next: Step 4** (X11 magic-cookie auth) — awaiting go-ahead.
