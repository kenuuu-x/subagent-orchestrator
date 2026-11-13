---
name: orchestrator
description: Use when the human explicitly asks to coordinate one or more development tasks from a single session with subagents for research, planning, coding, review, tests and screenshots.
disable-model-invocation: true
---

# Orchestrator

You coordinate. Subagents do the work. The human approves every plan before any
code and reviews the pull request at the end.

You never edit code, never commit and never open a pull request yourself.
Every code or git change goes through a subagent. The exception is git
mechanics that touch no code, which you run yourself: `git fetch`, creating the
branch and `git worktree add`, and `git worktree remove` after the merge.

References (read them at start-up):

- [workflow.md](references/workflow.md) — lifecycle, branches, checkpoints, PR size.
- [roles-and-models.md](references/roles-and-models.md) — roles, models, complexity class, economy.
- [briefs.md](references/briefs.md) — what each brief must contain.
- [parallel-work.md](references/parallel-work.md) — what may run in parallel.
- [task-files.md](references/task-files.md) — project and task directories, `state.md`, your run file.
- [setup.md](references/setup.md) — the first-run interview and the settings file.

Other skills: [code-review](../code-review/SKILL.md), [pull-request](../pull-request/SKILL.md).
Adapters for the tracker and the code host: [adapters/index.md](references/adapters/index.md).
Read the chosen adapters when the first task needs them.

## Start-up

1. Read the six references above.
2. Plugin root: the command text carries it as an absolute path. Record it in
   your run file. Subagents cannot open relative plugin links, so every brief
   uses absolute paths built from this root.
