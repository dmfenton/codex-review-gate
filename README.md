# Codex review gate

Shared fail-closed GitHub Actions enforcement for Codex pull-request feedback.

Consumers keep a small event wrapper and call the reusable workflow at an immutable commit SHA:

```yaml
jobs:
  enforce:
    uses: dmfenton/codex-review-gate/.github/workflows/codex-review-gate.yml@<commit-sha>
    with:
      pr_number: ${{ inputs.pr_number || '0' }}
```

The caller must grant `actions: write`, `contents: read`, `issues: write`,
`pull-requests: write`, and `statuses: write`. The caller file must remain named
`.github/workflows/codex-p1-gate.yml` because the workflow redispatches that
entrypoint when review state changes. Its `workflow_dispatch.pr_number` input
must be a string so redispatched PR numbers match the reusable boundary.

The caller must also run on `schedule` at least every five minutes. GitHub exposes
review-thread resolution changes to webhooks, but not as GitHub Actions workflow
triggers. Scheduled reconciliation invalidates reopened threads, while repository
instructions must require a live GraphQL `reviewThreads` audit immediately before
every merge to close the interval between polls.

Every consumer must pin a full commit SHA. Do not reference a mutable branch or tag.

Validate changes with `scripts/validate.sh`.
