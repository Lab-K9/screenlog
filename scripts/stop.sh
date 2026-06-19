#!/bin/bash
# ScreenLog 停止スクリプト

PID_FILE="$HOME/ScreenLog/screenlog.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Stopping ScreenLog (PID: $PID)..."
        kill -TERM "$PID"
        for _ in {1..10}; do
            if ! ps -p "$PID" > /dev/null 2>&1; then
                rm "$PID_FILE"
                echo "ScreenLog stopped."
                exit 0
            fi
            sleep 1
        done
        echo "ScreenLog did not stop within 10 seconds. PID file kept: $PID_FILE"
        exit 1
    else
        echo "ScreenLog is not running (stale PID file)."
        rm "$PID_FILE"
    fi
else
    echo "ScreenLog is not running."
fi
