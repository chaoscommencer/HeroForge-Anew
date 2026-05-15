FROM mcr.microsoft.com/devcontainers/python:1-3.11-bookworm

# Runtime libraries required by Qt/PyQt6 in Linux containers.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libasound2 \
        libdbus-1-3 \
        libegl1 \
        libgl1 \
        libglib2.0-0 \
        libnss3 \
        libx11-xcb1 \
        libxcb-cursor0 \
        libxcb-glx0 \
        libxcb-icccm4 \
        libxcb-image0 \
        libxcb-keysyms1 \
        libxcb-randr0 \
        libxcb-render-util0 \
        libxcb-shape0 \
        libxcb-shm0 \
        libxcb-sync1 \
        libxcb-util1 \
        libxcb-xfixes0 \
        libxcb-xinerama0 \
        libxcb-xkb1 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxkbcommon-x11-0 \
    && rm -rf /var/lib/apt/lists/*