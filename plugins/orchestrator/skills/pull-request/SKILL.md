---
name: pull-request
description: Use when an orchestrator implementer subagent must publish a task, fix the human's PR review comments or merge the PR, per its pass goal in the orchestrator plugin's flow.
disable-model-invocation: true
---

# Pull request

Work with `git` and the code-host adapter. The brief carries the adapter's
absolute path (a `host-*.md` file under
`skills/orchestrator/references/adapters/`). Read it first with the Read tool:
it holds every host command, under the headings Check access, Find or open,
Review threads, Reply and resolve, Checks and approval and Merge. This skill
names the step; the adapter gives the command. Build the PR only from the
proven scope of the task. Work in the task worktree and branch.

## Modes

- Draft: produce title, description and commit plan only. Change nothing.
- Publish: stage, commit, push, create or update the PR. Do it when the
  pass goal is `publish`. "Write the description" is not a request to publish.
  After a `PR comments` pass and its re-review, the same goal commits, pushes
  and resolves the fixed threads.
- Comments: goal `PR comments`, after the human says "done reviewing". Fix
  only; no commit.
- Merge: goal `merge`, only after the human explicitly asked.

## Preconditions for publish

All must hold. If not, stop and report which one failed.

1. The independent review is clean: verdict `APPROVE` = no open blocker or
   major finding. Minor findings and nits listed under it are not fixed first;
   list them in the PR description under "Known minor findings".
2. The checks from the plan are green on the current diff. Re-run them if the
   diff changed.
3. PR size is within 1000 changed lines (command in
   [workflow.md](../orchestrator/references/workflow.md), section "PR size check").
   Over 1000: stop and report the count; the orchestrator asks the human before
   publishing. Suggest a stack of PRs.
4. The branch is based on the confirmed base branch.

## Remote and tools

- Adapter section "Check access". No remote, or the host's CLI missing or not
  logged in: there is no code host. Follow the host-none adapter (file
  `adapters/host-none.md` in the same folder): commit locally and stop. Report
  the branch, the SHA and the reason you did not push. Do not try other
  hosting.
- Adapter section "Find or open": find an existing PR for the branch first.
  Update it instead of creating a duplicate.

## Commit

- Stage only the files of this task. Keep foreign and unrelated changes
  untouched. Never `git add -A` blindly; read `git status` first.
- Message convention: the repository's own (`AGENTS.md`, `CONTRIBUTING`, last
  15 commit subjects). Without one use Conventional Commits:
  `<type>: <short summary>` where type is `feat`, `fix`, `refactor`, `docs`,
  `test`, `chore`. Add the issue reference when the task has one, in the form
  the tracker adapter's "Link a pull request" gives (`#123`, `ABC-123`).
- Atomic commits by meaning, not one per file.
- Never skip hooks (`--no-verify`) and never amend or force-push a pushed
  branch unless the human asks.

## Push and create

Commands: adapter section "Find or open".

1. Push the branch to `origin`.
2. Create the PR from the base to the branch, with the description in a file.
   Do not add assignees, reviewers, labels, auto-merge or branch deletion
   unless the repository's rules or the human say so.
3. Title: same form as the commit subject. Several issues: name all of them.
4. Re-read the PR and check base, head, commits and the diff size.
5. Return the PR URL, the commits, the checks that actually ran and known limits.
   Say plainly what was not checked.

## PR description

A reader who did not write the code must understand the change without reading
the diff. Use the repository's PR template if there is one. Otherwise:

```markdown
## What
What changed, for the user and for the code.

## Why
The problem, and the issue link in the form the tracker adapter's "Link a pull
request" gives, for example `Closes #123` (omit if none).

## How to verify
Exact commands and steps. Results of the checks with the commit SHA.

## Risks
Compatibility, migrations, follow-ups, anything not checked.

## Known minor findings
Minor findings and nits from the review that were not fixed (omit if none).
```

Write connected prose; a list only for separate items. Take the content from the
plan, `changes-N.md` and the review reports. Report only checks that really
ran.

## PR comment loop

Start when the human says they are done reviewing. Work in the PR branch; sync
with the remote first. This pass only fixes and leaves the diff uncommitted.
The orchestrator then runs a focused re-review; only after `APPROVE` does a
`publish` pass commit, push and resolve the fixed threads (steps 8 to 10).

1. Find the repository and the PR (adapter section "Find or open").
2. List the review threads with their state (adapter section "Review
   threads").
3. Take unresolved threads whose first comment is by the human (the PR author's
   account in a solo flow). If it is unclear which account is the human's, fix
   nothing and say so in your report. Comments by other people: do not touch
   them; list them in your report and finish.
4. Unclear comment: do not guess and do not change code for it; list it in your
   report.
5. Valid comment: fix it. Do not reply in the thread about a fix.
6. Invalid or inapplicable comment: reply in that thread with the reason, short
   and concrete (adapter section "Reply and resolve"). Leave the thread open
   and list it in your report.
7. After the fixes run the checks of the touched code and list every thread
   (id, path, fixed, replied or left open) in the journal. Stop here: leave the
   diff uncommitted.
8. In the `publish` pass after the re-review: commit (convention above) and
   push.
9. Resolve the fixed threads (adapter section "Reply and resolve"). Leave
   invalid and unclear threads open.
10. Report: threads fixed, replied to, left open and why, and (after the
   `publish` pass) the new commit SHA.

## Merge

Goal `merge`, only after the human's explicit request. With no code host there
is no PR: follow the host-none adapter, which merges the task branch into its
confirmed base locally. Otherwise, before it:

1. No unresolved human threads; other people's comments handled.
2. Required approvals present and checks green (adapter section "Checks and
   approval").
3. Merge with the repository's usual method, the one the human or the
   repository rules name (adapter section "Merge"). Add no flags of your own,
   except those the adapter names.
4. Re-read the PR and confirm it is merged. Report to the orchestrator.
