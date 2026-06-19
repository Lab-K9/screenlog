import unittest
from pathlib import Path


class LocalOperationsTests(unittest.TestCase):
    def test_install_local_app_uses_stable_user_app_path_and_build_script(self):
        script = Path("scripts/install-local-app.sh").read_text(encoding="utf-8")

        self.assertIn("SCREENLOG_APP_DEST", script)
        self.assertIn("$HOME/Applications/ScreenLog.app", script)
        self.assertIn("./scripts/build-app.sh", script)
        self.assertIn("codesign --verify --deep --strict", script)

    def test_launch_agent_scripts_use_screenlog_launch_agent_module(self):
        install_script = Path("scripts/install-launch-agent.sh").read_text(encoding="utf-8")
        uninstall_script = Path("scripts/uninstall-launch-agent.sh").read_text(encoding="utf-8")

        self.assertIn("screenlog.launch_agent install", install_script)
        self.assertIn("launchctl bootstrap", install_script)
        self.assertIn("screenlog.launch_agent uninstall", uninstall_script)
        self.assertIn("launchctl bootout", uninstall_script)


if __name__ == "__main__":
    unittest.main()
