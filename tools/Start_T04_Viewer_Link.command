#!/bin/sh
set -eu
TASK_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$TASK_ROOT"
"$TASK_ROOT/tools/Prepare_LaCie_Workspace.command"
VIEWER_LINK="$TASK_ROOT/out/lacie_work/viewer/t04_live"
"$TASK_ROOT/.venv/bin/python" -B "$TASK_ROOT/tools/viewer_live.py" --connection "$VIEWER_LINK" start
exec "$TASK_ROOT/tools/Start_Gerber_Viewer.command" --workspace "$VIEWER_LINK/session" --live "$@"
