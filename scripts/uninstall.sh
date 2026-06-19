#!/bin/bash
# ScreenLog アンインストールスクリプト

echo "=== ScreenLog Uninstaller ==="
echo ""

for PLIST_NAME in "com.screenlog.app.plist" "com.screenlog.agent.plist"; do
    PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME"
    if [ -f "$PLIST_DST" ]; then
        echo "Stopping ScreenLog agent: $PLIST_NAME"
        launchctl bootout "gui/$UID" "$PLIST_DST" 2>/dev/null || true
        launchctl unload "$PLIST_DST" 2>/dev/null || true
        rm "$PLIST_DST"
        echo "Agent removed."
    else
        echo "Agent not installed: $PLIST_NAME"
    fi
done

echo ""
echo "=== Uninstallation Complete ==="
echo ""
echo "Note: activity logs are preserved at $HOME/Library/Application Support/ScreenLog/logs/"
echo "Process logs and PID files may remain at $HOME/ScreenLog/"
