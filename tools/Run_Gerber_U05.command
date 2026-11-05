#!/bin/sh
set -eu
TASK_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$TASK_ROOT"
"$TASK_ROOT/tools/Prepare_LaCie_Workspace.command"
exec "$TASK_ROOT/.venv/bin/python" -B -m src.gerber_u05.run "$@"
