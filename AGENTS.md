# Repository Instructions

- Finish implementation and required checks before requesting `@codex review`.
- Codex is advisory except for explicit P0/P1 findings. A valid P2/P3 finding is not a release blocker by default.
- Use at most two Codex review rounds per pull request. Address all blocking findings from a round together before requesting the second and final review.
- If the second review reports blocking findings, fix them, rerun required checks, resolve only those blocking threads, and manually dispatch the gate. Defer advisory findings and never request a third review.
- Before the two-round limit, any code or base-branch change makes the existing review stale; finish the new final state before requesting the remaining review.
- Reviewed pull requests target `main`; the gate must fail closed for every other base.
- Merge only when the pinned `Codex review gate` status and all repository checks pass.
- Immediately before merging, query the pull request's live `reviewThreads` state and require zero unresolved P0/P1 Codex threads.
- After resolving a fixed Codex thread, manually dispatch the gate for the current PR; hourly self-hosted reconciliation is a fail-closed backstop, not the normal feedback loop.
- Never dismiss, resolve, edit, or delete Codex feedback merely to make the gate pass; fix the underlying issue.
- Never open a replacement pull request, rewrite history, or otherwise reset the review budget. If the gate remains blocked, stop for owner direction.
