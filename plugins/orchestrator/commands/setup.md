---
description: Run or change the first-run setup of this project: tracker, code host, roles and chat language
argument-hint: [setting to change, for example "chat language"]
disable-model-invocation: true
---

Plugin root: `${CLAUDE_PLUGIN_ROOT}`

Read `${CLAUDE_PLUGIN_ROOT}/skills/orchestrator/references/setup.md` and follow it. Find the work home and the project key of the current repository as `${CLAUDE_PLUGIN_ROOT}/skills/orchestrator/references/task-files.md` says.

Run the interview for this project. If a settings file exists, use its values as the defaults.

Change only: `$ARGUMENTS`

If that is empty, or if no valid settings file exists, ask all four questions. Start no task and no subagent.
