#!/bin/bash
# Remove ScreenLog LaunchAgent login startup.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON_BIN="$PROJECT_DIR/venv/bin/python"
PLIST_PATH="$HOME/Library/LaunchAgents/com.screenlog.app.plist"

cd "$PROJECT_DIR"

launchctl bootout "gui/$UID" "$PLIST_PATH" >/dev/null 2>&1 || true

if [ -x "$PYTHON_BIN" ]; then
    "$PYTHON_BIN" -m screenlog.launch_agent uninstall --plist-path "$PLIST_PATH"
else
    rm -f "$PLIST_PATH"
fi

echo "Removed LaunchAgent: $PLIST_PATH"
