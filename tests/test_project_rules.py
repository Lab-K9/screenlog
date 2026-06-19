import json
import tempfile
import unittest
from pathlib import Path

from screenlog.project_rules import (
    DEFAULT_PROJECT_KEYWORDS,
    load_summary_rules,
    write_default_summary_rules,
)
from screenlog.summarize import infer_project_hints


class ProjectRulesTests(unittest.TestCase):
    def test_infer_project_hints_uses_external_project_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            rules_path = Path(tmp) / "project-rules.json"
            rules_path.write_text(
                json.dumps(
                    {
                        "project_keywords": {
                            "custom-client": ["CustomClient", "案件X"],
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            rules = load_summary_rules(rules_path)
            hints = infer_project_hints(
                [{"working_title": "CustomClient", "ocr_text": "案件Xの調査"}],
                rules=rules,
            )

        self.assertEqual(hints["custom-client"], 1)

    def test_external_project_rules_merge_with_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            rules_path = Path(tmp) / "project-rules.json"
            rules_path.write_text(
                json.dumps({"project_keywords": {"custom": ["Custom"]}}),
                encoding="utf-8",
            )

            rules = load_summary_rules(rules_path)

        self.assertIn("screenlog", rules.project_keywords)
        self.assertIn("custom", rules.project_keywords)

    def test_invalid_project_rules_fall_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            rules_path = Path(tmp) / "project-rules.json"
            rules_path.write_text("{broken", encoding="utf-8")

            rules = load_summary_rules(rules_path)

        self.assertEqual(rules.project_keywords, DEFAULT_PROJECT_KEYWORDS)

    def test_write_default_summary_rules_creates_editable_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            rules_path = Path(tmp) / "project-rules.json"

            self.assertTrue(write_default_summary_rules(rules_path))
            data = json.loads(rules_path.read_text(encoding="utf-8"))

        self.assertIn("project_keywords", data)
        self.assertIn("topic_keywords", data)


if __name__ == "__main__":
    unittest.main()
