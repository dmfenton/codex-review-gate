# Repository Instructions

- Finish implementation and required checks before requesting one final `@codex review`.
- Do not request another review for the same head and base unless the previous review reported substantive findings and those findings were fixed.
- After any code or base-branch change, the existing review is stale; finish the new final state before requesting another review.
- Reviewed pull requests target `main`; the gate must fail closed for every other base.
- Merge only when the pinned `Codex review gate` status and all repository checks pass.
- Immediately before merging, query the pull request's live `reviewThreads` state and require zero unresolved Codex threads.
- After resolving a fixed Codex thread, manually dispatch the gate for the current PR; hourly self-hosted reconciliation is a fail-closed backstop, not the normal feedback loop.
- Never dismiss, resolve, edit, or delete Codex feedback merely to make the gate pass; fix the underlying issue.
