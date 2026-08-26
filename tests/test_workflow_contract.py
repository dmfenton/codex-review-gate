import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CALLER = (ROOT / ".github/workflows/codex-p1-gate.yml").read_text()
GATE = (ROOT / ".github/workflows/codex-review-gate.yml").read_text()


class WorkflowContractTests(unittest.TestCase):
    def test_gate_remains_automatic_with_hourly_thread_reconciliation(self) -> None:
        self.assertIn("schedule:\n    - cron: '17 * * * *'", CALLER)
        self.assertIn("push:\n    branches: [main]", CALLER)
        self.assertIn("pull_request_target:", CALLER)
        self.assertIn("ready_for_review, edited, closed", CALLER)
        self.assertIn("pull_request_review:", CALLER)
        self.assertIn("issue_comment:", CALLER)
        self.assertIn("github.event_name == 'schedule'", CALLER)

    def test_reusable_gate_serializes_per_pull_request(self) -> None:
        self.assertNotIn("concurrency:", CALLER)
        self.assertIn("discover-base-prs:", GATE)
        self.assertIn("matrix:\n        pr_number:", GATE)
        self.assertIn("group: codex-review-gate-${{ github.repository }}-pr-", GATE)
        self.assertIn("cancel-in-progress: true", GATE)

    def test_base_push_invalidates_without_redispatch(self) -> None:
        self.assertIn("invalidate-base:", GATE)
        self.assertIn("needs: discover-base-prs", GATE)
        self.assertIn("Base advanced; fresh exact-head review required", GATE)
        self.assertIn("BASE_RUN_CREATED_AT", GATE)
        self.assertIn("gate_run_created_at", GATE)

    def test_gate_has_minimal_write_permission(self) -> None:
        self.assertIn("statuses: write", GATE)
        self.assertIn("actions: read", GATE)
        self.assertIn("actions: read", CALLER)
        self.assertIn("issues: read", GATE)
        self.assertIn("pull-requests: read", GATE)
        self.assertNotIn("issues: write", GATE)
        self.assertNotIn("pull-requests: write", GATE)
        self.assertNotIn("actions: write", GATE)

    def test_gate_never_comments_or_redispatches(self) -> None:
        self.assertNotIn('/comments" -f body', GATE)
        self.assertNotIn("gh workflow run", GATE)
        self.assertNotIn("reconcile-open-pull-requests", GATE)

    def test_hourly_reconciliation_only_fails_unresolved_threads(self) -> None:
        self.assertIn("reconcile-threads:", GATE)
        self.assertIn("github.event_name != 'push'", GATE)
        self.assertIn("Unresolved Codex review thread remains", GATE)
        reconcile = GATE[GATE.index("  reconcile-threads:") :]
        self.assertNotIn("publish_status success", reconcile)

    def test_gate_runs_on_configurable_runner_pool(self) -> None:
        self.assertIn("runner_labels_json:", GATE)
        self.assertIn("runs-on: ${{ fromJSON(inputs.runner_labels_json) }}", GATE)

    def test_gate_requires_exact_head_and_live_threads(self) -> None:
        self.assertIn('[[ "$reviewed_sha" == "$head_sha" ]]', GATE)
        self.assertIn("reviewThreads(first: 100)", GATE)
        self.assertIn("unresolved Codex review thread", GATE)
        self.assertIn("The base branch advanced after the latest Codex review", GATE)

    def test_gate_streams_unbounded_review_records(self) -> None:
        self.assertIn("| jq -cs", GATE)
        self.assertIn("pulls/$PR_NUMBER/comments?per_page=100", GATE)
        self.assertNotIn('--argjson issues "$issue_pages"', GATE)
        self.assertNotIn('--argjson reviews "$review_pages"', GATE)

    def test_gate_accepts_new_clean_review_shape_only_without_inline_findings(self) -> None:
        self.assertIn("pull_request_review_id == $review_id", GATE)
        self.assertIn("$inline_findings == 0", GATE)
        self.assertIn(
            "Here are some automated review suggestions for this pull request", GATE
        )

    def test_paginated_inline_comments_are_flattened_before_review_filtering(self) -> None:
        pages = [
            [{"pull_request_review_id": 41, "user": {"login": "someone"}}],
            [
                {
                    "pull_request_review_id": 42,
                    "user": {"login": "chatgpt-codex-connector[bot]"},
                }
            ],
        ]
        program = """
          [add[]?
            | select(.pull_request_review_id == $review_id)
            | select((.user.login // "")
              | IN("chatgpt-codex-connector", "chatgpt-codex-connector[bot]"))]
          | length
        """

        result = subprocess.run(
            ["jq", "--argjson", "review_id", "42", program],
            input=json.dumps(pages),
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertEqual("1", result.stdout.strip())

    def test_gate_publishes_stable_commit_status(self) -> None:
        self.assertIn("statuses/$head_sha", GATE)
        self.assertIn("context='Codex review gate'", GATE)
        self.assertIn("publish_status success", GATE)
        self.assertIn("publish_status failure", GATE)


if __name__ == "__main__":
    unittest.main()
