import unittest

from screenlog.quality import classify_capture, looks_like_menu_only


class CaptureQualityTests(unittest.TestCase):
    def test_classifies_empty_ocr_as_diagnostic_failure(self):
        result = classify_capture("", screen_recording_allowed=True)

        self.assertEqual(result["capture_status"], "empty_ocr")
        self.assertEqual(result["ocr_length"], 0)
        self.assertTrue(result["is_suspicious"])

    def test_classifies_menu_only_ocr_as_suspicious(self):
        text = "Codex\nFile\nEdit\nView\nWindow\nHelp"

        self.assertTrue(looks_like_menu_only(text))
        result = classify_capture(text, screen_recording_allowed=True)

        self.assertEqual(result["capture_status"], "suspicious_menu_only")
        self.assertEqual(result["ocr_length"], len(text))
        self.assertTrue(result["is_suspicious"])

    def test_screen_recording_denied_takes_precedence(self):
        result = classify_capture("some text", screen_recording_allowed=False)

        self.assertEqual(result["capture_status"], "screen_permission_denied")
        self.assertTrue(result["is_suspicious"])

    def test_normal_text_is_ok(self):
        result = classify_capture(
            "Project notes\nThis window has enough body text to be useful for activity logging.",
            screen_recording_allowed=True,
        )

        self.assertEqual(result["capture_status"], "ok")
        self.assertFalse(result["is_suspicious"])


if __name__ == "__main__":
    unittest.main()
