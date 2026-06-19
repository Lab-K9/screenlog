#!/usr/bin/env python3
"""ScreenLog サマリー生成モジュール

このモジュールはOCRログを整形して出力します。
実際の「何をしていたか」のサマライズはLLMが行う前提です。
"""

import argparse
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path
from .logger import read_log_entries, LogEntry
from .project_rules import SummaryRules, load_summary_rules

QUALITY_RISK_APPS = {"tldv", "loginwindow", "unknown"}


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


def _entry_haystack(entry: LogEntry | dict) -> str:
    return "\n".join(
        str(entry.get(key) or "")
        for key in (
            "working_app",
            "working_title",
            "active_app",
            "window_title",
            "focused_app",
            "focused_title",
            "ocr_text",
        )
    )


def extract_topic_hints(
    entries: list[LogEntry] | list[dict],
    *,
    rules: SummaryRules | None = None,
) -> list[str]:
    """OCR本文から日次振り返りに使いやすいトピック候補を抽出する。"""
    if rules is None:
        rules = load_summary_rules()
    haystack = "\n".join(
        "\n".join(
            str(entry.get(key) or "")
            for key in ("working_title", "window_title", "ocr_text")
        )
        for entry in entries
    )
    lower_haystack = haystack.casefold()
    hints = []
    for keyword in rules.topic_keywords:
        if keyword.casefold() in lower_haystack:
            hints.append(keyword)
    return hints


def infer_project_hints(
    entries: list[LogEntry] | list[dict],
    *,
    rules: SummaryRules | None = None,
) -> dict[str, int]:
    """ログ本文・タイトルから、関係しそうなプロジェクト候補を数える。"""
    if rules is None:
        rules = load_summary_rules()
    counts: dict[str, int] = {}
    for entry in entries:
        haystack = _entry_haystack(entry).casefold()
        for project, keywords in rules.project_keywords.items():
            if any(keyword.casefold() in haystack for keyword in keywords):
                counts[project] = counts.get(project, 0) + entry_duration(entry)
    return dict(sorted(counts.items(), key=lambda item: item[1], reverse=True))


def detect_quality_flags(entries: list[LogEntry] | list[dict]) -> list[str]:
    """日次レビューで人間が確認すべきログ品質の怪しい点を抽出する。"""
    if not entries:
        return ["記録がありません。ScreenLog本体の稼働状態を確認してください。"]

    total = len(entries)
    legacy_count = sum(
        1 for entry in entries if not entry.get("schema_version") or not entry.get("working_app")
    )
    unknown_count = sum(
        1 for entry in entries if entry_app_name(entry).strip().casefold() in QUALITY_RISK_APPS
    )
    short_ocr_count = sum(
        1 for entry in entries if len(str(entry.get("ocr_text") or "").strip()) < 50
    )
    focus_mismatch_count = sum(
        1
        for entry in entries
        if entry.get("focused_app")
        and str(entry.get("focused_app")).casefold() != entry_app_name(entry).casefold()
    )

    flags: list[str] = []
    if unknown_count:
        flags.append(
            f"Unknown/tldv/loginwindow が作業アプリ扱いの記録が {unknown_count}/{total} 件あります。"
        )
    if legacy_count:
        flags.append(
            f"legacy形式またはworking_appなしの記録が {legacy_count}/{total} 件あります。"
        )
    if short_ocr_count:
        flags.append(f"短いOCRしかない記録が {short_ocr_count}/{total} 件あります。")
    if focus_mismatch_count:
        flags.append(
            f"focused_app と working_app が異なる記録が {focus_mismatch_count}/{total} 件あります。"
        )
    if not infer_project_hints(entries):
        flags.append("推定プロジェクトが見つかりません。キーワード辞書かログ品質の確認が必要です。")

    return flags or ["大きな異常は検出されませんでした。目視で作業理解だけ確認してください。"]


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


def default_daily_summary_path(date: datetime | None = None, home: Path | None = None) -> Path:
    """日次ScreenLogサマリーのデフォルト保存先を返す。"""
    if date is None:
        date = datetime.now()
    root = home if home is not None else Path.home()
    return root / "daily-notes" / "JOURNAL" / "Daily" / f"{date.strftime('%Y-%m-%d')}_screenlog-summary.md"


def _time_range(entries: list[LogEntry] | list[dict]) -> str:
    if not entries:
        return "-"
    return f"{entries[0]['start_time'][11:16]} 〜 {entries[-1]['start_time'][11:16]}"


def _trim_text(text: str, limit: int = 260) -> str:
    compact = " ".join(line.strip() for line in text.splitlines() if line.strip())
    if len(compact) <= limit:
        return compact
    return compact[:limit] + "..."


