# subagent-orchestrator

A Claude Code plugin for plan-first development of one or several tasks from a
single session. The session you talk to is the orchestrator: it never writes
code itself. Research, planning, implementation, review, tests and screenshot
checks are done by subagents, each on the model and effort that fits the job.
You approve every plan before any code is written and you review the pull
request at the end.

## Install

```
/plugin marketplace add kenuuu-x/subagent-orchestrator
/plugin install orchestrator@subagent-orchestrator
```

Restart Claude Code (or run `/reload-plugins`) after installing.

### Requirements

- Claude Code with subagent support (the `Agent` tool).
- `git` 2.5+ (worktrees).
- Optional: the CLI of your code host, logged in: the
  [GitHub CLI](https://cli.github.com/) `gh` (`gh auth login`) or the GitLab
  CLI `glab` (`glab auth login`). It is used for pull requests and, with
  GitHub, for issues. Without it the flow stays local: a local commit, and a
  local merge when you ask for it.
- Optional: an MCP server for your tracker (Jira, Linear, Yandex Tracker or
  another), added to Claude Code by you. See "Setup and integrations".
- Python 3 for the plugin's safety hook.

## Quick start

Open Claude Code in your repository and run:

```
/orchestrator:orchestrate #42 #57 "add a dark theme toggle to settings"
```

Tasks can be GitHub issue numbers, tracker keys such as `ABC-123`, or plain
descriptions. The first time in a repository the orchestrator runs a short
setup interview (see "Setup and integrations"). Then it asks for the base
branch, builds a dependency graph, and runs independent tasks in parallel.

## How a task flows

1. **Intake.** Goal, acceptance criteria, repository and base branch are
   confirmed with you.
2. **Research.** The scout reads the code and writes a short summary with
   file paths and line numbers. Small tasks skip this step.
3. **Plan.** The planner writes `01-plan.md`: steps, files, checks, risks,
   expected diff size and the complexity (`Complexity: hard`, or
   `Hard part: <files>`) with its reason.
4. **Your approval.** The orchestrator retells the plan in chat. Nothing is
   written to the repository before you say yes.
5. **Implementation.** The implementer works in its own git worktree and
   branch, runs your project's checks and writes a change journal. The diff
   stays uncommitted.
6. **Review.** A fresh, read-only reviewer checks the diff and starts its
   report with `APPROVE (<n> findings)`, `REQUEST CHANGES (<n> findings)` or
   `BLOCKED (<n> findings): <reason>`. Blocker and major findings go back to a
   new implementer, then a focused re-review.
7. **Pull request.** After `APPROVE` (no open blocker or major finding) and
   green checks the implementer commits, pushes and opens the PR; unfixed minor
   findings go into the description. Diffs over 1000 lines are discussed with
   you first.
8. **Your review.** Comment on the PR on your code host, then tell the
   orchestrator you are done. An implementer fixes your comments without
   committing, a focused re-review checks the fixes, and after `APPROVE` another
   implementer commits, pushes and resolves the threads. The PR is merged only
   when you ask.

## Roles and models

The model and effort of each role depend on the task's complexity class.

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
model and effort. Rows of roles you switched off in the settings are skipped.

### Complexity class

The class comes from what the code does, not from how big the diff is. A task
is **hard** when it touches concurrency and races, lifecycle and state
restoration, data migrations, offline caching or server sync, or a public API
used by several consumers. A large but straightforward UI change is medium.

When only part of a task is hard, the plan names those files as a hard part:
the main work runs on sonnet and a short separate opus pass handles only those
files.

## Setup and integrations

The first time you start the orchestrator in a repository, it asks four
questions and saves the answers as `settings.json` in the project's directory
(see "Files it creates"). It never writes your repository for this.

1. **Tracker and mode.** GitHub Issues, Jira, Linear, Yandex Tracker, another
   tracker or none. Mode `read-only` only reads tasks; mode `automate` also
   sets statuses and comments, with the three status names you give (start,
   review, done).
2. **Code host.** GitHub (`gh`), GitLab (`glab`) or none (local commits).
3. **Roles.** The scout, the tester and the visual checker can be switched off.
   You may add custom roles: each has a name, a phase (`research`, `plan`,
   `review`, `publish`), a model and an effort. A custom role is read-only by
   default and writes only its own notes. A role with `writes: true` runs in the
   task worktree after the implementer, one at a time; its changes stay
   uncommitted and are reviewed with the rest. Writing is normally the
   implementer's job, so the interview asks once whether you want that; your
   choice wins.
4. **Chat language.** The language of the orchestrator's messages to you.
   Repository artifacts keep the project's own language: code, commit messages,
   PR descriptions and tracker comments follow the repository's rules.

Change an answer later with `/orchestrator:setup`, by saying "change setting X"
during a run, or by editing the JSON. Changes apply from the next phase. The
strict schema is in
`plugins/orchestrator/skills/orchestrator/references/setup.md`.

Everything that depends on a tracker or a code host lives in one short adapter
file per integration, in
`plugins/orchestrator/skills/orchestrator/references/adapters/`. The flow text
and the pull-request skill stay neutral. The adapters come from your settings.

| | Adapter | Setting |
|---|---|---|
| Code host | GitHub (`gh`) | `code_host`: `github` |
| Code host | GitLab (`glab`) | `code_host`: `gitlab` |
| Code host | none | `code_host`: `none`, or the host's CLI is missing or not logged in: local commits and a local merge |
| Tracker | GitHub Issues (`gh`) | `tracker.type`: `github-issues` |
| Tracker | Jira, Linear, Yandex Tracker or another, through your MCP server | `tracker.type` and `tracker.mcp_server` |

The plugin never stores a token or a password: the CLI logins and your MCP
servers hold them. A tracker is written to (status, comment) only in mode
`automate`.

## Cost guards

A plugin hook enforces three rules that keep subagent usage cheap:

- A finished implementer with a long history (over 200k tokens) or idle for
  an hour is not resumed; a new one starts from the task files.
- An implementer call needs an explicit model, and an opus implementer needs
  the line `Complexity: hard` or `Hard part: <files>` in its brief (the main sonnet brief gets
  `Skip (separate opus pass): <files>` instead).
- Only the visual checker among the plugin's roles opens images; everyone else
  reads its text verdict.

## Files it creates

Task documents live outside your repository, in `~/.subagent-orchestrator/`,
grouped per project:

```
~/.subagent-orchestrator/
  projects/<project-key>/
    settings.json            your setup answers
    roles/<name>.md          instruction files of custom roles
    runs/<run-id>.md         one state file per run: queue, your decisions,
                             active subagents
    tasks/<task-id>/
      research.md  01-plan.md  changes-N.md  review-N.md  visual-N.md
      test-N.md  custom-<name>-N.md  remarks-N.md  state.md  logs/
```

The project key is the name of your checkout directory (`-2` for a second
repository with the same name); `settings.json` records which repository the
directory belongs to. Each orchestrator run
has its own run file, so two sessions never overwrite each other; at start the
orchestrator asks which active run to resume. A 0.1.0 home (`orchestrator.md`
and `tasks/` directly in the home) can be resumed once and is moved into the
new layout.

Worktrees go next to your repository: `<repo>-worktrees/<task-id>/`.

## Customising

- Set `SUBAGENT_ORCHESTRATOR_HOME` to move the task documents, or put the
  line `Subagent orchestrator home: <absolute path>` in your project's
  `CLAUDE.md`. The environment variable wins; without either the home is
  `~/.subagent-orchestrator/`.
- Run `/orchestrator:setup` to change the tracker, the code host, the roles or
  the chat language.
- Put project rules in `AGENTS.md` or `CLAUDE.md` in your repository: build,
  test and lint commands, branch and commit conventions, language of commit
  messages. Every role reads them.

## Limitations

- At most three implementers run in parallel: all subagents share one
  subscription.
- The session cannot verify which model a subagent actually ran on; the
  orchestrator passes the model explicitly and records it in `state.md`.
- Pull requests: GitHub and GitLab. Without a remote, or without a login for
  the host's CLI, the flow is local: a local commit, your remarks in chat, and a
  local merge when you ask. A stacked task branches from its predecessor only
  after the predecessor is published.

## Development

```
./scripts/validate.sh
```

runs the structural contract (including the adapter files and their fixed
headings, the settings markers, and the word ban: integration names are allowed
only in the adapters, the setup reference and this README) and the hook tests.

## License

MIT
