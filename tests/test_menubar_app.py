import unittest
from datetime import datetime
from unittest.mock import patch

from screenlog.logger import create_log_entry
from screenlog.menubar_app import ScreenLogApp


class MenuBarAppStateTests(unittest.TestCase):
    def test_flush_current_entry_queues_and_writes_entry(self):
        app = ScreenLogApp.__new__(ScreenLogApp)
        app.current_entry = create_log_entry(
            active_app="Codex",
            window_title="Codex",
            ocr_text="pending",
            timestamp=datetime.fromisoformat("2026-06-19T10:00:00+09:00"),
        )
        app.pending_entries = []

        with patch("screenlog.menubar_app.write_log_entries", return_value=[]) as writer:
            app.flush_current_entry()

        self.assertIsNone(app.current_entry)
        writer.assert_called_once()
        self.assertEqual(writer.call_args.args[0][0]["ocr_text"], "pending")
        self.assertEqual(app.pending_entries, [])

    def test_flush_current_entry_keeps_entry_pending_when_write_fails(self):
        app = ScreenLogApp.__new__(ScreenLogApp)
        entry = create_log_entry("Codex", "Codex", "pending")
        app.current_entry = entry
        app.pending_entries = []

        with patch("screenlog.menubar_app.write_log_entries", return_value=[entry]):
            app.flush_current_entry()

        self.assertIsNone(app.current_entry)
        self.assertEqual(app.pending_entries, [entry])


if __name__ == "__main__":
    unittest.main()
