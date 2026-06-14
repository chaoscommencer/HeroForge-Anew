# Isolated Runtime Environment (Codespaces, Docker & Podman)

HeroForge-Anew ships two complementary, **isolated** container setups:

| Purpose | Lives in | What it is |
| --- | --- | --- |
| **Develop** the code | `.devcontainer/` | A Codespaces / Dev Containers definition with Python 3.12, PyQt6 runtime libraries, and Docker-in-Docker. |
| **Run** the GUI for QA | `Dockerfile` + `Dockerfile.display` + `docker-compose.yml` | A two-container Compose stack: a `display` sidecar that hosts the viewable desktop (Xvfb + noVNC) and an `app` container that runs the Qt application. |

The two are deliberately separate: the dev container is where you edit, lint and
test; the Compose stack is a clean, reproducible way to *run* the desktop app for
"developer-in-the-loop" QA without polluting your environment. The viewable
desktop is hosted **inside the Compose stack**, not in the editor container.

---

## 1. Develop in a Codespace / Dev Container

Open the repository in a GitHub Codespace (or locally via **Dev Containers:
Reopen in Container**). The container defined in
[`.devcontainer/devcontainer.json`](../.devcontainer/devcontainer.json):

- builds [`.devcontainer/Dockerfile`](../.devcontainer/Dockerfile) — the official
  devcontainers Python 3.12 image plus the Qt/X11 system libraries PyQt6 needs;
- adds the **docker-in-docker** feature, so the QA Compose stack can be built and
  run from inside the Codespace;
- runs `pip install -e ".[dev]"` on creation and runs as the non-root `vscode`
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
It is read from a git-ignored `.env` file in the project root. Create it once:

```bash
cp .env.example .env
# then edit .env and set a strong VNC_PASSWORD
```

Then use the helper script:

```bash
scripts/run-gui.sh            # build the images (first run) and launch the GUI
scripts/run-gui.sh --build    # force a rebuild
scripts/run-gui.sh down       # tear the stack down
```

Then open the forwarded **port 6080** (noVNC) and enter your `VNC_PASSWORD` — the
HeroForge-Anew window appears on the desktop, ready to click through for QA.

The script auto-detects a container engine, preferring **Podman** (rootless, more
secure) and falling back to Docker:

1. `podman-compose`
2. `podman compose`
3. `docker compose`
4. `docker-compose`

It aligns the in-container user with your UID/GID and refuses to start if
`VNC_PASSWORD` is set in neither your environment nor `.env`.

### Doing it by hand

```bash
cp .env.example .env   # set a strong VNC_PASSWORD (once)
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

Only the `display` service publishes a port, and only on loopback
(`127.0.0.1:6080`), so the desktop is reachable solely through VS Code's port
forwarding. Both containers drop all Linux capabilities and set
`no-new-privileges`, keeping the QA sandbox tight.

The repository is bind-mounted into the `app` container at `/app`, so source
edits are picked up on the next launch and the auto-seeded `heroforge.db`
persists on the host.

---

## Security notes

- Both containers run as **non-root** users.
- Both containers run with **all capabilities dropped** and
  **`no-new-privileges`**.
- The viewable desktop lives in the `display` sidecar, which carries **no
  application source and no workspace bind mounts** — a noVNC session is isolated
  from the editor container (and its repo/credentials), unlike the previous
  desktop-lite-in-devcontainer setup.
- noVNC is published on **loopback only** (`127.0.0.1:6080`) and gated by a
  **required** `VNC_PASSWORD` sourced from the git-ignored `.env` file; the stack
  refuses to start without it. Use a strong, unique value.
- Docker-in-Docker requires a privileged dev container; if you prefer a
  stricter, rootless model, run the Compose stack with **Podman**
  (`podman-compose`), which the helper script selects automatically when present.
