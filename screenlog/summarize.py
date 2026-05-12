#!/usr/bin/env python3
"""ScreenLog サマリー生成モジュール

このモジュールはOCRログを整形して出力します。
実際の「何をしていたか」のサマライズはLLMが行う前提です。
"""

import argparse
from datetime import datetime, timedelta
from collections import defaultdict
from .logger import read_log_entries, LogEntry


TOPIC_KEYWORDS = [
    "business-context",
    "BUSINESS-ALLIANCE",
    "Corporate-OS",
    "SCO",
    "IDEE",
    "beyondS",
    "morning routine",
    "now.md",
    "todo",
    "Issue",
    "Slack",
    "Claude",
]


def entry_app_name(entry: LogEntry | dict) -> str:
    """v2ログではworking_app、旧ログではactive_appを作業アプリ名として使う。"""
    return str(entry.get("working_app") or entry.get("active_app") or "Unknown")


def entry_window_title(entry: LogEntry | dict) -> str:
    """v2ログではworking_title、旧ログではwindow_titleを使う。"""
    return str(entry.get("working_title") or entry.get("window_title") or "")


def entry_duration(entry: LogEntry | dict) -> int:
    """ログエントリの継続時間を分単位で取得する。"""
    try:
        return max(1, int(entry.get("duration_minutes") or 1))
    except (TypeError, ValueError):
        return 1


def extract_topic_hints(entries: list[LogEntry] | list[dict]) -> list[str]:
    """OCR本文から日次振り返りに使いやすいトピック候補を抽出する。"""
    haystack = "\n".join(
        "\n".join(
            str(entry.get(key) or "")
            for key in ("working_title", "window_title", "ocr_text")
        )
        for entry in entries
    )
    lower_haystack = haystack.casefold()
    hints = []
    for keyword in TOPIC_KEYWORDS:
        if keyword.casefold() in lower_haystack:
            hints.append(keyword)
    return hints


def calculate_app_usage(entries: list[LogEntry]) -> dict[str, int]:
    """
    アプリ使用時間を計算

    Args:
        entries: ログエントリのリスト

    Returns:
        dict: アプリ名と使用分数のマップ
    """
    usage = defaultdict(int)

    for entry in entries:
        app = entry_app_name(entry)
        usage[app] += entry_duration(entry)

    return dict(sorted(usage.items(), key=lambda x: x[1], reverse=True))


