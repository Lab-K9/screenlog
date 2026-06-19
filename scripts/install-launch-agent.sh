#!/bin/bash
# Install ScreenLog LaunchAgent for login startup.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON_BIN="$PROJECT_DIR/venv/bin/python"
APP_PATH="${SCREENLOG_APP_DEST:-$HOME/Applications/ScreenLog.app}"
PLIST_PATH="$HOME/Library/LaunchAgents/com.screenlog.app.plist"

cd "$PROJECT_DIR"

if [ ! -x "$PYTHON_BIN" ]; then
    echo "Python venv not found: $PYTHON_BIN"
    exit 1
fi

if [ ! -d "$APP_PATH" ]; then
    echo "ScreenLog.app not found: $APP_PATH"
    echo "Run ./scripts/install-local-app.sh first."
    exit 1
fi

"$PYTHON_BIN" -m screenlog.launch_agent install --app-path "$APP_PATH" --plist-path "$PLIST_PATH"
launchctl bootout "gui/$UID" "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID" "$PLIST_PATH"
launchctl enable "gui/$UID/com.screenlog.app"

echo "Installed LaunchAgent: $PLIST_PATH"
