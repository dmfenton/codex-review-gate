#!/usr/bin/env python3
"""Request a Codex review for a pull request when the two-round budget allows it.

Canonical copy: dmfenton/codex-review-gate scripts/request-review.py. Consumer repositories keep
an identical copy at scripts/request-review.py; change it here first, then copy it.

Run without --request to print the decision. With --request it posts `@codex review` only when
the PR is open, ready (not a draft), targets the base branch, and the rules below allow a round.
Counting follows the gate's README: only completed Codex outcomes consume the budget. A trigger
comment that Codex never completed does not, so a failed attempt can be requested again.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass

BOTS = {"chatgpt-codex-connector", "chatgpt-codex-connector[bot]"}
TRUSTED = {"OWNER", "MEMBER", "COLLABORATOR"}
ROUND_BUDGET = 2  # limit: dmfenton/codex-review-gate two-round review policy (README)
RECEIPT = re.compile(r"Reviewed commit:\*\*\s*`([0-9a-f]{7,40})`")
STATE = re.compile(r"<!-- codex-review-state:v1 (\{.*?\}) -->")
SUMMARY = "<!-- codex-pull-request-review-summary -->"
RETRYABLE = {"failed", "error", "errored", "cancelled", "canceled", "timed_out"}


@dataclass(frozen=True)
class Outcome:
    commit: str
    at: str


def _bot(item: dict) -> bool:
    return item["user"]["login"] in BOTS


def completed_rounds(reviews: list[dict], comments: list[dict]) -> list[Outcome]:
    """Codex review objects (findings) plus clean-review receipts, which are issue comments."""
    rounds = [Outcome(r["commit_id"], r.get("submitted_at") or "") for r in reviews if _bot(r)]
    for c in comments:
        match = RECEIPT.search(c["body"]) if _bot(c) and SUMMARY not in c["body"] else None
        if match:
            rounds.append(Outcome(match[1], c["created_at"]))
    return rounds


def summary_status(comments: list[dict]) -> tuple[str, str]:
    """(status, updated_at) of the connector's persistent summary, or ("", "")."""
    summaries = [c for c in comments if _bot(c) and SUMMARY in c["body"]]
    if not summaries:
        return "", ""
    latest = summaries[-1]
    match = STATE.search(latest["body"])
    status = ""
    if match:
        status = (json.loads(match[1]).get("code_review") or {}).get("status") or ""
    elif "**Running**" in latest["body"]:
        status = "running"
    return status.lower(), latest.get("updated_at") or latest["created_at"]


def decision(head: str, reviews: list[dict], comments: list[dict]) -> tuple[bool, str]:
    rounds = completed_rounds(reviews, comments)
    if len(rounds) >= ROUND_BUDGET:
        return False, (
            "Review budget spent (two completed Codex rounds). Fix agreed P0/P1 blockers, rerun "
            "checks, resolve those threads, dispatch the gate "
            "(gh workflow run codex-p1-gate.yml -f pr_number=<PR>), and merge. Never request a third review."
        )
    if any(head.startswith(r.commit) or r.commit.startswith(head) for r in rounds):
        return False, "This head already has a completed Codex review. Do not request it again."
    status, status_at = summary_status(comments)
    if status in {"running", "queued", "pending", "in_progress"}:
        return False, "A Codex review is already running. Wait for it."
    last_done = max((r.at for r in rounds), default="")
    requests = [c for c in comments if not _bot(c) and "@codex review" in c["body"]
                and c.get("author_association") in TRUSTED and c["created_at"] > last_done]
    if requests and not (status in RETRYABLE and status_at > requests[-1]["created_at"]):
        return False, "A review request is already pending. Wait for Codex before requesting again."
    return True, f"Ready for review round {len(rounds) + 1}/{ROUND_BUDGET}."


def gh(*args: str):
    return json.loads(subprocess.check_output(["gh", *args], text=True))


def pages(resource: str) -> list[dict]:
    return [item for page in gh("api", "--paginate", "--slurp", resource) for item in page]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pr", type=int)
    parser.add_argument("--request", action="store_true", help="post the request when eligible")
    parser.add_argument("--repo", help="owner/name; defaults to the current checkout's repository")
    parser.add_argument("--base", default="main", help="required base branch (default main)")
    args = parser.parse_args()
    repo = args.repo or gh("repo", "view", "--json", "nameWithOwner")["nameWithOwner"]
    pr = gh("api", f"repos/{repo}/pulls/{args.pr}")
    if pr["state"] != "open" or pr["base"]["ref"] != args.base:
        print(f"Review requests require an open PR targeting {args.base}.")
        return 1
    if pr["draft"]:
        print(f"PR is a draft. When it is ready, run `gh pr ready {args.pr}` and request again.")
        return 1
    allowed, message = decision(
        pr["head"]["sha"],
        pages(f"repos/{repo}/pulls/{args.pr}/reviews?per_page=100"),
        pages(f"repos/{repo}/issues/{args.pr}/comments?per_page=100"),
    )
    print(message)
    if not allowed:
        return 1
    if args.request:
        subprocess.run(["gh", "api", "--method", "POST", f"repos/{repo}/issues/{args.pr}/comments",
                        "-f", "body=@codex review", "--silent"], check=True)
        print(f"Requested Codex review on {repo}#{args.pr}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
