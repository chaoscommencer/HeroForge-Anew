# Isolated Runtime Environment (Codespaces, Docker & Podman)

HeroForge-Anew ships two complementary, **isolated** container setups:

| Purpose | Lives in | What it is |
| --- | --- | --- |
| **Develop** the code | `.devcontainer/` | Two Codespaces / Dev Containers profiles on one image (Python 3.12, PyQt6 runtime libraries): the default, unprivileged profile, and an opt-in QA profile with Docker-in-Docker. |
| **Run** the GUI for QA | `Dockerfile.heroforge-app` + `Dockerfile.display` + `docker-compose.yml` | A two-container Compose stack: a `display` sidecar that hosts the viewable desktop (Xvfb + noVNC) and an `app` container that runs the Qt application. |

The two are deliberately separate: the dev container is where you edit, lint and
test; the Compose stack is a clean, reproducible way to *run* the desktop app for
"developer-in-the-loop" QA in an isolated container. In the default profile,
which cannot run containers, `scripts/run-gui-local.sh` shows the same desktop
as plain processes instead.

---

## 1. Develop in a Codespace / Dev Container

There are two profiles. When you create a Codespace, pick one under
*Dev container configuration* (or in VS Code, **Dev Containers: Reopen in
Container** lists both). The Codespace must be created from a branch that
contains `.devcontainer/`; otherwise Codespaces falls back to its generic
universal image and none of this applies.

| | Default — `.devcontainer/devcontainer.json` | QA — `.devcontainer/qa/devcontainer.json` |
| --- | --- | --- |
| Use for | Everyday development, and **all unattended agents** | Running the containerized Compose QA stack |
| Privileged | No; also `no-new-privileges`, all capabilities dropped except the few root needs for Codespaces setup, 4096-process and 6 GiB memory limits | Yes (Docker-in-Docker requires it) |
| Containers | None | Docker CE, feature and engine pinned to exact versions |
| GUI | `scripts/run-gui-local.sh` (plain processes) | `scripts/run-gui.sh` (Compose stack) |
| sudo | None | None |

Both build [`.devcontainer/Dockerfile.devcontainer-default`](../.devcontainer/Dockerfile.devcontainer-default):
the official devcontainers Python 3.12 image (pinned by digest) plus the Qt/X11
libraries PyQt6 needs, the desktop tools for `run-gui-local.sh` (default profile
only), and the hash-pinned `requirements-pip.txt` + `requirements-dev.txt` in a
virtual environment at `/opt/venv`. Two hardening choices apply to both:

- **No sudo.** The base image's passwordless sudo rule for `vscode` is removed
  at build time, so nothing running as the editor user can become root.
  Installing system packages means changing the Dockerfile and rebuilding.
- **Read-only toolchain.** `/opt/venv` is owned by root, and so are the base
  image's tool directories on `PATH` (`/usr/local/py-utils`,
  `/usr/local/share/nvm`), so a compromised tool or dependency cannot replace
  pytest, black, ruff, git, a library, or any other program that later runs
  with your credentials. To change a Python dependency, update the lock file and
  rebuild. The project itself is not pip-installed; `PYTHONPATH` points at
  `src/` instead, so run the app with `python -m heroforge`. The image build
  fails if `vscode` could write any directory on `PATH` or any system login
  script, so a base-image update cannot quietly undo this.

  What this does **not** stop: your home directory (`~/.bashrc` and similar) and
  the workspace stay writable, as development needs. Code running as `vscode`
  can still leave a persistent foothold there, for example a
  `src/sitecustomize.py`, which every Python process would import because `src/`
  is on `PYTHONPATH`. Review untracked files (`git status`) after running
  untrusted code or agents.

Why the default profile cannot run containers: Docker-in-Docker needs a
privileged container, which can take over the Codespace VM, and rootless Podman
was tested and cannot start in an unprivileged container (creating its user
namespace fails even with seccomp and AppArmor disabled). So container work lives
only in the opt-in QA profile. Never point unattended agents at the QA profile.

Once the container is up you can immediately develop and test:

