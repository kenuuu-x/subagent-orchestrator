# Task files

## Locations

- Work home: `$SUBAGENT_ORCHESTRATOR_HOME`, else the line
  `Subagent orchestrator home: <absolute path>` in the project's `CLAUDE.md`,
  else `~/.subagent-orchestrator/`. Expand `~` in every path you pass on.
- Orchestrator state file: `<home>/orchestrator.md`.
- Task directory: `<home>/tasks/<task-id>/`.
- Task id: `gh-<number>` for a GitHub issue, else a short kebab-case slug the
  human confirmed (`fix-login-timeout`).

## Task directory

| File | Writer | Content |
|---|---|---|
| `research.md` | scout | short summary with file paths and line numbers |
| `01-plan.md` | planner | class and reason, role/model table, files, steps, checks, risks, estimated diff size |
| `changes-N.md` | implementer, pass N | what changed, checks run with results, screenshot paths, open questions |
| `review-N.md` | orchestrator | the reviewer's report, saved verbatim |
| `visual-N.md` | visual-checker | short text verdict on the screenshots of pass N |
| `test-N.md` | tester | scenario notes (the test code goes into the worktree) |
| `logs/` | anyone | long command output; read only the tail and errors |
| `state.md` | orchestrator | see below |

Update `state.md` on a phase change, not on every step.

## `state.md` template

```markdown
# Task <task-id>

- Goal: <one line>
- Source: <GitHub issue URL | free text>
- Repo: <absolute path>
- Base branch: <name> (confirmed by the human: yes/no)
- Worktree: <absolute path>
- Branch: <type>/<task-id>
- HEAD SHA: <sha>
- PR: <URL | none>
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

## Orchestrator state file template

`<home>/orchestrator.md`. You write only this file; update it after every
change of the queue or of a decision.

```markdown
# Orchestrator state

- Plugin root: <absolute path>
- Work home: <absolute path>
- Started: <date>
- Context note: <restart suggested at ~100k tokens, only with no active subagent>

## Queue

| Task id | Source | Repo | Base | Phase | Depends on | Owns (files/modules) |
|---|---|---|---|---|---|---|
| gh-12 | #12 | <path> | main | plan | — | <paths> |

## Human decisions

- <date> <task id>: <decision, for example "plan approved", "base = main", "PR size over 1000 OK">

## Active subagents

| Task id | Role | Agent id | Started |
|---|---|---|---|

## Notes

- <anything a restarted orchestrator needs>
```

Resume rule: a restarted orchestrator reads this file and each `state.md`, then
continues with new subagents. Old subagents are not reachable.
