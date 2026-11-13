# subagent-orchestrator — design spec

A Claude Code plugin that coordinates one or more development tasks from a
single session. Every role (research, plan, code, review, tests, screenshots,
mechanics) is a subagent with its own model and effort. The human approves the
plan before any code and reviews the pull request at the end.

This spec is the single source of truth for file names, agent names, paths and
rules. Every file in the plugin must agree with it.

## Hard constraints

- English everywhere in the plugin (skills, agents, commands, README, tests).
- Generic: no company, product or platform names. Never write any of:
  `locali`, `LOCALIAPP`, `pult`, `OPSBOT`, bare `Yandex` (only the integration
  name `Yandex Tracker` is allowed), `Gradle`, `Android`, `iOS`, `Maestro`,
  `emulator`, `Figma`, `libs` (as a product), `StudioProjects`,
  `.locali-handoff`, `build-lock`, `work-slot`, `emulator-lock`, Cyrillic text.
  The contract test fails on these words.
- Integration names (`GitLab`, `glab`, `Yandex Tracker`) are product features,
  not company words. They are allowed only in the adapter files under
  `references/adapters/`, in `references/setup.md` and
  `hooks/orchestrator_settings.py` (both hold the settings schema enums) and in
  `README.md`. This spec and the test list them on purpose. Anywhere else in
  the generic flow text they fail the contract test.
- Stack-agnostic: build, test and lint commands come from the target
  repository (`AGENTS.md`, `CLAUDE.md`, `README`, `package.json`, `Makefile`,
  `pyproject.toml`, CI config). Examples may name several ecosystems side by
  side (`npm test`, `pytest`, `cargo test`, `./gradlew test`) only as a list of
  examples — prefer no examples at all.
- Code hosting and issue tracking go through adapters, one short file per
  integration with fixed headings (contract-tested). The flow text and the
  `pull-request` skill are host-neutral: every host command lives in the host
  adapter, whose absolute path the brief carries.
  - Code hosts: GitHub (`gh`), GitLab (`glab`), or none. With no remote, or no
    login for the host's CLI, `publish` is a local commit, the human's remarks
    come in chat and `merge` is a local merge (`host-none.md`).
  - Trackers are optional. GitHub Issues uses `gh`. Every other tracker (Jira,
    Linear, Yandex Tracker, other) goes through the human's own MCP server. The
    adapters describe operations, never MCP tool names, and the plugin never
    stores a token, a password or a URL with credentials.
  - A task is an issue (`#123`, or a key such as `ABC-123`) or a free-text
    description.
- Per-project choices (tracker, code host, roles, chat language) come from a
  settings file written by a first-run interview, never from guesses (see
  "First-run setup and settings").
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
  .claude-plugin/plugin.json             plugin "orchestrator", version 0.2.0
  commands/orchestrate.md                /orchestrator:orchestrate <tasks>
  commands/setup.md                      /orchestrator:setup [setting to change]
  skills/orchestrator/SKILL.md           entry skill (disable-model-invocation: true)
  skills/orchestrator/references/
    workflow.md                          task lifecycle, branches, worktrees, checkpoints, PR size
    roles-and-models.md                  role table, complexity class, subagent economy, call rules
    briefs.md                            what each subagent brief must contain
    parallel-work.md                     when tasks may run in parallel
    task-files.md                        project, run and task layout, state.md and run-file templates
    setup.md                             first-run interview, settings.json schema, change path
    adapters/index.md                    which adapter to use and how to choose it
    adapters/host-github.md              code host GitHub: gh and GraphQL commands
    adapters/host-gitlab.md              code host GitLab: glab and API commands
    adapters/host-none.md                no code host: local commit, remarks, stacked tasks, local merge
    adapters/tracker-github-issues.md    tracker GitHub Issues (gh)
    adapters/tracker-mcp.md              shared rules for every tracker reached through MCP
    adapters/tracker-jira.md             tracker Jira, through MCP
    adapters/tracker-linear.md           tracker Linear, through MCP
    adapters/tracker-yandex-tracker.md   tracker Yandex Tracker, through MCP
    adapters/tracker-other.md            any other tracker, through MCP
  skills/code-review/SKILL.md            review procedure + report format (read-only; disable-model-invocation: true)
  skills/pull-request/SKILL.md           host-neutral: commit, push, PR, PR comment loop, merge on request (disable-model-invocation: true)
  agents/scout.md
  agents/planner.md
  agents/implementer.md
  agents/reviewer.md
  agents/tester.md
  agents/visual-checker.md
  hooks/hooks.json
  hooks/subagent-guard.py
  hooks/orchestrator-context.py
  hooks/orchestrator_settings.py
