import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from screenlog.doctor import build_doctor_report


class DoctorTests(unittest.TestCase):
    def test_report_includes_permission_and_health_fields(self):
        with TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "2026-06-17.jsonl"
            log_path.write_text('{"capture_status":"ok"}\n', encoding="utf-8")
            checked_at = datetime.fromisoformat("2026-06-17T10:10:00+09:00")
            modified_at = checked_at - timedelta(seconds=30)

            with patch("screenlog.doctor.get_window_context") as context_mock:
                context_mock.return_value = {
                    "focused_app": "Codex",
                    "focused_title": "Codex",
                    "working_app": "Codex",
                    "working_title": "Codex",
                    "window_id": 1,
                    "capture_mode": "working_window",
                    "selection_reason": "focused_app_visible_window",
                    "top_windows": [],
                }
                report = build_doctor_report(
                    now=checked_at,
                    latest_log_path=log_path,
                    latest_log_modified_at=modified_at,
                    screen_permission_checker=lambda: True,
                    config={"interval": 60, "flush_interval": 300},
                )

        self.assertTrue(report["screen_recording_allowed"])
        self.assertEqual(report["health_status"], "ok")
        self.assertLess(report["latest_log"]["age_seconds"], 300)

    def test_report_marks_permission_denied(self):
        with patch("screenlog.doctor.get_window_context") as context_mock:
            context_mock.return_value = {}
            report = build_doctor_report(
                now=datetime.fromisoformat("2026-06-17T10:10:00+09:00"),
                latest_log_path=None,
                screen_permission_checker=lambda: False,
                config={"interval": 60, "flush_interval": 300},
            )

        self.assertFalse(report["screen_recording_allowed"])
        self.assertEqual(report["health_status"], "screen_permission_denied")


if __name__ == "__main__":
    unittest.main()
