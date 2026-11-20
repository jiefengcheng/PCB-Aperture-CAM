#!/bin/sh
set -eu
TASK_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$TASK_ROOT"
"$TASK_ROOT/tools/Prepare_LaCie_Workspace.command"
VIEWER_WORK="$TASK_ROOT/out/lacie_work/viewer"
VIEWER_RUN="$VIEWER_WORK/checks/$(date +%Y%m%dT%H%M%S)-$$"
mkdir -p "$VIEWER_RUN" "$VIEWER_WORK/tmp" "$VIEWER_WORK/cache"
export TMPDIR="$VIEWER_WORK/tmp"
export CLANG_MODULE_CACHE_PATH="$VIEWER_WORK/cache/clang"
export SWIFTPM_MODULECACHE_OVERRIDE="$VIEWER_WORK/cache/swift"
export SWIFT_MODULECACHE_PATH="$VIEWER_WORK/cache/swift"
export XDG_CACHE_HOME="$VIEWER_WORK/cache"
export VIEWER_TEST_ROOT="$VIEWER_RUN/native-fixtures"
"$TASK_ROOT/tools/Run_PCB_Tests.command" -q tests/test_viewer_abi.py > "$VIEWER_RUN/publisher.log" 2>&1 || { cat "$VIEWER_RUN/publisher.log"; exit 1; }
swift test --package-path "$TASK_ROOT/viewer" --scratch-path "$VIEWER_WORK/build" --cache-path "$VIEWER_WORK/cache/swiftpm" --config-path "$VIEWER_WORK/config" --security-path "$VIEWER_WORK/security" --disable-sandbox > "$VIEWER_RUN/native.log" 2>&1 || { cat "$VIEWER_RUN/native.log"; exit 1; }
printf 'Viewer checks passed. Retained logs: %s\n' "$VIEWER_RUN"
