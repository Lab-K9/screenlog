#!/bin/bash
# Uninstall ScreenLog watchdog LaunchAgent (com.labk9.screenlog-watchdog).

set -euo pipefail

LABEL="com.labk9.screenlog-watchdog"
PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$UID" "$PLIST_PATH" >/dev/null 2>&1 || true
rm -f "$PLIST_PATH"

echo "Uninstalled watchdog LaunchAgent: $PLIST_PATH"
