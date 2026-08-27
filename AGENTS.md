# Repository Instructions

- Finish implementation and required checks before requesting `@codex review`.
- Use at most two Codex review rounds per pull request. Address all findings from a round together before requesting the second and final review.
- If the second review reports findings, fix them, rerun required checks, resolve only the threads whose underlying issues were fixed, and manually dispatch the gate. Never request a third review.
- Before the two-round limit, any code or base-branch change makes the existing review stale; finish the new final state before requesting the remaining review.
- Reviewed pull requests target `main`; the gate must fail closed for every other base.
- Merge only when the pinned `Codex review gate` status and all repository checks pass.
- Immediately before merging, query the pull request's live `reviewThreads` state and require zero unresolved Codex threads.
- After resolving a fixed Codex thread, manually dispatch the gate for the current PR; hourly self-hosted reconciliation is a fail-closed backstop, not the normal feedback loop.
- Never dismiss, resolve, edit, or delete Codex feedback merely to make the gate pass; fix the underlying issue.
