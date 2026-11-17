#!/usr/bin/env bash
# Throwaway Home Assistant in Podman to test the integration.   Usage: dev/ha.sh [up|setup|restart|down|logs|reset]
# Published on 127.0.0.1 only: the dev user is dev/dev, so it must not be reachable from the network.
# The integration folder is bind-mounted, so Python changes need `dev/ha.sh restart` (no rebuild).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
DOMAIN="$(basename "$(find "$ROOT/custom_components" -mindepth 1 -maxdepth 1 -type d ! -name __pycache__ | head -n1)")"
NAME="${DOMAIN//_/-}-dev-ha"
IMAGE="${HA_IMAGE:-ghcr.io/home-assistant/home-assistant:stable}"
PORT="${HA_PORT:-8123}"

up() {
  if podman container exists "$NAME"; then
    podman start "$NAME" >/dev/null
  else
    mkdir -p "$HERE/config"
    podman run -d --name "$NAME" \
      -e TZ=Europe/Madrid \
      -p "127.0.0.1:$PORT:8123" \
      -v "$HERE/config:/config:z" \
      -v "$ROOT/custom_components/$DOMAIN:/config/custom_components/$DOMAIN:ro,z" \
      "$IMAGE" >/dev/null
  fi
  echo "Home Assistant starting on http://localhost:$PORT (first boot takes a minute)…"
  node "$HERE/setup.mjs" "http://localhost:$PORT" "$DOMAIN"
}

case "${1:-up}" in
  up)      up ;;
  setup)   node "$HERE/setup.mjs" "http://localhost:$PORT" "$DOMAIN" ;;
  restart) podman restart "$NAME" >/dev/null && node "$HERE/setup.mjs" "http://localhost:$PORT" "$DOMAIN" ;;
  down)    podman rm -f "$NAME" >/dev/null && echo "Stopped (state kept in dev/config)." ;;
  logs)    podman logs -f "$NAME" ;;
  reset)   podman rm -f "$NAME" >/dev/null 2>&1 || true
           find "$HERE/config" -mindepth 1 -maxdepth 1 ! -name configuration.yaml -exec rm -rf {} +
           echo "Dev Home Assistant state wiped." ;;
  *)       echo "usage: $0 [up|setup|restart|down|logs|reset]" >&2; exit 1 ;;
esac
