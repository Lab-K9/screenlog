import json
import tempfile
import unittest
from pathlib import Path

from screenlog.project_rules import (
    DEFAULT_PROJECT_KEYWORDS,
    keyword_matches,
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

    def test_ascii_keyword_word_boundary(self):
        # SCOはASCII英字のみのキーワード。前後がASCII英字の一部として
        # 出現している場合（vscode / scope外）は誤爆として不一致にする。
        self.assertFalse(keyword_matches("SCO", "vscode"))
        self.assertFalse(keyword_matches("SCO", "scope外".casefold()))
        # 大文字小文字が異なっても境界判定は同じくfalseになる
        self.assertFalse(keyword_matches("SCO", "ivscoded".casefold()))

    def test_ascii_keyword_allows_digit_and_hyphen(self):
        # 数字・記号・日本語文字は境界として扱われるため、マッチを維持する。
        self.assertTrue(keyword_matches("SCO", "sco2700万".casefold()))
        self.assertTrue(keyword_matches("SCO", "sco-hub".casefold()))
        self.assertTrue(keyword_matches("SCO", "次はscoの".casefold()))
        # 単語として独立して出現していれば通常通りマッチする
        self.assertTrue(keyword_matches("SCO", "SCO定例".casefold()))

    def test_japanese_keyword_substring(self):
        # 非ASCII文字を含むキーワードは従来通りcasefold部分一致。
        self.assertTrue(keyword_matches("案件X", "続き案件Xの調査".casefold()))
        self.assertFalse(keyword_matches("案件X", "無関係なテキスト".casefold()))

    def test_default_project_keywords_minimal(self):
        # DEFAULT_PROJECT_KEYWORDSはscreenlog自身のみに縮小されている。
        # 実運用辞書はsummary-rules.jsonが正。
        self.assertEqual(
            DEFAULT_PROJECT_KEYWORDS,
            {"screenlog": ["ScreenLog", "screenlog", "working_app"]},
        )


if __name__ == "__main__":
    unittest.main()
