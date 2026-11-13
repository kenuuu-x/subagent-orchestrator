# Task files

## Locations

- Work home: `$SUBAGENT_ORCHESTRATOR_HOME`, else the line
  `Subagent orchestrator home: <absolute path>` in the project's `CLAUDE.md`,
  else `~/.subagent-orchestrator/`. Expand `~` in every path you pass on.
  The hooks find the home from the session's working directory; see
  [setup.md](setup.md), "Work home of the hooks".
- Project directory: `<home>/projects/<project-key>/`. Everything of one
  repository lives there, so ids of different repositories never collide.
- Project key: the name of the main checkout directory (the parent of
  `git rev-parse --git-common-dir`, resolved to an absolute path first), in
  lowercase kebab-case. Lookup:
  1. Scan `<key>`, `<key>-2`, `<key>-3`, ... up to the first suffix that does
     not exist.
  2. A `settings.json` that parses and has a `repo` equal to the absolute path
     of this main checkout: this directory is the project.
  3. A `settings.json` that exists but cannot be parsed, or has no string
     `repo`: stop, show the error and ask the human. Never skip it.
  4. No match after the scan: the new project is the first scanned directory
     without a `settings.json` whose tasks are empty or all name this checkout
     in their `state.md` `Repo:` line (ask before you adopt a directory that
     has tasks); if there is none, the first suffix that does not exist. Run
     the setup interview there ([setup.md](setup.md)).

  The settings hook uses steps 1-3 only: no match means no settings, so run setup.
- Settings file: `<home>/projects/<project-key>/settings.json`. Format and
  interview: [setup.md](setup.md).
- A task directory always lives in the project of its own `Repo:`, and that
  project needs its own settings file before the task starts. Per task, use the
  settings of the task's own project; the chat language comes from the project
  where the run started.
- Run file (your state file, one per run):
  `<home>/projects/<project-key>/runs/<run-id>.md`.
- Task directory: `<home>/projects/<project-key>/tasks/<task-id>/`.
- Run id: `<YYYYMMDD-HHMM>` of the start, with the suffix `-2` (then `-3`) if
  that id is taken.
- Task id: `gh-<number>` for a GitHub issue; a tracker key such as `ABC-123`
  in lowercase (`abc-123`); else a short kebab-case slug the human confirmed
  (`fix-login-timeout`). If the task id already exists in the project, ask:
  resume that task, or use a new id with the suffix `-2`.

```
<home>/projects/<project-key>/
  settings.json             first-run setup answers, see setup.md
  roles/<name>.md           instruction file of a custom role
  runs/<run-id>.md          one state file per run
  tasks/<task-id>/          one directory per task
```

## Task directory

| File | Writer | Content |
|---|---|---|
| `research.md` | scout | short summary with file paths and line numbers |
| `01-plan.md` | planner | class and reason, role/model table, files, steps, checks, risks, estimated diff size |
| `changes-N.md` | implementer, pass N | what changed, checks run with results, screenshot paths, open questions |
| `review-N.md` | orchestrator | the reviewer's report, saved verbatim |
| `visual-N.md` | visual-checker | short text verdict on the screenshots of pass N |
| `test-N.md` | tester | scenario notes (the test code goes into the worktree) |
| `custom-<name>-N.md` | custom role `<name>`, pass N | read-only role: its notes or findings (verdict line first in the `review` and `publish` phases); writing role: change journal with the sections of `changes-N.md` |
| `remarks-N.md` | orchestrator | the human's remarks on a local commit, saved verbatim (no code host) |
| `logs/` | anyone | long command output; read only the tail and errors |
| `state.md` | orchestrator | see below |

Update `state.md` on a phase change, not on every step. `PR: local` means the
task is published as a local commit only (no code host). A task owned by
another active run is not touched without the human's word. Find the owner
through `Run:`: its run file is `<home>/projects/<project-key>/runs/<run-id>.md`,
whichever project you started in.

## `state.md` template

```markdown
# Task <task-id>

- Goal: <one line>
- Run: <project-key>/<run-id of the run that owns this task>
- Source: <GitHub issue URL | tracker key | free text>
- Repo: <absolute path>
- Base branch: <name> (confirmed by the human: yes/no)
- Worktree: <absolute path>
- Branch: <type>/<task-id>
- HEAD SHA: <sha>
- PR: <URL | local | none>
- Phase: <intake | research | plan | approved | implementing | review | fixes | publish | pr-review | merging | done>
- Complexity: <light | medium | hard>
- Complexity reason: <signal, file>
- Hard part: <files | none>
- Last verdict: <verdict line of review-N.md, for example `APPROVE (0 findings)`>
- Checks: <command → result, at SHA>
- Blockers: <none | text>

## Agent calls

| Pass | Role | Model | Effort | Agent id | Goal | Status |
|---|---|---|---|---|---|---|
| 1 | implementer | sonnet | high | <id> | implementation | running |
```

A custom role appears as `custom:<name>`; its goal is its phase.

## Run file template

`<home>/projects/<project-key>/runs/<run-id>.md`. This is your state file;
update it after every change of the queue or of a decision.
The first block is machine-read: keep the lines exactly as written.

```markdown
# Orchestrator run <run-id>

- Run id: <run-id>
- Project: <project-key>
- Status: active
- Sessions: <session id>, <session id>
- Last update: <date and time>

- Plugin root: <absolute path>
- Work home: <absolute path>
- Started: <date>
- Context note: <restart suggested at ~100k tokens, only with no active subagent>

## Queue

| Task id | Source | Repo | Base | Phase | Depends on | Owns (files/modules) | Task directory |
|---|---|---|---|---|---|---|---|
| gh-12 | #12 | <path> | main | plan | — | <paths> | <absolute path> |

## Human decisions

- <date> <task id>: <decision, for example "plan approved", "base = main", "PR size over 1000 OK">

## Active subagents

| Task id | Role | Agent id | Started |
|---|---|---|---|

## Notes

- <anything a restarted orchestrator needs>
```

- `Status` is `active` or `finished`. Set `finished` when the queue is done or
  the human ends the run.
- `Sessions` lists the ids of the sessions that worked on this run. Append
  your own session id; the hook denies plugin agent calls from a session not
  listed in an active run file. If the id is unknown, the first denial shows it.
- A run that spans several repositories lives in the project where it
  started. Each task directory still lives in the project of its own `Repo:`;
  the queue keeps the absolute path of each.

## Start and resume rules

- At start list the run files with `- Status: active` in this project's
  `runs/`. None: start a new run (new run id, new run file).
- There are some: show each one (run id, tasks, last update) and ask which to
  resume, or whether to start a new run. Never resume silently: a session that
  is still running keeps its own file.
- Resuming: read the run file and each `state.md` of its tasks, add your
  session id to `Sessions`, and continue with new subagents. Old subagents are
  not reachable.
- Legacy 0.1.0 home: a state file `orchestrator.md` directly in the home (the
  top-level `tasks/` directory holds its tasks). Tell the human and offer to
  resume it once. If they agree, move each task directory into the project of
  its own `Repo:`, create a run file from the old queue (set `Run:` in each
  `state.md`), rename the old file to `orchestrator.md.migrated-<run-id>` and
  remove the empty top-level `tasks/`. A renamed file is not detected again.
  These are home files, which you may write.
