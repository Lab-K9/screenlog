#!/bin/bash
# Install ScreenLog watchdog LaunchAgent (com.labk9.screenlog-watchdog).
# 30分おきに watchdog.sh を実行し、ScreenLog の停止を検知して自動再起動・通知する。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WATCHDOG_SH="$SCRIPT_DIR/watchdog.sh"
LABEL="com.labk9.screenlog-watchdog"
PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ ! -f "$WATCHDOG_SH" ]; then
    echo "watchdog.sh not found: $WATCHDOG_SH"
    exit 1
fi

chmod +x "$WATCHDOG_SH"

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key>
	<string>$LABEL</string>
	<key>ProgramArguments</key>
	<array>
		<string>/bin/bash</string>
		<string>$WATCHDOG_SH</string>
	</array>
	<key>RunAtLoad</key>
	<true/>
	<key>StartInterval</key>
	<integer>1800</integer>
	<key>StandardOutPath</key>
	<string>$HOME/Library/Logs/ScreenLog.watchdog.launchd.log</string>
	<key>StandardErrorPath</key>
	<string>$HOME/Library/Logs/ScreenLog.watchdog.launchd.err.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$UID" "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID" "$PLIST_PATH"
launchctl enable "gui/$UID/$LABEL"

echo "Installed watchdog LaunchAgent: $PLIST_PATH"
