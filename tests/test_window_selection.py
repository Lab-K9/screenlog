import unittest

from screenlog.window import select_working_window


class WindowSelectionTests(unittest.TestCase):
    def test_ignores_overlay_frontmost_app_when_selecting_working_window(self):
        windows = [
            {
                "window_id": 10,
                "owner_name": "tldv",
                "window_title": "Floating recorder",
                "layer": 0,
                "alpha": 1,
                "bounds": {"X": 10, "Y": 10, "Width": 260, "Height": 120},
            },
            {
                "window_id": 20,
                "owner_name": "Google Chrome",
                "window_title": "business-context - Claude Code",
                "layer": 0,
                "alpha": 1,
                "bounds": {"X": 0, "Y": 0, "Width": 1440, "Height": 900},
            },
        ]

        selected = select_working_window(
            windows,
            focused_app="tldv",
            focused_title="Floating recorder",
        )

        self.assertIsNotNone(selected)
        self.assertEqual(selected["owner_name"], "Google Chrome")
        self.assertEqual(selected["selection_reason"], "first_non_excluded_visible_window")

    def test_prefers_focused_window_when_it_is_not_excluded(self):
        windows = [
            {
                "window_id": 30,
                "owner_name": "Cursor",
                "window_title": "screenlog/window.py",
                "layer": 0,
                "alpha": 1,
                "bounds": {"X": 0, "Y": 0, "Width": 1440, "Height": 900},
            },
            {
                "window_id": 40,
                "owner_name": "Slack",
                "window_title": "daily-meeting",
                "layer": 0,
                "alpha": 1,
                "bounds": {"X": 20, "Y": 20, "Width": 1200, "Height": 800},
            },
        ]

        selected = select_working_window(
            windows,
            focused_app="Cursor",
            focused_title="screenlog/window.py",
        )

        self.assertIsNotNone(selected)
        self.assertEqual(selected["window_id"], 30)
        self.assertEqual(selected["selection_reason"], "focused_app_visible_window")

    def test_returns_none_when_no_visible_normal_window_exists(self):
        windows = [
            {
                "window_id": 50,
                "owner_name": "Dock",
                "window_title": "",
                "layer": 20,
                "alpha": 1,
                "bounds": {"X": 0, "Y": 0, "Width": 100, "Height": 100},
            }
        ]

        selected = select_working_window(windows, focused_app="Dock", focused_title="")

        self.assertIsNone(selected)


if __name__ == "__main__":
    unittest.main()