tests/test_subagent_guard.py             unittest for the guard hook
tests/test_orchestrator_context.py       unittest for the context hook
tests/test_orchestrator_settings.py      unittest for the settings module
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
  lowercase kebab-case (the git common dir resolved to an absolute path first).
  Lookup: (1) scan `<key>`, `<key>-2`, ... to the first missing suffix;
  (2) a parsed `settings.json` with `repo` equal to this main checkout is the
  project; (3) a `settings.json` that exists but cannot be parsed, or has no
  string `repo`: stop, show the error, ask the human, never skip it; (4) no
  match: the first settings-less directory whose tasks are empty or all name
  this checkout (ask before adopting one with tasks), else the first missing
  suffix, and run setup there. The hooks use steps 1-3 (no match means no
  settings: run setup). A task directory always lives in the project of its
  own `Repo:`; per task, the settings of that project apply, and the chat
  language comes from the project where the run started.
- Settings file: `<home>/projects/<project-key>/settings.json`. Custom role
  instruction files: `<home>/projects/<project-key>/roles/<name>.md`.
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
  - `custom-<name>-N.md` (a custom role: notes or findings; for a writing role
    a change journal)
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
  (follow the repository's own convention if it has one). One writer per
  worktree: every implementer, tester and writing custom role brief carries
  the standalone line `Worktree: <absolute path>`, and the hook denies a
  second writer there (rule 10).

## Adapters

Host adapters have the headings `## Check access`, `## Find or open`,
`## Review threads`, `## Reply and resolve`, `## Checks and approval`,
`## Merge`. Tracker adapters have `## Read a task`, `## Task id`,
`## Change status`, `## Comment`, `## Link a pull request`. The contract test
requires every adapter file and every heading.

- Host adapters: `host-github.md` (the `gh` and GraphQL commands), `host-gitlab.md`
  (`glab mr` commands, `glab api` for discussions, `resolved=true` to resolve a
  thread), `host-none.md` (local flow).
- Tracker adapters: `tracker-github-issues.md`, `tracker-mcp.md` (shared rules),
  `tracker-jira.md`, `tracker-linear.md`, `tracker-yandex-tracker.md`,
  `tracker-other.md`.
- Choice (`adapters/index.md`): the settings decide. The host from `code_host`
  (a host CLI that is missing or not logged in now means `host-none.md` for
  this run); the tracker from `tracker.type` (`github-issues` uses `gh`; the
  others use the MCP adapter; type or access `none` means free text). A task
  whose form does not fit the type: ask. The orchestrator records both in the
  run file.
- Who does what: the orchestrator reads tasks itself. Status changes and
  comments go to a `general-purpose` `haiku` mechanics subagent, one exact
  action per call, and the orchestrator writes the comment text. The
  orchestrator writes to a tracker only in mode `automate`, with the status
  names from the settings. Automation points: the start status when the plan
  is approved; the review status and a comment with the PR link after
  `publish`; the done status after `merge`.
- Briefs: the code-host adapter's absolute path goes into every `publish`,
  `PR comments` and `merge` brief; the tracker adapter's into a `publish` brief
  with an issue reference and into a mechanics brief that changes a tracker.

## First-run setup and settings

- Reference `references/setup.md` and command `/orchestrator:setup` (a command,
  not an argument keyword, so it cannot clash with a free-text task called
  "setup"). The settings file is `<home>/projects/<project-key>/settings.json`.
  It lives in the work home, not in the repository: the orchestrator never
  writes the repository, and the answers are personal.
- When: before the intake of the first task in a repository whose settings file
  is missing or invalid. The orchestrator detects defaults (`git remote get-url
  origin`, `gh auth status`, `glab auth status`, the MCP servers visible in the
  session), asks four numbered questions in one message and writes the file
  only after the human answered. It validates the file and retells it in two
  lines.
- Questions: (1) tracker and mode (`read-only` or `automate`, with the status
  names `start`, `review`, `done`); (2) code host (`github`, `gitlab`, `none`);
  (3) roles: the core is fixed, scout, tester and visual-checker can be
  switched off (`roles_off`), custom roles are optional; (4) chat language.
- Schema (version 1, strict JSON, every key required, `null` when it does not
  apply, unknown keys are errors): `version`, `repo`, `tracker` (`type`,
  `name`, `access`, `mcp_server`, `mode`, `statuses`), `code_host`,
  `roles_off`, `custom_roles`, `chat_language`, `saved`. The allowed values and
  the cross-field rules are in `setup.md`; the file never holds a token, a
  password or a URL with credentials.
- Language rule: Repository artifacts keep the project's own language (code,
  comments, commit messages, PR descriptions, tracker comments follow the
  repository's `AGENTS.md` / `CLAUDE.md` or history). Briefs and reports between
  agents stay in English. Only messages to the human use `chat_language`.
- Change path: `/orchestrator:setup` runs the interview again with the current
  values as defaults (one answer may be changed alone); during a run "change
  setting X" asks only that question and rewrites the file; or the human edits
  the JSON. Changes apply from the next phase; a running subagent keeps its
  brief.
- Use: the settings pick the adapters, switch roles off (the planner leaves
  them out of the task's role table; their rows are skipped), and add custom
  roles. The planner and the reviewer briefs carry the settings path. The
  reviewer adds a route-check finding when the agent calls in `state.md`
  disagree with the settings: minor, and major only when the wrongly run role
  changed the diff. The reviewer brief also carries the `custom-<name>-N.md`
  journals and instruction paths of the writing roles; their changes are in
  scope.

### Custom roles

- A role runs as a `general-purpose` agent with an instruction file
  (`<home>/projects/<project-key>/roles/<name>.md`, or a path the human gives),
  or as a project-defined or user-defined agent type the human names. Never in
  the plugin's own agent namespace. Each role has a `phase`, a `model` and an
  `effort`, passed explicitly on the `Agent` call. In `state.md` it is
  `custom:<name>`; the goal is the phase.
- Read-only (the default, `writes: false`): phases `research` (after the scout;
  the planner gets the output), `plan` (after `01-plan.md`, before the retell),
  `review` (parallel with the reviewer, same uncommitted diff), `publish` (a
  gate after the clean review and the size check). It writes only
  `<task dir>/custom-<name>-N.md`; in `review` and `publish` the file starts
  with a verdict line, and `REQUEST CHANGES` joins the fix loop (the `review
  fixes` brief lists the file next to `review-N.md`).
- Writing (`writes: true`, phase `implementation` only): runs in the task
  worktree after the implementer pass `implementation`, strictly one at a time,
  never with an implementer or another writer. Its changes stay uncommitted and
  the review runs after the writers. It writes `custom-<name>-N.md` as a change
  journal with the sections of `changes-N.md`, runs the plan's checks, never
  commits. Its brief carries the standalone line `Worktree: <absolute path>`
  (rule 10). A role with `writes: false` writes only inside the task directory
  (rule 12).
  The interview warns once that writing is normally the implementer's job; the
  human's choice wins.
- Custom roles are not rows of the shared role table: a rule under the table
  says so. Docs never write the plugin's agent prefix followed by a custom role
  name (the contract test would fail).

## Task flow (orchestrator)

1. Intake: for each task record goal, acceptance criteria, repository, base
   branch (confirmed by the human), links. An issue is read through the tracker
   adapter (GitHub Issues: `gh issue view`).
2. Decompose and build a dependency graph (`parallel-work.md`).
3. Research: `orchestrator:scout`, read-only. Small tasks skip the scout, and
   so do projects that switched it off.
4. Plan: `orchestrator:planner` writes `01-plan.md` including the complexity
   (the standalone line `Complexity: light|medium|hard`, or `Hard part: <files>`
   when only part is hard) with its reason, the role/model table for this task,
   files, steps, checks (commands from the repo), risks, and an estimated diff
   size. The planner reads the settings and builds the table from them.
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
   for the listed files. It and the main implementer run one after the other
   in the same worktree (one writer per worktree), the pass that the plan puts
   first going first; by default the hard part goes first. Stuck on `sonnet`
   (two attempts at the same error, or edits going in circles) → repeat the
   step with a new `opus` implementer.
   Writing custom roles run after it, one at a time.
8. Review: fresh `orchestrator:reviewer`, read-only, per `code-review`. First
   line of its report is the verdict: `APPROVE (<n> findings)`,
   `REQUEST CHANGES (<n> findings)` or `BLOCKED (<n> findings): <reason>`.
   `APPROVE` = no open blocker or major finding; the PR may be published.
   Minor findings and nits under an APPROVE are not fixed before publishing;
   the publish implementer lists them in the PR description under "Known minor
   findings". `REQUEST CHANGES` = at least one blocker or major. The
   orchestrator saves the report as `review-N.md` and tells the human only the
   first line. If `changes-N.md`
   lists screenshots, run `orchestrator:visual-checker` in parallel (unless
   switched off). Read-only `review` custom roles run in parallel too.
9. Fixes: a NEW implementer, goal `review fixes`, pass N+1, gets only paths to
   `review-N.md` / `visual-N.md` and each `custom-<name>-N.md` with
   `REQUEST CHANGES`. Then a focused re-review (small fixes → reviewer on
   `sonnet`/`high`).
10. Tests on request (not when the tester is switched off):
    `orchestrator:tester` writes an end-to-end or integration test in the
    project's existing test framework (its brief has
    absolute paths of the worktree, `01-plan.md` and `changes-N.md`, no pasted
    diff; it reads files with Read/Glob/Grep); running it is a `general-purpose`
    `haiku` subagent, only when the human asks. The test code joins the diff:
    after the tester the orchestrator has the tests run (implementer pass
    `review fixes` or mechanics, per the rules above), then a focused re-review
    before `publish`.
11. Publish: after a clean review and green checks, a new implementer with goal
    `publish` commits, pushes and opens the PR per `pull-request`. Before that,
    check PR size (`workflow.md`); over 1000 changed lines → ask the human first.
    `publish` custom roles run as a gate after the clean review and the size
    check.
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
    `merge` (checks green, approval present, the host adapter's merge command
    with the repository's merge method, then report; when the adapter requires
    a method flag and none is named it stops and reports). With no code host it
    merges the task branch into its confirmed base locally (`host-none.md`): in the
    worktree where the base is checked out, never stash a dirty one, `--no-ff
    --no-commit` unless the human or repository names a method, the plan's
    checks on the result, commit only when green. Conflicts: `git merge
    --abort`, report, and the orchestrator runs a `merge base` pass and tries
    again. Red checks without conflicts: `git merge --abort`, report the
    failing checks; the orchestrator tells the human and does not retry. The
    task worktree is switched back to the task branch if it was used. The
    local merge commit is the one commit a `merge` pass may make. After the
    merge the orchestrator removes the task worktree if the human agrees; the
    branch stays.

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
| Mechanics: tracker status/comments, running a given script (`general-purpose`) | haiku / low | haiku / low | haiku / low |
| Orchestrator session itself | sonnet / medium (opus also fine) | | |

Custom roles come from the settings file, not from this table: each has its own
model and effort. Rows of roles switched off in the settings are skipped.

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

PreToolUse on `SendMessage|Agent|Read|Write|Edit|MultiEdit|NotebookEdit`.
Both hooks share `hooks/orchestrator_settings.py` (stdlib only). It holds
`find_home`, `main_checkout`, `project_key` and `project_dir` (the lookup of
task-files.md, steps 1-3), `load_settings` and `validate_settings` (the schema
of setup.md, then the existence of instruction files), `active_runs` and
`parse_run_file`, `task_dir_from_brief` and `brief_line`. It also holds the
path helpers `path_key`, `same_path` and `is_inside` (`~` expanded, relative
paths joined to the cwd, symlinks resolved, case folded on a case-insensitive
file system), `trusted_task` and `repo_names_home`.

Known bad states get an explicit deny. An unexpected exception, or a failed
import of that module (rules 5-12 are then skipped), allows the call.

1. `SendMessage` to an agent whose type is `orchestrator:implementer`, whose
   last turn is finished, and whose transcript context exceeds 200k tokens or
   whose last assistant message is older than 60 minutes → deny with a reason
   telling the orchestrator to start a new implementer with the next pass
   number.
2. `Agent` with `subagent_type` `orchestrator:implementer` and model `opus`
   (or `claude-opus-*`) whose prompt has no standalone `Complexity: hard` or
   `Hard part: <files>` line → deny. An optional leading `- ` or `* ` bullet is
   accepted; `Hard part:` followed by nothing, `none` or `n/a` (any case), a
   value starting with `<` or only punctuation does not count.
3. `Read` of an image file (`.png .jpg .jpeg .webp .gif`) from inside a
   subagent whose type starts with `orchestrator:` and is not
   `orchestrator:visual-checker` (bare `visual-checker` is accepted too) →
   deny. The main orchestrator session and subagents of any other type
   (`general-purpose`, `Explore`, other plugins) may read images.

An `Agent` call with an `orchestrator:*` type is checked in the order 4, 2, 5,
6, 7, 8, and, for an implementer or a tester, 10:

4. No explicit `model` → deny, reason "pass model and effort explicitly (see
   roles-and-models.md)". It applies to every plugin agent.
