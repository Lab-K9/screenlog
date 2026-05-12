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

from .capture import take_screenshot, delete_screenshot
from .window import get_window_context
from .ocr import extract_text
from .logger import (
    create_log_entry,
    update_log_entry,
    write_log_entry,
    cleanup_old_logs,
    LogEntry
)
from .config import (
    get_config,
    save_config,
    validate_interval,
    DEFAULT_INTERVAL,
    DEFAULT_RETENTION_DAYS,
    MIN_INTERVAL,
)


# グローバルな停止フラグ
running = True


def signal_handler(signum, frame):
    """シグナルハンドラ（SIGINT, SIGTERM）"""
    global running
    print("\nStopping ScreenLog...")
    running = False


def process_single_capture(
    previous_entry: LogEntry | None = None
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
    timestamp = datetime.now()

    # 1. 作業ウィンドウの文脈を取得
    window_context = get_window_context()
    window_id = window_context.get("window_id")
    if window_id is None:
        print(
            f"[{timestamp.strftime('%H:%M:%S')}] "
            "Warning: Could not get working window ID, capturing full screen"
        )

    # 2. スクリーンショットを撮影（アクティブウィンドウのみ）
    screenshot_path = take_screenshot(window_id=window_id if isinstance(window_id, int) else None)
    if screenshot_path is None:
        print(f"[{timestamp.isoformat()}] Screenshot capture failed, skipping...")
        return (None, previous_entry)

    try:
        # 3. 作業ウィンドウ情報を取得
        active_app = str(window_context.get("working_app") or "Unknown")
        window_title = str(window_context.get("working_title") or "Unknown")

        # 4. OCR処理
        ocr_result = extract_text(screenshot_path)

        # 5. 前回のエントリと比較
        same_working_app = (
            previous_entry is not None
            and previous_entry.get("working_app", previous_entry.get("active_app")) == active_app
            and previous_entry.get("working_title", previous_entry.get("window_title")) == window_title
        )
        if (
            previous_entry is not None
            and previous_entry["ocr_text"] == ocr_result.text
            and same_working_app
        ):
            # OCRテキストが同じ場合は既存エントリを更新
            current_entry = update_log_entry(
                entry=previous_entry,
                new_timestamp=timestamp,
                new_confidence=ocr_result.confidence
            )
            to_write = None  # ファイルには書き込まない
            text_preview = ocr_result.text[:50].replace('\n', ' ') if ocr_result.text else "(empty)"
            print(f"[{timestamp.strftime('%H:%M:%S')}] (continuing) {active_app} | Snapshots: {current_entry['snapshot_count']}")
        else:
            # OCRテキストが変わった場合は新しいエントリを作成
            current_entry = create_log_entry(
                active_app=active_app,
                window_title=window_title,
                ocr_text=ocr_result.text,
                ocr_confidence=ocr_result.confidence,
                timestamp=timestamp,
                window_context=window_context,
            )
            to_write = previous_entry  # 前回のエントリをファイルに書き込む
            text_preview = ocr_result.text[:50].replace('\n', ' ') if ocr_result.text else "(empty)"
            focused_app = window_context.get("focused_app")
            focus_note = f" focused={focused_app}" if focused_app and focused_app != active_app else ""
            print(
                f"[{timestamp.strftime('%H:%M:%S')}] "
                f"(new) {active_app} - {window_title[:30]}...{focus_note} | OCR: {text_preview}..."
            )

        return (to_write, current_entry)

    except Exception as e:
        print(f"Error in process_single_capture: {e}")
        return (None, previous_entry)

    finally:
        # 6. 一時ファイルを削除
        delete_screenshot(screenshot_path)


def run_loop(interval: int = DEFAULT_INTERVAL, retention_days: int = DEFAULT_RETENTION_DAYS):
    """
    メインループを実行

    Args:
        interval: キャプチャ間隔（秒）
        retention_days: ログ保持日数
    """
    global running

    print(f"ScreenLog started. Capturing every {interval} seconds.")
    print(f"Log retention: {retention_days} days")
    print(f"Logs will be saved to: {Path.home() / 'Library' / 'Application Support' / 'ScreenLog' / 'logs'}")
    print("-" * 60)

    # 起動時に古いログをクリーンアップ
    deleted = cleanup_old_logs(days=retention_days)
    if deleted > 0:
        print(f"Cleaned up {deleted} old log file(s)")

    # 前回のログエントリを保持（まだファイルに書き込んでいないもの）
    current_entry: LogEntry | None = None
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
                    write_log_entry(current_entry)
                    print(f"[{now.strftime('%H:%M:%S')}] Date changed - wrote final entry to previous day's log")
                current_entry = None
                current_date = now.date()

            # キャプチャ処理
            to_write, new_entry = process_single_capture(current_entry)

            # OCRテキストが変わった場合は前回のエントリを書き込む
            if to_write is not None:
                success = write_log_entry(to_write)
                if not success:
                    print(f"[{now.strftime('%H:%M:%S')}] Failed to write log entry")

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
        write_log_entry(current_entry)
        print("Wrote final log entry before stopping.")

    # 最終GC
    gc.collect()
    print("ScreenLog stopped.")


def main():
    """メインエントリーポイント"""
    # 設定ファイルからデフォルト値を読み込む
    config = get_config()

    parser = argparse.ArgumentParser(
        description="ScreenLog - 作業ログ自動生成ツール"
    )
    parser.add_argument(
        "-i", "--interval",
        type=int,
        default=config.get("interval", DEFAULT_INTERVAL),
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
        default=config.get("retention_days", DEFAULT_RETENTION_DAYS),
        help="ログ保持日数。デフォルト: %(default)s"
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
    except ValueError as e:
        parser.error(str(e))

    # 設定保存モード
    if args.save_config:
        new_config = {
            "interval": args.interval,
            "retention_days": args.retention,
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
        to_write, current_entry = process_single_capture()
        # 即座にエントリを書き込む
        if current_entry is not None:
            success = write_log_entry(current_entry)
            sys.exit(0 if success else 1)
        else:
            sys.exit(1)
    else:
        # ループ実行
        run_loop(interval=args.interval, retention_days=args.retention)


if __name__ == "__main__":
    main()
