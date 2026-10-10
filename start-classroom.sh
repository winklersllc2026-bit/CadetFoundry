#!/bin/sh
# Start class on Linux / Raspberry Pi / macOS: Cadets join from phones on the same Wi-Fi. Needs Python 3.10+.
cd "$(dirname "$0")" && exec python3 run.py --lan "$@"