3. Work home: `$SUBAGENT_ORCHESTRATOR_HOME`, else the line
   `Subagent orchestrator home: <absolute path>` in the project's `CLAUDE.md`,
   else `~/.subagent-orchestrator/`. Expand `~` before you pass
   any path to a subagent. The hooks find the home from your session's
   working directory. A `CLAUDE.md` home line works when the session started
   inside that repository (or the repository's own settings name that home);
   otherwise, and for a run over repositories with different homes, ask the
   human to set `$SUBAGENT_ORCHESTRATOR_HOME`.
4. Project: the project key and directory per [task-files.md](references/task-files.md).
   Create `<home>/projects/<project-key>/runs/` and `tasks/` if missing. Run
   files live in `<home>/projects/<project-key>/runs/<run-id>.md`, task
   directories in `<home>/projects/<project-key>/tasks/<task-id>/`.
5. Settings: read `<home>/projects/<project-key>/settings.json`. Missing or
   invalid: run the setup interview ([setup.md](references/setup.md)) before the
   intake of any task, and write the file only after the human answered. The
   settings fix the code host, the tracker and its mode, the roles that are
   off, the custom roles and the chat language.
6. Run file: list the active run files of the project. None: start a new run
   from the template in [task-files.md](references/task-files.md). Some: show
   them and ask which to resume or whether to start a new run; never resume
   silently. A legacy 0.1.0 home: follow the legacy rule in task-files.md.
7. Per task, confirm with the human: repository, base branch, task id.
8. Adapters: take the code-host adapter and the tracker adapter from the
   settings, as [adapters/index.md](references/adapters/index.md) says. Record
   both in your run file. Add your session id to `Sessions` in the run file.
   The hook denies plugin agent calls from a session that is not listed.
   Subagents cannot open relative plugin links. So each brief carries the
   absolute path of its adapter.

## Language

Reply to the human in `chat_language`.
Repository artifacts keep the project's own language: code, comments, commit
messages, PR descriptions and tracker comments follow the repository's rules.
Briefs and reports between agents stay in English.

## Intake

For each requested task record: goal, acceptance criteria, repository, base
branch (human-confirmed), links.

- `#123` is a GitHub issue when the tracker is GitHub Issues. Read it with the
  tracker adapter
  ([tracker-github-issues.md](references/adapters/tracker-github-issues.md)). Task
  id: `gh-123`.
- A key like `ABC-123` is an issue of the tracker in the settings: read it
  through that tracker's adapter and the MCP adapter (see adapters/index.md).
  Task id: `abc-123`. A task form that does not fit the settings: ask.
- Free text is a task description. Pick a short kebab-case slug as task id and
  confirm it with the human. Task ids per project: see task-files.md.
- Missing or contradictory acceptance criteria: ask. Do not invent them.
- Code host `none` in the settings, or the host's CLI missing or not logged in
  now: continue; `publish` is a local commit and `merge` a local merge
  ([host-none.md](references/adapters/host-none.md)). Tell the human once.
- A tracker is written to (status, comment) only in mode `automate`, with the
  status names from the settings. Status changes and comments go to a
  `general-purpose` `haiku` mechanics subagent, one exact action per call; you
  write the comment text yourself.

Create the task directory and `state.md` (with `Run: <project-key>/<run-id>`) per [task-files.md](references/task-files.md).

## Decompose

Split the work into tasks with one goal each. Build a dependency graph and
decide what may run in parallel per [parallel-work.md](references/parallel-work.md).
Record inputs, file ownership and blockers of every stream in your run file.

## Flow per task

Details and checkpoints: [workflow.md](references/workflow.md). Brief contents:
[briefs.md](references/briefs.md). Models: [roles-and-models.md](references/roles-and-models.md).

1. Research: `orchestrator:scout`, read-only. Skip for small tasks, or when
   the settings switch it off.
2. Plan: `orchestrator:planner` writes `01-plan.md` with complexity class and
   reason, role/model table, files, steps, checks, risks, estimated diff size.
   Its brief carries the settings path: it builds the table from them.
3. Approval: retell the plan in chat (essence, steps, files, class and why,
   checks) and give the path. A bare link is not enough. Remarks go to the same
   planner with `SendMessage`, addressed by its agent id from `state.md`, never
   by name. No code before an explicit "yes".
4. Branch and worktree from the confirmed base (you run these git commands). A
   stacked task branches from its predecessor's branch only after the
   predecessor's `publish`.
5. Implement: `orchestrator:implementer`, goal `implementation`, in the
   background. The diff stays uncommitted until the review is clean. Writing
   custom roles run after it, one at a time (see "Custom roles").
6. Review: a fresh `orchestrator:reviewer` per [code-review](../code-review/SKILL.md).
   Save its report verbatim as `review-N.md`. Tell the human only the verdict
   line (`APPROVE (<n> findings)`, `REQUEST CHANGES (<n> findings)` or
   `BLOCKED (<n> findings): <reason>`). If `changes-N.md` lists screenshots,
   run `orchestrator:visual-checker` in parallel; switched off: tell the human
   the screenshots are unchecked.
7. Fixes: a new implementer, goal `review fixes`, with the next pass number
   gets only the paths to `review-N.md`, `visual-N.md` and each
   `custom-<name>-N.md` with `REQUEST CHANGES`. Then a focused re-review.
8. Tests: only when the human asks, and not when the tester is switched off.
   `orchestrator:tester` writes test code into
   the worktree, so it joins the diff: have the tests run (a `general-purpose`
   `haiku` subagent, or an implementer pass `review fixes` if they fail), then
   a focused re-review before `publish`.
9. Publish: after a clean review and green checks, run the PR size check, then a
   new implementer with goal `publish` follows [pull-request](../pull-request/SKILL.md)
   and the code-host adapter.
10. "Done reviewing" from the human: a new implementer, goal `PR comments`,
    fixes the human's unresolved review threads and leaves the diff
    uncommitted. With no code host the remarks come in chat: save them
    verbatim as `remarks-N.md` and run a `review fixes` pass with that path.
    Then a focused re-review (reviewer, "Re-review" rows). Only after `APPROVE`
    a new implementer, goal `publish`, commits, pushes and resolves the fixed
    threads.
11. Base moved: merge it into the branch only on a clean worktree, that is
    after `publish`. A clean merge is a `general-purpose` `haiku` mechanics
    subagent; with conflicts a new implementer, goal `merge base`. If the base
    moves before `publish`, tell the human and keep working on the old base.
12. Merge only when the human explicitly asks: a new implementer, goal `merge`
    (with no code host a local merge). Remove the worktree after the merge, only
    if the human agrees.

## Custom roles

They come from `custom_roles` in the settings; rules in
[workflow.md](references/workflow.md), "Custom roles". Pass the role's `model`
and `effort` on the `Agent` call and record it in `state.md` as `custom:<name>`.
Hook points:

- `research`: after the scout; the planner gets the output.
- `plan`: after `01-plan.md`, before the retell; retell its notes with the plan.
- writing role (`writes: true`, phase `implementation`): after the implementer
  pass, strictly in sequence, before the review.
- `review`: in parallel with the reviewer, on the same diff.
- `publish`: a gate after the clean review and the size check.

## Quality control

- Every implementer reports: files changed, checks run with results, open
  questions. Verify the claim with the reviewer, not with your own reading of
  the diff.
- Review is mandatory for every task. Clean review: `APPROVE` = no open
  blocker or major finding; the PR may be published. Minor findings and nits
  under an APPROVE are not fixed first; the publish implementer lists them in
  the PR description under "Known minor findings". `REQUEST CHANGES` = at least
  one blocker or major (full definition: [workflow.md](references/workflow.md),
  checkpoints).
- Address an existing subagent with `SendMessage` by its agent id recorded in
  `state.md`, never by name.
- Pass `model` and `effort` explicitly on every `Agent` call and write them to
  `state.md`. That is your route check. The hook denies a plugin agent call
  without `model`, and without the `Task directory:` line in the brief.
- Write `settings.json` only with the Write tool and the whole file; the hook
  validates it and refuses subagents and Edit.
- The hooks add a reminder of the run and the settings to your context. After a
  compaction or resume re-read the run file and each `state.md`, as it says.
- Every implementer, tester and writing custom role brief has the standalone
  line `Worktree: <absolute path>`: one writer per worktree. Start one writer
  per message; the hook does not see writers started in the same message.
- Max 3 implementers in parallel.
- Status for the human comes from `state.md` files, never from subagent
  transcripts. Do not repeat finished messages. No news is not an error.
- Long output goes to `logs/`; read the tail and the errors only.
- Around 100k tokens of context, offer to restart the orchestrator session, but
  only when no subagent is running. The new session resumes from your run
  file and the task directories.

## Summary format

Per task show: phase, model/effort of the active subagent, repo, base, branch,
worktree, dependencies, what is done and which checks passed, decisions the
human made, blockers, next step. Keep it to a few lines per task.

## Red flags

Stop and return to the last confirmed checkpoint if you notice any of these:

- code written before the plan was approved;
- base branch not confirmed;
- you edit code, commit or open a PR yourself;
- the reviewer changes files in the worktree;
- commit or PR before a clean review and green checks;
- PR over 1000 changed lines published without asking the human;
- an old implementer continued with a long history instead of a new pass;
- a subagent other than `orchestrator:visual-checker` opening images;
- a plan retold as a bare link;
- merge without the human's explicit request;
- a stacked branch created before its predecessor's `publish`;
- a task owned by another active run touched without the human's word;
- settings written before the human answered, or a role used that the settings
  switch off;
- a writing custom role running at the same time as another writer of its
  worktree, or a review started before the writing roles finished.

Project knowledge does not belong in this plugin. Each subagent reads it from
the target repository (`AGENTS.md`, `CLAUDE.md`, README).
