# Repository Instructions

- Address every Codex review comment before merging any pull request, regardless of severity.
- After every code or base-branch change, request a fresh Codex review for the exact pull-request head.
- Merge only when the pinned Codex review gate and all repository checks pass.
- Immediately before merging, query the pull request's live `reviewThreads` state and require zero unresolved Codex threads; a previously successful commit status is not enough.
- Never dismiss, resolve, edit, or delete Codex feedback merely to make the gate pass; fix the underlying issue.
