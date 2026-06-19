#!/usr/bin/env python3
"""ScreenLog - メインエントリーポイント"""

import gc
import signal
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

# launchdからの実行時に出力をバッファリングしないようにする
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from .logger import (
    write_log_entry,
    write_log_entries,
    cleanup_old_logs,
    LogEntry
)
from .config import (
    save_config,
    MIN_INTERVAL,
    validate_interval,
    validate_retention_days,
)
from .recorder import CaptureCycleResult, process_capture
from .runtime import load_runtime_settings
from .capture import cleanup_tmp_screenshots


# グローバルな停止フラグ
running = True


def signal_handler(signum, frame):
    """シグナルハンドラ（SIGINT, SIGTERM）"""
    global running
    print("\nStopping ScreenLog...")
    running = False


def process_single_capture(
    previous_entry: LogEntry | None = None,
    *,
    flush_interval_seconds: int = 300,
) -> tuple[LogEntry | None, LogEntry | None]:
    """
    1回のキャプチャ処理を実行

    Args:
        previous_entry: 前回のログエントリ（まだファイルに書き込んでいないもの）

    Returns:
        tuple[LogEntry | None, LogEntry | None]: (書き込むべきエントリ, 現在のエントリ)
            - 書き込むべきエントリ: OCRテキストが変わった場合は前回のエントリ、変わってない場合はNone
            - 現在のエントリ: 今回のキャプチャで作成または更新されたエントリ
    """
    result = process_capture(
        previous_entry=previous_entry,
        flush_interval_seconds=flush_interval_seconds,
    )
    _print_capture_result(result)
    return (result.to_write, result.current_entry)


