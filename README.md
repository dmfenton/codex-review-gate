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
`pull-requests: read`, and `statuses: write`. The caller file must remain named
`.github/workflows/codex-p1-gate.yml` because the workflow redispatches that
entrypoint when review state changes.

Every consumer must pin a full commit SHA. Do not reference a mutable branch or tag.
