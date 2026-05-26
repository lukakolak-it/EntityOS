from __future__ import annotations

import json
import unittest
from pathlib import Path

from target_radar.use_cases import validate_use_case_config


ROOT = Path(__file__).resolve().parents[1]


class ReleaseDocsTests(unittest.TestCase):
    def test_open_source_metadata_files_exist(self) -> None:
        required_files = [
            "LICENSE",
            "CONTRIBUTING.md",
            "CODE_OF_CONDUCT.md",
            "SECURITY.md",
            "CHANGELOG.md",
            "README.md",
            "docs/releases/v0.1.0-local-osint.md",
            "docs/demo/walkthrough.md",
            "docs/planning/post-v0.1-roadmap.md",
        ]

        for relative_path in required_files:
            with self.subTest(path=relative_path):
                path = ROOT / relative_path
                self.assertTrue(path.is_file(), f"missing {relative_path}")
                self.assertGreater(path.stat().st_size, 0, f"empty {relative_path}")

    def test_feedback_templates_and_labels_cover_release_channels(self) -> None:
        issue_templates = [
            "bug_report.yml",
            "eval_case.yml",
            "use_case.yml",
            "provider_issue.yml",
            "docs_issue.yml",
        ]
        for file_name in issue_templates:
            with self.subTest(template=file_name):
                self.assertTrue((ROOT / ".github" / "ISSUE_TEMPLATE" / file_name).is_file())

        labels = (ROOT / ".github" / "labels.yml").read_text(encoding="utf-8")
        for label in ("bug", "eval-case", "use-case", "provider", "docs", "privacy"):
            with self.subTest(label=label):
                self.assertIn(f"name: {label}", labels)

    def test_example_use_cases_are_importable(self) -> None:
        example_paths = [
            ROOT / "examples" / "use-cases" / "company-osint-demo.json",
            ROOT / "examples" / "use-cases" / "open-source-project-research.json",
        ]

        for path in example_paths:
            with self.subTest(path=path.name):
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(payload["format"], "target-radar-use-case-v1")
                validate_use_case_config(payload["use_case"])

    def test_release_walkthrough_documents_secret_free_demo_path(self) -> None:
        walkthrough = (ROOT / "docs" / "demo" / "walkthrough.md").read_text(encoding="utf-8")

        self.assertIn("fake", walkthrough)
        self.assertIn("/#dashboard", walkthrough)
        self.assertIn("/#runs", walkthrough)
        self.assertIn("/#review", walkthrough)
        self.assertIn("/#secrets", walkthrough)
        self.assertIn("examples/use-cases/company-osint-demo.json", walkthrough)

    def test_release_notes_and_ci_document_quality_gates(self) -> None:
        release_notes = (
            ROOT / "docs" / "releases" / "v0.1.0-local-osint.md"
        ).read_text(encoding="utf-8")
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        self.assertIn("v0.1.0-local-osint", release_notes)
        self.assertIn("privacy-check", release_notes)
        for gate in ("unittest", "evaluate", "privacy-check", "node --check"):
            with self.subTest(gate=gate):
                self.assertIn(gate, ci)

    def test_sprint_decision_merge_uses_rating_action_vocabulary(self) -> None:
        roadmap = (ROOT / "docs" / "planning" / "sprints-und-slices.md").read_text(
            encoding="utf-8"
        )
        decision_merge = roadmap.split("### Slice 5.5: Decision Merge", 1)[1].split(
            "### Slice 5.6: Rating-Versionen",
            1,
        )[0]

        for action in ("skip", "review", "draft"):
            with self.subTest(action=action):
                self.assertIn(f"`{action}`", decision_merge)
        for stale_action in (
            "recommended",
            "maybe",
            "reject",
            "needs_context",
            "needs_review",
        ):
            with self.subTest(stale_action=stale_action):
                self.assertNotIn(f"`{stale_action}`", decision_merge)


if __name__ == "__main__":
    unittest.main()
