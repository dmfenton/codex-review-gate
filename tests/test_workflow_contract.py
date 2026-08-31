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
        self.assertIn('if [[ "$reviewed_sha" == "$head_sha" ]]', GATE)
        self.assertIn("reviewThreads(first: 100)", GATE)
        self.assertIn("unresolved Codex review thread", GATE)
        self.assertIn("The base branch advanced after the latest Codex review", GATE)

    def test_gate_caps_review_rounds_with_bounded_remediation(self) -> None:
        self.assertNotIn("max_review_rounds:", GATE)
        self.assertIn("MAX_REVIEW_ROUNDS: 2", GATE)
        self.assertIn("review_rounds=\"$(jq 'length'", GATE)
        self.assertIn("review_rounds <= MAX_REVIEW_ROUNDS", GATE)
        self.assertIn("review_rounds == MAX_REVIEW_ROUNDS", GATE)
        self.assertIn("Codex review limit exceeded", GATE)
        self.assertIn("compare/$reviewed_sha...$head_sha", GATE)
        self.assertIn('[[ "$compare_status" == ahead ]]', GATE)
        self.assertIn("final-round findings remediated", GATE)

    def test_clean_review_summary_requires_timely_codex_reaction(self) -> None:
        self.assertIn(
            'contains("<!-- codex-pull-request-review-summary -->") | not', GATE
        )
        self.assertIn("issues/$PR_NUMBER/reactions?per_page=100", GATE)
        self.assertIn("fromdateiso8601", GATE)
        records = [
            [
                [
                    {
                        "id": 1,
                        "body": "<!-- codex-pull-request-review-summary -->\n"
                        "## Codex Review Summary\n"
                        "| Review | Status | Commit | Review trigger |\n"
                        "| --- | --- | --- | --- |\n"
                        "| Code Review | **Completed** now | `de72c2e` | PR opened |",
                        "created_at": "2026-08-29T11:27:31Z",
                        "updated_at": "2026-08-29T11:34:55Z",
                        "user": {"login": "chatgpt-codex-connector"},
                    },
                ]
            ],
            [
                [
                    {
                        "content": "+1",
                        "created_at": "2026-08-29T11:34:54Z",
                        "user": {"login": "chatgpt-codex-connector[bot]"},
                    }
                ]
            ],
        ]
        program = r"""
          .[0] as $issues
          | .[1] as $reactions
          | [
              $issues | add[]?
              | select((.user.login // "")
                  | IN("chatgpt-codex-connector", "chatgpt-codex-connector[bot]"))
              | select(.body | contains("<!-- codex-pull-request-review-summary -->"))
              | . as $summary
              | (try (.body | capture(
                  "\\*\\*Completed\\*\\*[^\\n]*\\|[[:space:]]*`(?<sha>[0-9a-fA-F]{7,40})`[[:space:]]*\\|"
                ).sha) catch "") as $sha
              | select($sha != "")
              | select(any($reactions | add[]?;
                  ((.user.login // "")
                    | IN("chatgpt-codex-connector", "chatgpt-codex-connector[bot]")) and
                  .content == "+1" and
                  ((((.created_at | fromdateiso8601) -
                    ($summary.updated_at | fromdateiso8601)) | fabs) <= 300)))
              | {id, commit_id: $sha, kind: "summary"}
            ]
        """

        result = subprocess.run(
            ["jq", "-cs", program],
            input="\n".join(json.dumps(page) for page in records),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)

        normalized = json.loads(result.stdout)
        self.assertEqual([{"id": 1, "commit_id": "de72c2e", "kind": "summary"}], normalized)

        records[1][0][0]["created_at"] = "2026-08-29T10:00:00Z"
        stale_result = subprocess.run(
            ["jq", "-cs", program],
            input="\n".join(json.dumps(page) for page in records),
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual([], json.loads(stale_result.stdout))

        records[1][0][0]["created_at"] = "2026-08-29T11:34:54Z"
        records[1][0][0]["user"]["login"] = "someone-else"
        wrong_actor_result = subprocess.run(
            ["jq", "-cs", program],
            input="\n".join(json.dumps(page) for page in records),
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual([], json.loads(wrong_actor_result.stdout))

        records[1][0][0]["user"]["login"] = "chatgpt-codex-connector[bot]"
        records[0][0][0]["body"] = records[0][0][0]["body"].replace(
            "**Completed**", "**Running**"
        )
        running_result = subprocess.run(
            ["jq", "-cs", program],
            input="\n".join(json.dumps(page) for page in records),
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual([], json.loads(running_result.stdout))

    def test_bounded_remediation_requires_findings_and_resolved_threads(self) -> None:
        self.assertIn('[[ "$clean_review" == false ]]', GATE)
        self.assertIn("current head is not a remediation descendant", GATE)
        self.assertIn("(( unresolved == 0 ))", GATE)

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

    def test_review_commit_metadata_wins_when_body_omits_label(self) -> None:
        program = r'''
          if .kind == "review" and .commit_id != "" then
            .commit_id
          else
            ([.body | capture("Reviewed commit:[^0-9a-fA-F]*(?<sha>[0-9a-fA-F]{7,40})").sha]
              | first // "")
          end
        '''
        payload = {
            "kind": "review",
            "commit_id": "9782bbc22efaab907799868a86edbec32f133fa9",
            "body": "Codex Review: finding with a source link but no commit label",
        }

        result = subprocess.run(
            ["jq", "-r", program],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertEqual(payload["commit_id"], result.stdout.strip())

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
