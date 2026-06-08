# Isolated Runtime Environment

This document describes how to spin up HeroForge Anew (the Python edition) in a
**separate, isolated container** with full **viewing and interactivity**, so QA
can perform user-in-the-loop testing without installing anything on the host or
configuring X11 forwarding.

The PyQt application runs entirely inside the container on a virtual display.
The desktop is streamed to your browser via **noVNC**, so you simply open a URL
to see and click the live application.

```
┌──────────────────────── container ────────────────────────┐
│  Xvfb (virtual display)                                    │
│    └─ fluxbox (window manager)                             │
│         └─ HeroForge Anew (PyQt6 app)                      │
│  x11vnc ──► websockify/noVNC ──► :6080 (browser)           │
│                           └────► :5900 (native VNC client) │
└────────────────────────────────────────────────────────────┘
```

## Option A – Docker Compose (local QA)

Requirements: Docker (with the Compose plugin).

```bash
docker compose up --build
```

Then open <http://localhost:6080/vnc.html> in your browser and click **Connect**.
The HeroForge Anew window appears on the virtual desktop, ready for testing.

To stop:

```bash
docker compose down
```

### Useful knobs

All are set via environment variables (see `docker-compose.yml`):

| Variable          | Default        | Purpose                                   |
|-------------------|----------------|-------------------------------------------|
| `SCREEN_GEOMETRY` | `1280x800x24`  | Virtual display resolution and depth      |
| `NOVNC_PORT`      | `6080`         | Browser (noVNC) port                      |
| `VNC_PORT`        | `5900`         | Raw VNC port for native clients           |
| `VNC_PASSWORD`    | _(unset)_      | Require a password to connect             |

You can also run other commands in the same isolated desktop, for example a
shell or the test suite:

```bash
docker compose run --rm app bash
docker compose run --rm app pytest
```

## Option B – Dev Container / GitHub Codespaces

The repository ships a `.devcontainer/` configuration that builds the same
image. In VS Code (Dev Containers extension) or in a Codespace:

1. Open the repository in the container ("Reopen in Container" / "Create
   Codespace").
2. The desktop and application start automatically (`postStartCommand`).
3. Open the forwarded **6080** port (labelled *HeroForge Anew (noVNC desktop)*)
   to view and interact with the app in your browser.

If you stop the app and want to relaunch it inside the running container:

```bash
DISPLAY=:1 python -m heroforge
```

## Running the app without a container

The container is only required for the **isolated, browser-viewable** desktop.
On a normal desktop machine you can run the app directly:

```bash
pip install -r requirements.txt
pip install -e .
python -m heroforge
```

For headless automated tests (no display needed), Qt's offscreen platform is
used automatically by the test suite:

```bash
pip install -e ".[dev]"
pytest
```
