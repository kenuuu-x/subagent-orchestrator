# Parallel work

Parallelism saves time and costs one subscription. Use it only when streams
cannot break each other. Max 3 implementers at once.

## May run in parallel

- Tasks in different repositories or modules with no shared mutable contract.
- Read-only research of independent sources (several scouts).
- Independent checks of different worktrees.
- Preparing the next task (research, plan) while the previous one waits for the
  human or for a long run.
- Screenshots check next to the review of the same diff.

## Only in sequence

- A change to a shared API or data contract and its consumers.
- Plan, implementation and review of one task.
- Implementer and reviewer on the same uncommitted diff.
- Fixes before the review report is saved.
- Commit and PR before a clean review and green checks.
- Merge before the human's review threads are handled.
- Two writers in the same file set.

## Before starting a stream

Record in your state file: inputs, file or module ownership, done criteria,
blockers, dependencies. If two streams own overlapping files, merge them into
one task or run them in sequence.

## Dependent tasks

- Give the dependent task the exact base branch (the predecessor's branch),
  the merge order and the condition to retarget or rebase after the predecessor
  merges.
- Each PR must be reviewable and green on its own and must not break its base.
- Do not split work just to have more parallel streams.

## One worktree per writer

Each writing task has its own worktree and branch. Never run two implementers
in one worktree.
