# syntax=docker/dockerfile:1
#
# Development container image for HeroForge-Anew.
#
# This is the image GitHub Codespaces / VS Code Dev Containers build from
# devcontainer.json. It is for *developing* the project — editing, linting,
# type-checking and running the (offscreen-capable) test suite — and is distinct
# from the root Dockerfile, which exists to *run* the GUI for QA.
#
# It layers the Qt runtime libraries and a couple of X11 client utilities on top
# of the official devcontainers Python image so that:
#   * `pytest` can import PyQt6 for real (instead of skipping the widget tests),
#   * `xhost` is available to grant the QA container access to the X server.

FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

RUN apt-get update \
    && export DEBIAN_FRONTEND=noninteractive \
    && apt-get install --no-install-recommends -y \
        libgl1 \
        libegl1 \
        libglib2.0-0 \
        libdbus-1-3 \
        libfontconfig1 \
        libfreetype6 \
        libx11-6 \
        libx11-xcb1 \
        libxcb1 \
        libxcb-cursor0 \
        libxcb-glx0 \
        libxcb-icccm4 \
        libxcb-image0 \
        libxcb-keysyms1 \
        libxcb-randr0 \
        libxcb-render0 \
        libxcb-render-util0 \
        libxcb-shape0 \
        libxcb-shm0 \
        libxcb-sync1 \
        libxcb-util1 \
        libxcb-xfixes0 \
        libxcb-xinerama0 \
        libxcb-xkb1 \
        libxkbcommon0 \
        libxkbcommon-x11-0 \
        libxext6 \
        libxrender1 \
        libsm6 \
        libice6 \
        x11-utils \
        x11-xserver-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
