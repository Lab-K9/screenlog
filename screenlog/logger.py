"""ログ保存モジュール"""

import json
import fcntl
from pathlib import Path
from datetime import datetime
from typing import Any, Callable, NotRequired, TypedDict

from .config import validate_retention_days

class LogEntry(TypedDict):
    """圧縮されたログエントリの型定義"""
    schema_version: NotRequired[int]
    start_time: str
    end_time: str
    duration_minutes: int
    snapshot_count: int
    active_app: str
    window_title: str
    ocr_text: str
    avg_ocr_confidence: float | None
    focused_app: NotRequired[str]
    focused_title: NotRequired[str]
    focused_bundle_id: NotRequired[str | None]
    focused_pid: NotRequired[int | None]
    working_app: NotRequired[str]
    working_title: NotRequired[str]
    working_bundle_id: NotRequired[str | None]
    window_id: NotRequired[int | None]
    capture_mode: NotRequired[str]
    selection_reason: NotRequired[str]
    capture_status: NotRequired[str]
    capture_error: NotRequired[str | None]
    ocr_length: NotRequired[int]
    is_suspicious: NotRequired[bool]
    screen_recording_allowed: NotRequired[bool | None]
    top_windows: NotRequired[list[dict[str, Any]]]
    idle: NotRequired[bool]


def get_log_dir() -> Path:
    """ログディレクトリを取得"""
    # macOS標準のApplication Supportディレクトリを使用
    log_dir = Path.home() / "Library" / "Application Support" / "ScreenLog" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_log_file_path(date: datetime | None = None) -> Path:
    """
    ログファイルのパスを取得

    Args:
        date: 対象日付。Noneの場合は今日

    Returns:
        Path: ログファイルのパス
    """
    if date is None:
        date = datetime.now()

    filename = date.strftime("%Y-%m-%d") + ".jsonl"
    return get_log_dir() / filename


def _entry_log_datetime(entry: LogEntry) -> datetime:
    """ログ保存先の日付に使う時刻をエントリから取得する。"""
    try:
        return datetime.fromisoformat(str(entry["start_time"]))
    except (KeyError, TypeError, ValueError):
        return datetime.now().astimezone()


def create_log_entry(
    active_app: str,
    window_title: str,
    ocr_text: str,
    ocr_confidence: float | None = None,
    timestamp: datetime | None = None,
    window_context: dict[str, Any] | None = None,
    idle: bool = False,
) -> LogEntry:
    """
    ログエントリを作成（初回作成時）

    Args:
        active_app: アクティブなアプリケーション名
        window_title: ウィンドウタイトル
        ocr_text: OCRで抽出されたテキスト
        ocr_confidence: OCR信頼度
        timestamp: タイムスタンプ。Noneの場合は現在時刻
        idle: 無操作サイクルで作成されたエントリかどうか。Trueのときのみ
            entryに"idle": Trueを含める（Falseの場合はキーを追加せず、
            既存のログ形式を変えない）

    Returns:
        LogEntry: ログエントリ
    """
    if timestamp is None:
        timestamp = datetime.now()

    timestamp_str = timestamp.astimezone().isoformat()

    context = window_context or {}
    working_app = str(context.get("working_app") or active_app or "Unknown")
    working_title = str(context.get("working_title") or window_title or "Unknown")

    entry: LogEntry = {
        "schema_version": 2,
        "start_time": timestamp_str,
        "end_time": timestamp_str,
        "duration_minutes": 1,
        "snapshot_count": 1,
        "active_app": working_app,
        "window_title": working_title,
        "ocr_text": ocr_text,
        "avg_ocr_confidence": ocr_confidence
    }

    optional_fields = [
        "focused_app",
        "focused_title",
        "focused_bundle_id",
        "focused_pid",
        "working_app",
        "working_title",
        "working_bundle_id",
        "window_id",
        "capture_mode",
        "selection_reason",
        "capture_status",
        "capture_error",
        "ocr_length",
        "is_suspicious",
        "screen_recording_allowed",
        "top_windows",
    ]
    for field in optional_fields:
        if field in context:
            entry[field] = context[field]

    entry.setdefault("working_app", working_app)
    entry.setdefault("working_title", working_title)

    if idle:
        entry["idle"] = True

    return entry