5. The brief has no `Task directory: <home>/projects/<key>/tasks/<id>` line
   (absolute path, optional bullet and backticks; `~` is not expanded) → deny.
   The home in that line must be the trusted work home, `find_home(cwd)` of the
   event (symlinks and case variants compared as one path), or a home that the
   project's repository names: the `repo` of that project's `settings.json` is
   a main checkout whose project key fits and whose `find_home` is that home
   (`repo_names_home`). Another home → deny. The brief cannot point the hook
   at settings it chose. So the hooks find the home from the session's working
   directory; a `CLAUDE.md` home line works only for a session started inside
   that repository or for a project whose repository names it. Otherwise, and
   for runs over repositories with different homes, the human sets
   `$SUBAGENT_ORCHESTRATOR_HOME`. The deny reason names the cwd and the hook's
   home: "start the session in the repository whose CLAUDE.md names <task
   home>, or set SUBAGENT_ORCHESTRATOR_HOME".
6. The project from that path has no `settings.json` → deny, "run the setup
   interview". A file that is not JSON, breaks the setup.md schema or names a
   missing instruction file → deny with the errors.
7. When the event has `session_id`: it must be in the `Sessions` line of an
   active run file (`- Status: active`) in the `runs/` of any project of the
   brief's home or of the cwd home; otherwise deny, the reason carries the
   id. A run file is parsed by its first `- Status:`, `- Sessions:` and
   `- Run id:` lines; placeholders like `<session id>` are ignored.
