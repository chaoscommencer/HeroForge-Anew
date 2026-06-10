# Isolated Runtime Environment (Codespaces, Docker & Podman)

HeroForge-Anew ships two complementary, **isolated** container setups:

| Purpose | Lives in | What it is |
| --- | --- | --- |
| **Develop** the code | `.devcontainer/` | A Codespaces / Dev Containers definition with Python 3.12, PyQt6 runtime libraries, a web desktop, and Docker-in-Docker. |
| **Run** the GUI for QA | `Dockerfile` + `docker-compose.yml` | A single application image launched via Compose, with the Qt window forwarded to a viewable X server. |

The two are deliberately separate: the dev container is where you edit, lint and
test; the Compose stack is a clean, reproducible way to *run* the desktop app for
"developer-in-the-loop" QA without polluting your environment.

---

## 1. Develop in a Codespace / Dev Container

Open the repository in a GitHub Codespace (or locally via **Dev Containers:
Reopen in Container**). The container defined in
[`.devcontainer/devcontainer.json`](../.devcontainer/devcontainer.json):

- builds [`.devcontainer/Dockerfile`](../.devcontainer/Dockerfile) — the official
  devcontainers Python 3.12 image plus the Qt/X11 system libraries PyQt6 needs;
- adds the **desktop-lite** feature, a lightweight Linux desktop served over
  noVNC on port **6080** (`DISPLAY=:1`), so GUI windows are viewable in a browser
  tab;
- adds the **docker-in-docker** feature, so the QA Compose stack can be built and
  run from inside the Codespace;
- runs `pip install -e ".[dev]"` on creation and runs as the non-root `vscode`
  user.

Once the container is up you can immediately develop and test:

```bash
pytest tests/ -v        # widget tests run for real (PyQt6 is installed)
ruff check src/
black src/ tests/
```

---

## 2. Run the GUI for QA (Docker / Podman)

From inside the Codespace (or any Docker/Podman host with an X server), use the
helper script:

```bash
scripts/run-gui.sh            # build the image (first run) and launch the GUI
scripts/run-gui.sh --build    # force a rebuild
scripts/run-gui.sh down       # tear the stack down
```

Then open the forwarded **port 6080** (noVNC, password `vscode`) — the
HeroForge-Anew window appears on the desktop, ready to click through for QA.

The script auto-detects a container engine, preferring **Podman** (rootless, more
secure) and falling back to Docker:

1. `podman-compose`
2. `podman compose`
3. `docker compose`
4. `docker-compose`

It also exports your `DISPLAY`, aligns the in-container user with your UID/GID,
and best-effort runs `xhost +local:` so Qt can draw to the shared X server.

### Doing it by hand

```bash
export DISPLAY=:1
export APP_UID=$(id -u) APP_GID=$(id -g)
xhost +local: || true

# Podman (preferred)
podman-compose -f docker-compose.yml up --build
# …or Docker
docker compose -f docker-compose.yml up --build
```

### How the display forwarding works

`docker-compose.yml` shares the host/devcontainer X11 socket
(`/tmp/.X11-unix`) into the application container and sets `DISPLAY=:1`,
`QT_QPA_PLATFORM=xcb` and `QT_X11_NO_MITSHM=1`. Inside a Codespace the X server
on `:1` is the desktop-lite desktop, which is why the window shows up at the
noVNC URL. The container also drops all Linux capabilities and sets
`no-new-privileges`, keeping the QA sandbox tight.

The repository is bind-mounted at `/app`, so source edits are picked up on the
next launch and the auto-seeded `heroforge.db` persists on the host.

---

## Security notes

- Both containers run as **non-root** users.
- The QA container runs with **all capabilities dropped** and
  **`no-new-privileges`** — it only ever needs to talk to the X socket.
- Docker-in-Docker requires a privileged dev container; if you prefer a
  stricter, rootless model, run the Compose stack with **Podman**
  (`podman-compose`), which the helper script selects automatically when present.
- The desktop password defaults to `vscode`; change it in
  `.devcontainer/devcontainer.json` (and rebuild) for shared environments.
