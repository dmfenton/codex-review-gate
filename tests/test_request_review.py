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


def review(commit, at="2026-01-01T10:00:00Z"):
    return {"user": BOT, "commit_id": commit, "submitted_at": at}


def request(at="2026-01-01T09:00:00Z"):
    return {"user": OWNER, "body": "@codex review", "created_at": at, "author_association": "OWNER"}


def receipt(commit, at="2026-01-01T10:00:00Z"):
    body = f"<!-- codex-review-receipt:v1 -->\nCodex Review: no issues.\n**Reviewed commit:** `{commit[:10]}`"
    return {"user": BOT, "body": body, "created_at": at, "author_association": "NONE"}


def summary(status, commit="a" * 40, at="2026-01-01T10:00:00Z"):
    body = (
        "<!-- codex-pull-request-review-summary -->\n"
        f'<!-- codex-review-state:v1 {{"code_review":{{"commit_sha":"{commit}","status":"{status}"}}}} -->'
    )
    return {"user": BOT, "body": body, "created_at": at, "updated_at": at, "author_association": "NONE"}


HEAD = "b" * 40
OLD = "a" * 40


class RequestReviewTests(unittest.TestCase):
    def check(self, reviews, comments, expected, head=HEAD):
        allowed, message = module.decision(head, reviews, comments)
        self.assertEqual(allowed, expected, message)

    def test_first_request_is_allowed(self):
        self.check([], [], True)

    def test_second_round_after_findings_on_older_head(self):
        self.check([review(OLD)], [request(), summary("completed", OLD)], True)

    def test_budget_counts_completed_outcomes(self):
        self.check([review(OLD)], [receipt("c" * 40, "2026-01-01T11:00:00Z")], False)

    def test_exact_head_already_reviewed(self):
        self.check([], [receipt(HEAD)], False)

    def test_running_review_blocks(self):
        self.check([], [request(), summary("running", HEAD)], False)

    def test_unanswered_request_is_pending(self):
        self.check([], [request()], False)

    def test_failed_attempt_does_not_spend_budget(self):
        self.check([], [request(), summary("failed", HEAD, "2026-01-01T09:05:00Z")], True)

    def test_summary_is_not_a_round(self):
        body = summary("completed", OLD)["body"] + "\n**Reviewed commit:** `aaaaaaaaaa`"
        self.check([], [{**summary("completed", OLD), "body": body}], True)

    def test_untrusted_request_is_ignored(self):
        self.check([], [{**request(), "author_association": "NONE"}], True)


if __name__ == "__main__":
    unittest.main()
