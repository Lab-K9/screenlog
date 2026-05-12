import unittest

from screenlog.summarize import calculate_app_usage, entry_app_name, extract_topic_hints


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


if __name__ == "__main__":
    unittest.main()
