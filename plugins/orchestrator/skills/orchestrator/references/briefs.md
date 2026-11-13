# Briefs

A subagent sees nothing of your context and cannot open relative plugin links.
Write everything it needs into the brief. Rules for every brief:

- Start with two lines: `Task directory: <absolute path>` (always
  `<home>/projects/<project-key>/tasks/<task-id>`; the hook denies a call
  without it, for every `orchestrator:*` agent) and `Task: <id>, <one-line goal>`.
- Always absolute paths. Expand `~`. Plugin files: build them from the plugin
  root recorded in your run file, for example
  `<plugin root>/skills/code-review/SKILL.md`.
- Pass paths, not file contents.
- Say what to write and where. End: "Answer briefly; details go to files."
- Missing information is the subagent's cue to ask, not guess. Do not hide gaps.

## What to put in each brief

| Role | Put in the brief |
|---|---|
| Scout `orchestrator:scout` | Task (id, goal, acceptance criteria); absolute repo path; areas or questions to look at; output path `<task dir>/research.md` |
| Planner `orchestrator:planner` | Task and the human's decisions; absolute repo path; path to `research.md` if there is one, and the `custom-<name>-N.md` files of `research` roles; the absolute path of `<home>/projects/<project-key>/settings.json` (it builds the task's role table from it); confirmed base branch; output path `<task dir>/01-plan.md`; reminder: class with signal and file, role/model table, steps, files, checks from the repo, risks, estimated diff size, `Hard part: <files>` if any |
| Implementer `orchestrator:implementer` | Path to `01-plan.md`; absolute worktree path and branch; pass number N; goal of the pass (see "Pass goals"); for `review fixes` the paths to `review-<N-1>.md` and `visual-<N-1>.md` (with no code host also `remarks-<N-1>.md`; also each `custom-<name>-<N-1>.md` that holds a `REQUEST CHANGES`); for the `opus` implementer the standalone line `Complexity: hard` or `Hard part: <files>` copied from `01-plan.md` (only the opus brief carries `Hard part:`); for the main `sonnet` implementer, when the plan has a hard part, the standalone line `Skip (separate opus pass): <files>` (same files): it must not change them; the exact check commands (from the plan); output path `<task dir>/changes-N.md`; extras per goal below |
| Reviewer `orchestrator:reviewer` | Task and acceptance criteria; paths to `01-plan.md`, `changes-N.md`, `<task dir>/state.md`, the settings path (route check), and for every writing custom role of this pass its `custom-<name>-N.md` and its instruction path (change journal and criteria of the same diff), the repository's `AGENTS.md` / `CLAUDE.md`; absolute worktree path; absolute path `<plugin root>/skills/code-review/SKILL.md`; pass number N; the check results for the current state of the diff; for a re-review the path to the previous `review-<N-1>.md` and "check only the fixes and the previous findings"; reminder: first line is the verdict, read-only, report comes back as the answer |
| Custom role, read-only (`writes: false`) | Absolute path of its instruction file (`instructions` in the settings); the inputs of its phase: the task, `research.md` (`research`), `01-plan.md` (`plan`), the worktree path, `changes-N.md` and the `custom-<name>-N.md` journals of the writing roles (`review`, `publish`); output path `<task dir>/custom-<name>-N.md`; "read-only, write nothing else"; for `review` and `publish` the verdict-line rule of the reviewer brief and, on a re-review, the previous file |
| Custom role, writing (`writes: true`) | The standalone line `Worktree: <absolute path>`; paths of `01-plan.md`, `changes-N.md` and the instruction file; the exact check commands; output path `<task dir>/custom-<name>-N.md` (change journal, sections of `changes-N.md`); "no commit, no other worktree"; it starts only after the implementer pass has finished |
| Visual-checker `orchestrator:visual-checker` | Task directory; pass number N; path to `changes-N.md` (its screenshot list); paths to reference images if any; output path `<task dir>/visual-N.md` |
| Tester `orchestrator:tester` | Acceptance criteria; paths to `01-plan.md` and `changes-N.md`; absolute worktree path; pass number N; the tester reads files with Read, Glob and Grep (it has no Bash), so no pasted diff; the project's test framework and an existing test as a pattern; output path `<task dir>/test-N.md` |
| Test runner (`general-purpose`, `haiku`) | Exact command to run; absolute worktree path; output path `<task dir>/logs/<name>.log`; "report pass or fail and the first error, nothing else" |
| Mechanics (`general-purpose`, `haiku`) | One exact action (for example `git -C <worktree> merge <base>` with no conflicts expected, or one exact command or tracker operation from an adapter, with the absolute path of that adapter); stop and report on any unexpected output |

## Checks in the brief

- Take check commands from the plan, which took them from the repository's own
  files (`AGENTS.md`, `CLAUDE.md`, `README`, `package.json`, `Makefile`,
  `pyproject.toml`, CI config). Never invent a command.
- Write them as exact lines, one per check, with the directory they run in.
- Missing check commands: ask the human before the first implementer starts.

## Adapters in the brief

Code-host and tracker commands live in adapters under
`<plugin root>/skills/orchestrator/references/adapters/`
([adapters/index.md](adapters/index.md) says how you choose them). A subagent
cannot guess the adapter, so the brief carries its absolute path:

- the code-host adapter (`host-*.md`) in every `publish`, `PR comments` and
  `merge` brief, also when it is `host-none.md`;
- the tracker adapter (`tracker-*.md`) in a `publish` brief when the task has an
  issue reference, and in any mechanics brief that changes a tracker. A
  tracker other than GitHub Issues also needs `tracker-mcp.md`.

## Pass numbers and goals

Every pass is a new implementer with its own `changes-N.md`. Pass 1 has the
goal `implementation`; later passes have the goal you name. Use exactly these
goal names:

| Goal | Extras in the brief |
|---|---|
| `implementation` | none |
| `review fixes` | paths to `review-<N-1>.md` and `visual-<N-1>.md`; with no code host also the path to `remarks-<N-1>.md`; each `custom-<name>-<N-1>.md` that holds a `REQUEST CHANGES` |
| `publish` | `<plugin root>/skills/pull-request/SKILL.md`, the code-host adapter path, base branch, issue reference with the tracker adapter path; after PR comments also the ids of the fixed threads |
| `PR comments` | PR URL, the same skill path and the code-host adapter path |
| `merge base` | base branch; only after `publish`, on a clean worktree, and only when merging it into the task branch has conflicts (a clean merge is a `general-purpose` `haiku` mechanics subagent) |
| `merge` | PR URL, the same skill path, the code-host adapter path, the merge method if the human named one; only after the human explicitly asked. With no code host: no PR URL; the adapter is `<plugin root>/skills/orchestrator/references/adapters/host-none.md`, and the brief adds the task branch, the confirmed base branch and the plan's check commands |

## Review brief checklist

Before you send it: absolute worktree path, the diff is uncommitted and
unchanged since the checks ran, `code-review` path built from the plugin root,
pass number, check results.
