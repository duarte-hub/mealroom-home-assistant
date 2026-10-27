#!/bin/sh
set -eu
mkdir -p "${DATA_DIR:-/data}"
# The Supervisor mounts persistent app data as root. The server runs unprivileged.
if [ "$(id -u)" = "0" ]; then
    chown -R mealroom:mealroom "${DATA_DIR:-/data}"
    exec su-exec mealroom:mealroom python /app/run.py
fi
exec python /app/run.py
