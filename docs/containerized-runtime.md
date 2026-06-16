# Isolated Runtime Environment (Codespaces, Docker & Podman)

HeroForge-Anew ships two complementary, **isolated** container setups:

| Purpose | Lives in | What it is |
| --- | --- | --- |
| **Develop** the code | `.devcontainer/` | A Codespaces / Dev Containers definition with Python 3.12, PyQt6 runtime libraries, and Docker-in-Docker. |
| **Run** the GUI for QA | `Dockerfile.heroforge-app` + `Dockerfile.display` + `docker-compose.yml` | A two-container Compose stack: a `display` sidecar that hosts the viewable desktop (Xvfb + noVNC) and an `app` container that runs the Qt application. |

The two are deliberately separate: the dev container is where you edit, lint and
test; the Compose stack is a clean, reproducible way to *run* the desktop app for
"developer-in-the-loop" QA without polluting your environment. The viewable
desktop is hosted **inside the Compose stack**, not in the editor container.

---

## 1. Develop in a Codespace / Dev Container

Open the repository in a GitHub Codespace (or locally via **Dev Containers:
Reopen in Container**). The container defined in
[`.devcontainer/devcontainer.json`](../.devcontainer/devcontainer.json):

- builds [`.devcontainer/Dockerfile.devcontainer-default`](../.devcontainer/Dockerfile.devcontainer-default) — the official
  devcontainers Python 3.12 image plus the Qt/X11 system libraries PyQt6 needs,
  the rootless-Podman runtime packages (gated by the `INSTALL_PODMAN_DEPS` build
  arg), and the hash-pinned third-party dependencies (`requirements-pip.txt` +
  `requirements-dev.txt`) baked into a `vscode`-owned virtual environment at
  `/opt/venv`;
- adds the **docker-in-docker** feature, so the QA Compose stack can be built and
  run from inside the Codespace;
- on creation installs only the editable project into that venv
  (`pip install --no-deps -e .`, since the workspace is bind-mounted at runtime
  and absent at build time) and then
  `scripts/setup-podman.sh` (which provisions rootless Podman + podman-compose;
  it is optional, so a failure only warns), and runs as the non-root `vscode`
  user.

The editor container does **not** run a desktop of its own; the QA stack's
`display` sidecar provides the viewable GUI on port **6080** while it is running.

Once the container is up you can immediately develop and test:

```bash
pytest tests/ -v        # widget tests run for real (PyQt6 is installed)
ruff check src/
black src/ tests/
```

---

## 2. Run the GUI for QA (Docker / Podman)

The QA stack requires a **VNC password** that gates access to the noVNC desktop.
It is read from a git-ignored `.env` file in the project root. The easiest path
is to let the helper script manage it for you:

```bash
scripts/run-gui.sh                      # build (first run) and launch the GUI
scripts/run-gui.sh --build              # force a rebuild
scripts/run-gui.sh --generate-password  # rotate the VNC password, then launch
scripts/run-gui.sh down                 # tear the stack down
```

On launch the script ensures `.env` exists (seeding it from `.env.example`) and
that it carries a strong, randomly generated `VNC_PASSWORD`: one is created
whenever the value is missing, empty, or still the `change-me` placeholder, and
`--generate-password` forces a fresh one even if a real password is already set.
The active password is always written back to `.env` for you to read. (VNC's
classic auth only honours the first **8 characters**, so the generated secret is
exactly 8 alphanumeric characters.)

The script then writes that password into a git-ignored `secrets/vnc_password`
file, which Compose mounts into the display sidecar as a **secret** at
`/run/secrets/vnc_password` instead of injecting it as an environment variable.
This keeps the password out of the container environment (so it does not appear
in `docker inspect` or `/proc/<pid>/environ`).

To set it yourself instead, edit `.env` by hand and materialize the secret file:

```bash
cp .env.example .env
# then edit .env and set a strong VNC_PASSWORD
mkdir -p secrets && printf '%s' "$VNC_PASSWORD" > secrets/vnc_password
```

Then open the forwarded **port 6080** (noVNC) and enter your `VNC_PASSWORD` — the
HeroForge-Anew window appears on the desktop, ready to click through for QA.

The script auto-detects a container engine, preferring **Podman** (rootless, more
secure) and falling back to Docker:

1. `podman-compose`
2. `podman compose`
3. `docker compose`
4. `docker-compose`

It aligns the in-container user with your UID/GID and, as described above,
provisions a `VNC_PASSWORD` automatically when one is not already present.

### Doing it by hand