8. The role (`scout`, `tester`, `visual-checker`) is in `roles_off` → deny.

9. A custom role call (any other `Agent` call): found by `subagent_type`
   equal to a role's non-general-purpose `agent_type`, or by a role's
   instruction path in the prompt. Its settings come from the brief's
   `Task directory:` line. Without that line they come from the cwd lookup,
   in any session in that repository. So a configured non-general-purpose
   `agent_type` is held to the settings' model there, also outside a run.
   The `model` must equal the role's, and `effort` too when the call passes
   it; otherwise deny. With several matched roles one fitting pair is enough.
   A broken `settings.json` (not JSON, breaks the schema, or names a missing
   instruction file):
   - found through `Task directory:` → deny;
   - found through cwd → deny when the raw JSON still matches a custom role
     (type-guarded) or when the event's `session_id` is in an active run of
     that home. Otherwise allow: a session that does not orchestrate is not
     blocked by broken settings.

10. One writer per worktree. It applies to an `orchestrator:implementer` or
    `orchestrator:tester` call (after rules 4-8) and to a custom role call
    whose matched role has `writes: true` (after rule 9). The brief needs a
    standalone absolute `Worktree: <path>` line (optional bullet and
    backticks); without it → deny. Also deny when another unfinished
    subagent of the same session has a brief with the same `Worktree:`
    (symlinks and case compared) and its last transcript activity is under
    60 minutes old. The subagent is read
    from the session's `subagents/agent-<id>.meta.json` (`finished: true` once
    done) and its transcript. Not counted: the plugin's read-only roles
    (`scout`, `planner`, `reviewer`, `visual-checker`) and the caller itself.
    The tester counts: it writes test code into the worktree. A subagent idle
    for over 60 minutes (for example after a crash) no longer blocks. The deny
    reason gives the last activity as a local time and the time the lock ends:
    after a resume the old subagent is gone and cannot be stopped, so the
    orchestrator waits until then or asks the human.

