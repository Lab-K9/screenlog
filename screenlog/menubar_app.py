"""ScreenLog - メニューバーアプリ"""

import gc
import rumps
import threading
import time
from datetime import datetime
from pathlib import Path

from .capture import take_screenshot, delete_screenshot
from .window import get_active_window_info, get_active_window_id
from .ocr import extract_text
from .logger import (
    create_log_entry,
    update_log_entry,
    write_log_entry,
    cleanup_old_logs,
    LogEntry
)


class ScreenLogApp(rumps.App):
    def __init__(self):
        super().__init__(
            name="ScreenLog",
            title="📷",
            icon=None,
            quit_button=None
        )

        # 設定
        self.interval = 60  # キャプチャ間隔（秒）
        self.retention_days = 30  # ログ保持日数
        self.enabled = True
        self.running = True

        # 状態
        self.current_entry: LogEntry | None = None
        self.current_date = datetime.now().date()
        self.last_capture_time: datetime | None = None
        self.today_capture_count = 0
        self.capture_thread: threading.Thread | None = None

        # メニュー構築
        self.build_menu()

        # 起動時に古いログをクリーンアップ
        deleted = cleanup_old_logs(days=self.retention_days)
        if deleted > 0:
            print(f"Cleaned up {deleted} old log file(s)")

        # キャプチャスレッド開始
        self.start_capture_thread()

        # ステータス更新タイマー（10秒ごと）
        self.status_timer = rumps.Timer(self.update_status, 10)
        self.status_timer.start()

    def build_menu(self):
        """メニューを構築"""
        self.menu.clear()

        # ステータス表示
        status_text = "記録中" if self.enabled else "停止中"
        self.status_item = rumps.MenuItem(f"状態: {status_text}", callback=None)
        self.menu.add(self.status_item)

        # 最終キャプチャ時刻
        if self.last_capture_time:
            time_str = self.last_capture_time.strftime('%H:%M:%S')
            self.last_capture_item = rumps.MenuItem(f"最終: {time_str}", callback=None)
        else:
            self.last_capture_item = rumps.MenuItem("最終: -", callback=None)
        self.menu.add(self.last_capture_item)

        # 今日のキャプチャ数
        self.count_item = rumps.MenuItem(f"今日: {self.today_capture_count}件", callback=None)
        self.menu.add(self.count_item)

        self.menu.add(rumps.separator)

        # 有効/無効トグル
        toggle_text = "⏸ 一時停止" if self.enabled else "▶ 再開"
        self.menu.add(rumps.MenuItem(toggle_text, callback=self.toggle_enabled))

        self.menu.add(rumps.separator)

        # ログフォルダを開く
        self.menu.add(rumps.MenuItem("ログフォルダを開く", callback=self.open_log_folder))

        self.menu.add(rumps.separator)

        # 終了
        self.menu.add(rumps.MenuItem("終了", callback=self.quit_app))

        # アイコン更新
        self.update_icon()

    def update_icon(self):
        """状態に応じてアイコンを更新"""
        if not self.enabled:
            self.title = "⏸️"
        else:
            self.title = "📷"

    def update_status(self, _):
        """ステータス表示を更新"""
        status_text = "記録中" if self.enabled else "停止中"
        self.status_item.title = f"状態: {status_text}"

        if self.last_capture_time:
            time_str = self.last_capture_time.strftime('%H:%M:%S')
            self.last_capture_item.title = f"最終: {time_str}"

        self.count_item.title = f"今日: {self.today_capture_count}件"
        self.update_icon()

    def toggle_enabled(self, _):
        """有効/無効を切り替え"""
        self.enabled = not self.enabled
        self.build_menu()

        if self.enabled:
            rumps.notification(
                title="ScreenLog",
                subtitle="記録を再開しました",
                message="",
                sound=False
            )
        else:
            rumps.notification(
                title="ScreenLog",
                subtitle="記録を一時停止しました",
                message="",
                sound=False
            )

    def open_log_folder(self, _):
        """ログフォルダをFinderで開く"""
        import subprocess
        log_dir = Path.home() / "Library" / "Application Support" / "ScreenLog" / "logs"
        subprocess.run(["open", str(log_dir)])

    def start_capture_thread(self):
        """キャプチャスレッドを開始"""
        self.capture_thread = threading.Thread(target=self.capture_loop, daemon=True)
        self.capture_thread.start()

    def capture_loop(self):
        """バックグラウンドでキャプチャを実行するループ"""
        capture_count = 0
        GC_INTERVAL = 10

        while self.running:
            try:
                # 無効なら待機
                if not self.enabled:
                    time.sleep(1)
                    continue

                # 日付が変わったかチェック
                now = datetime.now()
                if now.date() != self.current_date:
                    if self.current_entry is not None:
                        write_log_entry(self.current_entry)
                    self.current_entry = None
                    self.current_date = now.date()
                    self.today_capture_count = 0

                # キャプチャ処理
                to_write, new_entry = self.process_single_capture()

                if to_write is not None:
                    write_log_entry(to_write)
                    self.today_capture_count += 1

                self.current_entry = new_entry
                self.last_capture_time = now

                # 定期的にGCを実行
                capture_count += 1
                if capture_count >= GC_INTERVAL:
                    gc.collect()
                    capture_count = 0

                # 次のキャプチャまで待機
                for _ in range(self.interval):
                    if not self.running:
                        break
                    time.sleep(1)

            except Exception as e:
                print(f"Error in capture loop: {e}")
                time.sleep(self.interval)

        # 停止時に最後のエントリを書き込む
        if self.current_entry is not None:
            write_log_entry(self.current_entry)

    def process_single_capture(self) -> tuple[LogEntry | None, LogEntry | None]:
        """1回のキャプチャ処理を実行"""
        timestamp = datetime.now()

        # アクティブウィンドウのIDを取得
        window_id = get_active_window_id()

        # スクリーンショットを撮影
        screenshot_path = take_screenshot(window_id=window_id)
        if screenshot_path is None:
            return (None, self.current_entry)

        try:
            # アクティブウィンドウ情報を取得
            active_app, window_title = get_active_window_info()

            # OCR処理
            ocr_result = extract_text(screenshot_path)

            # 前回のエントリと比較
            if self.current_entry is not None and self.current_entry["ocr_text"] == ocr_result.text:
                # OCRテキストが同じ場合は既存エントリを更新
                current_entry = update_log_entry(
                    entry=self.current_entry,
                    new_timestamp=timestamp,
                    new_confidence=ocr_result.confidence
                )
                to_write = None
            else:
                # OCRテキストが変わった場合は新しいエントリを作成
                current_entry = create_log_entry(
                    active_app=active_app,
                    window_title=window_title,
                    ocr_text=ocr_result.text,
                    ocr_confidence=ocr_result.confidence,
                    timestamp=timestamp
                )
                to_write = self.current_entry

            return (to_write, current_entry)

        except Exception as e:
            print(f"Error in process_single_capture: {e}")
            return (None, self.current_entry)

        finally:
            delete_screenshot(screenshot_path)

    def quit_app(self, _):
        """アプリを終了"""
        self.running = False
        self.enabled = False

        # キャプチャスレッドが終了するのを待つ
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=5)

        rumps.quit_application()


def main():
    """アプリを起動"""
    app = ScreenLogApp()
    app.run()


if __name__ == "__main__":
    main()
