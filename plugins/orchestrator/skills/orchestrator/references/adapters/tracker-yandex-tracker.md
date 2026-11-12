# Tracker: Yandex Tracker

A task is a Yandex Tracker issue with a key like `QUEUE-123` (the queue name
and a number). Reach it through the human's MCP server; follow
[tracker-mcp.md](tracker-mcp.md) first.

## Read a task

Read the issue by key: summary, description, status, type, links, checklist and
comments. The server may allow only some queues; "not found or not allowed"
can mean that limit, not a missing issue.

## Task id

`queue-123` (the key in lowercase).

## Change status

A status changes by a transition. List the transitions available for the issue
now, and run the one whose target is the status name from `tracker.statuses`. Status
names differ per queue; never guess them. Write only in mode `automate`.

## Comment

Post the text with the server's comment tool. A plain `@login` in the text
notifies nobody; use the tool's own field for people to notify, and only when
the human asked.

## Link a pull request

Put the key in the branch name, the commit subject, the PR title and the PR
description (`QUEUE-123`). Add the PR URL in a comment on the issue, since the
key alone may not link it.