def update_log_entry(
    entry: LogEntry,
    new_timestamp: datetime,
    new_confidence: float | None = None
) -> LogEntry:
    """
    既存のログエントリを更新（OCRテキストが同じ場合）

    Args:
        entry: 既存のログエントリ
        new_timestamp: 新しいタイムスタンプ
        new_confidence: 新しいOCR信頼度

    Returns:
        LogEntry: 更新されたログエントリ
    """
    from datetime import datetime as dt

    # start_timeからdatetimeオブジェクトを作成
    start_dt = dt.fromisoformat(entry["start_time"])

    # new_timestampがnaiveな場合はタイムゾーンを付与
    if new_timestamp.tzinfo is None:
        new_timestamp = new_timestamp.astimezone()

    # 経過時間を計算（分単位）
    duration = int((new_timestamp - start_dt).total_seconds() / 60) + 1

    # snapshot_countを増やす
    new_count = entry["snapshot_count"] + 1

    # 平均信頼度を再計算
    if new_confidence is not None and entry["avg_ocr_confidence"] is not None:
        old_total = entry["avg_ocr_confidence"] * entry["snapshot_count"]
        new_avg = (old_total + new_confidence) / new_count
    elif new_confidence is not None:
        new_avg = new_confidence
    else:
        new_avg = entry["avg_ocr_confidence"]

    # エントリを更新。v2の追加メタデータはそのまま保持する。
    updated_entry: LogEntry = dict(entry)  # type: ignore[assignment]
    updated_entry["end_time"] = new_timestamp.astimezone().isoformat()
    updated_entry["duration_minutes"] = duration
    updated_entry["snapshot_count"] = new_count
    updated_entry["avg_ocr_confidence"] = new_avg

    return updated_entry


def write_log_entry(entry: LogEntry, log_file: Path | None = None) -> bool:
    """
    ログエントリをファイルに書き込む

    OCRテキストが空白の場合も診断目的で保存する。

    Args:
        entry: ログエントリ

    Returns:
        bool: 書き込み成功した場合True
    """
    try:
        if log_file is None:
            log_file = get_log_file_path(_entry_log_datetime(entry))
        else:
            log_file.parent.mkdir(parents=True, exist_ok=True)

        # JSON行を作成（ensure_ascii=Falseで日本語を保持）
        json_line = json.dumps(entry, ensure_ascii=False)

        # 追記モードで書き込み
        with open(log_file, "a", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            f.write(json_line + "\n")
            f.flush()
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        return True

    except Exception as e:
        print(f"Failed to write log entry: {e}")
        return False


def write_log_entries(
    entries: list[LogEntry],
    *,
    writer: Callable[[LogEntry], bool] = write_log_entry,
) -> list[LogEntry]:
    """複数エントリを順に保存し、失敗した地点以降をpendingとして返す。"""
    for index, entry in enumerate(entries):
        if not writer(entry):
            return entries[index:]
    return []


def _entry_matches_date(entry: dict[str, Any], target: datetime | None) -> bool:
    """日付指定読み込み時、明らかに別日付のエントリを除外する。"""
    if target is None:
        return True
    start_time = entry.get("start_time")
    if not start_time:
        return True
    try:
        return datetime.fromisoformat(str(start_time)).date() == target.date()
    except ValueError:
        return True


def read_log_entries(
    date: datetime | None = None,
    log_file: Path | None = None,
) -> list[LogEntry]:
    """
    ログエントリを読み込む

    Args:
        date: 対象日付。Noneの場合は今日

    Returns:
        list[LogEntry]: ログエントリのリスト
    """
    if log_file is None:
        log_file = get_log_file_path(date)

    if not log_file.exists():
        return []

    entries = []
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entry = json.loads(line)
                    if isinstance(entry, dict) and _entry_matches_date(entry, date):
                        entries.append(entry)
    except Exception as e:
        print(f"Failed to read log entries: {e}")

    return entries


def cleanup_old_logs(days: int = 30) -> int:
    """
    指定日数より古いログファイルを削除

    Args:
        days: 保持する日数。デフォルト30日

    Returns:
        int: 削除したファイル数
    """
    from datetime import timedelta

    days = validate_retention_days(days)
    log_dir = get_log_dir()
    cutoff_date = datetime.now() - timedelta(days=days)
    deleted_count = 0

    for log_file in log_dir.glob("*.jsonl"):
        try:
            # ファイル名から日付を取得（YYYY-MM-DD.jsonl）
            date_str = log_file.stem
            file_date = datetime.strptime(date_str, "%Y-%m-%d")

            if file_date < cutoff_date:
                log_file.unlink()
                print(f"Deleted old log: {log_file.name}")
                deleted_count += 1

        except ValueError:
            # ファイル名が日付形式でない場合はスキップ
            continue
        except Exception as e:
            print(f"Failed to delete {log_file}: {e}")

    return deleted_count
