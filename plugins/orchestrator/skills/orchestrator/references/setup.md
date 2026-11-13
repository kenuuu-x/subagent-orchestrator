# Setup and settings

Each project has one settings file. A first-run interview creates it, and
`/orchestrator:setup` changes it. The orchestrator reads this file at
start-up; subagents get only what their brief says.

## Where and when

- File: `<home>/projects/<project-key>/settings.json`. Home and project key:
  [task-files.md](task-files.md). The file is personal and stays outside the
  repository: you never write the repository, and answers such as your chat
  language or MCP server names must not reach teammates.
- Run the interview before the intake of the first task, when the project has
  no settings file or the file fails the rules below. Also run it on
  `/orchestrator:setup`.
- Write the file only after the human answered, with the Write tool and the
  whole file. The hook refuses Edit; never write it through Bash. Never fill
  answers in yourself.
  A missing or invalid file is never "fixed" silently: ask, then rewrite.
- The file never holds a token, a password or a URL with credentials. Logins
  stay in the `gh`/`glab` CLIs and in the human's MCP servers.

## Interview

1. Detect defaults with read-only commands: `git remote get-url origin`,
   `gh auth status`, `glab auth status`, and the MCP servers whose tools are
   visible in the session. With an existing file, its values are the defaults.
2. Ask the four numbered questions in one message, each with its default:
   1. Tracker and mode. Tracker: GitHub Issues (`gh`), Jira, Linear,
      Yandex Tracker, another tracker, or none. Every tracker except GitHub
      Issues is read through the human's MCP server: ask for its name. If its
      tools are not visible, tell the human to add the server, and set access
      `none` for now (tasks are free text). Mode: `read-only` (only read tasks)
      or `automate` (also set statuses and comment); `automate` needs three
      status names: start, review, done.
   2. Code host: `github` (`gh`), `gitlab` (`glab`) or `none` (local commits
      only).
   3. Roles. The core is fixed: intake, plan approval, planner, implementer,
      read-only reviewer, checkpoints. Scout, tester and visual-checker can be
      switched off. Custom roles are optional: see "Custom roles".
   4. Chat language: the language of your messages to the human.
3. Validate the answers against the rules below before any write. A rule fails
   because of an answer: ask that question again. Fix only formatting mistakes
   yourself, and tell the human what you changed.
4. Write the instruction file of each custom role first, then write
   `settings.json` with the Write tool. Set `saved` to today's date. Retell the
   result in two lines: tracker with mode, host, roles, language.

### Language rule

Repository artifacts keep the project's own language. Code, code comments,
commit messages, PR descriptions and tracker comments follow the project's
`AGENTS.md` / `CLAUDE.md` or its history. Briefs and reports between agents stay
in English. Only your messages to the human in chat use `chat_language`.

### Custom roles

A custom role is an extra subagent of one project. Ask for each role: a name,
what it checks or does, its phase, model and effort. Phases and the rules for
running them: [workflow.md](workflow.md), "Custom roles". Suggest defaults and
let the human change them: `opus` / `high` for `review` and `plan`, `sonnet` /
`medium` for `research` and `publish`.

- Default: read-only (`writes: false`). Run it as a `general-purpose` agent with
  an instruction file. Write the human's description to
  `<home>/projects/<project-key>/roles/<name>.md` (purpose, what to check or
  do, what to report), or use an absolute path the human gives. Or the human
  names an agent type defined in the project's or the user's `.claude/agents/`.
- A role that writes or implements (`writes: true`, phase `implementation`):
  say once that implementation is normally the implementer's job, and ask
  whether the role should be an extra implementer pass or a reviewer-style
  role instead. The human's choice wins; nothing is forbidden.

## Change path

Changes apply from the next phase; a running subagent keeps its brief.

1. `/orchestrator:setup` runs the interview again with the current values as
   defaults. The human may change one answer alone.
2. During a run the human says "change setting X". Ask only that question,
   rewrite the whole file with Write, and note the decision in your run file.
3. The human edits the JSON by hand. Validate it when you next read it.

A rewrite keeps `repo` and every untouched value, and sets `saved`.

## Schema, version 1

