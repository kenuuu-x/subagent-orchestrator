# Tracker: other

Use this when the human's tracker has no adapter of its own. Reach it through
the human's MCP server; follow [tracker-mcp.md](tracker-mcp.md) first. Ask the
human once for what the tracker calls an issue, its key format and its status
names, and record the answers in your run file.

## Read a task

Read the issue with the server's read tools: title, description, acceptance
criteria, status, links and comments. No MCP server for the tracker: ask the
human to paste the task text and treat it as a free-text task.

## Task id

The key in lowercase, when it has the form `ABC-123`. Otherwise a short
kebab-case slug that the human confirms.

## Change status

Read the transitions or states the server offers and use the one that leads to
the status name from `tracker.statuses`. If the server offers none, tell the
human and do not change the status. Write only in mode `automate`.

## Comment

Post the text you wrote with the server's comment tool, one exact comment per
mechanics call.

## Link a pull request

Put the key in the branch name, the PR title and the PR description. If you do
not know whether that links the PR in this tracker, add the PR URL in a
comment on the issue.