```bash
cp .env.example .env   # set a strong VNC_PASSWORD (once)
mkdir -p secrets && printf '%s' "$VNC_PASSWORD" > secrets/vnc_password
export APP_UID=$(id -u) APP_GID=$(id -g)

# Podman (preferred)
podman-compose -f docker-compose.yml up --build
# …or Docker
docker compose -f docker-compose.yml up --build
```

### How the display works

There is **no host X server**. The `display` sidecar
([`Dockerfile.display`](../Dockerfile.display)) runs a virtual X server (Xvfb on
`:99`), a window manager (fluxbox), a VNC server (x11vnc, bound to loopback) and
the noVNC web client (websockify on `6080`). The `app` container sets
`DISPLAY=:99`, `QT_QPA_PLATFORM=xcb` and `QT_X11_NO_MITSHM=1`, and draws into the
sidecar's X server over a **shared `x11-socket` volume** mounted at
`/tmp/.X11-unix` in both containers. Compose starts `app` only once the display
is healthy (`depends_on: condition: service_healthy`).

The slim display image ships no wallpaper setter, so the stock `fbsetbg` would
pop a *blocking* "I can't find an app to set the wallpaper with" dialog when
fluxbox starts. fluxbox calls `fbsetbg` by absolute path, so the binary itself is
replaced at build time with a tiny shim that paints a solid background
(`fbsetroot -solid black`) — the desktop comes up clean and unattended.

### TLS on the noVNC WebSocket

websockify is launched with `--cert`, `--key` and `--ssl-only`, so it serves
**only** `https://` / `wss://` and refuses plaintext `http://` / `ws://`. The
entrypoint generates a **self-signed** certificate (`CN=localhost`, RSA-2048)
into the in-RAM `/home/app` tmpfs at startup, with the private key written
`0600`. Self-signed is appropriate because the endpoint is reached only over
loopback (the VS Code port-forwarding proxy on `127.0.0.1:6080`); the
laptop→Codespace hop is already TLS via the VS Code tunnel, and this closes the
remaining in-host plaintext segment.

Because the certificate is self-signed, the **browser shows a one-time security
warning** on first connect — accept it to proceed. VS Code's port-forwarding
proxy must also be told the backend speaks TLS: the `6080` entry in
[`.devcontainer/devcontainer.json`](../.devcontainer/devcontainer.json) (and the
live `remote.portsAttributes` mirror in [`.vscode/settings.json`](../.vscode/settings.json))
sets `"protocol": "https"`. Without it the proxy connects over plain HTTP,
websockify rejects it (`non-SSL connection received but disallowed`), and the
browser sees a **502**.

#### Benign log lines

With TLS enforced, a few `display` log lines are **expected and harmless**:

- `handler exception: [SSL: UNEXPECTED_EOF_WHILE_READING] unexpected eof while
  reading` — OpenSSL 3.0 (Debian bookworm) raises this when a TLS peer drops the
  TCP connection without a clean `close_notify` alert. Browsers and the
  port-forwarding proxy routinely abandon idle/pooled/probe connections this
  way; the active VNC session is unaffected.
- `code 404, message File not found` — the noVNC client probes for optional
  static assets (e.g. a favicon) that the Debian `novnc` package's web root does
  not ship. The very next log lines —
  `SSL/TLS (wss://) WebSocket connection`, `Path: '/websockify'`,
  `connecting to: localhost:5900` — are the **successful** encrypted WebSocket
  upgrade, i.e. the desktop is connecting normally.

### Persistence and writable paths

Both containers run with a **read-only root filesystem**; the only writable
locations are explicit mounts:

- **`heroforge-data`** — a persistent named volume mounted at `/app/userdata`
  (`HEROFORGE_DATA_DIR`). The auto-seeded `heroforge.db` and your character
  `.hfc` saves live here, so they **survive container removal** (`run-gui.sh
  down`). They are only discarded by an explicit
  `scripts/run-gui.sh down --volumes`. The image creates `/app/userdata` owned by
  the non-root `app` user so the volume inherits that ownership on first use.
- **`/tmp` and `/home/app`** — in-RAM `tmpfs` mounts (wiped on stop) for X/Qt
  scratch files, the runtime VNC password and fluxbox config. `/home/app` is
  mounted `mode=0o1777` because a `tmpfs` over the image directory would
  otherwise mount root-owned and lock out the non-root user.

The application source is bind-mounted **read-only** into the `app` container
(`./src`, `./pyproject.toml`, and the seed data/workbooks under
`./data`), so edits are picked up on the next launch but the running container
cannot modify the repo.

---

## Security notes

- Both containers run as **non-root** users, with **all Linux capabilities
  dropped** (`cap_drop: ALL`) and **`no-new-privileges`** set.
