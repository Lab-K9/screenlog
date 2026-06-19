import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from screenlog.logger import create_log_entry, read_log_entries, write_log_entry
from screenlog.recorder import process_capture, should_flush_entry
from screenlog.ocr import OCRResult


class RecorderTests(unittest.TestCase):
    def test_should_flush_entry_after_interval(self):
        entry = create_log_entry(
            active_app="Codex",
            window_title="Codex",
            ocr_text="same text",
            timestamp=datetime.fromisoformat("2026-06-17T10:00:00+09:00"),
        )

        self.assertFalse(
            should_flush_entry(
                entry,
                datetime.fromisoformat("2026-06-17T10:04:59+09:00"),
                flush_interval_seconds=300,
            )
        )
        self.assertTrue(
            should_flush_entry(
                entry,
                datetime.fromisoformat("2026-06-17T10:05:00+09:00"),
                flush_interval_seconds=300,
            )
        )

    def test_process_capture_flushes_same_ocr_without_overlap(self):
        previous = create_log_entry(
            active_app="Codex",
            window_title="Codex",
            ocr_text="same text",
            timestamp=datetime.fromisoformat("2026-06-17T10:00:00+09:00"),
            window_context={"working_app": "Codex", "working_title": "Codex", "window_id": 1},
        )

        result = process_capture(
            previous_entry=previous,
            timestamp=datetime.fromisoformat("2026-06-17T10:05:00+09:00"),
            flush_interval_seconds=300,
            window_context_provider=lambda: {
                "working_app": "Codex",
                "working_title": "Codex",
                "window_id": 1,
            },
            screenshot_taker=lambda window_id=None: "/tmp/screenlog-test.png",
            text_extractor=lambda path: OCRResult(text="same text", confidence=0.9),
            screenshot_deleter=lambda path: True,
            screen_permission_checker=lambda: True,
        )

        self.assertIs(result.to_write, previous)
        self.assertIsNotNone(result.current_entry)
        self.assertEqual(result.current_entry["start_time"], "2026-06-17T10:05:00+09:00")
        self.assertEqual(result.current_entry["snapshot_count"], 1)
        self.assertEqual(result.reason, "flush_interval")

    def test_process_capture_records_empty_ocr_status(self):
        result = process_capture(
            previous_entry=None,
            timestamp=datetime.fromisoformat("2026-06-17T10:00:00+09:00"),
            window_context_provider=lambda: {
                "working_app": "Codex",
                "working_title": "Codex",
                "window_id": 1,
            },
            screenshot_taker=lambda window_id=None: "/tmp/screenlog-test.png",
            text_extractor=lambda path: OCRResult(text="", confidence=None),
            screenshot_deleter=lambda path: True,
            screen_permission_checker=lambda: True,
        )

        self.assertIsNone(result.to_write)
        self.assertIsNotNone(result.current_entry)
        self.assertEqual(result.current_entry["capture_status"], "empty_ocr")
        self.assertTrue(result.current_entry["is_suspicious"])

    def test_write_log_entry_keeps_empty_ocr_diagnostics(self):
        with TemporaryDirectory() as tmp:
            entry = create_log_entry(
                active_app="Codex",
                window_title="Codex",
                ocr_text="",
                timestamp=datetime.fromisoformat("2026-06-17T10:00:00+09:00"),
                window_context={
                    "capture_status": "empty_ocr",
                    "ocr_length": 0,
                    "is_suspicious": True,
                },
            )

            log_path = Path(tmp) / "2026-06-17.jsonl"
            self.assertTrue(write_log_entry(entry, log_file=log_path))
            entries = read_log_entries(log_file=log_path)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["capture_status"], "empty_ocr")


if __name__ == "__main__":
    unittest.main()
