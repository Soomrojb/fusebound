#!/usr/bin/env bash
# Launch Fusebound (sets up a local virtualenv with pygame-ce on first run).
set -e
cd "$(dirname "$(readlink -f "$0")")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
exec .venv/bin/python -m fusebound "$@"
