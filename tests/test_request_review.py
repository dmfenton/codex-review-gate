import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/request-review.py"
spec = importlib.util.spec_from_file_location("request_review", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

BOT = {"login": "chatgpt-codex-connector[bot]"}
OWNER = {"login": "owner"}
P1 = (
    "**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  Fix it"
)
P2 = "**<sub><sub>![P2 Badge](https://img.shields.io/badge/P2-yellow?style=flat)</sub></sub>  Nit"
HEAD = "b" * 40
OLD = "a" * 40
MID = "c" * 40


def review(commit, at="2026-01-01T10:00:00Z", review_id=1):
    return {"id": review_id, "user": BOT, "commit_id": commit, "submitted_at": at, "body": ""}


def finding(body, review_id=1):
    return {"pull_request_review_id": review_id, "user": BOT, "body": body}


def request(at="2026-01-01T09:00:00Z"):
    return {"user": OWNER, "body": "@codex review", "created_at": at, "author_association": "OWNER"}


def receipt(commit, at="2026-01-01T10:00:00Z"):
    body = f"<!-- codex-review-receipt:v1 -->\nCodex Review: no issues.\n**Reviewed commit:** `{commit[:10]}`"
    return {"user": BOT, "body": body, "created_at": at, "author_association": "NONE"}


def report(commit, badge, at="2026-01-01T10:00:00Z"):
    url = f"https://github.com/o/r/blob/{commit}/app.py#L3"
    body = f"### \U0001f4a1 Codex Review\n\n{url}\n{badge}\n"
    return {"user": BOT, "body": body, "created_at": at, "author_association": "NONE"}


def summary(status, commit=OLD, at="2026-01-01T10:00:00Z", findings="null"):
    state = f'{{"code_review":{{"commit_sha":"{commit}","has_any_findings":{findings},"status":"{status}"}}}}'
    body = f"<!-- codex-pull-request-review-summary -->\n<!-- codex-review-state:v1 {state} -->"
    return {
        "user": BOT,
        "body": body,
        "created_at": at,
        "updated_at": at,
        "author_association": "NONE",
    }


class RequestReviewTests(unittest.TestCase):
    def check(self, expected, reviews=(), comments=(), review_comments=(), head=HEAD):
        allowed, message = module.decision(
            head, list(reviews), list(comments), list(review_comments)
        )
        self.assertEqual(allowed, expected, message)

    def test_first_request_is_allowed(self):
        self.check(True)

    def test_second_round_after_blocking_findings(self):
        self.check(True, [review(OLD)], [request(), summary("completed", OLD)], [finding(P1)])

    def test_advisory_only_round_is_final(self):
        self.check(False, [review(OLD)], [request()], [finding(P2)])

    def test_clean_receipt_round_is_final(self):
        self.check(False, comments=[receipt(OLD)])

    def test_clean_summary_without_receipt_is_a_final_round(self):
        self.check(False, comments=[request(), summary("completed", OLD, findings="false")])

    def test_issue_findings_report_counts_as_a_round(self):
        self.check(True, comments=[report(OLD, P1)])
        self.check(False, comments=[report(OLD, P1), report(MID, P1, "2026-01-01T11:00:00Z")])

    def test_budget_counts_completed_outcomes(self):
        self.check(False, [review(OLD)], [receipt(MID, "2026-01-01T11:00:00Z")], [finding(P1)])

    def test_exact_head_already_reviewed(self):
        self.check(False, [review(HEAD)], review_comments=[finding(P1)])

    def test_running_review_blocks(self):
        self.check(False, comments=[request(), summary("running", HEAD)])

    def test_unanswered_request_is_pending(self):
        self.check(False, comments=[request()])

    def test_failed_attempt_does_not_spend_budget(self):
        self.check(True, comments=[request(), summary("failed", HEAD, "2026-01-01T09:05:00Z")])

    def test_summary_with_findings_is_not_a_separate_round(self):
        comments = [request(), summary("completed", OLD, findings="true")]
        self.check(True, [review(OLD)], comments, [finding(P1)])

    def test_origin_pattern_reads_owner_and_name(self):
        for url in (
            "https://github.com/o/r",
            "https://github.com/o/r.git",
            "git@github.com:o/r.git",
            "http://proxy@127.0.0.1:8080/git/o/r",
        ):
            self.assertEqual(module.ORIGIN.search(url)[1], "o/r", url)

    def test_untrusted_request_is_ignored(self):
        self.check(True, comments=[{**request(), "author_association": "NONE"}])


if __name__ == "__main__":
    unittest.main()
