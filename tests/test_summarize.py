from datetime import datetime
from pathlib import Path
import unittest

from screenlog.summarize import (
    calculate_app_usage,
    default_daily_summary_path,
    detect_quality_flags,
    entry_app_name,
    extract_topic_hints,
    generate_daily_review_from_entries,
    infer_project_hints,
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

        hints = infer_project_hints(entries)

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

    def test_default_daily_summary_path_uses_daily_notes(self):
        path = default_daily_summary_path(datetime(2026, 5, 12), home=Path("/Users/example"))

        self.assertEqual(
            path,
            Path("/Users/example/daily-notes/JOURNAL/Daily/2026-05-12_screenlog-summary.md"),
        )


if __name__ == "__main__":
    unittest.main()