11. `Write`, `Edit`, `MultiEdit` or `NotebookEdit` of
    `<home>/projects/<key>/settings.json`. The home comes from
    `find_home(cwd)`, or it is a home that the repository in the present file
    or in the new content names (`repo_names_home`). The names
    `settings.json` and `projects` are compared without case. Other
    `settings.json` files are not touched.
    - From a subagent → deny: only the orchestrator writes it.
    - `Edit`, `MultiEdit` and `NotebookEdit` → deny: rewrite the whole file
      with `Write`.
    - `Write` whose content breaks the schema or names a missing instruction
      file → deny. Write the instruction files first, then the settings.

12. `Write`, `Edit`, `MultiEdit` or `NotebookEdit` from a read-only custom
    role (`writes: false`) → deny unless the resolved target is inside the
    task directory of its brief. The role is found from the event's `agent_id`
    (and a non-plugin `agent_type`): its brief is read from the subagent
    transcript and its settings from the trusted home. A brief without a
    `Task directory:` in the work home leaves it no writable place. The
    reason names the file to use, `custom-<name>-N.md` in the task directory.
    Runs after rule 11.

Hardening. Rule 11 resolves the target before any check: the path joined to
the cwd, `~` expanded, symlinks followed. A relative path, a symlink named like
another file, `..` and a case variant of the home (case-insensitive file
system) cannot hide a settings write. The same resolution protects rule 12. The
brief's task directory must lie inside the trusted work home (rule 5). Settings
for rules 9 and 12 come from that home; a brief in another home is ignored for
a non-plugin call (the cwd lookup applies) and denied for an `orchestrator:*`
call.

