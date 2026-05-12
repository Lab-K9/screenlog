#!/usr/bin/env python3
"""ScreenLogの稼働状態とウィンドウ判定を診断するCLI。"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .logger import get_log_dir
from .window import get_window_context


def _latest_log_file() -> Path | None:
    log_files = sorted(get_log_dir().glob("*.jsonl"))
    return log_files[-1] if log_files else None


def build_doctor_report() -> dict[str, Any]:
    """現在のScreenLog診断レポートを作る。"""
    context = get_window_context()
    latest_log = _latest_log_file()
    latest_log_info: dict[str, Any] | None = None

    if latest_log is not None:
        stat = latest_log.stat()
        latest_log_info = {
            "path": str(latest_log),
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(),
        }

    return {
        "checked_at": datetime.now().astimezone().isoformat(),
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
    print(f"focused: {report.get('focused_app') or '-'} / {report.get('focused_title') or '-'}")
    print(f"working: {report.get('working_app') or '-'} / {report.get('working_title') or '-'}")
    print(f"capture: {report.get('capture_mode') or '-'} / window_id={report.get('window_id') or '-'}")
    print(f"reason: {report.get('selection_reason') or '-'}")

    latest_log = report.get("latest_log")
    if latest_log:
        print(f"latest_log: {latest_log['path']}")
        print(f"latest_log_modified: {latest_log['modified_at']}")
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
