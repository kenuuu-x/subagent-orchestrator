# Workflow

Lifecycle of one task. Run it per task; several tasks may run in parallel per
[parallel-work.md](parallel-work.md).

## Phases

`intake` → `research` → `plan` → `approved` → `implementing` → `review` →
`fixes` → `publish` → `pr-review` → `merging` → `done`. Write the phase to `state.md` on
every change.

## Base branch confirmation

Before any branch or worktree, per task:

1. Find the repository default branch: `git remote show origin` (look for
   `HEAD branch`), or `git symbolic-ref refs/remotes/origin/HEAD`.
2. Propose a base: the default branch, or the predecessor branch for a
   dependent task. Ask the human to confirm. A guess is not a confirmation.
3. Record the base in `state.md`. Never change it silently.

No remote: the base is the current local branch; still ask.

Stacked task: the base is the predecessor's branch, and the branch is created
only after the predecessor's `publish`, so it contains the published commits.
The rule is the same with and without a remote. After the predecessor merges,
the base becomes the predecessor's base (the human confirms) and is merged
into the dependent branch.

## Worktree and branch

- Branch: `<type>/<task-id>`, `type` is `feat`, `fix`, `refactor`, `docs` or
  `chore`. Example: `fix/gh-42`, `feat/export-csv`. If the repository has its
  own branch convention (`AGENTS.md`, `CONTRIBUTING`, recent branches), follow
  it instead.
- Worktree: `<repo-parent>/<repo-name>-worktrees/<task-id>/`.
- Create from the confirmed base:
  `git -C <repo> worktree add -b <branch> <worktree> <base>`.
- Dirty main checkout: leave it alone. Never stash or reset the human's work.
- One worktree and one branch per writing task. A stacked task branches from its
  predecessor's branch.
- Record repo, base, worktree, branch and HEAD SHA in `state.md`.
- You run this git mechanics yourself, since it touches no code:
  `git fetch`, creating the branch and worktree, and `git worktree remove`
  after the merge. Everything else in git goes through a subagent.
- Remove the worktree only after the merge (the PR merged, or the local merge
  with no code host) and the human agrees. The branch stays; delete it only
  when the human asks.

## Checkpoints

1. No code before plan approval. The human says an explicit "yes" to a plan you
   retold in chat. Silence and "ok, later" are not approval.
2. The diff stays uncommitted until the review is clean. The reviewer sees the
   uncommitted diff only in the same worktree, so no commits in between.
3. Commit, push and PR (also for PR comment fixes) only after a clean review
   and green checks. Clean review: `APPROVE` = no open blocker or major
   finding; the PR may be published. Minor findings and nits listed under an
   APPROVE are not fixed before publishing; the publish implementer lists them
   in the PR description under "Known minor findings". `REQUEST CHANGES` = at
   least one blocker or major. Green checks = the commands the plan lists, run
   on the current state of the diff.
4. A change of the approved plan (scope, files, class) goes back to the human.
5. Merge only on the human's explicit request.

A fix pass resets checkpoint 3: new diff, new checks, new review.

## Fix loop

1. Reviewer returns `REQUEST CHANGES (<n> findings)`: save as `review-N.md`.
2. Start a new implementer, pass N+1, goal `review fixes`, with the path to
   `review-N.md` (and `visual-N.md`).
3. Implementer fixes every confirmed blocker and major finding. A finding it
   believes is wrong gets a short reasoned note in `changes-N+1.md`; you decide,
   and ask the human if it changes the plan.
4. Re-review per the "Re-review" rows in
   [roles-and-models.md](roles-and-models.md). Two rounds without convergence:
   stop and tell the human what keeps failing.

## Tests

Only when the human asks. `orchestrator:tester` writes test code into the
worktree, so the tests join the diff. After the tester: have the tests run (a
`general-purpose` `haiku` subagent; failures go to an implementer pass
`review fixes` or mechanics, per the rules above), then a focused re-review of
the new diff before `publish`.