What the hooks cannot enforce:

- That a subagent really runs the model it was given (the route check in
  `state.md` plus the reviewer's finding stand in).
- The `Sessions` entry being genuine (it is a link, not a proof).
- A settings file changed by `Bash`, and files written by a read-only custom
  role through `Bash`. The orchestrator is told in its skill to write the
  settings only with `Write`.
- Rule 12 needs `agent_id` in the event; without it nothing is checked.
- After a crashed subagent the worktree lock of rule 10 holds for up to 60
  minutes. Check its `agent-<id>.meta.json` or stop it. After a resume of the
  orchestrator session the old subagent cannot be stopped: wait for the time
  in the deny reason, or ask the human.
- Rule 10 sees only subagents that already exist. Writers started in the same
  assistant message are not seen; the orchestrator starts one writer per
  message.

Deny format: JSON on stdout,
`{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "..."}}`.

## Hook: `orchestrator-context.py`

The orchestrator session loses its settings when the context is compacted, and
it can forget the chat language over a long run. This hook puts them back.
Events: `UserPromptSubmit` (every prompt) and `SessionStart` with matcher
`compact|resume`. Output: `hookSpecificOutput.additionalContext`.

- Active only in a session listed under `Sessions` in an active run file of the
  work home (`find_home(cwd)`). For a cwd outside any repository it also looks
  in the homes that the repositories directly below the cwd name in their
  `CLAUDE.md`; a run there counts only when its project's repository names
  that home (`repo_names_home`, as rule 5). Other sessions get nothing.
- Every prompt: at most three lines. The run id and the rule to answer the
  human in the chat language (repository artifacts keep the project's own
  language); the settings path with the roles that are off and the custom
  roles; for a prompt that starts with `/orchestrator:orchestrate` (or the
  short form `/orchestrate`), the bootstrap line with the session id and the
  instruction to record it in the `Sessions` line of the run file.
- Bootstrap: a session that is not yet listed gets only the bootstrap line, and
  only for that command.
- After `compact` or `resume`: the full block. It adds the code host, the
  tracker, the run file path, the task directories of the queue rows whose
  phase is not `done`, and the instruction to re-read the run file and every
  `state.md` before the next step. With several active runs of the session the
  last one by project and run name is used.
- Invalid settings: the lines say so with the first error and point to
  `/orchestrator:setup`.
- Every value from the settings or the run file (run id, chat language,
  paths, roles, tracker, code host, first error, task directories) is
  rendered as quoted data: control, format and separator characters and
  whitespace runs become one space, `"` becomes `'`, and the length is capped
  (60 characters for names, 200 for paths and the error, 300 for role lists;
  at most five task directories). A value cannot add a line or an
  instruction-like block. `validate_settings` also limits `chat_language` to
  one line of at most 40 letters, spaces, hyphens and parentheses.
- Fail open: any error, an unreadable event or a missing shared module injects
  nothing.

## Agents (frontmatter)

| File | name | tools / disallowedTools | model in frontmatter |
|---|---|---|---|
| scout.md | scout | tools: Read, Grep, Glob, Write; disallowed: Edit, NotebookEdit, Agent, Bash | none (caller sets) |
| planner.md | planner | tools: Read, Grep, Glob, Write; disallowed: Edit, NotebookEdit, Agent, Bash | none |
| implementer.md | implementer | disallowed: Agent | none |
| reviewer.md | reviewer | tools: Read, Grep, Glob, Bash; disallowed: Write, Edit, NotebookEdit, Agent | none |
| tester.md | tester | tools: Read, Grep, Glob, Write, Edit; disallowed: Agent, Bash | none |
| visual-checker.md | visual-checker | tools: Read, Glob, Write; disallowed: Edit, NotebookEdit, Agent, Bash | none |

The planner reads `settings.json` and builds the task's role table from it. The
reviewer reads it and the task's `state.md` for the route check.

Every agent: if the brief lacks the task directory or a required path, ask
instead of guessing. Answer the orchestrator briefly; details go to files.

The reviewer uses Bash only for read-only git commands (`git diff`,
`git status`, `git log`, `git show`) and the repo's read-only checks if the
brief asks. It never writes to the worktree.

The tester writes test code into the worktree (that is why it has
Write/Edit) and notes into `test-N.md`; it never runs anything.

## Skills

- `orchestrator` (entry, ~210 lines): purpose, start-up (read references,
  record plugin root and home, read or create the settings, confirm repo/base
  per task), intake and
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
- `pull-request` (~110 lines): host-neutral. The brief carries the absolute
  path of the code-host adapter, which holds every host command. Preconditions
  (clean review, green checks, size check), commit message convention (repo's
  own, else Conventional Commits, with the issue reference in the form the
  tracker adapter gives), push, create the PR with a description template (what,
  why, how to verify, risks, linked issue, "Known minor findings"), no remote
  or no login → host-none adapter, stop after the commit and report. PR comment
  loop: list unresolved review threads by the human (adapter), fix valid ones
  and leave the diff uncommitted, reply only when a comment is invalid (explain
  why); other people's comments are not touched but listed in the report. After
  the re-review, the `publish` goal commits, pushes and resolves the fixed
  threads. Merge only on the human's explicit request (goal `merge`), after
  green checks and approval. A subagent never waits for the human: it lists
  open points in its report and finishes.

## README

Sections: what it is (2–3 sentences), install
(`/plugin marketplace add kenuuu-x/subagent-orchestrator`,
`/plugin install orchestrator@subagent-orchestrator`), requirements (Claude
Code, git, optional host CLI logged in and optional tracker MCP server), quick
start example, how a task flows (short list), roles and models table,
complexity class, setup and integrations (the interview, the settings,
adapters), files it creates,
customising (home dir, per-project rules in `CLAUDE.md`), limitations, license.
