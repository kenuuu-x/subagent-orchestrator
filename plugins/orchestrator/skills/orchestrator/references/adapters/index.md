# Adapters

Tracker and code-host behaviour lives in one short file per tracker and per
host. The flow text stays neutral and points here. Every file has fixed
headings.

## Code host adapters

Headings: Check access, Find or open, Review threads, Reply and resolve,
Checks and approval, Merge.

| Adapter | When |
|---|---|
| [host-github.md](host-github.md) | `origin` is on GitHub and `gh` is logged in |
| [host-gitlab.md](host-gitlab.md) | `origin` is on GitLab and `glab` is logged in |
| [host-none.md](host-none.md) | no remote, no login for the host's CLI, or the human says so |

## Tracker adapters

Headings: Read a task, Task id, Change status, Comment, Link a pull request.

| Adapter | When |
|---|---|
| [tracker-github-issues.md](tracker-github-issues.md) | task is `#123` on a GitHub host |
| [tracker-mcp.md](tracker-mcp.md) | shared rules for every tracker below |
| [tracker-jira.md](tracker-jira.md) | key of a Jira project |
| [tracker-linear.md](tracker-linear.md) | identifier of a Linear team |
| [tracker-yandex-tracker.md](tracker-yandex-tracker.md) | key of a Yandex Tracker queue |
| [tracker-other.md](tracker-other.md) | any other tracker |

## Choose the adapters

Do this at intake, once per repository, and record the choice in your run
file.

- Code host, from `git remote get-url origin`: a GitHub host (github.com, or a
  host that `gh auth status` lists) takes the GitHub adapter; a GitLab host
  (gitlab.com, or a host that `glab auth status` lists) takes the GitLab
  adapter. No remote, an unknown host, or a CLI that is missing or not logged
  in: [host-none.md](host-none.md). A host you cannot classify: ask the human.
- Tracker, from the form of the task:
  - `#123` on a GitHub host: GitHub Issues. On another host: ask the human
    which tracker it is, and use [tracker-other.md](tracker-other.md).
  - `ABC-123` (letters, a dash, digits): ask the human which tracker it is
    (Jira, Linear, Yandex Tracker or other), and use its adapter with
    [tracker-mcp.md](tracker-mcp.md).
  - Free text: no tracker. Skip the tracker steps.
- Write to a tracker (status, comment) only when the human asked for it, with
  the status names the human gave. Reading a task is always allowed.
- Paths in a brief are absolute: `<plugin root>/skills/orchestrator/references/adapters/<file>`.
