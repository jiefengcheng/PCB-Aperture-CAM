#!/bin/sh
# Project-local native host; no install, login item, network service or MCP.
set -eu
cd "$(dirname "$0")/.."
exec .venv/bin/python -B tools/pcb_workspace.py "$PWD/.venv/bin/python" -B tools/t01_crop_launcher.py
