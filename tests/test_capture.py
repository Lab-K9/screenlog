import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from screenlog.capture import cleanup_tmp_screenshots, screenshot_file_path


class CaptureFileTests(unittest.TestCase):
    def test_screenshot_file_path_is_unique_within_same_second(self):
        with TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            first = screenshot_file_path(tmp_dir, timestamp="20260619_101010")
            second = screenshot_file_path(tmp_dir, timestamp="20260619_101010")

        self.assertNotEqual(first, second)
        self.assertEqual(first.parent, tmp_dir)
        self.assertTrue(first.name.startswith("screenshot_20260619_101010_"))

    def test_cleanup_tmp_screenshots_removes_only_old_screenlog_pngs(self):
        with TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            old_file = tmp_dir / "screenshot_20260109_175435_old.png"
            recent_file = tmp_dir / "screenshot_20260619_101010_recent.png"
            unrelated_file = tmp_dir / "other.png"
            for path in (old_file, recent_file, unrelated_file):
                path.write_text("x", encoding="utf-8")

            now = 2_000_000
            os.utime(old_file, (now - 10_000, now - 10_000))
            os.utime(recent_file, (now, now))
            os.utime(unrelated_file, (now - 10_000, now - 10_000))

            with patch("screenlog.capture.get_tmp_dir", return_value=tmp_dir):
                deleted = cleanup_tmp_screenshots(max_age_seconds=3600, now=now)

            self.assertEqual(deleted, 1)
            self.assertFalse(old_file.exists())
            self.assertTrue(recent_file.exists())
            self.assertTrue(unrelated_file.exists())


if __name__ == "__main__":
    unittest.main()