## PR comments loop

After the human says "done reviewing" (with no code host: after the human's
remarks in chat, saved as `remarks-N.md`, which go through a `review fixes` pass
and the same re-review, see [adapters/host-none.md](adapters/host-none.md)):

1. New implementer, goal `PR comments`: fixes the human's valid unresolved
   threads, replies only to invalid ones, leaves the diff uncommitted and lists
   the threads in `changes-N.md`. No code changed: stop here.
2. Focused re-review: reviewer, "Re-review" rows of
   [roles-and-models.md](roles-and-models.md). `REQUEST CHANGES`: fix loop above.
3. After `APPROVE`: new implementer, goal `publish`, with the fixed thread ids.
   It commits, pushes and resolves the fixed threads.

Nothing reaches the PR branch before step 3.

## Merge base and merge

- Merge the base into the task branch only on a clean worktree, that is after
  `publish`. If the base moves before `publish`, tell the human and keep
  working on the old base; do not merge it into uncommitted work.
- The base moved after `publish` and there are no conflicts: a `general-purpose`
  `haiku` mechanics subagent runs the merge. With conflicts: a new implementer,
  goal `merge base`. Re-review a conflict resolution before the next push.
- Merge: only when the human explicitly asks. Set the phase `merging`. New
  implementer, goal `merge`: checks green, approval present, `gh pr merge` with
  the repository's merge method, then it reports.
- No code host: there is no PR. Goal `merge` merges the task branch into its
  confirmed base locally, as described in
  [adapters/host-none.md](adapters/host-none.md): find where the base is
  checked out, merge in a clean worktree (never stash a dirty one), method the
  human or repository names else `--no-ff --no-commit`, the plan's checks on
  the result, commit only when green, else `git merge --abort` (then a `merge base` pass for conflicts);
  switch the task worktree back to the task branch. Then remove the worktree
  if the human agrees.

## PR size check

Before the publish pass, count changed lines (added + removed) of everything
that will go into the PR: commits already on the branch plus uncommitted work.
Exclude lockfiles and generated files. Replace `<base>` with the confirmed base
and run in the worktree:

```bash
EX=(':(exclude)*.lock' ':(exclude)*lock.json' ':(exclude)*lock.yaml' ':(exclude)go.sum' ':(exclude)*.min.js' ':(exclude)*.snap' ':(exclude)*.generated.*' ':(exclude)dist')
{ git diff --numstat <base>...HEAD -- . "${EX[@]}"; git diff --numstat HEAD -- . "${EX[@]}"; } | awk '$1!="-"{s+=$1+$2} END{print s+0}'
```

Add the lines of new untracked files: `git ls-files --others --exclude-standard`,
then `wc -l` on the source files in that list (skip generated ones). Binary
files count as 0. Adjust the excludes to the repository's own generated paths.

Rules:

- Up to 1000 changed lines: go on.
- Over 1000: stop. Ask the human before publishing, not after. Show the count
  and offer a stack of PRs, each within 1000 lines, each reviewable and green on
  its own, with the merge order and the base of each. A larger single PR only on
  the human's explicit word.
- The planner estimates the size in `01-plan.md`. If the estimate is over 1000,
  the plan already proposes the stack, and the human approves it with the plan.
- For a stack, count each PR from its own base, not from the top of the stack.

## Red flags

Stop and return to the last confirmed checkpoint:

- code before an approved plan;
- base branch not confirmed;
- a worktree shared by two writing tasks;
- a stacked branch created before its predecessor's `publish`;
- commit, push or PR (PR comment fixes included) before a clean review and
  green checks;
- reviewer result not saved as `review-N.md`, or retold from memory;
- checks reported green without a command and its result;
- PR over 1000 lines published without asking;
- diff changed after the review without a new review;
- a plan change applied without the human's "yes".
