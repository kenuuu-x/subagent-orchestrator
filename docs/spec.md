# subagent-orchestrator — design spec

A Claude Code plugin that coordinates one or more development tasks from a
single session. Every role (research, plan, code, review, tests, screenshots,
mechanics) is a subagent with its own model and effort. The human approves the
plan before any code and reviews the pull request at the end.

This spec is the single source of truth for file names, agent names, paths and
rules. Every file in the plugin must agree with it.

## Hard constraints

- English everywhere in the plugin (skills, agents, commands, README, tests).
- Fully generic: no company, product, tracker or platform names. Never write
  any of: `locali`, `LOCALIAPP`, `pult`, `OPSBOT`, `Yandex`, `Tracker` (as a
  product), `GitLab`, `glab`, `Gradle`, `Android`, `iOS`, `Maestro`,
  `emulator`, `Figma`, `libs` (as a product), `StudioProjects`, `.locali-handoff`,
  `build-lock`, `work-slot`, `emulator-lock`, Cyrillic text. The contract test
  fails on these words.
- Stack-agnostic: build, test and lint commands come from the target
  repository (`AGENTS.md`, `CLAUDE.md`, `README`, `package.json`, `Makefile`,
  `pyproject.toml`, CI config). Examples may name several ecosystems side by
  side (`npm test`, `pytest`, `cargo test`, `./gradlew test`) only as a list of
  examples — prefer no examples at all.
- Code hosting: GitHub through the `gh` CLI. Works without a remote too: then
  `publish` is a local commit, the human's remarks come in chat, and `merge` is
  a local merge (`host-none.md`).
- Issue tracking is optional: a task is either a GitHub issue (`#123`) or a
  free-text description.
- Only one mode: subagents inside one orchestrator session. No background
  sessions, no worker scripts, no external dashboards.
- Model names are aliases only: `opus`, `sonnet`, `haiku` (no version numbers).
  Effort values: `low`, `medium`, `high`, `xhigh`.
- Keep files short and imperative. Skills are instructions for a model, not
  essays. Target sizes are given per file below.

## Repository layout

```
.claude-plugin/marketplace.json          marketplace "subagent-orchestrator"
plugins/orchestrator/
  .claude-plugin/plugin.json             plugin "orchestrator", version 0.1.0
  commands/orchestrate.md                /orchestrator:orchestrate <tasks>
  skills/orchestrator/SKILL.md           entry skill (disable-model-invocation: true)
  skills/orchestrator/references/
    workflow.md                          task lifecycle, branches, worktrees, checkpoints, PR size
    roles-and-models.md                  role table, complexity class, subagent economy, call rules
    briefs.md                            what each subagent brief must contain
    parallel-work.md                     when tasks may run in parallel
    task-files.md                        project, run and task layout, state.md and run-file templates
    adapters/host-none.md                no code host: local commit, remarks, stacked tasks, local merge
  skills/code-review/SKILL.md            review procedure + report format (read-only; disable-model-invocation: true)
  skills/pull-request/SKILL.md           commit, push, PR, PR comment loop, merge on request (disable-model-invocation: true)
  agents/scout.md
  agents/planner.md
  agents/implementer.md
  agents/reviewer.md
  agents/tester.md
  agents/visual-checker.md
  hooks/hooks.json
  hooks/subagent-guard.py
tests/test_subagent_guard.py             unittest for the hook
tests/check_contract.py                  forbidden words, frontmatter, links, names
scripts/validate.sh                      runs both tests
README.md, LICENSE (MIT), .gitignore
```

Subagent types as seen by the orchestrator: `orchestrator:scout`,
`orchestrator:planner`, `orchestrator:implementer`, `orchestrator:reviewer`,
`orchestrator:tester`, `orchestrator:visual-checker`. Mechanics use the
built-in `general-purpose` type.

## Paths and files

- Plugin root: the command text has `${CLAUDE_PLUGIN_ROOT}` expanded to an
  absolute path. The orchestrator records it in its run file and builds
  absolute paths to plugin files from it. Subagents cannot open relative plugin
  links, so briefs always carry absolute paths.
