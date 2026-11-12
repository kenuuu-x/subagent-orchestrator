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
  another), added to Claude Code by you. See "Integrations".
- Python 3 for the plugin's safety hook.

## Quick start

Open Claude Code in your repository and run:

```
/orchestrator:orchestrate #42 #57 "add a dark theme toggle to settings"
```

Tasks can be GitHub issue numbers, tracker keys such as `ABC-123`, or plain
descriptions. The orchestrator asks for the base branch, builds a dependency
graph, and runs independent tasks in parallel.

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
| Mechanics: issue labels/comments, running a given script (`general-purpose`) | haiku / low | haiku / low | haiku / low |
| Orchestrator session itself | sonnet / medium (opus also fine) | | |

### Complexity class

The class comes from what the code does, not from how big the diff is. A task
is **hard** when it touches concurrency and races, lifecycle and state
restoration, data migrations, offline caching or server sync, or a public API
used by several consumers. A large but straightforward UI change is medium.

When only part of a task is hard, the plan names those files as a hard part:
the main work runs on sonnet and a short separate opus pass handles only those
files.

## Integrations

Everything that depends on a tracker or a code host lives in one short adapter
file per integration, in
`plugins/orchestrator/skills/orchestrator/references/adapters/`. The flow text
and the pull-request skill stay neutral. The orchestrator picks the adapters
itself, from the `origin` URL and from the form of the task.

| | Adapter | Chosen when |
|---|---|---|
| Code host | GitHub (`gh`) | `origin` is on GitHub |
| Code host | GitLab (`glab`) | `origin` is on GitLab |
| Code host | none | no remote, or the host's CLI is missing or not logged in: local commits and a local merge |
| Tracker | GitHub Issues (`gh`) | the task is `#123` on a GitHub host |
| Tracker | Jira, Linear, Yandex Tracker or another, through your MCP server | the task is a key such as `ABC-123`; the orchestrator asks which tracker |

The plugin never stores a token or a password: the CLI logins and your MCP
servers hold them. A tracker is written to (status, comment) only when you ask
for it.

## Cost guards

A plugin hook enforces three rules that keep subagent usage cheap:

- A finished implementer with a long history (over 200k tokens) or idle for
  an hour is not resumed; a new one starts from the task files.
- An implementer call needs an explicit model, and an opus implementer needs
  the line `Complexity: hard` or `Hard part: <files>` in its brief (the main sonnet brief gets `Skip (separate opus pass): <files>` instead).
- Only the visual checker among the plugin's roles opens images; everyone else
  reads its text verdict.

## Files it creates

Task documents live outside your repository, in `~/.subagent-orchestrator/`,
grouped per project:

```
~/.subagent-orchestrator/
  projects/<project-key>/
    runs/<run-id>.md         one state file per run: queue, your decisions,
                             active subagents
    tasks/<task-id>/
      research.md  01-plan.md  changes-N.md  review-N.md  visual-N.md
      test-N.md  remarks-N.md  state.md  logs/
```

The project key is the name of your checkout directory. Each orchestrator run
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
headings, and the word ban: integration names are allowed only in the adapters
and this README) and the hook tests.

## License

MIT