def group_entries_by_time_block(entries: list[LogEntry], block_minutes: int = 30) -> dict:
    """
    エントリを時間ブロックでグループ化

    Args:
        entries: ログエントリのリスト
        block_minutes: ブロックの分数

    Returns:
        dict: 時間ブロックごとのエントリ
    """
    blocks = defaultdict(list)

    for entry in entries:
        ts = datetime.fromisoformat(entry["start_time"])
        block_start = ts.replace(
            minute=(ts.minute // block_minutes) * block_minutes,
            second=0,
            microsecond=0
        )
        blocks[block_start].append(entry)

    return dict(sorted(blocks.items()))


def generate_raw_log(date: datetime | None = None, max_entries_per_block: int = 2) -> str:
    """
    LLMが解釈するための整形済みログを生成

    Args:
        date: 対象日付。Noneの場合は今日
        max_entries_per_block: 時間ブロックあたりの最大エントリ数

    Returns:
        str: マークダウン形式の整形済みログ
    """
    if date is None:
        date = datetime.now()

    entries = read_log_entries(date)

    if not entries:
        return f"## {date.strftime('%Y-%m-%d')} のScreenLog\n\n記録がありません。"

    app_usage = calculate_app_usage(entries)
    time_blocks = group_entries_by_time_block(entries, 30)
    topic_hints = extract_topic_hints(entries)

    lines = [
        f"## {date.strftime('%Y-%m-%d')} のScreenLog",
        "",
        f"**記録数**: {len(entries)}件",
        f"**記録時間**: {entries[0]['start_time'][11:16]} 〜 {entries[-1]['start_time'][11:16]}",
        "",
        "---",
        "",
        "### 作業アプリ使用時間",
        "",
    ]

    # アプリ使用時間
    total = sum(app_usage.values())
    for app, minutes in list(app_usage.items())[:10]:
        pct = (minutes / total) * 100 if total > 0 else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        lines.append(f"- {app}: {minutes}分 ({pct:.0f}%) {bar}")

    if topic_hints:
        lines.extend(["", "### 検出トピック候補", ""])
        for hint in topic_hints:
            lines.append(f"- {hint}")

    lines.extend(["", "---", "", "### 時間帯別の作業内容（OCRテキスト）", ""])
    lines.append("以下は各時間帯のスクリーンショットからOCRで抽出したテキストです。")
    lines.append("これを読んで、ユーザーが何をしていたか、何を学んだかをサマライズしてください。")
    lines.append("")

    # 時間帯別ログ
    for block_time, block_entries in time_blocks.items():
        time_str = block_time.strftime("%H:%M")
        end_time = (block_time + timedelta(minutes=30)).strftime("%H:%M")

        # このブロックのメインアプリ
        block_usage = calculate_app_usage(block_entries)
        main_app = next(iter(block_usage.keys()), "Unknown")

        lines.append(f"#### {time_str} - {end_time}（{main_app}）")
        lines.append("")

        # 重複を避けつつ、代表的なエントリのみ出力
        seen_prefixes = set()
        output_count = 0

        for entry in block_entries:
            if output_count >= max_entries_per_block:
                break

            ocr_text = entry.get("ocr_text", "").strip()
            if not ocr_text or len(ocr_text) < 50:
                continue

            # 重複チェック（最初の100文字で判定）
            prefix = ocr_text[:100]
            if prefix in seen_prefixes:
                continue
            seen_prefixes.add(prefix)

            ts = entry["start_time"][11:16]
            app = entry_app_name(entry)
            window = entry_window_title(entry)[:60]

            lines.append(f"**{ts}** [{app}] {window}")
            if entry.get("focused_app") and entry.get("focused_app") != app:
                lines.append(
                    f"- focused: {entry.get('focused_app')} / capture: {entry.get('capture_mode', '-')}"
                )
            lines.append("```")
            # OCRテキストは長すぎる場合は切り詰め
            if len(ocr_text) > 1500:
                lines.append(ocr_text[:1500] + "\n...(省略)")
            else:
                lines.append(ocr_text)
            lines.append("```")
            lines.append("")

            output_count += 1

        if output_count == 0:
            lines.append("（このブロックには有意なOCRテキストがありませんでした）")
            lines.append("")

    return "\n".join(lines)


def generate_summary(date: datetime | None = None) -> str:
    """
    日次サマリーを生成（後方互換性のため維持）

    Args:
        date: 対象日付。Noneの場合は今日

    Returns:
        str: マークダウン形式のサマリー
    """
    return generate_raw_log(date)


def main():
    """CLIエントリーポイント"""
    parser = argparse.ArgumentParser(
        description="ScreenLog - 作業ログ出力（LLMサマライズ用）"
    )
    parser.add_argument(
        "-d", "--date",
        type=str,
        default=None,
        help="対象日付（YYYY-MM-DD形式）。デフォルト: 今日"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="出力ファイルパス。指定しない場合は標準出力"
    )
    parser.add_argument(
        "-n", "--max-per-block",
        type=int,
        default=2,
        help="時間ブロックあたりの最大エントリ数。デフォルト: 2"
    )

    args = parser.parse_args()

    if args.date:
        date = datetime.strptime(args.date, "%Y-%m-%d")
    else:
        date = datetime.now()

    output = generate_raw_log(date, max_entries_per_block=args.max_per_block)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"ログを {args.output} に保存しました")
    else:
        print(output)


if __name__ == "__main__":
    main()
