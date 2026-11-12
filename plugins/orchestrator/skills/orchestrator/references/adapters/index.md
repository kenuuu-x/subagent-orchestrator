# Adapters

Tracker and code-host behaviour lives in one short file per tracker and per
host. The flow text stays neutral and points here. Every file has fixed
headings.

## Code host adapters

Headings: Check access, Find or open, Review threads, Reply and resolve,
Checks and approval, Merge.

| Adapter | When |
|---|---|
| [host-github.md](host-github.md) | `code_host` is `github` |
| [host-gitlab.md](host-gitlab.md) | `code_host` is `gitlab` |
| [host-none.md](host-none.md) | `code_host` is `none`, or the host's CLI is missing or not logged in |

## Tracker adapters

Headings: Read a task, Task id, Change status, Comment, Link a pull request.

| Adapter | When |
|---|---|
| [tracker-github-issues.md](tracker-github-issues.md) | `tracker.type` is `github-issues` |
| [tracker-mcp.md](tracker-mcp.md) | shared rules for every tracker below |
| [tracker-jira.md](tracker-jira.md) | `tracker.type` is `jira` |
| [tracker-linear.md](tracker-linear.md) | `tracker.type` is `linear` |
| [tracker-yandex-tracker.md](tracker-yandex-tracker.md) | `tracker.type` is `yandex-tracker` |
| [tracker-other.md](tracker-other.md) | `tracker.type` is `other` |

## Choose the adapters

The project's `settings.json` decides ([setup.md](../setup.md)). Do not infer
the adapters from the `origin` URL or from the form of the task. Record the
choice in your run file.

- Code host, from `code_host`: `github` takes the GitHub adapter, `gitlab` the
  GitLab adapter, `none` [host-none.md](host-none.md). A host CLI that is
  missing or not logged in now: tell the human and use host-none.md for this
  run; do not rewrite the settings.
- Tracker, from `tracker.type` and `tracker.access`:
  - `github-issues`: [tracker-github-issues.md](tracker-github-issues.md), a
    task `#123`.
  - `jira`, `linear`, `yandex-tracker` or `other` with access `mcp`: that
    type's adapter together with [tracker-mcp.md](tracker-mcp.md), a key such
    as `ABC-123`.
  - Type `none`, or access `none` (no MCP server visible): free text, skip the
    tracker steps.
  - A task whose form does not fit the type (a key with GitHub Issues, `#123`
    with Jira): ask the human.
- Write to a tracker (status, comment) only in mode `automate`, with the
  status names from `tracker.statuses`. Mode `read-only` only reads tasks.
- Paths in a brief are absolute: `<plugin root>/skills/orchestrator/references/adapters/<file>`.