def _print_capture_result(result: CaptureCycleResult) -> None:
    """CLI向けに1回のキャプチャ結果を短く出力する。"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = result.current_entry
    if entry is None:
        print(f"[{timestamp}] {result.reason}: {result.message}")
        return

    app = entry.get("working_app", entry.get("active_app", "Unknown"))
    title = str(entry.get("working_title", entry.get("window_title", "Unknown")))
    status = entry.get("capture_status", "ok")
    snapshots = entry.get("snapshot_count", 1)
    print(
        f"[{timestamp}] ({result.reason}) {app} - {title[:30]}... "
        f"status={status} snapshots={snapshots}"
    )


def run_loop(interval: int, retention_days: int, flush_interval_seconds: int):
    """
    メインループを実行

    Args:
        interval: キャプチャ間隔（秒）
        retention_days: ログ保持日数
    """
    global running

    print(f"ScreenLog started. Capturing every {interval} seconds.")
    print(f"Log retention: {retention_days} days")
    print(f"Flush interval: {flush_interval_seconds} seconds")
    print(f"Logs will be saved to: {Path.home() / 'Library' / 'Application Support' / 'ScreenLog' / 'logs'}")
    print("-" * 60)

    # 起動時に古いログをクリーンアップ
    deleted = cleanup_old_logs(days=retention_days)
    if deleted > 0:
        print(f"Cleaned up {deleted} old log file(s)")
    deleted_tmp = cleanup_tmp_screenshots()
    if deleted_tmp > 0:
        print(f"Cleaned up {deleted_tmp} old temporary screenshot(s)")

    # 前回のログエントリを保持（まだファイルに書き込んでいないもの）
    current_entry: LogEntry | None = None
    pending_entries: list[LogEntry] = []
    current_date = datetime.now().date()

    # GC実行カウンター（10回ごとにフルGCを実行）
    capture_count = 0
    GC_INTERVAL = 10

    while running:
        try:
            # 日付が変わったかチェック
            now = datetime.now()
            if now.date() != current_date:
                # 日付が変わった場合は前回のエントリを書き込む
                if current_entry is not None:
                    pending_entries.append(current_entry)
                    pending_entries = write_log_entries(pending_entries)
                    if pending_entries:
                        print(f"[{now.strftime('%H:%M:%S')}] Date changed - failed to write pending entry")
                    else:
                        print(f"[{now.strftime('%H:%M:%S')}] Date changed - wrote final entry to previous day's log")
                current_entry = None
                current_date = now.date()

            # キャプチャ処理
            to_write, new_entry = process_single_capture(
                current_entry,
                flush_interval_seconds=flush_interval_seconds,
            )

            # OCRテキストが変わった場合は前回のエントリを書き込む
            if to_write is not None:
                pending_entries.append(to_write)

            if pending_entries:
                pending_entries = write_log_entries(pending_entries)
                if pending_entries:
                    print(f"[{now.strftime('%H:%M:%S')}] Failed to write pending log entry")

            # 現在のエントリを更新
            current_entry = new_entry

            # 定期的にGCを実行してメモリを解放
            capture_count += 1
            if capture_count >= GC_INTERVAL:
                gc.collect()
                capture_count = 0

            # 次のキャプチャまで待機（1秒ずつ確認して停止フラグをチェック）
            for _ in range(interval):
                if not running:
                    break
                time.sleep(1)

        except Exception as e:
            print(f"Error in main loop: {e}")
            # エラーが発生しても継続
            time.sleep(interval)

    # 停止時に最後のエントリを書き込む
    if current_entry is not None:
        pending_entries.append(current_entry)
        current_entry = None

    if pending_entries:
        pending_entries = write_log_entries(pending_entries)
        if pending_entries:
            print(f"Failed to write {len(pending_entries)} pending log entry/entries before stopping.")
        else:
            print("Wrote final log entry before stopping.")

    # 最終GC
    gc.collect()
    print("ScreenLog stopped.")


def main():
    """メインエントリーポイント"""
    # 設定ファイルからデフォルト値を読み込む
    settings = load_runtime_settings()

    parser = argparse.ArgumentParser(
        description="ScreenLog - 作業ログ自動生成ツール"
    )
    parser.add_argument(
        "-i", "--interval",
        type=int,
        default=settings.interval,
        help=f"キャプチャ間隔（秒）。最小: {MIN_INTERVAL}秒。デフォルト: %(default)s"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="1回だけキャプチャして終了"
    )
    parser.add_argument(
        "-r", "--retention",
        type=int,
        default=settings.retention_days,
        help="ログ保持日数。デフォルト: %(default)s"
    )
    parser.add_argument(
        "--flush-interval",
        type=int,
        default=settings.flush_interval,
        help=f"同一画面継続時にログを分割保存する間隔（秒）。最小: {MIN_INTERVAL}秒。デフォルト: %(default)s"
    )
    parser.add_argument(
        "--save-config",
        action="store_true",
        help="現在のオプションを設定ファイルに保存して終了"
    )

    args = parser.parse_args()

    # 間隔のバリデーション
    try:
        validate_interval(args.interval)
        validate_interval(args.flush_interval)
        validate_retention_days(args.retention)
    except ValueError as e:
        parser.error(str(e))

    # 設定保存モード
    if args.save_config:
        new_config = {
            "interval": args.interval,
            "retention_days": args.retention,
            "flush_interval": args.flush_interval,
        }
        if save_config(new_config):
            print(f"設定を保存しました: {new_config}")
        else:
            print("設定の保存に失敗しました")
            sys.exit(1)
        sys.exit(0)

    # シグナルハンドラを設定
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if args.once:
        # 1回だけ実行
        to_write, current_entry = process_single_capture(
            flush_interval_seconds=args.flush_interval,
        )
        # 即座にエントリを書き込む
        if current_entry is not None:
            success = write_log_entry(current_entry)
            sys.exit(0 if success else 1)
        else:
            sys.exit(1)
    else:
        # ループ実行
        run_loop(
            interval=args.interval,
            retention_days=args.retention,
            flush_interval_seconds=args.flush_interval,
        )


if __name__ == "__main__":
    main()
