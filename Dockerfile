# Isolated runtime image for HeroForge Anew.
#
# Builds a self-contained container that can run the PyQt application headless
# and expose it for viewing/interactivity over noVNC (browser) or VNC. This is
# used both by docker-compose (local QA) and by the dev container / Codespaces.
FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    QT_QPA_PLATFORM=xcb \
    DISPLAY=:1

# System packages:
#   - Qt6 / PyQt6 runtime libraries (xcb, opengl, dbus, fontconfig, ...)
#   - the virtual desktop stack (Xvfb, fluxbox, x11vnc, novnc, websockify)
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        xvfb \
        x11vnc \
        x11-utils \
        fluxbox \
        novnc \
        websockify \
        libgl1 \
        libegl1 \
        libdbus-1-3 \
        libxkbcommon0 \
        libxkbcommon-x11-0 \
        libfontconfig1 \
        libfreetype6 \
        libglib2.0-0 \
        libxcb-cursor0 \
        libxcb-icccm4 \
        libxcb-image0 \
        libxcb-keysyms1 \
        libxcb-randr0 \
        libxcb-render-util0 \
        libxcb-shape0 \
        libxcb-xinerama0 \
        libxcb-xfixes0 \
        libxrender1 \
        libxi6 \
    && rm -rf /var/lib/apt/lists/*

# noVNC ships vnc.html; also expose it at index.html for convenience.
RUN if [ -f /usr/share/novnc/vnc.html ] && [ ! -f /usr/share/novnc/index.html ]; then \
        ln -s /usr/share/novnc/vnc.html /usr/share/novnc/index.html; \
    fi

WORKDIR /app

# Install Python dependencies first to leverage Docker layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install the application package.
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -e .

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# noVNC web UI (browser) and raw VNC.
EXPOSE 6080 5900

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