```json
{
  "version": 1,
  "repo": "/home/dev/work/my-app",
  "tracker": {
    "type": "jira",
    "name": null,
    "access": "mcp",
    "mcp_server": "jira",
    "mode": "automate",
    "statuses": {"start": "In Progress", "review": "In Review", "done": "Done"}
  },
  "code_host": "gitlab",
  "roles_off": ["visual-checker"],
  "custom_roles": [
    {
      "name": "security-reviewer",
      "agent_type": "general-purpose",
      "instructions": "/home/dev/.subagent-orchestrator/projects/my-app/roles/security-reviewer.md",
      "phase": "review",
      "writes": false,
      "model": "opus",
      "effort": "high"
    }
  ],
  "chat_language": "German",
  "saved": "2026-11-12"
}
```

The file is one JSON object. These rules are strict, because a program parses
the file:

- Every key below is required; a key that does not apply holds `null`. A key not
  listed is an error, at every level. Strings are non-empty.
- `version`: the integer `1`.
- `repo`: the absolute path of the main checkout, as `task-files.md` defines it.
- `tracker`: an object with exactly these keys:
  - `type`: `none`, `github-issues`, `jira`, `linear`, `yandex-tracker` or
    `other`.
  - `name`: the tracker's name when `type` is `other`, else `null`.
  - `access`: `gh`, `mcp` or `none`. `github-issues` takes `gh`, `none` takes
    `none`, every other type takes `mcp` or `none`.
  - `mcp_server`: the MCP server's name when `access` is `mcp`, else `null`.
  - `mode`: `read-only` or `automate`. `access` `none` requires `read-only`.
  - `statuses`: an object with exactly `start`, `review` and `done` (the
    status names) when `mode` is `automate`, else `null`.
- `code_host`: `github`, `gitlab` or `none`.
- `roles_off`: an array without duplicates; each item is `scout`, `tester` or
  `visual-checker`. It may be empty.
- `custom_roles`: an array, possibly empty, with unique `name` values. Each item
  has exactly these keys:
  - `name`: matches `^[a-z0-9]+(-[a-z0-9]+)*$` (`security-reviewer`), not the
    name of a plugin role (`scout`, `planner`, `implementer`, `reviewer`,
    `tester`, `visual-checker`), and not `general-purpose`.
  - `agent_type`: `general-purpose` or the name of a project-defined or
    user-defined agent type. It never starts with the plugin's own prefix.
    Among roles that are not `general-purpose`, each value is unique.
  - `instructions`: required for `general-purpose`; `null` or a path
    otherwise. A non-null value is an absolute path to a file that must exist,
    and all non-null paths are unique. The existence check is separate from
    the pure schema check, so the example above validates without the file.
  - `phase`: `research`, `plan`, `review`, `publish` or `implementation`.
  - `writes`: `true` or `false`. `true` requires `phase` `implementation`;
    `false` requires one of the other four phases.
  - `model`: `opus`, `sonnet` or `haiku`.
  - `effort`: `low`, `medium`, `high` or `xhigh`.
- `chat_language`: a language name, for example `German`: one line of at most
  40 characters, made of letters, spaces, hyphens and parentheses.
- `saved`: the date of the last write, `YYYY-MM-DD`.

## Use

- Code host adapter: from `code_host` ([adapters/index.md](adapters/index.md)).
  Tracker adapter: from `tracker.type`, with `access` and `mode` deciding what
  you may do.
- Roles in `roles_off` are skipped everywhere. Custom roles join the flow at
  their phase.
- Pass the settings path to the planner and the reviewer.

## Enforcement

The plugin's hook checks the file. A plugin agent call (`orchestrator:*`) is
denied when:

- the call has no explicit `model`;
- the brief has no `Task directory:` line;
- the project has no valid settings file;
- the session is not in the `Sessions` line of an active run file;
- the role is in `roles_off`.

A custom role call is denied when its `model` differs from the settings. Its
`effort` is checked only when the call passes one. Without a
`Task directory:` line the hook finds the settings from the working
directory, in any session in that repository. So a custom role with its own
`agent_type` is held to the settings' model there, also outside a run. Broken
settings found this way block a call only when it runs a custom role or comes
from a session in an active run.

Settings writes: only the orchestrator writes this file, with a whole-file
`Write`. A `Write` that breaks the rules above is denied, and so are partial
edits and writes from a subagent. Write the instruction files of custom roles
before the settings, because the hook checks that they exist.

The model a subagent really runs on is not visible: the reviewer's route check
covers it.
