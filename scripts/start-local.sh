#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT/backend"
exec "$ROOT/.venv/bin/python" -m app.local "$@"
