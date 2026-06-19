import unittest

from screenlog.permissions import ensure_screen_recording_access


class ScreenRecordingPermissionTests(unittest.TestCase):
    def test_ensure_access_does_not_request_when_already_allowed(self):
        calls = []

        result = ensure_screen_recording_access(
            checker=lambda: True,
            requester=lambda: calls.append("requested") or True,
        )

        self.assertTrue(result.allowed)
        self.assertFalse(result.requested)
        self.assertEqual(calls, [])

    def test_ensure_access_requests_when_denied(self):
        calls = []

        result = ensure_screen_recording_access(
            checker=lambda: False,
            requester=lambda: calls.append("requested") or False,
        )

        self.assertFalse(result.allowed)
        self.assertTrue(result.requested)
        self.assertEqual(calls, ["requested"])

    def test_ensure_access_returns_allowed_after_successful_request(self):
        result = ensure_screen_recording_access(
            checker=lambda: False,
            requester=lambda: True,
        )

        self.assertTrue(result.allowed)
        self.assertTrue(result.requested)

    def test_ensure_access_does_not_request_when_status_is_unknown(self):
        calls = []

        result = ensure_screen_recording_access(
            checker=lambda: None,
            requester=lambda: calls.append("requested") or True,
        )

        self.assertIsNone(result.allowed)
        self.assertFalse(result.requested)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
