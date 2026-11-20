#!/bin/sh
set -eu
TASK_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$TASK_ROOT"
"$TASK_ROOT/tools/Prepare_LaCie_Workspace.command"
VIEWER_WORK="$TASK_ROOT/out/lacie_work/viewer"
mkdir -p "$VIEWER_WORK/build" "$VIEWER_WORK/cache" "$VIEWER_WORK/tmp" "$VIEWER_WORK/session/tmp"
export TMPDIR="$VIEWER_WORK/tmp"
export CLANG_MODULE_CACHE_PATH="$VIEWER_WORK/cache/clang"
export SWIFTPM_MODULECACHE_OVERRIDE="$VIEWER_WORK/cache/swift"
export SWIFT_MODULECACHE_PATH="$VIEWER_WORK/cache/swift"
export XDG_CACHE_HOME="$VIEWER_WORK/cache"
VIEWER_BUILD_LOG="$VIEWER_WORK/build-$(date +%Y%m%dT%H%M%S)-$$.log"
swift build --package-path "$TASK_ROOT/viewer" --scratch-path "$VIEWER_WORK/build" --cache-path "$VIEWER_WORK/cache/swiftpm" --config-path "$VIEWER_WORK/config" --security-path "$VIEWER_WORK/security" --disable-sandbox > "$VIEWER_BUILD_LOG" 2>&1 || { cat "$VIEWER_BUILD_LOG"; exit 1; }
VIEWER_BIN=$(swift build --package-path "$TASK_ROOT/viewer" --scratch-path "$VIEWER_WORK/build" --cache-path "$VIEWER_WORK/cache/swiftpm" --config-path "$VIEWER_WORK/config" --security-path "$VIEWER_WORK/security" --show-bin-path)
VIEWER_APP="$VIEWER_WORK/Gerber Viewer.app"
mkdir -p "$VIEWER_APP/Contents/MacOS" "$VIEWER_APP/Contents/Resources"
cp "$VIEWER_BIN/GerberViewer" "$VIEWER_APP/Contents/MacOS/GerberViewer"
cp -R "$VIEWER_BIN/GerberViewer_GerberViewer.bundle" "$VIEWER_APP/Contents/Resources/"
cat > "$VIEWER_APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleIdentifier</key><string>local.pcbcam.gerberviewer</string>
<key>CFBundleName</key><string>Gerber Viewer</string>
<key>CFBundleExecutable</key><string>GerberViewer</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleVersion</key><string>1</string>
<key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST
"$TASK_ROOT/.venv/bin/python" -B - "$VIEWER_APP/Contents/Info.plist" "$VIEWER_WORK/session" "$TASK_ROOT" <<'PYCONFIG'
import plistlib, sys
from pathlib import Path
p = Path(sys.argv[1]); info = plistlib.loads(p.read_bytes())
info.update(ViewerWorkspace=sys.argv[2], ViewerRepository=sys.argv[3])
p.write_bytes(plistlib.dumps(info))
PYCONFIG
codesign --force --deep --sign - "$VIEWER_APP" > "$VIEWER_WORK/codesign-$(date +%Y%m%dT%H%M%S)-$$.log" 2>&1
open -n "$VIEWER_APP" --args --workspace "$VIEWER_WORK/session" --repository "$TASK_ROOT" "$@"
printf 'Viewer workspace: %s\n' "$VIEWER_WORK/session"
