# Tracker: Linear

A task is a Linear issue with an identifier like `ENG-123`. Reach Linear
through the human's MCP server; follow [tracker-mcp.md](tracker-mcp.md) first.

## Read a task

Read the issue by identifier: title, description, status, priority, project,
sub-issues, links and comments.

## Task id

`eng-123` (the identifier in lowercase).

## Change status

Linear sets a workflow state by name (for example the states of the team's
workflow). List the states of the issue's team, and set the one named in
`tracker.statuses`. Never guess a state name. Write only in mode `automate`.

## Comment

Post the comment with the server's comment tool. Linear renders Markdown.

## Link a pull request

Put the identifier in the branch name, the PR title or the PR description
(`ENG-123`). With a Linear code-host integration this links the PR by itself;
otherwise add the PR URL in a comment.