- Work home: `~/.subagent-orchestrator/` (override: env `SUBAGENT_ORCHESTRATOR_HOME`,
  else the line `Subagent orchestrator home: <absolute path>` in the project's
  `CLAUDE.md`). Always expand `~` before passing a path to a subagent.
  The README documents the override line.
- Project directory: `<home>/projects/<project-key>/`. The project key is the
  name of the main checkout directory (the parent of the git common dir), in
  lowercase kebab-case (the git common dir resolved to an absolute path first);
  `-2`, `-3` only when the directory has tasks and none names this repository
  in its `Repo:` line. A task directory always lives in the project of its own
  `Repo:`.
- Run file (the orchestrator state file, one per run):
  `<home>/projects/<project-key>/runs/<run-id>.md` — queue, user decisions,
  plugin root, repo paths, active subagents. Run id: `<YYYYMMDD-HHMM>` of the
  start, suffix `-2` if taken. It starts with strict lines: `- Run id:`,
  `- Project:`, `- Status: active|finished`, `- Sessions: <session ids>`,
  `- Last update:`. Restart rule: list the `active` run files of the project;
  none means a new run; otherwise show each and ask which to resume or whether
  to start a new run, never resume silently. A run is `finished` when the queue
  is done or the human ends it. A run spanning several repositories lives in
  the project where it started; its queue keeps the absolute task directory of
  each task. A task owned by another active run (`Run: <project-key>/<run-id>`
  line of `state.md`, resolvable across projects) is not touched without the
  human's word.
- Task id: `gh-<number>` for a GitHub issue, a tracker key in lowercase
  (`abc-123`), otherwise a short kebab-case slug chosen by the orchestrator and
  confirmed with the human (`fix-login-timeout`). An id that already exists in
  the project: ask whether to resume that task or use a new id with `-2`.
- Legacy 0.1.0 home (a state file `orchestrator.md` directly in the home and a
  top-level `tasks/`): the orchestrator tells the human and offers to resume it
  once by moving each task directory into the project of its own `Repo:`,
  creating a run file, renaming the old file to
  `orchestrator.md.migrated-<run-id>` and removing the empty top-level `tasks/`.
