from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CALLER = (ROOT / ".github/workflows/codex-p1-gate.yml").read_text()
GATE = (ROOT / ".github/workflows/codex-review-gate.yml").read_text()


class WorkflowContractTests(unittest.TestCase):
    def test_caller_polls_for_unobservable_thread_state_changes(self) -> None:
        self.assertIn("schedule:\n    - cron: '2-57/5 * * * *'", CALLER)
        self.assertIn("pull-requests: write", CALLER)
        self.assertIn("pull-requests: write", GATE)
        self.assertIn("github.event_name != 'schedule'", GATE)
        self.assertIn("reconcile-open-pull-requests:", GATE)

    def test_run_history_is_scoped_by_pr_title_not_shared_sha(self) -> None:
        self.assertNotIn("any(.pull_requests[]?; .head.sha == $head)", GATE)
        self.assertGreaterEqual(GATE.count(".display_title == $title"), 3)

    def test_shared_head_checks_include_dependabot(self) -> None:
        shared_filters = [
            line
            for line in GATE.splitlines()
            if "shared_head_count=" in line
        ]
        self.assertEqual(len(shared_filters), 3)
        self.assertTrue(all('dependabot[bot]' not in line for line in shared_filters))

    def test_rejected_repository_known_heads_are_invalidated(self) -> None:
        status_attempt = GATE.index('statuses/$rejected_head')
        repository_check = GATE.index('commits/$rejected_head')
        self.assertLess(status_attempt, repository_check)


if __name__ == "__main__":
    unittest.main()
