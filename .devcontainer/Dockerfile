# syntax=docker/dockerfile:1
#
# Development container image for HeroForge-Anew.
#
# This is the image GitHub Codespaces / VS Code Dev Containers build from
# devcontainer.json. It is for *developing* the project — editing, linting,
# type-checking and running the (offscreen-capable) test suite — and is distinct
# from the root Dockerfile, which exists to *run* the GUI for QA.
#
# It layers the Qt runtime libraries on top of the official devcontainers Python
# image so that `pytest` can import PyQt6 for real (instead of skipping the
# widget tests). The viewable QA desktop now lives entirely in the Compose
# `display` sidecar, so no X11 client utilities (xhost) are needed here.

# Pinned to a specific digest for reproducible, tamper-evident builds. The
# human-readable tag (3-3.12-bookworm) is kept alongside the digest for clarity;
# the @sha256 is what Docker actually resolves. Available tags/digests are listed
# at https://mcr.microsoft.com/en-us/artifact/mar/devcontainers/python/tags —
# update both the tag and the digest together when bumping the base image.
FROM mcr.microsoft.com/devcontainers/python:3-3.12-bookworm@sha256:4ace5266fed54e0e440d7b5142008684e305e5d456c8136f1bae5742139a95dc

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
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
