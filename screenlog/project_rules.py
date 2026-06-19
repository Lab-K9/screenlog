"""Configurable rules for ScreenLog summaries."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from .config import CONFIG_DIR


SUMMARY_RULES_FILE = CONFIG_DIR / "summary-rules.json"

DEFAULT_TOPIC_KEYWORDS = [
    "business-context",
    "BUSINESS-ALLIANCE",
    "Corporate-OS",
    "SCO",
    "IDEE",
    "beyondS",
    "morning routine",
    "now.md",
    "todo",
    "Issue",
    "Slack",
    "Claude",
]

DEFAULT_PROJECT_KEYWORDS = {
    "business-context": [
        "business-context",
        "operator-cockpit",
        "Corporate-OS",
        "source coverage",
    ],
    "sco": [
        "SCO",
        "Paylight",
        "recall-messenger",
        "tc-ai-assistant",
    ],
    "idee-ai-expert": [
        "IDEE",
        "AI顧問",
        "idee-ai-expert",
    ],
    "beyonds-ax": [
        "beyondS",
        "beyonds-ax",
    ],
    "screenlog": [
        "ScreenLog",
        "screenlog",
        "working_app",
    ],
    "claude-config": [
        "claude-config",
        "Skill",
        "skills/",
    ],
}


@dataclass(frozen=True)
class SummaryRules:
    """Keyword rules used by summary generation."""

    topic_keywords: list[str]
    project_keywords: dict[str, list[str]]


def _default_rules() -> SummaryRules:
    return SummaryRules(
        topic_keywords=list(DEFAULT_TOPIC_KEYWORDS),
        project_keywords={
            project: list(keywords)
            for project, keywords in DEFAULT_PROJECT_KEYWORDS.items()
        },
    )


def _string_list(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    keywords = [item for item in value if isinstance(item, str) and item]
    return keywords if len(keywords) == len(value) else None


def _merge_rules(base: SummaryRules, data: object) -> SummaryRules:
    if not isinstance(data, dict):
        return base

    topic_keywords = list(base.topic_keywords)
    configured_topics = _string_list(data.get("topic_keywords"))
    if configured_topics is not None:
        topic_keywords = list(dict.fromkeys(topic_keywords + configured_topics))

    project_keywords = {
        project: list(keywords)
        for project, keywords in base.project_keywords.items()
    }
    configured_projects = data.get("project_keywords")
    if isinstance(configured_projects, dict):
        for project, keywords in configured_projects.items():
            if not isinstance(project, str) or not project:
                continue
            keyword_list = _string_list(keywords)
            if keyword_list is not None:
                project_keywords[project] = keyword_list

    return SummaryRules(
        topic_keywords=topic_keywords,
        project_keywords=project_keywords,
    )


def load_summary_rules(path: Path | None = None) -> SummaryRules:
    """Load summary keyword rules, merging user config with defaults."""
    rules_path = path if path is not None else SUMMARY_RULES_FILE
    rules = _default_rules()
    if not rules_path.exists():
        return rules

    try:
        data = json.loads(rules_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: Could not read summary rules {rules_path}: {e}")
        return rules

    return _merge_rules(rules, data)


def write_default_summary_rules(path: Path | None = None) -> bool:
    """Write an editable default rules file if possible."""
    rules_path = path if path is not None else SUMMARY_RULES_FILE
    rules = _default_rules()
    data = {
        "topic_keywords": rules.topic_keywords,
        "project_keywords": rules.project_keywords,
    }
    try:
        rules_path.parent.mkdir(parents=True, exist_ok=True)
        rules_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return True
    except OSError as e:
        print(f"Warning: Could not write summary rules {rules_path}: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="ScreenLog summary rules")
    parser.add_argument("--init", action="store_true", help="write default rules JSON")
    parser.add_argument("--path", type=Path, default=SUMMARY_RULES_FILE)
    args = parser.parse_args()

    if args.init:
        if write_default_summary_rules(args.path):
            print(f"Summary rules written: {args.path}")
            return 0
        return 1

    rules = load_summary_rules(args.path)
    print(json.dumps({
        "topic_keywords": rules.topic_keywords,
        "project_keywords": rules.project_keywords,
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
