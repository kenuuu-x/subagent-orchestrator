---
description: Coordinate one or more development tasks with subagents; the human approves each plan and reviews each pull request
argument-hint: [#issue | "task description" ...]
disable-model-invocation: true
---

Plugin root: `${CLAUDE_PLUGIN_ROOT}`

Read `${CLAUDE_PLUGIN_ROOT}/skills/orchestrator/SKILL.md` and follow it. Record the plugin root above in your state file; build absolute paths to plugin files from it.

Coordinate only these tasks: `$ARGUMENTS`

If the list is empty, ask the human which tasks to coordinate. Do not pick tasks yourself.
