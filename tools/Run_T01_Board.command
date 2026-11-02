#!/bin/sh
# One native Terminal command. No daemon, MCP, model or global configuration.
set -eu
TASK_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec "$TASK_ROOT/.venv/bin/python" -B "$TASK_ROOT/tools/pcb_workspace.py" "$TASK_ROOT/.venv/bin/python" -B "$TASK_ROOT/tools/pcb_t01_board_run.py" "$@"
