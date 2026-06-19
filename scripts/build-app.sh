#!/bin/bash
# Build ScreenLog.app and bundle PyObjCTools consistently.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON_BIN="$PROJECT_DIR/venv/bin/python"
APP_PATH="$PROJECT_DIR/dist/ScreenLog.app"

cd "$PROJECT_DIR"

if [ ! -x "$PYTHON_BIN" ]; then
    echo "Python venv not found: $PYTHON_BIN"
    echo "Run: python3 -m venv venv"
    exit 1
fi

rm -rf build dist
"$PYTHON_BIN" setup.py py2app

PY_VERSION="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
TARGET="$APP_PATH/Contents/Resources/lib/python$PY_VERSION/PyObjCTools"
SOURCE="$PROJECT_DIR/venv/lib/python$PY_VERSION/site-packages/PyObjCTools"

if [ ! -d "$SOURCE" ]; then
    echo "PyObjCTools not found: $SOURCE"
    exit 1
fi

mkdir -p "$TARGET"
cp "$SOURCE"/*.py "$TARGET/"
touch "$TARGET/__init__.py"
"$APP_PATH/Contents/MacOS/python" -m compileall -q "$TARGET"

PYTHONPATH="$APP_PATH/Contents/Resources/lib/python$PY_VERSION:$APP_PATH/Contents/Resources/lib/python$PY_VERSION/lib-dynload" \
    PYTHONDONTWRITEBYTECODE=1 \
    "$APP_PATH/Contents/MacOS/python" -c "import objc; import Vision; import Quartz; import ApplicationServices; from Foundation import NSURL; from AppKit import NSWorkspace; print('PyObjC imports ok')"

CODESIGN_IDENTITY="${SCREENLOG_CODESIGN_IDENTITY:--}"
if [ "$CODESIGN_IDENTITY" = "-" ]; then
    echo "SCREENLOG_CODESIGN_IDENTITY is not set. Re-signing with ad-hoc identity."
else
    echo "Re-signing with identity: $CODESIGN_IDENTITY"
fi
codesign --force --deep --sign "$CODESIGN_IDENTITY" "$APP_PATH"

VERIFY_ARGS=()
if [ "${SCREENLOG_REQUIRE_TEAM_ID:-}" = "1" ]; then
    VERIFY_ARGS+=(--require-team-id)
fi
if [ -n "${SCREENLOG_EXPECTED_TEAM_ID:-}" ]; then
    VERIFY_ARGS+=(--expected-team-id "$SCREENLOG_EXPECTED_TEAM_ID")
fi

if [ "${#VERIFY_ARGS[@]}" -gt 0 ]; then
    "$PYTHON_BIN" -m screenlog.bundle_verify "$APP_PATH" "${VERIFY_ARGS[@]}"
else
    "$PYTHON_BIN" -m screenlog.bundle_verify "$APP_PATH"
fi

echo "Built: $APP_PATH"
