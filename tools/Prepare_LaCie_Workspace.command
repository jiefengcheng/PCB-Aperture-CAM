#!/bin/sh
set -eu
TASK_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec "$TASK_ROOT/.venv/bin/python" -B "$TASK_ROOT/tools/pcb_workspace.py"