def generate_daily_review_from_entries(
    entries: list[LogEntry] | list[dict],
    date: datetime,
    max_entries_per_block: int = 2,
) -> str:
    """毎日確認するためのScreenLog日次レビューMarkdownを生成する。"""
    lines = [
        f"# {date.strftime('%Y-%m-%d')} ScreenLog Daily Summary",
        "",
        "ScreenLogの自動記録を、人間が毎日確認して改善点に気づくためのMVPサマリーです。",
        "",
    ]

    if not entries:
        lines.extend(
            [
                "## 今日の作業概況",
                "",
                "- 記録数: 0件",
                "- 記録時間: -",
                "",
                "## 怪しい判定・改善メモ",
                "",
                "- 記録がありません。ScreenLog本体の稼働状態を確認してください。",
                "",
                "## 確認メモ",
                "",
                "- [ ] 今日の作業理解は合っているか確認する",
                "- [ ] 怪しい判定を1つ以上Issue/メモ化する",
                "- [ ] business-contextへ流す価値がある内容を確認する",
            ]
        )
        return "\n".join(lines)

    app_usage = calculate_app_usage(entries)  # type: ignore[arg-type]
    project_hints = infer_project_hints(entries)
    quality_flags = detect_quality_flags(entries)
    time_blocks = group_entries_by_time_block(entries, 30)  # type: ignore[arg-type]
    total_minutes = sum(app_usage.values())

    lines.extend(
        [
            "## 今日の作業概況",
            "",
            f"- 記録数: {len(entries)}件",
            f"- 記録時間: {_time_range(entries)}",
            f"- 推定記録分数: {total_minutes}分",
            "",
            "## 作業アプリ",
            "",
        ]
    )
    for app, minutes in list(app_usage.items())[:8]:
        pct = (minutes / total_minutes) * 100 if total_minutes else 0
        lines.append(f"- {app}: {minutes}分 ({pct:.0f}%)")

    lines.extend(["", "## 推定プロジェクト", ""])
    if project_hints:
        for project, minutes in list(project_hints.items())[:8]:
            lines.append(f"- {project}: {minutes}分相当のシグナル")
    else:
        lines.append("- 推定できませんでした。")

    lines.extend(["", "## 時間帯別", ""])
    for block_time, block_entries in time_blocks.items():
        time_str = block_time.strftime("%H:%M")
        end_time = (block_time + timedelta(minutes=30)).strftime("%H:%M")
        block_usage = calculate_app_usage(block_entries)
        main_app = next(iter(block_usage.keys()), "Unknown")
        block_projects = infer_project_hints(block_entries)
        project_text = ", ".join(list(block_projects.keys())[:3]) if block_projects else "未推定"
        lines.append(f"### {time_str} - {end_time} / {main_app}")
        lines.append(f"- 推定プロジェクト: {project_text}")

        output_count = 0
        for entry in block_entries:
            if output_count >= max_entries_per_block:
                break
            ocr_text = str(entry.get("ocr_text") or "").strip()
            if not ocr_text:
                continue
            ts = str(entry["start_time"])[11:16]
            window = entry_window_title(entry)[:80] or "-"
            lines.append(f"- {ts} {entry_app_name(entry)} / {window}")
            lines.append(f"  - OCR抜粋: {_trim_text(ocr_text)}")
            output_count += 1
        if output_count == 0:
            lines.append("- 有意なOCRテキストなし。")
        lines.append("")

    lines.extend(["## 怪しい判定・改善メモ", ""])
    for flag in quality_flags:
        lines.append(f"- {flag}")

    lines.extend(
        [
            "",
            "## 確認メモ",
            "",
            "- [ ] 今日の作業理解は合っているか確認する",
            "- [ ] 怪しい判定を1つ以上Issue/メモ化する",
            "- [ ] business-contextへ流す価値がある内容を確認する",
            "",
            "## 元データ",
            "",
            f"- ScreenLog raw log: ~/Library/Application Support/ScreenLog/logs/{date.strftime('%Y-%m-%d')}.jsonl",
        ]
    )
    return "\n".join(lines)


def generate_daily_review(date: datetime | None = None, max_entries_per_block: int = 2) -> str:
    """当日のログから日次レビューMarkdownを生成する。"""
    if date is None:
        date = datetime.now()
    entries = read_log_entries(date)
    return generate_daily_review_from_entries(entries, date, max_entries_per_block)


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

        lines.append(f"### {time_str} - {end_time}（{main_app}）")
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
    parser.add_argument(
        "--daily-review",
        action="store_true",
        help="毎日確認する日次レビュー形式で出力"
    )
    parser.add_argument(
        "--daily-note",
        action="store_true",
        help="日次レビューをdaily-notes配下のデフォルトパスへ保存"
    )

    args = parser.parse_args()

    if args.date:
        date = datetime.strptime(args.date, "%Y-%m-%d")
    else:
        date = datetime.now()

    if args.daily_review or args.daily_note:
        output = generate_daily_review(date, max_entries_per_block=args.max_per_block)
    else:
        output = generate_raw_log(date, max_entries_per_block=args.max_per_block)

    output_path = args.output
    if args.daily_note and not output_path:
        output_path = str(default_daily_summary_path(date))

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"ログを {path} に保存しました")
    else:
        print(output)


if __name__ == "__main__":
    main()