- **Syscall and MAC filtering** rely on the container engine's built-in
  defaults rather than a bespoke profile. Docker/Podman apply their **default
  seccomp profile** to every container unless told otherwise — it blocks ~44 of
  the most dangerous/obsolete syscalls (e.g. `keyctl`, `ptrace` of other
  processes, `mount`, `reboot`, kernel-module and `bpf` operations) while
  leaving the broad set a normal application needs. Combined with `cap_drop:
  ALL` and `no-new-privileges`, that default profile is what sandboxes these QA
  containers at the kernel boundary. A **custom** seccomp profile (an explicit
  JSON syscall allowlist attached via `security_opt: [seccomp:./security/seccomp.json]`)
  is deliberately **out of scope**: it would have to be traced with
  `strace`/`oci-seccomp-bpf-hook` and re-tuned on every Qt/Xorg update, which is
  high-maintenance and breakage-prone for a single-tenant QA stack with limited
  upside over the default. **AppArmor** (or SELinux) likewise applies the engine's
  default `docker-default` profile when the host enforces it; a custom AppArmor
  profile must be loaded into the **host** kernel and referenced by name, so it
  is not portable inside a devcontainer and cannot be enforced from this repo —
  it is a host-administration step, not a per-Compose setting.
- Both containers use a **read-only root filesystem**; only the explicit
  `heroforge-data` volume and in-RAM `tmpfs` mounts are writable (see *Persistence
  and writable paths* above). A compromised process cannot tamper with the image
  binaries or config.
- The `app` container runs with **`network_mode: none`** — it has no network
  interface at all, removing any inbound attack or outbound exfiltration path. It
  communicates only over the shared X11 unix socket and reads local mounts.
- Both containers carry **resource ceilings** (`mem_limit`, `pids_limit`,
  `cpus`, `ulimits.nofile`) to blunt local DoS such as fork bombs or memory/CPU
  exhaustion. Tune them from `docker stats` if needed.
- Source and seed-data bind mounts are **read-only**, so the running app cannot
  modify the repository.
- The viewable desktop lives in the `display` sidecar, which carries **no
  application source and no workspace bind mounts** — a noVNC session is isolated
  from the editor container (and its repo/credentials), unlike the previous
  desktop-lite-in-devcontainer setup.
- noVNC is served **only over TLS** (`wss://`): websockify runs with
  `--cert --key --ssl-only` and a self-signed loopback certificate, so the
  in-host segment between the VS Code port-forwarding proxy and websockify is
  encrypted and plaintext `ws://`/`http://` is refused (see *TLS on the noVNC
  WebSocket* above).
- noVNC is published on **loopback only** (`127.0.0.1:6080`) and gated by a
  **required** VNC password. The password is set in the git-ignored `.env` file
  but delivered to the display sidecar as a **Compose secret** (a file mounted at
  `/run/secrets/vnc_password`, sourced from a git-ignored `secrets/vnc_password`
  file that `scripts/run-gui.sh` materializes from `.env`) rather than an
  environment variable, so it never appears in the container environment
  (`docker inspect` / `/proc/<pid>/environ`). The stack refuses to start without
  a password (and rejects the `change-me` placeholder). `scripts/run-gui.sh`
  generates a strong password automatically — see section 2.
- Both base images are **pinned by digest** (not just a mutable tag) in
  `Dockerfile.heroforge-app` and `Dockerfile.display`, making builds reproducible and resistant
  to tag re-pointing / supply-chain tampering. Third-party Python wheels are
  installed with `--only-binary=:all:` to avoid executing sdist build code.
- Docker-in-Docker requires a privileged dev container; if you prefer a
  stricter, rootless model, run the Compose stack with **Podman**
  (`podman-compose`), which the helper script selects automatically when present.

### Residual / accepted risks

Some limitations are known and **knowingly accepted** for this single-tenant QA
stack rather than engineered around:

- **VNC password is capped at 8 significant characters.** The classic VNC
  authentication scheme (RFB) hashes the password with DES, which only consumes
  the first **8 characters** — anything beyond them is ignored. This is inherent
  to the protocol, not a configuration choice, so `scripts/run-gui.sh` generates
  exactly 8 random alphanumeric characters (a longer secret would buy nothing).
  The exposure is already narrowed by publishing noVNC on **loopback only** and
  serving it **over TLS** (see above), so the password is never the sole control
  and never crosses the wire in cleartext.
- **Dependabot security alerts are a repository-settings toggle, not a repo
  file.** `.github/dependabot.yml` configures **version-update** PRs only.
  Vulnerability **security alerts/updates** are enabled separately under the
  repository's *Settings → Code security and analysis* (Dependabot alerts +
  security updates) and cannot be committed to the repo. Confirm they are enabled
  there; the in-repo `dependabot.yml` does not and cannot turn them on.

