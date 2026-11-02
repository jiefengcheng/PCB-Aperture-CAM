#!/bin/sh
# Mount and verify the project cache volume before opening Local Code.
set -eu
TASK_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec "$TASK_ROOT/.venv/bin/python" -B "$TASK_ROOT/tools/pcb_workspace.py" /usr/bin/open -a "/Applications/Local Code.app"
