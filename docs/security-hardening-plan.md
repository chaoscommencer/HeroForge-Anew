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
| 4 | `50ac168` | Replace `Xvfb -ac` with `xauth` MIT-MAGIC-COOKIE-1 auth. The display entrypoint generates a cookie into the shared `x11-socket` volume (`/tmp/.X11-unix/.Xauthority`, 0600) and re-registers it as a FamilyWild (`ffff`) entry so the single cookie authenticates from either container's hostname over the shared socket. `XAUTHORITY` set on both services; `xauth` added to the display image. |
| 5a | `1a289a0` | Generate a hash-pinned lockfile (`requirements-lock.txt`) from the `pyproject.toml` runtime deps via `pip-compile --generate-hashes`, and install it in the `Dockerfile.heroforge-app` builder stage with `--require-hashes` (retaining `--only-binary=:all:`). pip now refuses any wheel whose sha256 is not in the lockfile. NO SBOM (overkill for this single-tenant QA stack); Dependabot already covers pip/docker/actions/devcontainers. |
| 5b | `b198a99` | Add an `audit` job to `.github/workflows/ci.yml` running `pip-audit` against `requirements-lock.txt` (CVEs in the exact shipped versions), independent of the lint/format/test job. A Trivy image scan (OS-level CVEs) remains an optional future addition. |
| 5b+ | `a141e23` | Harden the `audit` job: install a hash-checked pip from `requirements-pip.txt`, then `pip-audit` from a new hash-pinned `requirements-pip-audit.txt` (generated from `requirements-pip-audit.in`), joined with `&&`; the scan now loops over every `requirements*.txt` (runtime lockfile + CI tooling pins), so the auditing tool chain is audited too. |
| 6 | `2bce4fd` | Document the seccomp/AppArmor posture in `docs/containerized-runtime.md`: the stack relies on the engine's **default** seccomp + `docker-default` AppArmor profiles (plus `cap_drop: ALL` and `no-new-privileges`); a custom profile is out of scope (high-maintenance, host-loaded, not portable in a devcontainer). Docs-only. |
| 7 | `36735d3` | Add a `healthcheck:` to the `app` service in `docker-compose.yml`: a dependency-free pure-Python `/proc` scan (the app has `network_mode: none` and no extra tooling) that exits 0 once a `python -m heroforge` process is found, with a 30s `start_period` to cover first-launch DB seeding. Verified `health=healthy` live. |
| 8 | `fe9d9c0` | Serve noVNC over TLS: `display-entrypoint.sh` generates a self-signed loopback cert+key (CN=localhost, RSA-2048, key 0600) into the `/home/app` tmpfs and launches websockify with `--cert/--key/--ssl-only` (wss:// only; plaintext refused); `openssl` added to `Dockerfile.display`. Forwarded port 6080 marked `protocol: https` in `devcontainer.json` + a live `remote.portsAttributes` mirror in `.vscode/settings.json` so the VS Code forwarder speaks TLS to the backend (plain HTTP otherwise → 502); `onAutoForward` switched to `notify`. Task URLs updated to `https://wss://`; TLS setup and benign websockify log lines documented in `docs/containerized-runtime.md`. |
| 9 | `6b38652` | Document the knowingly accepted residual risks in `docs/containerized-runtime.md` under a new **Residual / accepted risks** subsection: VNC's DES-based password is capped at 8 significant characters (protocol-inherent), and Dependabot **security alerts** are a repository-settings toggle (*Settings → Code security and analysis*), not something `.github/dependabot.yml` can enable. Docs-only. |
| 10 | `01d678d` | Document `userns-remap` in `docs/containerized-runtime.md` as an **optional host daemon-level** hardening option (`/etc/docker/daemon.json` `{"userns-remap": "default"}`) that maps the container's UID 1000 to an unprivileged subordinate host UID for extra defense in depth on a shared host. Notes it cannot be enforced from this repo (not a per-Compose setting), plus the volume-ownership remapping caveat, the daemon-global scope, and that rootless Podman achieves a similar end without daemon config. Docs-only. |

---

## Remaining steps

### Step 11 — Remove this plan document (cleanup)

Once Steps 4–10 are all implemented and committed, this file has served its
purpose. Delete `docs/security-hardening-plan.md` so the tracking scaffold does
not linger in the repository.

**Verify:** the file is gone and nothing references it (e.g.
`grep -r security-hardening-plan` returns no hits).

**Commit:** `docs(security): remove completed hardening plan`

---

## Status

- Steps 1–10 complete and committed (see table above).
- **Next: Step 11** (remove this completed plan document) — awaiting go-ahead.
