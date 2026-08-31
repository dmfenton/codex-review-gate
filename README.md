# Codex review gate

Shared fail-closed GitHub Actions enforcement for Codex pull-request feedback.

The gate remains automatic. It publishes the `Codex review gate` commit status
on the live pull-request head and succeeds only when all of these are true:

- the latest Codex review is clean and covers the exact current head SHA;
- or, after the second and final review reports findings, the current head is a
  descendant that addresses them and all Codex threads are resolved;
- the review happened after the current base commit;
- the pull request head and base stay unchanged during the audit; and
- live GraphQL `reviewThreads` contains no unresolved Codex thread.

Finding-free connector reviews may be represented by the bot's completed summary
plus a pull-request thumbs-up. The gate accepts that shape only when the summary
names the reviewed commit and the bot-owned reaction follows that review's start
within the summary completion window. Review rounds are completed connector
outcomes, deduplicated by reviewed commit. Manual trigger comments and connector
errors do not consume the review budget; pending and failed attempts remain
fail-closed until a completed outcome exists. Stale, user-authored, running,
unbound, and over-budget signals fail closed.

The workflow does not post comments or redispatch itself. An hourly self-hosted
sentinel fails any PR head with a reopened or otherwise unresolved Codex thread;
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

Review work is capped at two Codex rounds. Request the first review only after
implementation and checks are complete. If it reports findings, address all of
them together and request one final review. If that final review finds more,
address those findings, resolve the corresponding threads, rerun the repository
checks, and manually dispatch the gate without requesting a third review. The
gate accepts that final remediation only when the reviewed commit is an ancestor
of the current head and no Codex thread remains unresolved. A clean review never
authorizes later unreviewed changes. More than two completed Codex reviews fail
the gate instead of silently extending the review budget.

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
completed clean review, but duplicate records for that same reviewed commit are
one round. Only distinct completed finding or clean-review outcomes count toward
the hard two-round limit.

Validate changes with `scripts/validate.sh`.
