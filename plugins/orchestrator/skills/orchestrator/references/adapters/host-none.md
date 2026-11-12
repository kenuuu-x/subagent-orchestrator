# Code host: none (local commits only)

Use this when the repository has no remote, `gh` is missing or not logged in,
or the human says there is no code host. Everything stays in local git. Do not
try other hosting.

## Check access

`git remote -v` prints nothing, or `gh auth status` fails. Tell the human once
that the flow is local. In `state.md` the line `PR:` is `local`.

## Find or open

There is no pull request. The goal `publish` is a local commit only: stage the
files of the task, commit with the repository's convention, report the branch
and the commit SHA. Do not push.

## Review threads

There are none. The human reviews the branch locally and sends remarks in chat.
The orchestrator saves them verbatim as `<task dir>/remarks-N.md`, then runs
this loop:

1. A `review fixes` pass whose brief carries the path of `remarks-N.md`.
2. A focused re-review.
3. After `APPROVE`, a `publish` pass: a new local commit on the same branch.

## Reply and resolve

Nothing to reply to or resolve. A remark that is invalid or unclear is
answered in `changes-N.md`, and the orchestrator tells the human in chat.

## Checks and approval

Green checks are the commands of the plan, run on the current state. Approval
is the human's explicit word in chat.

## Stacked tasks

- A stacked task takes the predecessor's local branch as its base, and only
  after the predecessor's `publish`. A branch cut earlier would miss later
  commits of the predecessor.
- After the predecessor is merged, the dependent task's base becomes the
  predecessor's base (the human confirms) and that base is merged into the
  dependent branch (goal `merge base`, or a `general-purpose` `haiku`
  mechanics subagent when there are no conflicts).

## Merge

Goal `merge`, only after the human's explicit request. The brief names the task
branch and its confirmed base. Merge the task branch into the base locally:

1. Find where the base is checked out: `git worktree list`.
2. Checked out in a clean worktree: merge there.
3. Checked out in a dirty worktree: stop and report. Never stash.
4. Not checked out anywhere: switch the clean task worktree to the base and
   merge there (remember to switch back, step 7).
5. Method: the one the human or the repository names, else
   `git merge --no-ff --no-commit`.
6. Run the plan's checks on the merged, uncommitted result. Green: commit the
   merge. Red, or conflicts: `git merge --abort` and report; the orchestrator
   then runs a `merge base` pass and tries again.
7. If step 4 switched the task worktree, switch it back to the task branch
   after the commit or after the abort, before you report. The task worktree
   never stays on the base.

The local merge commit is the one commit the `merge` pass may make. Do not
push, and do not delete the branch.

After the merge the orchestrator removes the task worktree
(`git worktree remove`), only if the human agrees. The branch stays;
`git branch -d` only when the human asks.
