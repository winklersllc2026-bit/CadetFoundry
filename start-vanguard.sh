#!/bin/sh
# Start Cadet Foundry on Linux / Raspberry Pi / macOS. Needs Python 3.10+.
cd "$(dirname "$0")" && exec python3 run.py "$@"
