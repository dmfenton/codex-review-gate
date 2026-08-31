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
                        "| Code Review | **Completed** <relative-time "
                        'datetime="2026-08-29T11:33:00Z">now</relative-time> '
                        "| `de72c2e` | PR opened |",
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
                  "\\*\\*Completed\\*\\*[^\\n]*datetime=\\\"(?<started>[^\\\"]+)\\\"[^\\n]*\\|[[:space:]]*`(?<sha>[0-9a-fA-F]{7,40})`[[:space:]]*\\|"
                )) catch {}) as $completion
              | select(($completion.sha // "") != "")
              | select(any($reactions | add[]?;
                  ((.user.login // "")
                    | IN("chatgpt-codex-connector", "chatgpt-codex-connector[bot]")) and
                  .content == "+1" and
                  .created_at >= $completion.started and
                  ((((.created_at | fromdateiso8601) -
                    ($summary.updated_at | fromdateiso8601)) | fabs) <= 300)))
              | {id, commit_id: $completion.sha, kind: "summary"}
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

        records[1][0][0]["created_at"] = "2026-08-29T11:32:59Z"
        prior_review_result = subprocess.run(
            ["jq", "-cs", program],
            input="\n".join(json.dumps(page) for page in records),
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual([], json.loads(prior_review_result.stdout))

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

    def test_review_round_count_uses_completed_distinct_review_heads(self) -> None:
        self.assertNotIn("manual_review_requests=", GATE)
        self.assertNotIn("requested_review_rounds=", GATE)
        self.assertIn("reviewed_ref:", GATE)
        self.assertIn('map(select(.reviewed_ref | test("^[0-9a-f]{7,40}$")))', GATE)
        self.assertIn("reduce .[] as $review", GATE)

        program = r'''
          .[0] as $records
          | .[1] as $manual_requests
          | $records
          | map(. + {
            reviewed_ref: (
              if (.commit_id // "") != "" then .commit_id
              else (try (.body | capture(
                "Reviewed commit:[^0-9a-fA-F]*(?<sha>[0-9a-fA-F]{7,40})"
              ).sha) catch "")
              end
              | ascii_downcase
            )
          })
          | map(select(.reviewed_ref | test("^[0-9a-f]{7,40}$")))
          | sort_by(.occurred_at, .id)
          | map(. as $review
              | ($manual_requests
                  | map(select(.created_at <= $review.occurred_at))
                  | last.id // null) as $request_id
              | . + {
                  round_key: (
                    if $request_id == null
                    then "automatic:\(.reviewed_ref[0:7])"
                    else "manual:\($request_id)"
                    end
                  )
                })
          | reduce .[] as $review ([];
              map(select(.round_key != $review.round_key)) + [$review])
        '''
        records = [
            {
                "id": 1,
                "kind": "review",
                "commit_id": "89856cce8ea68313eb79fdb78054f7b808658be3",
                "body": "Codex Review with findings",
                "occurred_at": "2026-08-31T15:08:08Z",
            },
            {
                "id": 2,
                "kind": "review",
                "commit_id": "50333f69def9011adfd2e524a1ce95914dcc93b6",
                "body": "Codex Review with findings",
                "occurred_at": "2026-08-31T15:28:15Z",
            },
            {
                "id": 3,
                "kind": "issue",
                "commit_id": "",
                "body": "Codex Review: Something went wrong. Try again later.",
                "occurred_at": "2026-08-31T15:46:47Z",
            },
            {
                "id": 4,
                "kind": "issue",
                "commit_id": "",
                "body": "Codex Review: Didn't find any major issues. "
                "Reviewed commit: `d6caf508f0`",
                "occurred_at": "2026-08-31T16:19:59Z",
            },
            {
                "id": 5,
                "kind": "summary",
                "commit_id": "d6caf50",
                "body": "Codex Review Summary",
                "occurred_at": "2026-08-31T16:20:08Z",
            },
        ]
        manual_requests = [
            {"id": 101, "created_at": "2026-08-31T15:00:00Z"},
            {"id": 102, "created_at": "2026-08-31T15:20:00Z"},
            {"id": 103, "created_at": "2026-08-31T15:35:25Z"},
            {"id": 104, "created_at": "2026-08-31T16:15:36Z"},
        ]

        result = subprocess.run(
            ["jq", program],
            input=json.dumps([records, manual_requests]),
            text=True,
            capture_output=True,
            check=True,
        )
        normalized = json.loads(result.stdout)

        self.assertEqual(3, len(normalized))
        self.assertEqual(
            ["89856cce8ea68313eb79fdb78054f7b808658be3", "50333f69def9011adfd2e524a1ce95914dcc93b6", "d6caf50"],
            [review["reviewed_ref"] for review in normalized],
        )
        self.assertEqual("summary", normalized[-1]["kind"])
        self.assertEqual(
            ["manual:101", "manual:102", "manual:104"],
            [review["round_key"] for review in normalized],
        )

        repeated_success = records + [
            {
                "id": 6,
                "kind": "issue",
                "commit_id": "",
                "body": "Codex Review: Didn't find any major issues. "
                "Reviewed commit: `d6caf508f0`",
                "occurred_at": "2026-08-31T16:30:00Z",
            }
        ]
        repeated_requests = manual_requests + [
            {"id": 105, "created_at": "2026-08-31T16:25:00Z"}
        ]
        repeated_result = subprocess.run(
            ["jq", program],
            input=json.dumps([repeated_success, repeated_requests]),
            text=True,
            capture_output=True,
            check=True,
        )
        repeated_normalized = json.loads(repeated_result.stdout)

        self.assertEqual(4, len(repeated_normalized))
        self.assertEqual(
            ["manual:101", "manual:102", "manual:104", "manual:105"],
            [review["round_key"] for review in repeated_normalized],
        )

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

    def test_record_commit_metadata_wins_when_body_omits_label(self) -> None:
        program = r'''
          ([.body | capture("Reviewed commit:[^0-9a-fA-F]*(?<sha>[0-9a-fA-F]{7,40})").sha]
            | first // "") as $body_sha
          | if (.commit_id // "") != "" then .commit_id else $body_sha end
        '''
        payload = {
            "kind": "summary",
            "commit_id": "33f18d1",
            "body": "<!-- codex-pull-request-review-summary --> completed",
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