- Task directory: `<home>/projects/<project-key>/tasks/<task-id>/` containing:
  - `research.md` (scout)
  - `01-plan.md` (planner)
  - `changes-N.md` (implementer, pass N)
  - `review-N.md` (orchestrator saves the reviewer's report verbatim)
  - `visual-N.md` (visual-checker)
  - `test-N.md` (tester's scenario notes; the test code itself goes into the worktree)
  - `remarks-N.md` (orchestrator: the human's remarks on a local commit, saved
    verbatim; no code host)
  - `logs/` (long command output)
  - `state.md` — run id, repo, base branch, worktree, branch, HEAD SHA,
    `PR: <URL|local|none>`, phase,
    `Complexity: <light|medium|hard>`, `Hard part: <files|none>`, last verdict
    line, and for every `Agent` call: role, model, effort, agent id, pass goal.
    Updated on phase change, not on every step.
  - Pass goals of `orchestrator:implementer`, used verbatim everywhere:
    `implementation`, `review fixes`, `publish`, `PR comments`, `merge base`,
    `merge`.
- Worktree: `<repo-parent>/<repo-name>-worktrees/<task-id>/`, branch
  `<type>/<task-id>` where type is `feat`, `fix`, `refactor`, `docs`, `chore`
  (follow the repository's own convention if it has one).

## Task flow (orchestrator)

1. Intake: for each task record goal, acceptance criteria, repository, base
   branch (confirmed by the human), links. A GitHub issue is read with
   `gh issue view`.
2. Decompose and build a dependency graph (`parallel-work.md`).
3. Research: `orchestrator:scout`, read-only. Small tasks skip the scout.
4. Plan: `orchestrator:planner` writes `01-plan.md` including the complexity
   (the standalone line `Complexity: light|medium|hard`, or `Hard part: <files>`
   when only part is hard) with its reason, the role/model table for this task,
   files, steps, checks (commands from the repo), risks, and an estimated diff
   size.
5. Approval: the orchestrator retells the plan in chat (essence, steps, files,
   class and why, checks) and gives the path. A bare link is not enough.
   Remarks go back to the same planner via `SendMessage`, addressed by its
   agent id from `state.md`, never by name. No code before an explicit "yes".
6. Branch + worktree from the confirmed base. The orchestrator runs this git
   mechanics itself (`git fetch`, branch, `git worktree add`). A stacked task
   branches from its predecessor's branch only after the predecessor's
   `publish`.
7. Implementation: `orchestrator:implementer`, goal `implementation`, in the
   background. It runs the
   repo's checks itself and writes `changes-N.md`. Diff stays uncommitted until
   the review is clean. Hard part: a separate short implementer on `opus` only
   for the listed files. Stuck on `sonnet` (two attempts at the same error, or
   edits going in circles) → repeat the step with a new `opus` implementer.
8. Review: fresh `orchestrator:reviewer`, read-only, per `code-review`. First
   line of its report is the verdict: `APPROVE (<n> findings)`,
   `REQUEST CHANGES (<n> findings)` or `BLOCKED (<n> findings): <reason>`.
   `APPROVE` = no open blocker or major finding; the PR may be published.
   Minor findings and nits under an APPROVE are not fixed before publishing;
   the publish implementer lists them in the PR description under "Known minor
   findings". `REQUEST CHANGES` = at least one blocker or major. The
   orchestrator saves the report as `review-N.md` and tells the human only the
   first line. If `changes-N.md`
   lists screenshots, run `orchestrator:visual-checker` in parallel.
9. Fixes: a NEW implementer, goal `review fixes`, pass N+1, gets only paths to
   `review-N.md` / `visual-N.md`. Then a focused re-review (small fixes → reviewer on
   `sonnet`/`high`).
10. Tests on request: `orchestrator:tester` writes an end-to-end or
    integration test in the project's existing test framework (its brief has
    absolute paths of the worktree, `01-plan.md` and `changes-N.md`, no pasted
    diff; it reads files with Read/Glob/Grep); running it is a `general-purpose`
    `haiku` subagent, only when the human asks. The test code joins the diff:
    after the tester the orchestrator has the tests run (implementer pass
    `review fixes` or mechanics, per the rules above), then a focused re-review
    before `publish`.
11. Publish: after a clean review and green checks, a new implementer with goal
    `publish` commits, pushes and opens the PR per `pull-request`. Before that,
    check PR size (`workflow.md`); over 1000 changed lines → ask the human first.
12. "Done reviewing" from the human → new implementer with goal `PR comments`:
    fixes the human's unresolved PR review comments per `pull-request` and
    leaves the diff uncommitted. The orchestrator runs a focused re-review
    (reviewer, re-review row); only after `APPROVE` a `publish` implementer
    commits, pushes and resolves the fixed threads. With no code host the
    remarks come in chat, are saved as `remarks-N.md` and go through a
    `review fixes` pass, a re-review and `publish`.
13. Base moved: merge it into the task branch only on a clean worktree, that
    is after `publish`. A clean merge is a `general-purpose` `haiku` mechanics
    subagent; with conflicts a new implementer with goal `merge base`. If the
    base moves before `publish`, tell the human and keep working on the old
    base.
14. Merge only when the human explicitly asks: a new implementer with goal
    `merge` (checks green, approval present, `gh pr merge` with the
    repository's merge method, then report). With no code host it merges the
    task branch into its confirmed base locally (`host-none.md`): in the
    worktree where the base is checked out, never stash a dirty one, `--no-ff
    --no-commit` unless the human or repository names a method, the plan's
    checks on the result, commit only when green, else `git merge --abort`;
    the task worktree is switched back to the task branch if it was used. The
    local merge commit is the one commit a `merge` pass may make. After the merge the orchestrator
    removes the task worktree if the human agrees; the branch stays.

The orchestrator never edits code, never commits and never opens a PR itself.
The only git it runs itself is mechanics that touch no code: `git fetch`,
creating the branch and `git worktree add`, `git worktree remove` after the
merge.
Max 3 implementers in parallel (one subscription feeds every subagent).
The implementer's description names all six pass goals (contract-tested).
Status for the human comes from `state.md` files, never from subagent
transcripts. Suggest restarting the orchestrator around 100k tokens of
context, only when no subagent is running.

## Roles and models (single table, by complexity class)

| Role | Light | Medium | Hard |
|---|---|---|---|
| Scout `orchestrator:scout` | sonnet / medium | sonnet / medium | sonnet / high |
| Planner `orchestrator:planner` | opus / high | opus / high | opus / xhigh |
| Implementation `orchestrator:implementer` | sonnet / medium | sonnet / high | opus / medium (high if stuck) |
| Review `orchestrator:reviewer` | opus / medium | opus / high | opus / high (mandatory) |
| Tester `orchestrator:tester` | sonnet / medium | sonnet / medium | sonnet / medium |
| Review fixes / PR comments (new implementer, goals `review fixes`, `PR comments`) | sonnet / medium | sonnet / medium | sonnet / high; hard part: opus / medium |
| Publish: commit, push, PR (new implementer, goal `publish`) | sonnet / low | sonnet / medium | sonnet / medium |
| Re-review of small fixes `orchestrator:reviewer` | sonnet / high | sonnet / high | opus / high |
| Screenshots `orchestrator:visual-checker` | haiku / low | haiku / low | sonnet / medium |
| Merge (new implementer, goal `merge`) | sonnet / low | sonnet / low | sonnet / low |
| Merge base into branch, no conflicts (`general-purpose`) | haiku / low | haiku / low | haiku / low |
| Mechanics: issue labels/comments, running a given script (`general-purpose`) | haiku / low | haiku / low | haiku / low |
| Orchestrator session itself | sonnet / medium (opus also fine) | | |

- Small fixes = up to ~200 changed lines since the last review, no shared
  contract change, no finding above "minor". Otherwise use the "Review" row.
- Merge base with conflicts → new implementer, goal `merge base`, sonnet / medium.
- Screenshot comparison against a design reference → sonnet / medium in any class.
- Text a human reads (commit messages, PR description) is written by sonnet,
  never haiku.

### Complexity class

Chosen by signals in the code, not by diff size. The planner names the class
with the signal and the file; the human approves it with the plan.

| Hard (opus) | Not hard (sonnet) |
|---|---|
| Concurrency: several async sources, cancellation, races, shared mutable state | New screen, page or component from a design |
| Lifecycle and state restoration, process/request lifetime, caching keys | Styling, themes, copy, previews |
| Data migrations, changes to persisted formats | Tests for existing logic |
| Offline cache, sync with a server, websockets, retries | Lint rule or config following an existing example |
| Public API used by two or more consumers: signature or behaviour change | Internal component of one module, new parameter with a default |

The plan states the class as an exact standalone line: `Complexity: hard` when
the whole task is hard, `Complexity: light` or `Complexity: medium` otherwise.
If only part of the task is hard, the plan lists it as the standalone line
`Hard part: <files>`. It never uses another label such as `Complexity class:`.
The main implementer runs on sonnet; a separate short implementer on opus
handles only those files. Only the opus implementer brief carries the
standalone line `Complexity: hard` or `Hard part: <files>`, copied from the
plan — the hook blocks it otherwise. The main sonnet brief carries
`Skip (separate opus pass): <files>` and must not change those files.

### Subagent economy

- Each subagent step re-reads its whole history: long history and images cost
  the most.
- New implementer per pass. Continue an old one with `SendMessage` only if its
  history is under 200k tokens and it has been idle under 60 minutes (the hook
  enforces this). Short notes to a running implementer are fine. Address an
  existing subagent by its agent id recorded in `state.md`, never by name.
- Images are opened only by `orchestrator:visual-checker` among the plugin's
  roles (hook-enforced). Implementer lists screenshot paths in `changes-N.md`; others read `visual-N.md`.
- Long output goes to `logs/` files; read only the tail and errors.
- Pass `model` (alias) and `effort` explicitly on every `Agent` call and write
  them to `state.md`. That is the route check: the session cannot observe the
  subagent's actual model.
- Bulk file reading goes to the scout, which returns short summaries with
  paths and line numbers.

## Hook: `subagent-guard.py`

PreToolUse on `SendMessage|Agent|Read`. Fails open (any exception → allow).
Port the logic of the original guard, generalized:

1. `SendMessage` to an agent whose type is `orchestrator:implementer`, whose
   last turn is finished, and whose transcript context exceeds 200k tokens or
   whose last assistant message is older than 60 minutes → deny with a reason
   telling the orchestrator to start a new implementer with the next pass
   number.
2. `Agent` with `subagent_type` `orchestrator:implementer`:
   - no explicit `model` → deny, reason "pass model and effort explicitly (see
     roles-and-models.md)";
   - model `opus` (or `claude-opus-*`) whose prompt has no standalone
     `Complexity: hard` or `Hard part: <files>` line → deny. An optional
     leading `- ` or `* ` bullet is accepted; `Hard part:` followed by
     nothing, `none` or `n/a` (any case), a value starting with `<` or only
     punctuation does not count.
3. `Read` of an image file (`.png .jpg .jpeg .webp .gif`) from inside a
   subagent whose type starts with `orchestrator:` and is not
   `orchestrator:visual-checker` (bare `visual-checker` is accepted too) →
   deny. The main orchestrator session and subagents of any other type
   (`general-purpose`, `Explore`, other plugins) may read images.

Deny format: JSON on stdout,
`{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "..."}}`.

## Agents (frontmatter)

| File | name | tools / disallowedTools | model in frontmatter |
|---|---|---|---|
| scout.md | scout | tools: Read, Grep, Glob, Write; disallowed: Edit, NotebookEdit, Agent, Bash | none (caller sets) |
| planner.md | planner | tools: Read, Grep, Glob, Write; disallowed: Edit, NotebookEdit, Agent, Bash | none |
| implementer.md | implementer | disallowed: Agent | none |
| reviewer.md | reviewer | tools: Read, Grep, Glob, Bash; disallowed: Write, Edit, NotebookEdit, Agent | none |
| tester.md | tester | tools: Read, Grep, Glob, Write, Edit; disallowed: Agent, Bash | none |
| visual-checker.md | visual-checker | tools: Read, Glob, Write; disallowed: Edit, NotebookEdit, Agent, Bash | none |

Every agent: if the brief lacks the task directory or a required path, ask
instead of guessing. Answer the orchestrator briefly; details go to files.

The reviewer uses Bash only for read-only git commands (`git diff`,
`git status`, `git log`, `git show`) and the repo's read-only checks if the
brief asks. It never writes to the worktree.

The tester writes test code into the worktree (that is why it has
Write/Edit) and notes into `test-N.md`; it never runs anything.

## Skills

- `orchestrator` (entry, ~130 lines): purpose, start-up (read references,
  record plugin root and home, confirm repo/base per task), intake and
  decomposition, the flow above in short form, quality control, summary
  format, red flags. Links to references.
- `code-review` (~90 lines): read-only; what to check (correctness against
  plan and acceptance criteria, single source of truth, duplication, error
  handling, concurrency, security, tests, repo conventions from AGENTS.md /
  CLAUDE.md, scope creep), severity scale (blocker, major, minor, nit),
  report format with the verdict line first (`APPROVE (<n> findings)`,
  `REQUEST CHANGES (<n> findings)`, `BLOCKED (<n> findings): <reason>`), each
  finding with file:line, why it matters and a concrete fix. Re-review checks
  only the fixes and the previous findings.
- `pull-request` (~110 lines): preconditions (clean review, green checks,
  size check), commit message convention (repo's own, else Conventional
  Commits, include issue reference `#123` when there is one), push, `gh pr
  create` with a description template (what, why, how to verify, risks,
  linked issue, "Known minor findings"), no remote → stop after commit and
  report. PR comment loop: `gh api` to list unresolved review threads by the
  human, fix valid ones and leave the diff uncommitted, reply only when a
  comment is invalid (explain why); other people's comments are not touched but
  listed in the report. After the re-review, the `publish` goal commits, pushes
  and resolves the fixed threads. Merge only on the human's explicit request
  (goal `merge`), after green checks and approval. A subagent never waits for
  the human: it lists open points in its report and finishes.

## README

Sections: what it is (2–3 sentences), install
(`/plugin marketplace add kenuuu-x/subagent-orchestrator`,
`/plugin install orchestrator@subagent-orchestrator`), requirements (Claude
Code, git, optional `gh` logged in), quick start example, how a task flows
(short list), roles and models table, complexity class, files it creates,
customising (home dir, per-project rules in `CLAUDE.md`), limitations, license.
