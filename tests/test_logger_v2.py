import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from screenlog.logger import (
    cleanup_old_logs,
    create_log_entry,
    read_log_entries,
    update_log_entry,
    write_log_entries,
    write_log_entry,
)


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

    def test_write_log_entry_defaults_to_entry_start_date(self):
        with TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            entry = create_log_entry(
                active_app="Codex",
                window_title="Codex",
                ocr_text="previous day entry",
                timestamp=datetime.fromisoformat("2026-06-18T23:59:30+09:00"),
            )

            with patch("screenlog.logger.get_log_dir", return_value=log_dir):
                self.assertTrue(write_log_entry(entry))

            self.assertTrue((log_dir / "2026-06-18.jsonl").exists())
            self.assertFalse((log_dir / "2026-06-19.jsonl").exists())
            entries = read_log_entries(log_file=log_dir / "2026-06-18.jsonl")

        self.assertEqual(entries[0]["ocr_text"], "previous day entry")

    def test_read_log_entries_with_date_ignores_mismatched_entry_dates(self):
        with TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "2026-06-19.jsonl"
            log_path.write_text(
                '{"start_time":"2026-06-18T23:59:30+09:00","ocr_text":"wrong day"}\n'
                '{"start_time":"2026-06-19T00:00:30+09:00","ocr_text":"right day"}\n',
                encoding="utf-8",
            )
            with patch("screenlog.logger.get_log_file_path", return_value=log_path):
                entries = read_log_entries(
                    date=datetime.fromisoformat("2026-06-19T12:00:00+09:00")
                )

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["ocr_text"], "right day")

    def test_write_log_entries_keeps_failed_and_later_entries_pending(self):
        entries = [
            create_log_entry("App", "First", "first"),
            create_log_entry("App", "Second", "second"),
        ]
        calls = []

        def writer(entry):
            calls.append(entry["window_title"])
            return entry["window_title"] != "Second"

        remaining = write_log_entries(entries, writer=writer)

        self.assertEqual(calls, ["First", "Second"])
        self.assertEqual([entry["window_title"] for entry in remaining], ["Second"])

    def test_cleanup_old_logs_rejects_zero_retention_without_deleting(self):
        with TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            log_file = log_dir / "2026-06-19.jsonl"
            log_file.write_text("{}\n", encoding="utf-8")

            with patch("screenlog.logger.get_log_dir", return_value=log_dir):
                with self.assertRaises(ValueError):
                    cleanup_old_logs(days=0)

            self.assertTrue(log_file.exists())


if __name__ == "__main__":
    unittest.main()