### Optional hardening: `userns-remap`

For extra defense in depth, enable the Docker daemon's **user-namespace
remapping**. With it on, the container's UID/GID (here UID 1000, the non-root
`app` user) is mapped to an **unprivileged subordinate UID** on the daemon side,
so even a process that somehow broke out of a container would not map to a
privileged user. It complements the per-container `cap_drop: ALL`,
`no-new-privileges` and read-only-rootfs settings already in
`docker-compose.yml`.

This is a **daemon-level** setting, not a per-Compose option, so which daemon you
apply it to matters:

- **The inner docker-in-docker daemon (enforceable from here).** The QA stack
  runs against the *inner* `dockerd` that the docker-in-docker feature starts
  inside this dev container — a daemon you fully own. Enable remapping on it with
  the helper script:

  ```bash
  scripts/enable-userns-remap.sh           # enable, then restart the inner daemon
  scripts/enable-userns-remap.sh --status  # check current state, change nothing
  ```

  It idempotently merges `"userns-remap": "default"` into
  `/etc/docker/daemon.json` and restarts the daemon; `"default"` makes Docker
  create and use a `dockremap` subordinate-ID range automatically. Re-running it
  is a no-op once remapping is on. A fresh `scripts/run-gui.sh` then launches the
  `app`/`display` containers remapped.

- **The real host daemon (cannot be enforced from this repository).** In
  Codespaces you do not control the outer host daemon, and the dev container is
  itself a privileged docker-in-docker host on that machine — so remapping the
  *inner* containers does **not** harden the outer DinD boundary against the real
  host. The full host-protection benefit of `userns-remap` is realised only when
  a host administrator sets it on the **real** host's `/etc/docker/daemon.json`
  (same key) and restarts that daemon. That is a host-administration step,
  documented here for completeness.

**Caveats:**

- **Volume ownership is remapped.** Files in named volumes (e.g.
  `heroforge-data`) and on bind mounts are owned by the *remapped* UID, not the
  literal UID 1000. The images already create `/app/userdata` owned by the
  in-container `app` user, so the volume inherits the correct mapped ownership on
  first use; pre-existing paths bind-mounted in may need `chown` to the
  subordinate range. Containers/volumes created **before** enabling remapping
  keep their old ownership — start a fresh QA run after enabling it.
- **It is global to the daemon.** Every container on that daemon runs remapped
  (the QA stack, the graphify builder, image builds), which can interfere with
  workloads that expect literal UIDs — hence it is opt-in via the script rather
  than baked into the stack.
- **Rootless Podman achieves a similar end** without daemon configuration, since
  it already runs containers under the invoking user's subordinate-ID range; see
  *Running the QA stack with Podman* below.

### Running the QA stack with Podman

`scripts/run-gui.sh` prefers **Podman** over Docker when it is present
(`podman-compose` → `podman compose` → `docker compose` → `docker-compose`), so
running the QA stack rootless needs no flags once Podman is installed. The dev
container provisions it automatically: the `postCreateCommand` in
[`.devcontainer/devcontainer.json`](../.devcontainer/devcontainer.json) runs
[`scripts/setup-podman.sh`](../scripts/setup-podman.sh) after the editable-project
install (non-fatally — a failure only warns, since Docker remains available).

You can also run it (or re-run it — it is idempotent) by hand:

```bash
scripts/setup-podman.sh          # install + configure rootless Podman
scripts/setup-podman.sh --check  # report state, change nothing
```

Rootless Podman *nested* inside the docker-in-docker dev container needs a few
prerequisites that the script installs and configures:

- **`uidmap`** — the `newuidmap`/`newgidmap` setuid helpers Podman uses to map
  container UIDs onto the user's delegated range.
- **Subordinate UID/GID ranges** for the remote user in `/etc/subuid` and
  `/etc/subgid` (the base image usually seeds these for `vscode`; the script
  adds them if missing).
- **`fuse-overlayfs`** — a nested container typically cannot use the kernel
  `overlay` storage driver, so the script points Podman at fuse-overlayfs via
  `~/.config/containers/storage.conf`. Without `/dev/fuse` Podman falls back to
  the slow `vfs` driver.
- **`slirp4netns`** — rootless user-mode networking.
- **`podman-compose`** — installed via `pipx` when available, else `pip --user`.

**Caveat:** this is rootless Podman nested inside a *privileged* docker-in-docker
dev container — workable for QA, but expect occasional storage/cgroup friction.
On a real host (no DinD layer) rootless Podman is cleaner, since there is no
nesting and it already maps to the invoking user's subordinate-ID range.


