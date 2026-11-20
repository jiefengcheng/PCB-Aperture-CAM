#!/bin/sh
set -eu
TASK_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$TASK_ROOT"
"$TASK_ROOT/tools/Prepare_LaCie_Workspace.command"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONSAFEPATH=1
export PYTHONPATH="$TASK_ROOT"
exec "$TASK_ROOT/.venv/bin/python" -B -m src.gerber_u05.profile_job "$@"
