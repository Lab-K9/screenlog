#!/bin/bash
# ScreenLog watchdog: プロセス死活とログ鮮度を監視し、停止時は再起動して macOS 通知する。
# launchd (com.labk9.screenlog-watchdog) から30分おきに実行される想定。
# exit 0: 正常（再起動成功を含む） / exit 1: 再起動失敗（corporateos-doctor チェック1が検知する）

set -uo pipefail

APP_PATH="${SCREENLOG_APP_DEST:-$HOME/Applications/ScreenLog.app}"
LOG_DIR="$HOME/Library/Application Support/ScreenLog/logs"
WATCHDOG_LOG="$HOME/Library/Logs/ScreenLog.watchdog.log"
STATE_FILE="$HOME/Library/Application Support/ScreenLog/watchdog-state"
STALE_MINUTES=30
NOTIFY_COOLDOWN_SECONDS=21600  # 同一警告の通知は6時間に1回まで

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$WATCHDOG_LOG"
}

notify() {
    /usr/bin/osascript -e "display notification \"$1\" with title \"ScreenLog Watchdog\"" >/dev/null 2>&1 || true
}

# ログ更新停止の警告のみクールダウンをかける（wake直後の誤検知や連続通知のスパム防止）
notify_rate_limited() {
    local now last=0
    now=$(date +%s)
    [ -f "$STATE_FILE" ] && last=$(cat "$STATE_FILE" 2>/dev/null || echo 0)
    if [ $((now - last)) -ge "$NOTIFY_COOLDOWN_SECONDS" ]; then
        notify "$1"
        echo "$now" > "$STATE_FILE"
    fi
}

is_running() {
    pgrep -f "ScreenLog.app/Contents/MacOS/ScreenLog" >/dev/null 2>&1
}

is_log_stale() {
    local today_jsonl="$LOG_DIR/$(date '+%Y-%m-%d').jsonl"
    if [ ! -f "$today_jsonl" ]; then
        return 0
    fi
    [ -n "$(find "$today_jsonl" -mmin +"$STALE_MINUTES" 2>/dev/null)" ]
}

if is_running; then
    if is_log_stale; then
        # スリープ復帰直後はキャプチャ再開前にmtimeが古く見えるため、70秒待って再判定する
        sleep 70
        if is_log_stale; then
            log "WARN: process alive but today's jsonl is stale/missing (> ${STALE_MINUTES}min)"
            notify_rate_limited "ScreenLogは稼働中ですがログが${STALE_MINUTES}分以上更新されていません。画面収録権限を確認してください。"
        fi
    fi
    exit 0
fi

log "WARN: ScreenLog process not running. Restarting via open -a $APP_PATH"
/usr/bin/open -a "$APP_PATH"
sleep 10

if is_running; then
    log "INFO: restart succeeded"
    notify "ScreenLogが停止していたため自動再起動しました。"
    exit 0
fi

log "ERROR: restart failed"
notify "ScreenLogの再起動に失敗しました。手動で確認してください。"
exit 1
