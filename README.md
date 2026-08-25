# Codex review gate

Shared fail-closed GitHub Actions enforcement for Codex pull-request feedback.

The gate remains automatic. It publishes the `Codex review gate` commit status
on the live pull-request head and succeeds only when all of these are true:

- the latest Codex review is clean and covers the exact current head SHA;
- the review happened after the current base commit;
- the pull request head and base stay unchanged during the audit; and
- live GraphQL `reviewThreads` contains no unresolved Codex thread.

The workflow does not poll, post comments, or redispatch itself. A base-branch
push runs one shared invalidation job that marks existing PR-head statuses
failed; it does not create per-PR workflow runs, and a newer base push cancels
an older invalidation still in progress. Consumers audit on pull-request
head/base changes, authenticated Codex review activity, explicit `@codex review`
comments, and optional manual dispatch. Job-level per-PR concurrency cancels
only superseded eligible audits; ignored webhook activity cannot cancel one.
Closing a pull request also runs the audit so its commit-scoped success is
replaced with failure before the head SHA can be reused by another PR.

Consumers keep a small event wrapper and pin the reusable workflow to a full
commit SHA:

```yaml
permissions:
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

Validate changes with `scripts/validate.sh`.
