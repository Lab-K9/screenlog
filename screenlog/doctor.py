#!/usr/bin/env python3
"""ScreenLogの稼働状態とウィンドウ判定を診断するCLI。"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import DEFAULT_FLUSH_INTERVAL, DEFAULT_INTERVAL, get_config
from .logger import get_log_dir
from .permissions import screen_recording_preflight
from .window import get_window_context


_USE_LATEST_LOG = object()


def _latest_log_file() -> Path | None:
    log_files = sorted(get_log_dir().glob("*.jsonl"))
    return log_files[-1] if log_files else None


def _latest_log_age_seconds(
    *,
    now: datetime,
    modified_at: datetime | None,
) -> int | None:
    if modified_at is None:
        return None
    return max(0, int((now - modified_at).total_seconds()))


def _health_status(
    *,
    screen_recording_allowed: bool | None,
    latest_log_age_seconds: int | None,
    stale_threshold_seconds: int,
) -> str:
    if screen_recording_allowed is False:
        return "screen_permission_denied"
    if latest_log_age_seconds is None:
        return "no_logs"
    if latest_log_age_seconds > stale_threshold_seconds:
        return "stale_log"
    if screen_recording_allowed is None:
        return "permission_unknown"
    return "ok"


def build_doctor_report(
    *,
    now: datetime | None = None,
    latest_log_path: Path | None | object = _USE_LATEST_LOG,
    latest_log_modified_at: datetime | None = None,
    screen_permission_checker=screen_recording_preflight,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """現在のScreenLog診断レポートを作る。"""
    checked_at = (now or datetime.now().astimezone()).astimezone()
    runtime_config = get_config() if config is None else config
    interval = int(runtime_config.get("interval", DEFAULT_INTERVAL))
    flush_interval = int(runtime_config.get("flush_interval", DEFAULT_FLUSH_INTERVAL))
    stale_threshold = max(interval, flush_interval) * 2

    context = get_window_context()
    if latest_log_path is _USE_LATEST_LOG:
        latest_log = _latest_log_file()
    elif latest_log_path is None:
        latest_log = None
    else:
        if not isinstance(latest_log_path, Path):
            latest_log_path = Path(str(latest_log_path))
        latest_log = latest_log_path
    latest_log_info: dict[str, Any] | None = None

    if latest_log is not None:
        stat = latest_log.stat() if latest_log_modified_at is None else None
        modified_at = (
            latest_log_modified_at.astimezone()
            if latest_log_modified_at is not None
            else datetime.fromtimestamp(stat.st_mtime).astimezone()
        )
        age_seconds = _latest_log_age_seconds(
            now=checked_at,
            modified_at=modified_at,
        )
        latest_log_info = {
            "path": str(latest_log),
            "size_bytes": stat.st_size if stat is not None else latest_log.stat().st_size,
            "modified_at": modified_at.isoformat(),
            "age_seconds": age_seconds,
        }

    screen_recording_allowed = screen_permission_checker()
    log_age = latest_log_info.get("age_seconds") if latest_log_info else None

    return {
        "checked_at": checked_at.isoformat(),
        "health_status": _health_status(
            screen_recording_allowed=screen_recording_allowed,
            latest_log_age_seconds=log_age,
            stale_threshold_seconds=stale_threshold,
        ),
        "screen_recording_allowed": screen_recording_allowed,
        "stale_threshold_seconds": stale_threshold,
        "focused_app": context.get("focused_app"),
        "focused_title": context.get("focused_title"),
        "working_app": context.get("working_app"),
        "working_title": context.get("working_title"),
        "window_id": context.get("window_id"),
        "capture_mode": context.get("capture_mode"),
        "selection_reason": context.get("selection_reason"),
        "latest_log": latest_log_info,
        "top_windows": context.get("top_windows", []),
    }


def _print_human(report: dict[str, Any]) -> None:
    print("ScreenLog Doctor")
    print("================")
    print(f"checked_at: {report['checked_at']}")
    print(f"health: {report.get('health_status') or '-'}")
    print(f"screen_recording_allowed: {report.get('screen_recording_allowed')}")
    print(f"focused: {report.get('focused_app') or '-'} / {report.get('focused_title') or '-'}")
    print(f"working: {report.get('working_app') or '-'} / {report.get('working_title') or '-'}")
    print(f"capture: {report.get('capture_mode') or '-'} / window_id={report.get('window_id') or '-'}")
    print(f"reason: {report.get('selection_reason') or '-'}")

    latest_log = report.get("latest_log")
    if latest_log:
        print(f"latest_log: {latest_log['path']}")
        print(f"latest_log_modified: {latest_log['modified_at']}")
        print(f"latest_log_age_seconds: {latest_log['age_seconds']}")
        print(f"latest_log_size: {latest_log['size_bytes']} bytes")
    else:
        print("latest_log: none")

    print("")
    print("Top windows")
    print("-----------")
    for index, window in enumerate(report.get("top_windows", [])[:8], start=1):
        owner = window.get("owner_name") or "-"
        title = window.get("window_title") or "-"
        layer = window.get("layer")
        alpha = window.get("alpha")
        print(f"{index}. {owner} / {title} / layer={layer} alpha={alpha}")


def main() -> None:
    parser = argparse.ArgumentParser(description="ScreenLog doctor")
    parser.add_argument("--json", action="store_true", help="JSON形式で出力")
    args = parser.parse_args()

    report = build_doctor_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)


if __name__ == "__main__":
    main()
