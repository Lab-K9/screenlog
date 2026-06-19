import unittest
from pathlib import Path


class CIWorkflowTests(unittest.TestCase):
    def test_github_actions_ci_runs_tests_and_build_checks(self):
        workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

        self.assertIn("macos-", workflow)
        self.assertIn("venv/bin/python -m unittest discover -v", workflow)
        self.assertIn("venv/bin/python -m compileall screenlog", workflow)
        self.assertIn("bash -n scripts/build-app.sh", workflow)
        self.assertIn("./scripts/build-app.sh", workflow)


if __name__ == "__main__":
    unittest.main()
