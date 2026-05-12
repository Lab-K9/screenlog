import unittest
from datetime import datetime

from screenlog.logger import create_log_entry, update_log_entry


class LoggerV2Tests(unittest.TestCase):
    def test_create_log_entry_preserves_v2_context_and_backwards_fields(self):
        context = {
            "focused_app": "tldv",
            "focused_title": "Floating recorder",
            "focused_bundle_id": "com.tldv.desktop",
            "working_app": "Google Chrome",
            "working_title": "business-context - Claude Code",
            "working_bundle_id": "com.google.Chrome",
            "window_id": 20,
            "capture_mode": "working_window",
            "selection_reason": "first_non_excluded_visible_window",
            "top_windows": [
                {"owner_name": "tldv", "window_title": "Floating recorder"},
                {"owner_name": "Google Chrome", "window_title": "business-context - Claude Code"},
            ],
        }

        entry = create_log_entry(
            active_app="tldv",
            window_title="Floating recorder",
            ocr_text="business-context update loop",
            ocr_confidence=0.9,
            timestamp=datetime.fromisoformat("2026-05-12T10:00:00+09:00"),
            window_context=context,
        )

        self.assertEqual(entry["schema_version"], 2)
        self.assertEqual(entry["active_app"], "Google Chrome")
        self.assertEqual(entry["window_title"], "business-context - Claude Code")
        self.assertEqual(entry["focused_app"], "tldv")
        self.assertEqual(entry["working_app"], "Google Chrome")
        self.assertEqual(entry["capture_mode"], "working_window")
        self.assertEqual(len(entry["top_windows"]), 2)

    def test_update_log_entry_preserves_v2_context(self):
        entry = create_log_entry(
            active_app="Google Chrome",
            window_title="business-context - Claude Code",
            ocr_text="same screen",
            ocr_confidence=0.8,
            timestamp=datetime.fromisoformat("2026-05-12T10:00:00+09:00"),
            window_context={
                "working_app": "Google Chrome",
                "working_title": "business-context - Claude Code",
                "capture_mode": "working_window",
                "selection_reason": "focused_app_visible_window",
            },
        )

        updated = update_log_entry(
            entry,
            datetime.fromisoformat("2026-05-12T10:05:00+09:00"),
            new_confidence=1.0,
        )

        self.assertEqual(updated["duration_minutes"], 6)
        self.assertEqual(updated["snapshot_count"], 2)
        self.assertEqual(updated["working_app"], "Google Chrome")
        self.assertEqual(updated["capture_mode"], "working_window")
        self.assertAlmostEqual(updated["avg_ocr_confidence"], 0.9)


if __name__ == "__main__":
    unittest.main()
