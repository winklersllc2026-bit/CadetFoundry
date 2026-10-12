#!/bin/sh
# One-click setup for Cadet Foundry on Linux / Raspberry Pi. Needs internet once.
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
  echo "Cadet Foundry needs Python 3.10 or newer. On Ubuntu/Debian: sudo apt install python3 python3-pip"
  exit 1
fi
exec python3 tools/setup.py "$@"
