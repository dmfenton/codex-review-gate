from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CALLER = (ROOT / ".github/workflows/codex-p1-gate.yml").read_text()
GATE = (ROOT / ".github/workflows/codex-review-gate.yml").read_text()


class WorkflowContractTests(unittest.TestCase):
    def test_gate_remains_automatic_without_polling(self) -> None:
        self.assertIn("push:\n    branches: [main]", CALLER)
        self.assertIn("pull_request_target:", CALLER)
        self.assertIn("ready_for_review, edited, closed", CALLER)
        self.assertIn("pull_request_review:", CALLER)
        self.assertIn("issue_comment:", CALLER)
        self.assertNotIn("schedule:", CALLER)

    def test_caller_serializes_each_pull_request(self) -> None:
        job_start = CALLER.index("jobs:")
        concurrency_start = CALLER.index("concurrency:")
        self.assertGreater(concurrency_start, job_start)
        self.assertIn("group: codex-review-gate-", CALLER)
        self.assertIn("github.event_name == 'push' && 'base-main'", CALLER)
        self.assertIn("cancel-in-progress: true", CALLER)

    def test_base_push_invalidates_without_redispatch(self) -> None:
        self.assertIn("invalidate-base:", GATE)
        self.assertIn("if: inputs.pr_number == '0'", GATE)
        self.assertIn("Base advanced; fresh exact-head review required", GATE)
        self.assertIn('[[ "$base_sha" == "$GITHUB_SHA" ]]', GATE)

    def test_gate_has_minimal_write_permission(self) -> None:
        self.assertIn("statuses: write", GATE)
        self.assertIn("issues: read", GATE)
        self.assertIn("pull-requests: read", GATE)
        self.assertNotIn("issues: write", GATE)
        self.assertNotIn("pull-requests: write", GATE)
        self.assertNotIn("actions: write", GATE)

    def test_gate_never_comments_or_redispatches(self) -> None:
        self.assertNotIn('/comments" -f body', GATE)
        self.assertNotIn("gh workflow run", GATE)
        self.assertNotIn("reconcile-open-pull-requests", GATE)

    def test_gate_runs_on_configurable_runner_pool(self) -> None:
        self.assertIn("runner_labels_json:", GATE)
        self.assertIn("runs-on: ${{ fromJSON(inputs.runner_labels_json) }}", GATE)

    def test_gate_requires_exact_head_and_live_threads(self) -> None:
        self.assertIn('[[ "$reviewed_sha" == "$head_sha" ]]', GATE)
        self.assertIn("reviewThreads(first: 100)", GATE)
        self.assertIn("unresolved Codex review thread", GATE)
        self.assertIn("The base branch advanced after the latest Codex review", GATE)

    def test_gate_publishes_stable_commit_status(self) -> None:
        self.assertIn("statuses/$head_sha", GATE)
        self.assertIn("context='Codex review gate'", GATE)
        self.assertIn("publish_status success", GATE)
        self.assertIn("publish_status failure", GATE)


if __name__ == "__main__":
    unittest.main()
