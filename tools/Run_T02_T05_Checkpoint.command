#!/bin/sh
set -eu
TASK_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$TASK_ROOT"
"$TASK_ROOT/tools/Prepare_LaCie_Workspace.command"
exec "$TASK_ROOT/.venv/bin/python" -B "$TASK_ROOT/tools/t02_t05_checkpoint.py" "$@"
