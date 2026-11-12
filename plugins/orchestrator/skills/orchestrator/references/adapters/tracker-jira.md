# Tracker: Jira

A task is a Jira issue with a key like `ABC-123`. Reach Jira through the
human's MCP server; follow [tracker-mcp.md](tracker-mcp.md) first.

## Read a task

Read the issue by key: summary, description, acceptance criteria (often a
field or a section of the description), status, linked issues, comments.

## Task id

`abc-123` (the key in lowercase).

## Change status

Jira moves an issue by workflow transitions. List the transitions that are
available now, and run the one whose target is the status name the human gave.
Names differ per project; never guess them.

## Comment

Post plain text with the server's comment tool. Jira renders Markdown only in
some editors, so keep the text simple: short sentences and bare URLs.

## Link a pull request

Put the key in the branch name (`feat/abc-123-short-title`), the PR title and
the PR description (`ABC-123`). If the human's Jira has a code-host
integration, the key links the PR by itself. Otherwise add the PR URL in a
comment.
