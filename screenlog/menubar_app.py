"""ScreenLog - メニューバーアプリ"""

import gc
import rumps
import threading
import time
from datetime import datetime
from pathlib import Path

from .logger import (
    write_log_entries,
    cleanup_old_logs,
    LogEntry
)
from .permissions import ensure_screen_recording_access
from .recorder import process_capture
from .runtime import load_runtime_settings
from .capture import cleanup_tmp_screenshots


class ScreenLogApp(rumps.App):
    def __init__(self):
        super().__init__(
            name="ScreenLog",
            title="📷",
            icon=None,
            quit_button=None
        )

        # 設定
        settings = load_runtime_settings()
        self.interval = settings.interval
        self.retention_days = settings.retention_days
        self.flush_interval = settings.flush_interval
        self.idle_threshold_seconds = settings.idle_threshold_seconds
        self.enabled = True
        self.running = True

        # 状態
        self.current_entry: LogEntry | None = None
        self.pending_entries: list[LogEntry] = []
        self.current_date = datetime.now().date()
        self.last_capture_time: datetime | None = None
        self.screen_recording_allowed: bool | None = None
        self.today_capture_count = 0
        self.capture_thread: threading.Thread | None = None
        self.state_lock = threading.RLock()

        # メニュー構築
        self.build_menu()
        self.check_screen_recording_permission(None, notify_allowed=False)

        # 起動時に古いログをクリーンアップ
        deleted = cleanup_old_logs(days=self.retention_days)
        if deleted > 0:
            print(f"Cleaned up {deleted} old log file(s)")
        deleted_tmp = cleanup_tmp_screenshots()
        if deleted_tmp > 0:
            print(f"Cleaned up {deleted_tmp} old temporary screenshot(s)")

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

        # 画面収録権限
        self.menu.add(rumps.MenuItem("画面収録の許可を確認", callback=self.check_screen_recording_permission))

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
        with self.get_state_lock():
            enabled = self.enabled
            last_capture_time = self.last_capture_time
            today_capture_count = self.today_capture_count

        status_text = "記録中" if enabled else "停止中"
        self.status_item.title = f"状態: {status_text}"

        if last_capture_time:
            time_str = last_capture_time.strftime('%H:%M:%S')
            self.last_capture_item.title = f"最終: {time_str}"

        self.count_item.title = f"今日: {today_capture_count}件"
        self.update_icon()

    def toggle_enabled(self, _):
        """有効/無効を切り替え"""
        with self.get_state_lock():
            was_enabled = self.enabled
            self.enabled = not self.enabled
        if was_enabled and not self.enabled:
            self.flush_current_entry()
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

    def check_screen_recording_permission(self, _, *, notify_allowed: bool = True):
        """Screen Recording permission check/request entry point."""
        result = ensure_screen_recording_access()
        self.screen_recording_allowed = result.allowed

        if result.allowed is True:
            if notify_allowed:
                rumps.notification(
                    title="ScreenLog",
                    subtitle="画面収録は許可されています",
                    message="",
                    sound=False,
                )
            return

        if result.requested:
            message = "システム設定でScreenLogを許可してから、ScreenLogを再起動してください"
        else:
            message = "画面収録の許可状態を確認できませんでした"

        rumps.notification(
            title="ScreenLog",
            subtitle="画面収録の許可が必要です",
            message=message,
            sound=False,
        )

    def get_state_lock(self) -> threading.RLock:
        """状態更新用ロックを返す。テスト用の未初期化インスタンスにも対応する。"""
        if not hasattr(self, "state_lock"):
            self.state_lock = threading.RLock()
        return self.state_lock

    def flush_pending_entries(self) -> None:
        """保存待ちエントリを順に書き込み、失敗分はpendingとして保持する。"""
        if self.pending_entries:
            self.pending_entries = write_log_entries(self.pending_entries)

    def flush_current_entry(self) -> None:
        """現在の未保存エントリを保存待ちに移してflushする。"""
        with self.get_state_lock():
            if self.current_entry is not None:
                self.pending_entries.append(self.current_entry)
                self.current_entry = None
            self.flush_pending_entries()

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
                with self.get_state_lock():
                    enabled = self.enabled
                if not enabled:
                    time.sleep(1)
                    continue

                with self.get_state_lock():
                    # 日付が変わったかチェック
                    now = datetime.now()
                    if now.date() != self.current_date:
                        if self.current_entry is not None:
                            self.pending_entries.append(self.current_entry)
                        self.current_entry = None
                        self.current_date = now.date()
                        self.today_capture_count = 0
                        self.flush_pending_entries()

                    # キャプチャ処理
                    result = process_capture(
                        previous_entry=self.current_entry,
                        flush_interval_seconds=self.flush_interval,
                        idle_threshold_seconds=self.idle_threshold_seconds,
                    )

                    if result.to_write is not None:
                        self.pending_entries.append(result.to_write)

                    before_pending_count = len(self.pending_entries)
                    self.flush_pending_entries()
                    self.today_capture_count += max(0, before_pending_count - len(self.pending_entries))

                    self.current_entry = result.current_entry
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
        self.flush_current_entry()

    def quit_app(self, _):
        """アプリを終了"""
        with self.get_state_lock():
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