```bash
pytest tests/ -v        # widget tests run for real (PyQt6 is installed)
ruff check src/
black src/ tests/
```

---

## 2a. Run the GUI in the default profile (no containers)

The default devcontainer profile has no container engine, so it shows the GUI
with plain processes:

```bash
scripts/run-gui-local.sh
```

It starts the same desktop the Compose `display` sidecar runs
([`scripts/display-entrypoint.sh`](../scripts/display-entrypoint.sh): Xvfb,
fluxbox, x11vnc and websockify/noVNC) in the background, prints a one-time VNC
password, and runs the app in the foreground on that display. Open the forwarded
**port 6080** from the *Ports* panel (or `https://localhost:6080/vnc.html`) and
enter the password. Closing the app or pressing Ctrl-C stops the desktop.

- noVNC listens on `127.0.0.1` only and serves TLS only, so it is reachable just
  through the private Codespaces / VS Code port forward.
- The password, X cookie, TLS key and desktop config live in a private `0700`
  directory on a RAM-backed tmpfs and are deleted on exit. The password file is
  deleted as soon as the desktop is up, and the password is never on a command
  line.
- Difference from the Compose stack: the **app runs as your own user**, with your
  network access and your workspace, not in a network-less, read-only
  container. Use the QA profile and section 2 when you need that isolation.

## 2. Run the GUI for QA (Docker / Podman)

The QA desktop is gated by a **one-time VNC password**. Let the helper script
manage it:

```bash
scripts/run-gui.sh            # build (first run) and launch the GUI
scripts/run-gui.sh --build    # force a rebuild
scripts/run-gui.sh down       # tear the stack down
```

Every launch generates a fresh random password and prints it once in the
terminal:

```text
  VNC password for this session: 4toN5hXw
```

Open the forwarded **port 6080** from VS Code's *Ports* panel (or
`https://localhost:6080/vnc.html`) and enter that password. The HeroForge-Anew
window appears on the desktop, ready to click through for QA. (VNC's classic
auth only honours the first **8 characters**, so the generated secret is exactly
8 alphanumeric characters.)

How the password is kept short-lived:

- It is **never written to `.env` or anywhere in the repository**. The script
  writes it to a `0600` file inside a new `0700` directory on a RAM-backed tmpfs
  (`$XDG_RUNTIME_DIR`, else `/dev/shm`) and passes that path to Compose in
  `HEROFORGE_VNC_SECRET_FILE`.
- Compose mounts the file into the display sidecar as a **secret** at
  `/run/secrets/vnc_password`, not as an environment variable, so it does not
  appear in `docker inspect` or `/proc/<pid>/environ`.
- A background watcher **deletes the host file** as soon as the display port
  answers (the container keeps its mounted copy), or when Compose exits, or
  after 30 minutes at most.
- Inside the sidecar the password goes to x11vnc through
  `-passwdfile rm:<file>`, which reads and then deletes the file, so it never
  appears on a command line and afterwards lives only in x11vnc's memory.

Restarting the stack gives a new password. Older versions stored the password
in `.env` and `secrets/vnc_password`; the script deletes the old
`secrets/vnc_password` and tells you to remove any leftover `VNC_PASSWORD` line
from `.env`.

The script auto-detects a container engine, preferring **Podman** (rootless, more
secure) and falling back to Docker:

1. `podman-compose`
2. `podman compose`
3. `docker compose`
4. `docker-compose`

It aligns the in-container user with your UID/GID and, as described above,
supplies a one-time VNC password for each launch.

### Doing it by hand

