from datetime import datetime
from pathlib import Path
import unittest

from screenlog.project_rules import SummaryRules
from screenlog.summarize import (
    calculate_app_usage,
    default_daily_summary_path,
    detect_quality_flags,
    entry_app_name,
    extract_topic_hints,
    generate_daily_review_from_entries,
    infer_project_hints,
    split_idle_entries,
)


class SummarizeTests(unittest.TestCase):
    def test_calculate_app_usage_uses_duration_and_working_app(self):
        entries = [
            {"active_app": "tldv", "working_app": "Google Chrome", "duration_minutes": 6},
            {"active_app": "tldv", "working_app": "Cursor", "duration_minutes": 11},
            {"active_app": "tldv", "duration_minutes": 1},
        ]

        usage = calculate_app_usage(entries)

        self.assertEqual(usage["Cursor"], 11)
        self.assertEqual(usage["Google Chrome"], 6)
        self.assertEqual(usage["tldv"], 1)

    def test_entry_app_name_falls_back_for_legacy_logs(self):
        self.assertEqual(
            entry_app_name({"active_app": "loginwindow", "window_title": "Unknown"}),
            "loginwindow",
        )

    def test_extract_topic_hints_finds_business_terms_from_ocr(self):
        entries = [
            {
                "ocr_text": "morning routine と business-context。15:00 BUSINESS-ALLIANCE ヒアリング準備。SCO定例も明日。",
            }
        ]

        hints = extract_topic_hints(entries)

        self.assertIn("business-context", hints)
        self.assertIn("BUSINESS-ALLIANCE", hints)
        self.assertIn("SCO", hints)

    def test_infer_project_hints_counts_project_keywords(self):
        # DEFAULT_PROJECT_KEYWORDSはscreenlog自身のみに縮小されているため、
        # 実運用辞書相当のrulesを明示的に渡してマッチングを検証する。
        entries = [
            {
                "working_title": "operator-cockpit.html",
                "ocr_text": "business-context の ScreenLog 連携とSCOの観測を確認",
            },
            {
                "working_title": "IDEE AI顧問",
                "ocr_text": "IDEEのGitHub運用ルールを整理",
            },
        ]
        rules = SummaryRules(
            topic_keywords=[],
            project_keywords={
                "business-context": ["business-context", "operator-cockpit"],
                "sco": ["SCO"],
                "idee-ai-expert": ["IDEE", "AI顧問"],
            },
        )

        hints = infer_project_hints(entries, rules=rules)

        self.assertGreaterEqual(hints["business-context"], 1)
        self.assertGreaterEqual(hints["sco"], 1)
        self.assertGreaterEqual(hints["idee-ai-expert"], 1)

    def test_detect_quality_flags_surfaces_review_points(self):
        entries = [
            {
                "schema_version": 2,
                "start_time": "2026-05-12T09:00:00+09:00",
                "active_app": "tldv",
                "focused_app": "tldv",
                "working_app": "Unknown",
                "working_title": "Unknown",
                "duration_minutes": 4,
                "ocr_text": "short",
            },
            {
                "start_time": "2026-05-12T09:05:00+09:00",
                "active_app": "loginwindow",
                "window_title": "Unknown",
                "duration_minutes": 3,
                "ocr_text": "SCO",
            },
        ]

        flags = detect_quality_flags(entries)
        joined = "\n".join(flags)

        self.assertIn("Unknown", joined)
        self.assertIn("legacy", joined)
        self.assertIn("短いOCR", joined)

    def test_generate_daily_review_includes_quality_and_checklist(self):
        entries = [
            {
                "schema_version": 2,
                "start_time": "2026-05-12T09:10:00+09:00",
                "end_time": "2026-05-12T09:20:00+09:00",
                "active_app": "tldv",
                "focused_app": "tldv",
                "working_app": "Cursor",
                "working_title": "business-context update",
                "duration_minutes": 10,
                "ocr_text": "business-context の ScreenLog 日次サマリーを作る。SCOの観測も確認する。",
            }
        ]

        review = generate_daily_review_from_entries(
            entries,
            datetime(2026, 5, 12),
            max_entries_per_block=1,
        )

        self.assertIn("# 2026-05-12 ScreenLog Daily Summary", review)
        self.assertIn("## 推定プロジェクト", review)
        self.assertIn("business-context", review)
        self.assertIn("## 怪しい判定・改善メモ", review)
        self.assertIn("## 確認メモ", review)
        self.assertIn("- [ ] 今日の作業理解は合っているか確認する", review)

    def test_unattributed_apps_flagged(self):
        # 非帰属分数が総分数の30%以上のとき、上位アプリを分数付きで出す。
        entries = [
            {
                "schema_version": 2,
                "start_time": "2026-05-12T09:00:00+09:00",
                "working_app": "AppA",
                "duration_minutes": 20,
                "ocr_text": "未知のテキストA",
            },
            {
                "schema_version": 2,
                "start_time": "2026-05-12T09:20:00+09:00",
                "working_app": "AppB",
                "duration_minutes": 15,
                "ocr_text": "未知のテキストB",
            },
            {
                "schema_version": 2,
                "start_time": "2026-05-12T09:35:00+09:00",
                "working_app": "ScreenLog",
                "duration_minutes": 5,
                "ocr_text": "ScreenLog の作業",
            },
        ]

        flags = detect_quality_flags(entries)
        joined = "\n".join(flags)

        self.assertIn("どのプロジェクトにも帰属しない作業が35分", joined)
        self.assertIn("AppA 20分", joined)
        self.assertIn("AppB 15分", joined)
        self.assertIn("summary-rules.json の辞書更新を検討", joined)

        # 非帰属が30%未満なら、このフラグは出さない。
        below_threshold_entries = [
            {
                "schema_version": 2,
                "start_time": "2026-05-12T09:00:00+09:00",
                "working_app": "ScreenLog",
                "duration_minutes": 90,
                "ocr_text": "ScreenLog の作業",
            },
            {
                "schema_version": 2,
                "start_time": "2026-05-12T10:30:00+09:00",
                "working_app": "AppC",
                "duration_minutes": 10,
                "ocr_text": "未知のテキストC",
            },
        ]

        below_flags = detect_quality_flags(below_threshold_entries)
        self.assertFalse(
            any("どのプロジェクトにも帰属しない作業" in flag for flag in below_flags)
        )

    def test_idle_entries_excluded_from_usage(self):
        entries = [
            {
                "schema_version": 2,
                "start_time": "2026-05-12T09:00:00+09:00",
                "working_app": "Cursor",
                "duration_minutes": 20,
                "ocr_text": "business-context の作業",
            },
            {
                "schema_version": 2,
                "start_time": "2026-05-12T09:20:00+09:00",
                "working_app": "Cursor",
                "duration_minutes": 15,
                "ocr_text": "",
                "idle": True,
            },
        ]

        active_entries, idle_minutes = split_idle_entries(entries)

        self.assertEqual(len(active_entries), 1)
        self.assertEqual(idle_minutes, 15)

        usage = calculate_app_usage(active_entries)
        self.assertEqual(usage["Cursor"], 20)

        review = generate_daily_review_from_entries(
            entries,
            datetime(2026, 5, 12),
        )
        self.assertIn("- 放置: 15分", review)
        self.assertIn("- 推定記録分数: 20分", review)

    def test_idle_fallback_detects_static_block(self):
        # 同じOCR先頭60字がidleフラグ無しで10件以上・30分以上続く場合、
        # fallback heuristicで放置と推定する。
        entries = [
            {
                "schema_version": 2,
                "start_time": f"2026-05-12T09:{i * 3:02d}:00+09:00",
                "working_app": "Slack",
                "duration_minutes": 3,
                "ocr_text": "Slack\nファイル\n編集\n表示\n開始\n履歴\nウィンドウ\nヘルプ",
            }
            for i in range(12)
        ]

        active_entries, idle_minutes = split_idle_entries(entries)

        self.assertEqual(active_entries, [])
        self.assertEqual(idle_minutes, 36)

        review = generate_daily_review_from_entries(entries, datetime(2026, 5, 12))
        self.assertIn("- 放置: 36分", review)
        self.assertIn("放置推定 36分（旧ログheuristic）", review)

    def test_idle_fallback_ignores_active_block(self):
        # OCR内容が毎回変わっている（3種類以上の先頭60字が出現する）場合は、
        # 10件以上続いても放置と推定しない。
        entries = [
            {
                "schema_version": 2,
                "start_time": f"2026-05-12T09:{i * 3:02d}:00+09:00",
                "working_app": "Cursor",
                "duration_minutes": 3,
                "ocr_text": f"business-context タスク{i}の作業メモ",
            }
            for i in range(12)
        ]

        active_entries, idle_minutes = split_idle_entries(entries)

        self.assertEqual(len(active_entries), 12)
        self.assertEqual(idle_minutes, 0)

    def test_idle_fallback_excludes_adjacent_singleton_active_entries(self):
        # 静的idleブロックに隣接する単発のアクティブエントリ（prefixが1回しか
        # 出現しない）が、ブロックに吸収されて放置扱いされないことを確認する。
        # active→idle / idle→active の両方向を検証する。
        def active_entry(index: int, minute: int) -> dict:
            return {
                "schema_version": 2,
                "start_time": f"2026-05-12T09:{minute:02d}:00+09:00",
                "working_app": "Cursor",
                "duration_minutes": 3,
                "ocr_text": f"business-context タスク{index}の作業メモ",
            }

        def static_entry(minute: int) -> dict:
            return {
                "schema_version": 2,
                "start_time": f"2026-05-12T10:{minute:02d}:00+09:00",
                "working_app": "Slack",
                "duration_minutes": 3,
                "ocr_text": "Slack\nファイル\n編集\n表示\n開始\n履歴\nウィンドウ\nヘルプ",
            }

        active_block = [active_entry(i, i * 3) for i in range(5)]
        static_block = [static_entry(i * 3) for i in range(10)]  # 30分

        # active→idle
        active_entries, idle_minutes = split_idle_entries(active_block + static_block)
        self.assertEqual(idle_minutes, 30)
        self.assertEqual(len(active_entries), 5)
        self.assertTrue(
            all(entry["working_app"] == "Cursor" for entry in active_entries)
        )

        # idle→active
        active_entries, idle_minutes = split_idle_entries(static_block + active_block)
        self.assertEqual(idle_minutes, 30)
        self.assertEqual(len(active_entries), 5)
        self.assertTrue(
            all(entry["working_app"] == "Cursor" for entry in active_entries)
        )

    def test_idle_fallback_boundary_thresholds(self):
        # 境界値: 静的10件・30分ちょうどは放置と推定し、
        # 9件（27分）は件数・分数とも閾値未満なので推定しない。
        def static_entries(count: int) -> list[dict]:
            return [
                {
                    "schema_version": 2,
                    "start_time": f"2026-05-12T09:{i * 3:02d}:00+09:00",
                    "working_app": "Slack",
                    "duration_minutes": 3,
                    "ocr_text": "Slack\nファイル\n編集\n表示\n開始\n履歴\nウィンドウ\nヘルプ",
                }
                for i in range(count)
            ]

        _, idle_minutes = split_idle_entries(static_entries(10))
        self.assertEqual(idle_minutes, 30)

        active_entries, idle_minutes = split_idle_entries(static_entries(9))
        self.assertEqual(idle_minutes, 0)
        self.assertEqual(len(active_entries), 9)

        # 10件以上でも合計29分なら推定しない。
        short_entries = [
            {
                "schema_version": 2,
                "start_time": f"2026-05-12T09:{i * 2:02d}:00+09:00",
                "working_app": "Slack",
                "duration_minutes": 2,
                "ocr_text": "Slack\nファイル\n編集\n表示\n開始\n履歴\nウィンドウ\nヘルプ",
            }
            for i in range(10)
        ]
        # 2分×10件=20分 < 30分
        active_entries, idle_minutes = split_idle_entries(short_entries)
        self.assertEqual(idle_minutes, 0)
        self.assertEqual(len(active_entries), 10)

    def test_default_daily_summary_path_uses_daily_notes(self):
        path = default_daily_summary_path(datetime(2026, 5, 12), home=Path("/Users/example"))

        self.assertEqual(
            path,
            Path("/Users/example/daily-notes/JOURNAL/Daily/2026-05-12_screenlog-summary.md"),
        )


if __name__ == "__main__":
    unittest.main()
