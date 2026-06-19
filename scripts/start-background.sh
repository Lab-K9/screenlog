#!/bin/bash
# ScreenLog バックグラウンド起動スクリプト
# ターミナルの画面収録権限を利用して実行
#
# Usage:
#   ./start-background.sh              # デフォルト設定で起動
#   ./start-background.sh --interval 60  # 60秒間隔で起動

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="$HOME/ScreenLog/screenlog.pid"
LOG_FILE="$HOME/ScreenLog/screenlog.log"
PYTHON_BIN="$PROJECT_DIR/venv/bin/python"

cd "$PROJECT_DIR"

# 既に実行中か確認
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "ScreenLog is already running (PID: $OLD_PID)"
        exit 1
    fi
fi

# プロセス管理用ディレクトリ作成
mkdir -p "$HOME/ScreenLog"

if [ ! -x "$PYTHON_BIN" ]; then
    echo "Python venv not found: $PYTHON_BIN"
    echo "Run: python3 -m venv venv"
    exit 1
fi

echo "Starting ScreenLog in background..."
nohup "$PYTHON_BIN" -m screenlog.main "$@" > "$LOG_FILE" 2>&1 &
PID=$!
echo $PID > "$PID_FILE"
sleep 1

if ! ps -p "$PID" > /dev/null 2>&1; then
    rm -f "$PID_FILE"
    echo "ScreenLog failed to start. Check log: $LOG_FILE"
    exit 1
fi

echo "ScreenLog started (PID: $PID)"
echo "Log file: $LOG_FILE"
echo ""
echo "Commands:"
echo "  Stop:   $SCRIPT_DIR/stop.sh"
echo "  Logs:   tail -f $LOG_FILE"