```bash
# Put a one-time password in a private tmpfs file (deleted again below).
export HEROFORGE_VNC_SECRET_FILE="$(mktemp -d /dev/shm/heroforge-vnc.XXXXXXXX)/vnc_password"
( umask 077; LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 8 >"$HEROFORGE_VNC_SECRET_FILE" )
cat "$HEROFORGE_VNC_SECRET_FILE"; echo   # your password for this session
export APP_UID=$(id -u) APP_GID=$(id -g)

# Podman (preferred)
podman-compose -f docker-compose.yml up --build
# …or Docker
docker compose -f docker-compose.yml up --build

# In another terminal, once port 6080 answers, delete the host copy:
rm -rf "$(dirname "$HEROFORGE_VNC_SECRET_FILE")"
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
  mounted owned by the non-root `app` user (`uid`/`gid` from `APP_UID`/`APP_GID`)
  with mode `0700`, because a `tmpfs` over the image directory would otherwise
  mount root-owned and lock that user out; no other user can read it.

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
  **required**, **one-time** VNC password. `scripts/run-gui.sh` generates a
  fresh one per launch and prints it once; it is never stored in `.env` or the
  repository. It reaches the display sidecar as a **Compose secret** (a file
  mounted at `/run/secrets/vnc_password`, sourced from a `0600` file on a
  RAM-backed tmpfs that is deleted once the container is up) rather than an
  environment variable, so it never appears in the container environment
  (`docker inspect` / `/proc/<pid>/environ`). x11vnc reads it through
  `-passwdfile rm:`, which deletes that copy too, so the password is never on a
  command line. The stack refuses to start without a password (and rejects the
  `change-me` placeholder) — see section 2.
- The **main access control is the port forward itself**: Codespaces forwards
  port 6080 **privately** (only your signed-in GitHub account can open it). Keep
  it private; never set the port's visibility to *Public*.
- Both base images are **pinned by digest** (not just a mutable tag) in
  `Dockerfile.heroforge-app` and `Dockerfile.display`, making builds reproducible and resistant
  to tag re-pointing / supply-chain tampering. Third-party Python wheels are
  installed with `--only-binary=:all:` to avoid executing sdist build code.
- Docker-in-Docker requires a privileged dev container, so it is confined to
  the opt-in QA profile (`.devcontainer/qa/`); the default profile is
  unprivileged and has no container engine (see section 1).

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
- **Debian (apt) packages are not pinned to exact versions.** The base images
  are pinned by digest and every Python wheel by hash, but the Qt libraries,
  Podman, Xvfb/x11vnc/noVNC and git come from `apt-get install` of the current
  bookworm packages at build time. apt verifies every package against Debian's
  signed release files, so a tampered mirror cannot inject a package; what is
  lost is byte-for-byte reproducibility. Pinning exact versions is deliberately
  not done: Debian drops superseded versions from its mirrors once a security
  update lands, so pinned builds would break exactly when a fix ships, and
  stale pins would hold back security fixes. If reproducible builds become a
  requirement, point apt at a dated `snapshot.debian.org` mirror instead.
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

- **The inner docker-in-docker daemon.** The QA stack runs against the *inner*
  `dockerd` that the docker-in-docker feature starts inside the QA profile.
  Changing its configuration needs root, and neither devcontainer profile gives
  the `vscode` user sudo any more, so the helper script below only works where
  you do have root (for example a Docker host you administer, or a custom image
  that runs it at build time):

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
on a host with rootless Podman the QA stack runs rootless with no flags.

Neither devcontainer profile includes Podman: the default profile cannot run it
(see section 1), and in the privileged QA profile it would add no isolation over
Docker. [`scripts/setup-podman.sh`](../scripts/setup-podman.sh) remains for
setting up rootless Podman on a machine you administer (it needs sudo):

```bash
scripts/setup-podman.sh          # install + configure rootless Podman
scripts/setup-podman.sh --check  # report state, change nothing
```

It installs and configures:

- **`uidmap`** — the `newuidmap`/`newgidmap` setuid helpers Podman uses to map
  container UIDs onto the user's delegated range.
- **Subordinate UID/GID ranges** for the user in `/etc/subuid` and `/etc/subgid`.
- **`fuse-overlayfs`** — for hosts where the kernel `overlay` driver is
  unavailable to rootless users. Without `/dev/fuse` Podman falls back to the
  slow `vfs` driver.
- **`slirp4netns`** — rootless user-mode networking.
- **`podman-compose`** — installed hash-pinned into its own virtualenv when it
  is not already on `PATH`.


