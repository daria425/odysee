#!/usr/bin/env bash
set -euo pipefail

DOCKER_DESKTOP_EXE="/mnt/c/Program Files/Docker/Docker/Docker Desktop.exe"

if ! docker info >/dev/null 2>&1; then
    if [ -f "$DOCKER_DESKTOP_EXE" ]; then
        echo "Docker daemon not running — starting Docker Desktop..."
        "$DOCKER_DESKTOP_EXE" &
        disown
    fi

    echo "Waiting for Docker daemon..."
    until docker info >/dev/null 2>&1; do
        sleep 2
    done
fi

docker compose up --build
