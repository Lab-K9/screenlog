import plistlib
import tempfile
import unittest
from pathlib import Path

from screenlog.launch_agent import (
    LAUNCH_AGENT_LABEL,
    render_launch_agent_plist,
    write_launch_agent_plist,
)


class LaunchAgentTests(unittest.TestCase):
    def test_render_launch_agent_plist_opens_fixed_app_at_login(self):
        plist = render_launch_agent_plist(Path("/Users/example/Applications/ScreenLog.app"))

        self.assertEqual(plist["Label"], LAUNCH_AGENT_LABEL)
        self.assertEqual(plist["ProgramArguments"], ["/usr/bin/open", "-a", "/Users/example/Applications/ScreenLog.app"])
        self.assertTrue(plist["RunAtLoad"])

    def test_write_launch_agent_plist_writes_valid_plist(self):
        with tempfile.TemporaryDirectory() as tmp:
            plist_path = Path(tmp) / "com.screenlog.app.plist"

            write_launch_agent_plist(
                plist_path,
                app_path=Path("/Users/example/Applications/ScreenLog.app"),
            )
            data = plistlib.loads(plist_path.read_bytes())

        self.assertEqual(data["Label"], LAUNCH_AGENT_LABEL)
        self.assertEqual(data["ProgramArguments"][2], "/Users/example/Applications/ScreenLog.app")


if __name__ == "__main__":
    unittest.main()
