# Codex review gate

Shared fail-closed GitHub Actions enforcement for Codex pull-request feedback.

The gate remains automatic. It publishes the `Codex review gate` commit status
on the live pull-request head and succeeds only when all of these are true:

- the latest Codex review covers the exact current head SHA and contains no P0/P1 finding;
- or, after the second and final review reports findings, the current head is a
  descendant that addresses its P0/P1 findings and all blocking Codex threads are resolved;
- the review happened after the current base commit;
- the pull request head and base stay unchanged during the audit; and
- live GraphQL `reviewThreads` contains no unresolved P0/P1 Codex thread; and
- no commit in the current branch's post-base ancestry, and no prior use of the
  source branch itself, identifies a closed unmerged pull request against that base.

Finding-free connector reviews may be represented by the bot's completed summary
plus a pull-request thumbs-up. The gate accepts that shape only when the summary
names the reviewed commit and the bot-owned reaction follows that review's start
within the summary completion window. Review rounds are authoritative completed
connector outcomes. A trigger comment alone and a connector error do not consume
the review budget; pending and failed attempts remain fail-closed until a
completed outcome exists. A summary published within 30 seconds of an explicit
completion for the same commit is the duplicate status artifact for that round.
Separate completed outcomes remain separate rounds even when they review the
same commit. Stale, user-authored, running, and unbound signals fail closed.

The workflow does not post comments or redispatch itself. An hourly self-hosted
sentinel fails any PR head with a reopened or otherwise unresolved P0/P1 Codex thread;
it never publishes success. This backstops GitHub Actions' lack of a review-thread
resolution trigger without generating another Codex review. A base-branch
push runs one shared discovery job and fans out invalidation jobs inside that
workflow; it does not create per-PR workflow runs. Each invalidation shares a
per-PR concurrency group with that PR's audits. A replacing audit revalidates
the live base, while a delayed invalidation preserves gate results from runs
created after the base push. Consumers audit on pull-request
head/base changes, authenticated Codex review activity, explicit `@codex review`
comments, and optional manual dispatch. New eligible activity supersedes only
older work for the same PR; ignored webhook activity never enters the queue.
After legitimately resolving a fixed thread, manually dispatch the gate for the
current PR instead of waiting for the hourly sentinel.
Closing a pull request also runs the audit so its commit-scoped success is
replaced with failure before the head SHA can be reused by another PR.

Review is capped by policy at two Codex rounds, then the pull request merges.
P0/P1 findings are blocking; P2/P3 findings are advisory even when valid.
Request the first review only after implementation and checks are complete.
If it reports blocking findings, address them together and request one final
review. After the final round, fix any blockers it reports, resolve the
corresponding blocking threads, rerun the repository checks, and manually
dispatch the gate; never request a third review. The gate then accepts any head
that descends from the final reviewed commit with no unresolved blocking Codex
thread, whether the later commits fix blockers, take advisory findings, or
merge the base branch. Before the final round, an unreviewed head still needs
its remaining round. Advisory findings never require another review, thread
resolution, or a follow-up issue. If more than two completed reviews already
exist, the gate warns but evaluates the latest result; exceeding the request
budget must never become a permanent merge blocker. The base branch advancing
after the latest review is a warning, not a block. Adding commits on top of a closed unmerged pull-request
head, or rewriting that source branch, cannot reset the budget.

Consumers keep a small event wrapper and pin the reusable workflow to a full
commit SHA:

```yaml
permissions:
  actions: read
  contents: read
  issues: read
  pull-requests: read
  statuses: write

jobs:
  enforce:
    uses: dmfenton/codex-review-gate/.github/workflows/codex-review-gate.yml@<commit-sha>
    with:
      pr_number: ${{ github.event.pull_request.number || github.event.issue.number || inputs.pr_number }}
      runner_labels_json: '["self-hosted","lilserver"]'
```

Every consumer must pin a full commit SHA. Do not reference a mutable branch or
tag. Keep the caller at `.github/workflows/codex-p1-gate.yml` so the commit
status context stays consistent across repositories.

The connector's persistent `Codex Review Summary` status comment can prove a
completed clean review, but duplicate records produced by that same review
completion are one round. Only completed finding or clean-review outcomes count
toward the two-round request budget. Extra completed outcomes do not fail the
gate.

Validate changes with `scripts/validate.sh`.
