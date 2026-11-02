#!/bin/sh
set -eu
TASK_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$TASK_ROOT"
exec "$TASK_ROOT/.venv/bin/python" -B "$TASK_ROOT/tools/pcb_workspace.py" "$TASK_ROOT/.venv/bin/python" -B -m pytest "$@"
